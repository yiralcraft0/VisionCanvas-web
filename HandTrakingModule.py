import cv2 as cv
import mediapipe as mp
import time


class HandDetection:
    def __init__(self,
                 mode: bool = False,
                 maxHands: int = 2,
                 modelComplexity: int = 0,  # 0 = Fast, 1 = Balanced/Accurate
                 detectConfidence: float = 0.5,
                 trackConfidence: float = 0.5):

        self.mode = mode
        self.maxHands = maxHands
        self.modelComplexity = modelComplexity
        self.detectConfidence = detectConfidence
        self.trackConfidence = trackConfidence

        self.mpHands = mp.solutions.hands

        # Added model_complexity=0 for faster CPU inference
        self.hands = self.mpHands.Hands(
            static_image_mode=self.mode,
            max_num_hands=self.maxHands,
            model_complexity=self.modelComplexity,
            min_detection_confidence=self.detectConfidence,
            min_tracking_confidence=self.trackConfidence
        )

        self.mpDraw = mp.solutions.drawing_utils

        self.tipIds = [4, 8, 12, 16, 20]

    def findHands(self, frame, isDraw=True):
        """
        Draw Hand Structure on the visual hand
        """
        frameRGB = cv.cvtColor(frame, cv.COLOR_BGR2RGB)

        # Optimizing memory layout for faster MediaPipe processing
        frameRGB.flags.writeable = False
        self.results = self.hands.process(frameRGB)
        frameRGB.flags.writeable = True

        if self.results.multi_hand_landmarks and isDraw:
            for handLms in self.results.multi_hand_landmarks:
                self.mpDraw.draw_landmarks(
                    frame,
                    handLms,
                    self.mpHands.HAND_CONNECTIONS
                )

        return frame

    def findHandPos(self, frame, handNo=0, isDraw=True):
        """
        Returns a list of 3 elements: [id, x, y]
        """
        self.lmList = []

        if self.results and self.results.multi_hand_landmarks:
            if handNo < len(self.results.multi_hand_landmarks):
                anyHand = self.results.multi_hand_landmarks[handNo]
                h, w, _ = frame.shape

                # List comprehension for faster processing
                self.lmList = [[id, int(lm.x * w), int(lm.y * h)]
                        for id, lm in enumerate(anyHand.landmark)]
        if len(self.lmList) != 0 :
            return self.lmList

    def fingersUp(self, handNo=0):
        """
        Returns a list of 5 elements: [Thumb, Index, Middle, Ring, Pinky]
        1 = Up / Open, 0 = Down / Closed
        """
        fingers = []

        if len(self.lmList) == 0:
            return fingers

        # Detect left vs right hand to handle the thumb properly
        is_right_hand = True
        if self.results.multi_handedness:
            # MediaPipe hand classification
            hand_type = self.results.multi_handedness[handNo].classification[0].label
            is_right_hand = (hand_type == "Right")

        # 1. Thumb (moves horizontally on the X-axis)
        # If Right Hand: open thumb is to the left (smaller X) than knuckle (landmark 2)
        # If Left Hand: open thumb is to the right (larger X) than knuckle (landmark 2)
        if is_right_hand:
            if self.lmList[self.tipIds[0]][1] < self.lmList[self.tipIds[0] - 2][1]:
                fingers.append(1)
            else:
                fingers.append(0)
        else:
            if self.lmList[self.tipIds[0]][1] > self.lmList[self.tipIds[0] - 2][1]:
                fingers.append(1)
            else:
                fingers.append(0)

        # 2. 4 Fingers (move vertically on the Y-axis)
        # In OpenCV, Y=0 is at the top. A tip higher up than its joint has a smaller Y value.
        for id in range(1, 5):
            if self.lmList[self.tipIds[id]][2] < self.lmList[self.tipIds[id] - 2][2]:
                fingers.append(1)
            else:
                fingers.append(0)

        return fingers



def main():
    pTime = 0
    cTime = 0

    capture = cv.VideoCapture(0)

    # 1. Lower Camera Resolution (30 FPS target)
    capture.set(cv.CAP_PROP_FRAME_WIDTH, 640)
    capture.set(cv.CAP_PROP_FRAME_HEIGHT, 480)

    # 2. Set lower model complexity (0 = fastest)
    handtraking = HandDetection(maxHands=2, modelComplexity=0,)

    while True:
        loaded, frame = capture.read()
        if not loaded:
            break

        frame = handtraking.findHands(frame)
        lmList = handtraking.findHandPos(frame)

        # if lmList:
        #     x, y = lmList[8][1], lmList[8][2]
        #     cv.circle(frame, (x, y), 8, (0, 255, 0), -1)  

        cTime = time.time()
        fps = int(1 / (cTime - pTime)) if (cTime - pTime) > 0 else 0
        pTime = cTime

        cv.putText(frame, f"FPS: {fps}", (20, 50),
                    cv.FONT_HERSHEY_PLAIN, 2, (60, 112, 206), 2)
        cv.imshow("Hand Tracking", frame)

        # Reduced waitKey time from 20ms to 1ms
        if cv.waitKey(1) & 0xFF == ord('q'):
            break

    capture.release()
    cv.destroyAllWindows()


if __name__ == "__main__":
    main()
