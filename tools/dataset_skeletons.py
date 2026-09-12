"""Batch-annotate an exercise image/video dataset with pose skeletons and
save the per-frame joint-angle time series to CSV files.

Usage:
    python tools/dataset_skeletons.py --input path/to/dataset --output path/to/out [--stride 1]

Input layout is not prescribed: the script walks --input recursively and
picks up any image (.jpg/.jpeg/.png/.bmp) or video (.mp4/.avi/.mov/.mkv) file
it finds, mirroring the same relative folder structure under --output.

- Each video is decoded frame by frame (every `--stride`th frame kept); each
  kept frame is saved as a skeleton-annotated JPEG in a folder named after
  the video, alongside a `<video>_angles.csv` with one row per saved frame
  (frame name, timestamp, joint angles) — the changing-angle time series.
- Each standalone image is saved as a skeleton-annotated copy, and its
  single angle snapshot is appended as a row to an `angles.csv` shared by
  all images in that same input folder.
"""

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

from pose.detector import PoseDetector
from pose.analyzer import compute_key_angles
from utils.drawing import draw_skeleton, draw_angles

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp'}
VIDEO_EXTS = {'.mp4', '.avi', '.mov', '.mkv'}

ANGLE_NAMES = ['left_elbow', 'right_elbow', 'left_knee', 'right_knee', 'left_hip', 'right_hip']


def _iter_dataset_files(input_dir):
    for root, _, files in os.walk(input_dir):
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext in IMAGE_EXTS or ext in VIDEO_EXTS:
                yield os.path.join(root, name), ext


def _out_path_for(input_dir, output_dir, file_path):
    rel = os.path.relpath(file_path, input_dir)
    return os.path.join(output_dir, rel)


def _annotate(detector, frame):
    results = detector.detect(frame)
    landmarks = detector.get_landmarks(results, frame.shape)
    angles = compute_key_angles(landmarks)
    draw_skeleton(frame, landmarks)
    draw_angles(frame, landmarks, angles)
    return angles


def _process_image(detector, file_path, out_image_path, angles_writer):
    frame = cv2.imread(file_path)
    if frame is None:
        print(f'  skip (unreadable): {file_path}')
        return

    angles = _annotate(detector, frame)

    os.makedirs(os.path.dirname(out_image_path), exist_ok=True)
    cv2.imwrite(out_image_path, frame)
    angles_writer.writerow([os.path.basename(file_path)] + [angles.get(n, '') for n in ANGLE_NAMES])


def _process_video(detector, file_path, out_dir, stride, angles_csv_path):
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        print(f'  skip (unreadable): {file_path}')
        return

    os.makedirs(out_dir, exist_ok=True)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    with open(angles_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['frame', 'time_sec'] + ANGLE_NAMES)

        frame_idx = 0
        saved_idx = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % stride == 0:
                    angles = _annotate(detector, frame)

                    frame_name = f'frame_{saved_idx:05d}.jpg'
                    cv2.imwrite(os.path.join(out_dir, frame_name), frame)
                    writer.writerow([frame_name, round(frame_idx / fps, 3)] +
                                     [angles.get(n, '') for n in ANGLE_NAMES])
                    saved_idx += 1
                frame_idx += 1
        finally:
            cap.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', required=True, help='Root directory of the dataset.')
    parser.add_argument('--output', required=True, help='Root directory for annotated output.')
    parser.add_argument('--stride', type=int, default=1,
                         help='Keep every Nth video frame (default: 1, every frame).')
    args = parser.parse_args()

    if not os.path.isdir(args.input):
        print(f'Error: input directory not found: {args.input}')
        sys.exit(1)

    detector = PoseDetector()
    image_csv_files = {}
    image_csv_writers = {}

    try:
        for file_path, ext in _iter_dataset_files(args.input):
            rel = os.path.relpath(file_path, args.input)
            print(f'Processing {rel}')

            if ext in VIDEO_EXTS:
                video_out_dir = os.path.splitext(_out_path_for(args.input, args.output, file_path))[0]
                angles_csv_path = video_out_dir + '_angles.csv'
                _process_video(detector, file_path, video_out_dir, args.stride, angles_csv_path)
            else:
                folder_rel = os.path.dirname(rel) or '.'
                if folder_rel not in image_csv_writers:
                    out_folder = os.path.join(args.output, folder_rel)
                    os.makedirs(out_folder, exist_ok=True)
                    f = open(os.path.join(out_folder, 'angles.csv'), 'w', newline='')
                    writer = csv.writer(f)
                    writer.writerow(['image'] + ANGLE_NAMES)
                    image_csv_files[folder_rel] = f
                    image_csv_writers[folder_rel] = writer

                out_image_path = _out_path_for(args.input, args.output, file_path)
                _process_image(detector, file_path, out_image_path, image_csv_writers[folder_rel])
    finally:
        detector.close()
        for f in image_csv_files.values():
            f.close()

    print('Done.')


if __name__ == '__main__':
    main()
