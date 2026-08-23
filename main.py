from flask import Flask, Response, render_template, request, send_file
from HandTrakingModule import HandDetection
from flask_socketio import SocketIO
from io import BytesIO
import numpy as np
import threading
import cv2 as cv
import time
import math

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

camera = cv.VideoCapture(0, cv.CAP_DSHOW)
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

latest_video_frame = None
latest_canvas_frame = None
canvas = None
frame_lock = threading.Lock()
processing_active = True
brushColour = (255, 255, 255)
brushSize = 5
fps = 0

wCam, hCam = 320, 240   # 4:3, still cheap to process
camera.set(cv.CAP_PROP_FRAME_WIDTH, wCam)
camera.set(cv.CAP_PROP_FRAME_HEIGHT, hCam)


def process_camera():
    """Continuously capture and process camera frames, detect hand landmarks, update the drawing canvas and the latest frame buffers.

    Runs in a dedicated background thread. Uses global variables:
    - latest_video_frame, latest_canvas_frame, canvas: buffers updated under frame_lock
    - processing_active: loop guard
    - fps: updated and emitted via socketio

    The function performs hand detection, computes fingertip positions, draws on the canvas, and publishes FPS to clients.
    """
    global latest_video_frame
    global latest_canvas_frame
    global canvas
    global processing_active

    global fps
    global hand_detected
    global drawing

    previous_x = 0
    previous_y = 0
    current_x = 0
    current_y = 0
    last_fps_update = 0
    pTime, cTime = 0, 0
    lineLength = 0
    frameR = 30
    drawing = False

    while processing_active:
        success, frame = camera.read()
        if not success:
            print("Failed to read camera frame.")
            time.sleep(0.05)
            continue

        frame = cv.flip(frame, 1)
        height, width, _ = frame.shape
        if canvas is None or canvas.shape != frame.shape:
            canvas = np.zeros_like(frame)

        hDetect.findHands(frame)
        landmark_list = hDetect.findHandPos(frame)
        isFingersUp = hDetect.fingersUp()

        hand_detected = False

        if landmark_list and len(landmark_list) > 8:
            xIndex, yIndex = landmark_list[8][1], landmark_list[8][2]
            xMiddel, yMiddel = landmark_list[12][1], landmark_list[12][2]
            cv.circle(frame, (xIndex, yIndex), 10, (0, 0, 0), -1)
            cv.circle(frame, (xMiddel, yMiddel), 10, (0, 0, 0), -1)
            cv.line(frame, (xIndex, yIndex),
                    (xMiddel, yMiddel), brushColour, 3)
            currentX, currentY = (
                xIndex + xMiddel) // 2, (yIndex + yMiddel) // 2
            cv.circle(frame, (currentX, currentY), brushSize, brushColour, -1)
            lineLength = int(math.hypot(xMiddel - xIndex, yMiddel - yIndex))
            hand_detected = True
            current_x = np.interp(currentX, [frameR, wCam - frameR], [0, wCam])
            current_y = np.interp(currentY, [frameR, hCam - frameR], [0, hCam])
            current_x = int(np.clip(current_x, 0, wCam - 1))
            current_y = int(np.clip(current_y, 0, hCam - 1))

            if hand_detected:
                if len(set(isFingersUp)) <= 1:
                    canvas[:] = 0, 0, 0
                if isFingersUp[1] == 1 and isFingersUp[2] == 1 and lineLength <= 35:
                    drawing = True
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
                    drawing = False

        cTime = time.time()
        fps = int(1 / (cTime - pTime)) if (cTime - pTime) > 0 else 0
        pTime = cTime
        cv.putText(frame, f"FPS: {fps}", (30, 50), cv.FONT_HERSHEY_PLAIN, .8, (60, 112, 206), 2)

        if cTime - last_fps_update >= 0.5:
            socketio.emit("statusUpdate", {
            "FPS" : fps,
            "handDetected" : hand_detected,
            "isDrawing" : drawing
            })
            last_fps_update = cTime

        with frame_lock:
            latest_video_frame = frame.copy()
            latest_canvas_frame = canvas.copy()


def generate_stream(stream_type):
    """Yield multipart JPEG frames for the requested stream_type ('video' or 'canvas').

    Safely reads the latest frame copy under frame_lock and encodes it as JPEG.
    This generator is suitable for Flask streaming responses (multipart/x-mixed-replace).
    """
    while True:
        with frame_lock:
            if stream_type == "video":
                frame = latest_video_frame.copy() if latest_video_frame is not None else None
            else:
                frame = latest_canvas_frame.copy() if latest_canvas_frame is not None else None

        if frame is None:
            time.sleep(0.01)
            continue

        success, buffer = cv.imencode(".jpg", frame, [cv.IMWRITE_JPEG_QUALITY, 70])
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
    """HTTP POST endpoint to update the brush color.

    Accepts JSON with 'color' either as an [r,g,b] list or a hex string '#rrggbb'.
    Converts incoming color to BGR tuple and updates the global brushColour.
    Returns a simple JSON status response.
    """
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


@app.route("/setBrushSize", methods=["POST"])
def setBrushSize():
    """HTTP POST endpoint to update the brush size.

    Expects JSON with integer 'size'. Updates the global brushSize used for drawing.
    Returns a JSON status response.
    """
    global brushSize
    data = request.get_json()
    brushSize = int(data["size"])
    return {"Status": "Success"}


@app.route("/clearCanvas", methods=["POST"])
def clearCanvas():
    global canvas

    data = request.get_json()
    if canvas is not None:
        canvas[:] = 0, 0, 0

    if data:
        return {"Status": data["status"]}
    else:
        return {"Status": "Fail"}


@app.route("/downloadCanvas", methods=["GET"])
def downloadCanvas():
    global canvas

    with frame_lock:
        if canvas is None:
            return {"error": "Canvas is empty"}, 400

        image = canvas.copy()

    success, buffer = cv.imencode(".png", image)

    if not success:
        return {"error": "Failed to encode canvas"}, 500

    return send_file(
        BytesIO(buffer.tobytes()),
        mimetype="image/png",
        as_attachment=True,
        download_name="my_drawing.png"
    )


@app.route("/")
def home():
    """Render the application's home page (client UI).

    The template 'home.html' should provide the front-end that connects to the
    video and canvas streaming endpoints and the control endpoints.
    """
    return render_template("home.html")


@app.route("/video_feed")
def video_feed():
    """Flask route that streams the processed camera video as an MJPEG multipart response.

    Clients should request this endpoint to receive continuously updated
    JPEG frames rendered by generate_stream('video').
    """
    return Response(
        generate_stream("video"),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/drawCanvas")
def draw_canvas_route():
    """Flask route that streams the drawing canvas as an MJPEG multipart response.

    Clients should request this endpoint to receive the current canvas contents
    rendered as JPEG frames from generate_stream('canvas').
    """
    return Response(
        generate_stream("canvas"),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


def release_resources():
    """Stop background processing and release camera resources.

    Sets processing_active to False so the camera thread exits its loop, and
    releases the OpenCV VideoCapture if it is open. Safe to call during
    application shutdown.
    """
    global processing_active
    processing_active = False
    if camera.isOpened():
        camera.release()


if __name__ == "__main__":

    camera_thread = threading.Thread(
        target=process_camera,
        daemon=True
    )

    camera_thread.start()

    try:
        socketio.run(
            app,
            host="127.0.0.1",
            port=5600,
            debug=True,
            use_reloader=False
        )


    finally:
        release_resources()
