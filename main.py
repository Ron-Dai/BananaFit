import cv2

from pose.detector import PoseDetector
from pose.analyzer import compute_key_angles
from pose.feedback import get_feedback
from exercises.classifier import classify_exercise
from utils.drawing import draw_skeleton, draw_angles, draw_feedback


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print('Error: cannot open webcam.')
        return

    detector = PoseDetector()
    print('Press Q to quit.')

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            results   = detector.detect(frame)
            landmarks = detector.get_landmarks(results, frame.shape)
            angles    = compute_key_angles(landmarks)
            exercise  = classify_exercise(landmarks, angles)
            feedback  = get_feedback(exercise, angles)

            draw_skeleton(frame, landmarks)
            draw_angles(frame, landmarks, angles)
            draw_feedback(frame, exercise, feedback)

            cv2.imshow('Gym Posture Analyzer', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        detector.close()


if __name__ == '__main__':
    main()
