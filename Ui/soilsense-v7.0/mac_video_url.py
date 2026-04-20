import cv2
from flask import Flask, Response

app = Flask(__name__)

# 0 is usually the default built-in Mac webcam. 
# If you have an external cam or it doesn't work, try changing this to 1 or 2.
camera = cv2.VideoCapture(0)

def generate_frames():
    while True:
        # Read the camera frame
        success, frame = camera.read()
        if not success:
            break
        else:
            # Encode the frame in JPEG format
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            
            # Yield the frame in the byte format expected by a multipart stream
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    # Return the response generated along with the specific media type (mime type)
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    # Host on 0.0.0.0 so it's accessible from other devices on your local network
    # Port 5000 is the default
    print("Starting camera stream...")
    print("Test in browser at: http://127.0.0.1:5005/video_feed")
    print("Test on network at: http://<your-macs-local-ip>:5000/video_feed")
    app.run(host='0.0.0.0', port=5005, debug=False)