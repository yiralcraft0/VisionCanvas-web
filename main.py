import time
import threading
import math
import cv2 as cv
import numpy as np
from flask import Flask, Response, render_template, request

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
    detectConfidence=0.6,
    trackConfidence=0.5
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
brushSize = 5

wCam, hCam = 300,300
camera.set(cv.CAP_PROP_FRAME_WIDTH, wCam)
camera.set(cv.CAP_PROP_FRAME_HEIGHT, hCam)

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
    current_x = 0
    current_y = 0
    pTime, cTime = 0, 0
    lineLength = 0
    frameR = 30
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

        # cv.rectangle(frame, (frameR, frameR), (width - frameR, height - frameR), (0,0,255), 4)

        if landmark_list and len(landmark_list) > 8:
            # Landmark 8 is the index fingertip
            xIndex, yIndex = landmark_list[8][1], landmark_list[8][2]
            xMiddel, yMiddel = landmark_list[12][1] ,landmark_list[12][2]

            cv.circle(frame,(xIndex, yIndex),10,(0,0,0),-1)
            cv.circle(frame,(xMiddel, yMiddel),10,(0,0,0),-1)

            cv.line(frame, (xIndex, yIndex), (xMiddel, yMiddel), brushColour, 3)
            
            currentX, currentY = (xIndex + xMiddel) // 2, (yIndex + yMiddel) // 2
            cv.circle(frame, (currentX,currentY), brushSize, brushColour, -1)

            lineLength = int(math.hypot(xMiddel - xIndex, yMiddel - yIndex ))

            hand_detected = True
            current_x = np.interp(currentX, [frameR, wCam - frameR], [0, wCam])
            current_y = np.interp(currentY, [frameR, hCam - frameR], [0, hCam])

            current_x = int(np.clip(current_x, 0, wCam - 1))
            current_y = int(np.clip(current_y, 0, hCam - 1))

            # Draw using index fingertip
            if hand_detected:
                if len(set(isFingersUp)) <= 1:
                    canvas[:] = 0,0,0

                if isFingersUp[1] == 1 and isFingersUp[2] == 1 and lineLength <= 35:
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

        # cv.rectangle(
        #     frame,
        #     (0, 0),
        #     (width - 1, height - 1),
        #     (255, 255, 255),
        #     5,
        # )


        cTime = time.time()
        fps = int(1 / (cTime - pTime)) if (cTime - pTime) > 0 else 0
        pTime = cTime

        cv.putText(frame, f"FPS: {fps}", (30, 50), cv.FONT_HERSHEY_PLAIN, .8, (60, 112, 206), 2)
        # cv.putText(frame, f"Length: {str(lineLength)}", (20, 80), cv.FONT_HERSHEY_PLAIN, 1, (60, 112, 206), 2)

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

@app.route("/setColor", methods=["POST"])
def set_color():
    global brushColour
    data = request.get_json()

    if type(data["color"]) == list:
        r, g, b = data["color"]
        brushColour = (b, g, r)

        return {"status": "success"}
    
    else:
        hex_color = data["color"]
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        brushColour = (b, g, r)
        
        return {"status": "success"}

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