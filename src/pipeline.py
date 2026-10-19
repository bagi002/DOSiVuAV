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
LOOK_AHEAD = 0.135     # top edge of the trapezoid, as a fraction of the way from the vanishing point down

# Binary image: lane paint is a bright (L) or yellow (b) stripe narrower than the top-hat kernel
TOPHAT_WIDTH = 61      # px = 35 cm, a lane line is 10-15 cm wide
WHITE_MIN = 30         # L - opening(L)
YELLOW_MIN = 8         # b - opening(b)


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


class LaneDetector:
    """The whole pipeline: detector(frame) returns the processed frame."""

    def __init__(self):
        self.mtx, self.dist, self.calib_size = calibrate()

    def __call__(self, frame):
        h, w = frame.shape[:2]
        undist = frame
        if (w, h) == self.calib_size:  # the calibration only holds for the camera it was computed for
            undist = cv2.undistort(frame, self.mtx, self.dist, None, self.mtx)
        M, Minv = perspective((w, h))
        binary = binarize(cv2.warpPerspective(undist, M, WARP_SIZE))
        return cv2.cvtColor(binary * 255, cv2.COLOR_GRAY2BGR)
