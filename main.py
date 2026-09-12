import cv2

from pose.detector import PoseDetector
from exercises.curl_tracker import CurlTracker
from pipeline import process_frame


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print('Error: cannot open webcam.')
        return

    detector    = PoseDetector()
    curl        = CurlTracker()
    print('Press Q to quit.')

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Bicep curl only: exercise classification is intentionally not wired up,
            # since a misfire mid-set switched modes and discarded the rep count.
            process_frame(frame, detector, curl)

            cv2.imshow('Gym Posture Analyzer', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        detector.close()


if __name__ == '__main__':
    main()
