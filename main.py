from flask import Flask, render_template, redirect, Response
import cv2 as cv
from HandTrakingModule import HandDetection
import numpy as np

app = Flask(__name__)
camera = cv.VideoCapture(1)
hDetect = HandDetection(maxHands=1,
                        modelComplexity=0,
                        detectConfidence=0.7,
                        trackConfidence=0.7)


def generate_frame():
    x_indexTip, y_indexTip = 0, 0
    while True:
        # Read the camera frame
        success, frame = camera.read()
        frameFlip = cv.flip(frame, 1)
        if not success:
            break
        else:

            cv.rectangle(frameFlip, (0, 0), (640, 480), (255, 255, 255), 5)
            hDetect.findHands(frameFlip)

            lmList = hDetect.findHandPos(frameFlip)

            if lmList != None:
                indexTip = lmList[8]
                x_indexTip, y_indexTip = indexTip[1], indexTip[2]

                cv.circle(frameFlip, (x_indexTip, y_indexTip),
                          10, (255, 0, 0), -1)

        return [frameFlip, (x_indexTip, y_indexTip)]


def generate_framesImg():

    while True:
        frameFlip = generate_frame()
        # Encode the frame in JPEG format
        ret, buffer = cv.imencode(".jpg", frameFlip[0])
        frame_bytes = buffer.tobytes()
        # Yield the output frame in the byte format required for MJPEG streaming
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )


def draw_Canvas():
    canvas = np.zeros((640, 480, 3), dtype="uint8")
    xPrev, yPrev = 0, 0
    while True:
        frameFlip = generate_frame()
        xInit, yInit = frameFlip[1]

        if xPrev is 0 or yPrev is 0:
            xPrev, yPrev = xInit, yInit
        else:
            cv.line(canvas, (xPrev, yPrev), (xInit, yInit), (255, 0, 0), 5)
            xPrev, yPrev = xInit, yInit

        ret, buffer = cv.imencode(".jpg", canvas)
        frame_bytes = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/drawCanves")
def drawCanves():
    return Response(draw_Canvas(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/video_feed")
def video_feed():
    # Return the response generated along with the specific media type (mime type)
    return Response(
        generate_framesImg(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    app.run(debug=True, port=5600)
