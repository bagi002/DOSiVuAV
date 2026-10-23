"""Regenerate the figures and videos used in README.md (written to docs/).

    python src/make_docs.py
"""
from pathlib import Path

import cv2
import matplotlib
import numpy as np

import pipeline as P

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
TEST_IMAGES = ROOT / "sources" / "test_images"
TEST_VIDEOS = ROOT / "sources" / "test_videos"
TILE = (640, 360)
CHALLENGE02_VP_Y = 437  # vanishing point row the video tracker converges to on challenge02.mp4
VIDEO_FRAMES = {        # frames shown in the README
    "project_video01": [110], "project_video02": [340], "challenge01": [125],
    "project_video03": [100, 400, 560, 610, 990, 1040],
    "challenge02": [30, 128, 330], "challenge03": [330, 960, 1050],
}


def tile(img, title):
    """Image resized to TILE with a title bar above it. Single channel images are scaled to 0-255."""
    if img.ndim == 2:
        img = cv2.cvtColor(cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U), cv2.COLOR_GRAY2BGR)
    bar = np.full((40, TILE[0], 3), 255, np.uint8)
    cv2.putText(bar, title, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2, cv2.LINE_AA)
    return cv2.copyMakeBorder(np.vstack([bar, cv2.resize(img, TILE)]), 0, 6, 0, 6, cv2.BORDER_CONSTANT,
                              value=(255, 255, 255))


def save(name, rows):
    """Grid of titled tiles, rows = [[(image, title), ...], ...]."""
    grid = np.vstack([np.hstack([tile(img, title) for img, title in row]) for row in rows])
    cv2.imwrite(str(DOCS / name), grid, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"Wrote {DOCS / name}")


def bird_eye(img, vp_y=None):
    """Undistorted 1280x720 frame, its bird's-eye view and the perspective matrices."""
    undist = cv2.undistort(img, mtx, dist, None, mtx)
    M, Minv = P.perspective((1280, 720), vp_y or P.CAMERAS[1280, 720][0][1])
    return undist, cv2.warpPerspective(undist, M, P.WARP_SIZE), M, Minv


def video_frame(name, index):
    video = cv2.VideoCapture(str(TEST_VIDEOS / f"{name}.mp4"))
    video.set(cv2.CAP_PROP_POS_FRAMES, index)
    return video.read()[1]


def calibration_figures():
    board = cv2.imread(str(P.CAMERA_CAL_DIR / "calibration1.jpg"))
    road = cv2.imread(str(TEST_IMAGES / "test1.jpg"))
    save("calibration.jpg", [[(board, "Original (calibration1.jpg)"), (bird_eye(board)[0], "Undistorted")]])
    save("undistort.jpg", [[(road, "Original (test1.jpg)"), (bird_eye(road)[0], "Undistorted")]])


def perspective_figure():
    rows = []
    for name in ["straight_lines1.jpg", "test2.jpg"]:
        undist, warped, _, Minv = bird_eye(cv2.imread(str(TEST_IMAGES / name)))
        src = cv2.perspectiveTransform(P.DST[None], Minv)[0]
        cv2.polylines(undist, [np.int32(src)], True, (0, 0, 255), 3)
        cv2.polylines(warped, [np.int32(P.DST)], True, (0, 0, 255), 3)
        rows.append([(undist, f"Source trapezoid ({name})"), (warped, "Bird's-eye view")])
    save("perspective.jpg", rows)


def binary_figures():
    examples = [("test5.jpg", cv2.imread(str(TEST_IMAGES / "test5.jpg")), None),
                ("test4.jpg", cv2.imread(str(TEST_IMAGES / "test4.jpg")), None),
                ("challenge02.mp4", video_frame("challenge02", 20), CHALLENGE02_VP_Y)]
    kernel = np.ones((1, P.TOPHAT_WIDTH), np.uint8)
    rows = []
    for name, img, vp_y in examples:
        warped = bird_eye(img, vp_y)[1]
        lab = cv2.cvtColor(cv2.GaussianBlur(warped, (5, 5), 0), cv2.COLOR_BGR2LAB)
        tophat_l, tophat_b = (cv2.morphologyEx(lab[:, :, c], cv2.MORPH_TOPHAT, kernel) for c in (0, 2))
        rows.append([(warped, f"Bird's-eye view ({name})"),
                     (np.minimum(tophat_l, 90), "Top-hat of L"),  # clipped to make weak responses visible
                     (np.minimum(tophat_b, 40), "Top-hat of b"),
                     (P.binarize(warped), f"Binary: L > {P.WHITE_MIN} or b > {P.YELLOW_MIN}")])
    save("binary.jpg", rows)

    # Why not Sobel: on challenge02 it also finds the tar seams and the edge between two kinds of asphalt
    warped = rows[-1][0][0]
    l_channel = cv2.cvtColor(cv2.GaussianBlur(warped, (5, 5), 0), cv2.COLOR_BGR2HLS)[:, :, 1]
    sobel = np.abs(cv2.Sobel(l_channel, cv2.CV_64F, 1, 0, ksize=3))
    sobel = np.uint8(255 * sobel / sobel.max())
    save("sobel_vs_tophat.jpg", [[(warped, "Bird's-eye view (challenge02.mp4)"),
                                  (((sobel > 20) & (sobel < 100)).astype(np.uint8), "Sobel x in (20, 100)"),
                                  (P.binarize(warped), "Top-hat binary")]])


def fit_figure():
    _, warped, M, _ = bird_eye(cv2.imread(str(TEST_IMAGES / "test3.jpg")))
    binary = P.binarize(warped)
    ys, xs = binary.nonzero()
    car_x = cv2.perspectiveTransform(np.float32([[[640, 720]]]), M)[0, 0, 0]
    masks, windows = P.sliding_windows(binary, car_x)
    fit = [P.fit_line(ys[m], xs[m], np.random.default_rng(0)) for m in masks]
    y = np.arange(P.WARP_SIZE[1])
    curves = [np.int32(np.column_stack([np.polyval(line, y), y])) for line in fit]

    windows_img, band_img = (np.dstack([binary * 90] * 3) for _ in range(2))
    for x0, y0, x1, y1 in windows:
        cv2.rectangle(windows_img, (x0, y0), (x1, y1), (0, 255, 0), 3)
    band = np.zeros_like(band_img)
    for curve in curves:
        cv2.fillPoly(band, [np.vstack([curve - (P.SEARCH_MARGIN, 0), (curve + (P.SEARCH_MARGIN, 0))[::-1]])],
                     (0, 255, 0))
    band_img = cv2.addWeighted(band_img, 1, band, 0.3, 0)
    for img, selected in [(windows_img, masks), (band_img, P.around_fit(ys, xs, fit))]:
        for mask, color in zip(selected, [(0, 0, 255), (255, 0, 0)]):
            img[ys[mask], xs[mask]] = color
        cv2.polylines(img, curves, False, (0, 255, 255), 4)
    save("fit.jpg", [[(windows_img, "Sliding windows (test3.jpg)"),
                      (band_img, f"Search around the previous fit (+/- {P.SEARCH_MARGIN} px)")]])


def ransac_figure():
    """Least squares and RANSAC on the same pixels of a frame with a lot of noise (challenge03.mp4)."""
    _, warped, M, _ = bird_eye(video_frame("challenge03", 100))
    binary = P.binarize(warped)
    ys, xs = binary.nonzero()
    masks, _ = P.sliding_windows(binary, cv2.perspectiveTransform(np.float32([[[640, 720]]]), M)[0, 0, 0])
    y = np.arange(P.WARP_SIZE[1])
    row = [(warped, "Bird's-eye view (challenge03.mp4, frame 100)")]
    for title, fit in [("Least squares", lambda m: np.polyfit(ys[m], xs[m], 2)),
                       (f"RANSAC ({P.RANSAC_ITERATIONS} iterations)",
                        lambda m: P.fit_line(ys[m], xs[m], np.random.default_rng(0)))]:
        img = np.dstack([binary * 90] * 3)
        for mask, color in zip(masks, [(0, 0, 255), (255, 0, 0)]):
            img[ys[mask], xs[mask]] = color
            curve = np.int32(np.column_stack([np.polyval(fit(mask), y), y]))
            cv2.polylines(img, [curve], False, (0, 255, 255), 4)
        row.append((img, title))
    save("ransac.jpg", [row])


def result_figure():
    names = [f"test{i}.jpg" for i in range(1, 7)]
    results = [(P.LaneDetector()(cv2.imread(str(TEST_IMAGES / n))), n) for n in names]
    save("result.jpg", [results[:3], results[3:]])


def videos():
    """Every test video processed at full resolution, plus the frames for the README and the measurements."""
    frames, measurements = {}, []
    for path in sorted(TEST_VIDEOS.glob("*.mp4")):
        video, detector = cv2.VideoCapture(str(path)), P.LaneDetector()
        fps = video.get(cv2.CAP_PROP_FPS)
        size = (int(video.get(cv2.CAP_PROP_FRAME_WIDTH)), int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        out = cv2.VideoWriter(str(DOCS / path.name), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
        index = 0
        while True:
            ok, frame = video.read()
            if not ok:
                break
            result = detector(frame)
            out.write(result)
            if index in VIDEO_FRAMES[path.stem]:
                frames[path.stem, index] = result
            if path.stem == "project_video03":
                measurements.append((index / fps, detector.radius, detector.offset))
            index += 1
        out.release()
        print(f"Wrote {DOCS / path.name}")

    def row(*names):
        return [(frames[n, i], f"{n}.mp4, frame {i}") for n in names for i in VIDEO_FRAMES[n]]
    project = row("project_video03")
    save("video_project.jpg", [project[:3], project[3:]])
    save("video_other.jpg", [row("project_video01", "project_video02", "challenge01"),
                             row("challenge02"), row("challenge03")])
    return np.array(measurements, float)


def measurement_chart(measurements):
    """Radius of curvature and vehicle offset over project_video03 (two panels, shared time axis)."""
    t, radius, offset = measurements.T
    ink, muted, grid, line = "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"
    fig, axes = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True, facecolor="#fcfcfb")
    panels = [(np.minimum(radius, 20000), "Radius of curvature (m, log scale, straight road shown as 20 km)"),
              (offset, "Vehicle offset from the lane center (m, + = right)")]
    for ax, (values, title) in zip(axes, panels):
        ax.set_facecolor("#fcfcfb")
        ax.plot(t, values, color=line, linewidth=2, solid_capstyle="round")
        ax.set_title(title, loc="left", color=ink, fontsize=11)
        ax.grid(color=grid, linewidth=1)
        ax.tick_params(colors=muted, labelsize=9)
        for spine in ax.spines.values():
            spine.set_visible(False)
    axes[0].set_yscale("log")
    axes[0].minorticks_off()
    axes[0].set_yticks([300, 1000, 3000, 10000], ["300", "1K", "3K", "10K"])
    axes[0].set_ylim(300, 25000)
    axes[1].axhline(0, color=muted, linewidth=1)
    axes[1].set_xlabel("time (s) in project_video03.mp4", color=muted, fontsize=9)
    fig.tight_layout()
    fig.savefig(DOCS / "measurements.png", dpi=110)
    print(f"Wrote {DOCS / 'measurements.png'}")


if __name__ == "__main__":
    DOCS.mkdir(exist_ok=True)
    mtx, dist, _ = P.calibrate()
    calibration_figures()
    perspective_figure()
    binary_figures()
    fit_figure()
    ransac_figure()
    result_figure()
    measurement_chart(videos())
