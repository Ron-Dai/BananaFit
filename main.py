import cv2

from pose.detector import PoseDetector
from pose.analyzer import compute_key_angles
from exercises.curl_tracker import CurlTracker
from utils.drawing import draw_skeleton, draw_angles, draw_curl_hud


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

            # Bicep curl only: exercise classification is intentionally not wired up,
            # since a misfire mid-set switched modes and discarded the rep count.
            curl.update(landmarks, angles)
            draw_skeleton(frame, landmarks, color=curl.get_color())
            draw_angles(frame, landmarks, angles)
            draw_curl_hud(frame,
                          rep_count=curl.rep_count,
                          last_score=curl.last_rep_score,
                          warnings=curl.warnings,
                          is_good_form=curl.is_good_form
                          )
            #print(curl._right.phase+":"+str(angles["right_elbow"])+"\t"+curl._left.phase+":"+str(angles["left_elbow"])+"\n")

            cv2.imshow('Gym Posture Analyzer', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        detector.close()


if __name__ == '__main__':
    main()
