"""Run the lane detection pipeline on an image, a directory of images or a video.

    python main.py sources/test_images/test1.jpg
    python main.py sources/test_images/
    python main.py sources/test_videos/project_video03.mp4 [--out output_videos/]
"""
import argparse
from pathlib import Path

import cv2

from src.pipeline import LaneDetector

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}


def process_image(path, out_dir):
    cv2.imwrite(str(out_dir / path.name), LaneDetector()(cv2.imread(str(path))))


def process_video(path, out_dir):
    video = cv2.VideoCapture(str(path))
    size = (int(video.get(cv2.CAP_PROP_FRAME_WIDTH)), int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    out = cv2.VideoWriter(str(out_dir / path.name), cv2.VideoWriter_fourcc(*"mp4v"),
                          video.get(cv2.CAP_PROP_FPS), size)
    detector = LaneDetector()  # one detector for all frames
    while True:
        ok, frame = video.read()
        if not ok:
            break
        out.write(detector(frame))
    video.release()
    out.release()


def main():
    parser = argparse.ArgumentParser(description="Lane detection with OpenCV.")
    parser.add_argument("input", type=Path, help="image, directory of images or video")
    parser.add_argument("--out", type=Path,
                        help="output directory (default: output_images/ or output_videos/)")
    args = parser.parse_args()

    paths = sorted(p for p in args.input.iterdir() if p.is_file()) if args.input.is_dir() else [args.input]
    for path in paths:
        is_video = path.suffix.lower() in VIDEO_EXTENSIONS
        out_dir = args.out or Path("output_videos" if is_video else "output_images")
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"{path} -> {out_dir / path.name}")
        (process_video if is_video else process_image)(path, out_dir)


if __name__ == "__main__":
    main()
