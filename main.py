import cv2

from pose.detector import PoseDetector
from pose.analyzer import compute_key_angles
from pose.feedback import get_feedback
from exercises.classifier import classify_exercise
from exercises.curl_tracker import CurlTracker
from utils.drawing import draw_skeleton, draw_angles, draw_curl_hud, draw_feedback


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

            results   = detector.detect(frame)
            landmarks = detector.get_landmarks(results, frame.shape)
            angles    = compute_key_angles(landmarks)
            exercise  = classify_exercise(landmarks, angles)

            if exercise == 'bicep_curl':
                curl.update(landmarks, angles)
                skel_color = curl.get_color()
                draw_skeleton(frame, landmarks, color=skel_color)
                draw_angles(frame, landmarks, angles)
                draw_curl_hud(frame,
                              rep_count=curl.rep_count,
                              last_score=curl.last_rep_score,
                              warnings=curl.warnings,
                              is_good_form=curl.is_good_form)
            else:
                # Reset curl tracker when exercise changes
                curl = CurlTracker()
                draw_skeleton(frame, landmarks)
                draw_angles(frame, landmarks, angles)
                feedback = get_feedback(exercise, angles)
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
