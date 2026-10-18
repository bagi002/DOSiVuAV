"""Lane detection pipeline. Every frame passes through the same chain of filters:

    undistort -> bird's-eye warp -> binary image -> lane pixels -> polynomial fit
    -> radius of curvature and vehicle offset -> lane drawn back onto the frame

`LaneDetector` keeps the fit between calls, so the same object is used for every frame of a video
and a new one for every independent image.
"""
from pathlib import Path

import cv2
import numpy as np

CAMERA_CAL_DIR = Path(__file__).resolve().parent / "sources" / "camera_cal"
CALIB_FILE = CAMERA_CAL_DIR / "calib.npz"
CHESSBOARD = (9, 6)  # inner corners


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


class LaneDetector:
    """The whole pipeline: detector(frame) returns the processed frame."""

    def __init__(self):
        self.mtx, self.dist, self.calib_size = calibrate()

    def __call__(self, frame):
        h, w = frame.shape[:2]
        undist = frame
        if (w, h) == self.calib_size:  # the calibration only holds for the camera it was computed for
            undist = cv2.undistort(frame, self.mtx, self.dist, None, self.mtx)
        return undist
