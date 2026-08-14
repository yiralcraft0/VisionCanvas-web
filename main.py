import time
import threading

import cv2 as cv
import numpy as np
from flask import Flask, Response, render_template

from HandTrakingModule import HandDetection


app = Flask(__name__)

# ---------------------------------------------------------
# Camera and hand detector
# ---------------------------------------------------------

camera = cv.VideoCapture(0)

# Change 1 to 0 if your main webcam uses index 0
if not camera.isOpened():
    raise RuntimeError(
        "Could not open camera. Try changing cv.VideoCapture(1) "
        "to cv.VideoCapture(0)."
    )

hDetect = HandDetection(
    maxHands=1,
    modelComplexity=0,
    detectConfidence=0.7,
    trackConfidence=0.7,
)


# ---------------------------------------------------------
# Shared data
# ---------------------------------------------------------

latest_video_frame = None
latest_canvas_frame = None
canvas = None

# Protect shared frames from being read and written simultaneously
frame_lock = threading.Lock()

# Used to stop the processing loop safely
processing_active = True

brushColour = (255,255,255)
brushSize = 10


def process_camera():
    """
    Continuously reads and processes camera frames.

    Only this function accesses the camera and MediaPipe detector.
    """

    global latest_video_frame
    global latest_canvas_frame
    global canvas
    global processing_active

    previous_x = 0
    previous_y = 0

    pTime, cTime = 0, 0

    while processing_active:
        success, frame = camera.read()

        if not success:
            print("Failed to read camera frame.")
            time.sleep(0.05)
            continue

        # Mirror the frame
        frame = cv.flip(frame, 1)

        height, width, _ = frame.shape

        # Create the drawing canvas
        if canvas is None or canvas.shape != frame.shape:
            canvas = np.zeros_like(frame)

        # Detect the hand
        hDetect.findHands(frame)
        landmark_list = hDetect.findHandPos(frame)
        isFingersUp = hDetect.fingersUp()

        hand_detected = False
        current_x = 0
        current_y = 0

        if landmark_list and len(landmark_list) > 8:
            # Landmark 8 is the index fingertip
            current_x = landmark_list[8][1]
            current_y = landmark_list[8][2]
            hand_detected = True

            cv.circle(frame,(current_x, current_y),brushSize,brushColour,-1)

            # Draw using index fingertip
            if hand_detected:
                if len(set(isFingersUp)) <= 1:
                    canvas[:] = 0,0,0

                if isFingersUp[1] == 1 and isFingersUp[2] == 1:
                    if previous_x == 0 and previous_y == 0:
                        previous_x = current_x
                        previous_y = current_y

                    cv.line(
                        canvas,
                        (previous_x, previous_y),
                        (current_x, current_y),
                        brushColour,
                        brushSize,
                    )

                    previous_x = current_x
                    previous_y = current_y

                else:
                    previous_x = 0
                    previous_y = 0

        cv.rectangle(
            frame,
            (0, 0),
            (width - 1, height - 1),
            (255, 255, 255),
            5,
        )


        cTime = time.time()
        fps = int(1 / (cTime - pTime)) if (cTime - pTime) > 0 else 0
        pTime = cTime

        cv.putText(frame, f"FPS: {fps}", (20, 50), cv.FONT_HERSHEY_PLAIN, 2, (60, 112, 206), 2)

        with frame_lock:
            latest_video_frame = frame.copy()
            latest_canvas_frame = canvas.copy()


def generate_stream(stream_type):
    """
    Streams either the processed webcam frame or the canvas frame.
    """

    while True:
        with frame_lock:
            if stream_type == "video":
                frame = (
                    latest_video_frame.copy()
                    if latest_video_frame is not None
                    else None
                )
            else:
                frame = (
                    latest_canvas_frame.copy()
                    if latest_canvas_frame is not None
                    else None
                )

        if frame is None:
            time.sleep(0.01)
            continue

        success, buffer = cv.imencode(".jpg", frame)

        if not success:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + buffer.tobytes()
            + b"\r\n"
        )


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_stream("video"),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/drawCanvas")
def draw_canvas_route():
    return Response(
        generate_stream("canvas"),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/clear_canvas")
def clear_canvas():
    """Clear the complete drawing canvas."""

    global canvas
    global latest_canvas_frame

    with frame_lock:
        if canvas is not None:
            canvas[:] = 0
            latest_canvas_frame = canvas.copy()

    return {"status": "Canvas cleared successfully"}


def release_resources():
    """Release the webcam when the application stops."""

    global processing_active

    processing_active = False

    if camera.isOpened():
        camera.release()


if __name__ == "__main__":
    camera_thread = threading.Thread(
        target=process_camera,
        daemon=True,
    )
    camera_thread.start()

    try:
        app.run(
            debug=True,
            port=5600,
            threaded=True,
            use_reloader=False,
        )
    finally:
        release_resources()