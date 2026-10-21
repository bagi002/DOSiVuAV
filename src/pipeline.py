"""Lane detection pipeline. Every frame passes through the same chain of filters:

    undistort -> bird's-eye warp -> binary image -> lane pixels -> polynomial fit
    -> radius of curvature and vehicle offset -> lane drawn back onto the frame

`LaneDetector` keeps the fit between calls, so the same object is used for every frame of a video
and a new one for every independent image.
"""
from pathlib import Path

import cv2
import numpy as np

CAMERA_CAL_DIR = Path(__file__).resolve().parent.parent / "sources" / "camera_cal"
CALIB_FILE = CAMERA_CAL_DIR / "calib.npz"
CHESSBOARD = (9, 6)  # inner corners

# Bird's-eye view: a trapezoid on the road is mapped onto a rectangle of a fixed top-down canvas.
# Its sides are the lane lines of a straight road, which meet at the vanishing point. Each camera in the
# data set (they differ in resolution) is described by that point and by the x where the lane lines
# cross the bottom row, both measured on straight road images.
WARP_SIZE = (1280, 720)
CAMERAS = {
    (1280, 720): ((641, 419), (207, 1107)),  # straight_lines1/2.jpg
    (960, 540): ((478, 307), (150, 850)),    # solidWhiteRight.jpg
}
DST = np.float32([(320, 0), (960, 0), (960, 720), (320, 720)])
XM_PER_PX = 3.7 / 640  # lane width (3.7 m) is 640 px on the canvas
Z_BOTTOM_M = 4.75      # distance from the camera to the road in the bottom row of the frame
LOOK_AHEAD = 0.135     # top edge of the trapezoid, as a fraction of the way from the vanishing point down

# Binary image: lane paint is a bright (L) or yellow (b) stripe narrower than the top-hat kernel
TOPHAT_WIDTH = 61      # px = 35 cm, a lane line is 10-15 cm wide
WHITE_MIN = 30         # L - opening(L)
YELLOW_MIN = 8         # b - opening(b)

# Lane pixel search
LANE_WIDTH_M = (2.5, 4.3)  # possible lane widths at the car
N_WINDOWS = 9
WINDOW_MARGIN = 100      # half-width of a sliding window
MIN_PIX = 50             # pixels needed to re-center a window
MIN_LINE_PIX = 300       # pixels needed to fit a line
RANSAC_ITERATIONS = 250  # as in lecture 04
RANSAC_TOLERANCE = 30    # px, a pixel this close to the curve is an inlier
MIN_INLIER_SHARE = 0.6   # a line is thin, so most pixels around it lie on it (noise fills the whole window)


def calibrate():
    """Camera matrix, distortion coefficients and image size, computed once from the chessboard images."""
    if CALIB_FILE.exists():
        data = np.load(CALIB_FILE)
        return data["mtx"], data["dist"], tuple(data["size"])

    objp = np.zeros((CHESSBOARD[0] * CHESSBOARD[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:CHESSBOARD[0], 0:CHESSBOARD[1]].T.reshape(-1, 2)  # board corners, z = 0
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    paths = sorted(CAMERA_CAL_DIR.glob("*.jpg"))
    obj_points, img_points = [], []
    for path in paths:
        gray = cv2.cvtColor(cv2.imread(str(path)), cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(gray, CHESSBOARD)
        if found:
            obj_points.append(objp)
            img_points.append(cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria))

    size = gray.shape[::-1]
    rms, mtx, dist, _, _ = cv2.calibrateCamera(obj_points, img_points, size, None, None)
    print(f"Calibration: chessboard found on {len(obj_points)}/{len(paths)} images, RMS error {rms:.2f} px")
    np.savez(CALIB_FILE, mtx=mtx, dist=dist, size=size)
    return mtx, dist, size


def ym_per_px(look_ahead):
    """Meters per canvas row: the canvas shows the road from Z_BOTTOM_M to Z_BOTTOM_M / look_ahead."""
    return Z_BOTTOM_M * (1 / look_ahead - 1) / WARP_SIZE[1]


def perspective(frame_size):
    """Matrices frame -> canvas and canvas -> frame for a frame of the given (width, height)."""
    (vx, vy), (left, right) = CAMERAS[frame_size]
    h = frame_size[1]
    top = vy + LOOK_AHEAD * (h - vy)
    src = np.float32([(vx + LOOK_AHEAD * (left - vx), top), (vx + LOOK_AHEAD * (right - vx), top),
                      (right, h), (left, h)])
    return cv2.getPerspectiveTransform(src, DST), cv2.getPerspectiveTransform(DST, src)


def binarize(warped):
    """0/1 image of lane-line pixels on the bird's-eye view.

    The top-hat (image minus its morphological opening) keeps only structures that are brighter than
    their surroundings and narrower than the kernel. On the L channel this finds white and yellow paint
    on both dark asphalt and light concrete, on the b channel (blue-yellow axis of LAB) yellow paint.
    """
    lab = cv2.cvtColor(cv2.GaussianBlur(warped, (5, 5), 0), cv2.COLOR_BGR2LAB)
    kernel = np.ones((1, TOPHAT_WIDTH), np.uint8)
    bright = cv2.morphologyEx(lab[:, :, 0], cv2.MORPH_TOPHAT, kernel) > WHITE_MIN
    yellow = cv2.morphologyEx(lab[:, :, 2], cv2.MORPH_TOPHAT, kernel) > YELLOW_MIN
    return (bright | yellow).astype(np.uint8)


def lane_starts(binary, car_x):
    """x of the left and right line at the bottom of the canvas.

    The column histogram of the lower half of the image is searched for the pair of columns that have the
    car between them and hold the most lane pixels together. A pair is weighted by how close its distance
    is to the usual lane width (3.7 m), which decides between peaks of similar height.
    """
    histogram = np.convolve(binary[binary.shape[0] // 2:].sum(axis=0), np.ones(31), "same")
    x = np.arange(len(histogram))
    best = (-1, 0, 0)
    for d in range(int(LANE_WIDTH_M[0] / XM_PER_PX), int(LANE_WIDTH_M[1] / XM_PER_PX), 5):
        score = (histogram[:-d] + histogram[d:]) * np.exp(-((d - 640) * XM_PER_PX / 1.5) ** 2)
        score[(x[:-d] > car_x) | (x[d:] < car_x)] = -1
        best = max(best, (score.max(), score.argmax(), score.argmax() + d))
    return best[1:]


def sliding_windows(binary, car_x):
    """Masks of the left / right line pixels (over binary.nonzero()) and the windows used to find them.

    Each line starts at lane_starts() and is followed upwards by windows that re-center on the mean x of
    their pixels (or keep the last direction in a gap).
    """
    h, w = binary.shape
    ys, xs = binary.nonzero()
    starts = lane_starts(binary, car_x)
    win_h = h // N_WINDOWS
    masks, windows = [], []
    for x in starts:
        mask, step = np.zeros(len(xs), bool), 0
        for y in range(h, 0, -win_h):
            inside = (ys >= y - win_h) & (ys < y) & (np.abs(xs - x) < WINDOW_MARGIN)
            windows.append((x - WINDOW_MARGIN, y - win_h, x + WINDOW_MARGIN, y))
            mask |= inside
            if inside.sum() > MIN_PIX:
                step, x = int(xs[inside].mean()) - x, int(xs[inside].mean())
            else:
                x += step
        masks.append(mask)
    return masks, windows


def fit_line(ys, xs, rng):
    """Second order polynomial x = Ay^2 + By + C through the pixels, robust to outliers (RANSAC, lecture 04).

    Every iteration draws one pixel from each third of the line (sorted by y), puts a parabola through
    the three and counts the pixels closer than RANSAC_TOLERANCE to it. The parabola with the most inliers
    wins, and the final fit is least squares on its inliers. None if there are too few pixels or inliers.
    """
    if len(xs) <= MIN_LINE_PIX:
        return None
    sample = [rng.choice(third, RANSAC_ITERATIONS) for third in np.array_split(np.argsort(ys), 3)]
    (y0, y1, y2), (x0, x1, x2) = ([v[i].astype(float) for i in sample] for v in (ys, xs))
    with np.errstate(divide="ignore", invalid="ignore"):  # two points in one row give no model (nan)
        d01, d12 = (x1 - x0) / (y1 - y0), (x2 - x1) / (y2 - y1)  # divided differences
        a = (d12 - d01) / (y2 - y0)
        b = d01 - a * (y0 + y1)
        c = x0 - a * y0 ** 2 - b * y0
        test = rng.choice(len(xs), min(len(xs), 1000), replace=False)  # pixels used to score the models
        error = np.abs(a[:, None] * ys[test] ** 2 + b[:, None] * ys[test] + c[:, None] - xs[test])
    best = np.argmax((error < RANSAC_TOLERANCE).sum(axis=1))
    inliers = np.abs(xs - np.polyval([a[best], b[best], c[best]], ys)) < RANSAC_TOLERANCE
    if inliers.sum() <= MIN_LINE_PIX or inliers.mean() < MIN_INLIER_SHARE:
        return None
    return np.polyfit(ys[inliers], xs[inliers], 2)


def curvature(line, ym):
    """Signed curvature (1/m) of a canvas polynomial at the car (bottom row).

    The polynomial is converted to meters, x_m = A_m y_m^2 + B_m y_m + C_m with A_m = A * xm / ym^2 and
    B_m = B * xm / ym, and the curvature is 2 A_m / (1 + (2 A_m y_m + B_m)^2)^1.5 = 1 / R.
    """
    a, b = line[0] * XM_PER_PX / ym ** 2, line[1] * XM_PER_PX / ym
    y = WARP_SIZE[1] * ym
    return 2 * a / (1 + (2 * a * y + b) ** 2) ** 1.5


def curvature_and_offset(fit, car_x, ym):
    """Radius of curvature of the lane center (m) and offset of the car from it (m, + = right)."""
    center = fit.mean(axis=0)
    radius = 1 / max(abs(curvature(center, ym)), 1e-9)
    offset = (car_x - np.polyval(center, WARP_SIZE[1])) * XM_PER_PX
    return radius, offset


def draw_lane(undist, fit, Minv, radius, offset):
    """Lane area painted on the canvas, warped back onto the frame, with radius and offset as text."""
    y = np.linspace(0, WARP_SIZE[1], 30)
    left, right = (np.column_stack([np.polyval(line, y), y]) for line in fit)
    lane = np.zeros((WARP_SIZE[1], WARP_SIZE[0], 3), np.uint8)
    cv2.fillPoly(lane, [np.vstack([left, right[::-1]]).astype(np.int32)], (0, 255, 0))
    cv2.polylines(lane, [left.astype(np.int32), right.astype(np.int32)], False, (0, 0, 255), 20)
    out = cv2.addWeighted(undist, 1, cv2.warpPerspective(lane, Minv, undist.shape[1::-1]), 0.4, 0)

    side = "right" if offset > 0 else "left"
    lines = [f"Radius of curvature: {radius:.0f} m" if radius < 5000 else "Radius of curvature: > 5 km",
             f"Vehicle is {abs(offset):.2f} m {side} of center"]
    scale = undist.shape[1] / 1280
    for i, text in enumerate(lines):
        for color, thickness in [((0, 0, 0), 6), ((255, 255, 255), 2)]:  # white text with a dark outline
            cv2.putText(out, text, (int(30 * scale), int((50 + 45 * i) * scale)), cv2.FONT_HERSHEY_SIMPLEX,
                        1.2 * scale, color, thickness, cv2.LINE_AA)
    return out


class LaneDetector:
    """The whole pipeline: detector(frame) returns the processed frame."""

    def __init__(self):
        self.mtx, self.dist, self.calib_size = calibrate()
        self.rng = np.random.default_rng(0)  # RANSAC samples: the same input always gives the same result
        self.ym = ym_per_px(LOOK_AHEAD)      # meters per canvas row
        self.fit = None    # (left, right) polynomials on the canvas
        self.radius = self.offset = None  # last measurement, in meters

    def __call__(self, frame):
        h, w = frame.shape[:2]
        undist = frame
        if (w, h) == self.calib_size:  # the calibration only holds for the camera it was computed for
            undist = cv2.undistort(frame, self.mtx, self.dist, None, self.mtx)
        M, Minv = perspective((w, h))
        binary = binarize(cv2.warpPerspective(undist, M, WARP_SIZE))

        car_x = cv2.perspectiveTransform(np.float32([[[w / 2, h]]]), M)[0, 0, 0]  # the car on the canvas
        ys, xs = binary.nonzero()
        masks, _ = sliding_windows(binary, car_x)
        lines = [fit_line(ys[mask], xs[mask], self.rng) for mask in masks]

        if lines[0] is None or lines[1] is None:
            self.fit = None
            return undist

        self.fit = np.array(lines)
        self.radius, self.offset = curvature_and_offset(self.fit, car_x, self.ym)
        return draw_lane(undist, self.fit, Minv, self.radius, self.offset)
