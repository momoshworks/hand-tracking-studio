import cv2
import time
import json
import asyncio
import os
import sys
import threading
from typing import List
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.detector import HandDetector
from core.gestures import GestureAnalyzer
from core.mouse_ctrl import VirtualMouse
from core.canvas_ctrl import AirCanvas
from core.audio_ctrl import VolumeController

app = FastAPI(title="Hand Tracking AI Studio", version="1.0.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

class VideoStreamManager:
    """
    Background Camera Worker that captures and processes frames in a dedicated thread.
    Allows multiple web clients without camera resource conflicts.
    """
    def __init__(self, camera_id=0, width=640, height=480):
        self.camera_id = camera_id
        self.width = width
        self.height = height

        self.detector = HandDetector(mode=False, max_hands=2, detection_con=0.7, track_con=0.6)
        self.analyzer = GestureAnalyzer()
        self.mouse = VirtualMouse(frame_w=width, frame_h=height, margin=70)
        self.canvas = AirCanvas(width=width, height=height)
        self.audio = VolumeController()

        self.current_mode = 1 # 1: Gestures, 2: Mouse, 3: Canvas, 4: Audio
        self.latest_data = {
            "mode": 1,
            "fps": 0,
            "hands_count": 0,
            "gesture": {"name": "None", "name_ar": "لا توجد يد", "emoji": "👋", "count": 0},
            "mouse": {"is_enabled": False, "action": "Idle", "x": 0, "y": 0},
            "volume": {"percent": 50, "dist": 0},
            "canvas": {"color": "Cyan"}
        }

        self.latest_jpeg = None
        self.cap = None
        self.is_running = False
        self.lock = threading.Lock()
        self.thread = None

        self.start()

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()

    def _capture_loop(self):
        print(f"[VideoStreamManager] Starting camera ID {self.camera_id}...")
        self.cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            # Fallback to default backend
            self.cap = cv2.VideoCapture(self.camera_id)

        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        p_time = time.time()

        while self.is_running:
            if not self.cap or not self.cap.isOpened():
                time.sleep(0.5)
                continue

            success, frame = self.cap.read()
            if not success:
                time.sleep(0.015)
                continue

            # Process Hand Detection
            img = self.detector.process_frame(frame, flip=True)
            hands = self.detector.get_all_hands(img)

            gesture_info = {"name": "Searching", "name_ar": "في انتظار يد...", "emoji": "🔍", "count": 0}
            mouse_info = {"is_enabled": self.mouse.is_enabled, "action": "Idle", "x": 0, "y": 0}
            vol_info = {"percent": self.audio.vol_percent, "dist": 0}

            if len(hands) > 0:
                primary = hands[0]
                gesture_info = self.analyzer.analyze_gesture(primary)

                # Mode 1: Gestures & Landmarks
                if self.current_mode == 1:
                    img = self.detector.draw_landmarks(img, custom_style=True)
                    lms = primary["landmarks"]
                    for idx, tip_id in enumerate([4, 8, 12, 16, 20]):
                        is_up = gesture_info["fingers"][idx]
                        col = (0, 255, 0) if is_up else (0, 0, 255)
                        cv2.circle(img, (lms[tip_id][0], lms[tip_id][1]), 7, col, cv2.FILLED)

                # Mode 2: Virtual Mouse
                elif self.current_mode == 2:
                    m = self.mouse.margin
                    cv2.rectangle(img, (m, m), (self.width - m, self.height - m), (120, 120, 140), 2)
                    res = self.mouse.update(primary, img)
                    mouse_info = {
                        "is_enabled": self.mouse.is_enabled,
                        "action": res["action"],
                        "x": res["screen_x"],
                        "y": res["screen_y"]
                    }
                    tx, ty = primary["landmarks"][8][0], primary["landmarks"][8][1]
                    cv2.circle(img, (tx, ty), 8, (255, 0, 255), 2)

                # Mode 3: Air Canvas
                elif self.current_mode == 3:
                    self.canvas.draw_palette(img)
                    self.canvas.update(primary, img)
                    img = self.canvas.blend(img)

                # Mode 4: Audio Controller
                elif self.current_mode == 4:
                    res_audio = self.audio.update(primary, img)
                    vol_info = {"percent": res_audio["volume"], "dist": res_audio["distance"]}

            else:
                if self.current_mode == 3:
                    self.canvas.draw_palette(img)
                    img = self.canvas.blend(img)

            # Compute FPS
            now = time.time()
            fps = 1.0 / (now - p_time) if (now - p_time) > 0 else 30
            p_time = now

            # Update telemetry cache
            with self.lock:
                self.latest_data = {
                    "mode": self.current_mode,
                    "fps": round(fps, 1),
                    "hands_count": len(hands),
                    "gesture": gesture_info,
                    "mouse": mouse_info,
                    "volume": vol_info,
                    "canvas": {"color": self.canvas.current_color_name}
                }

                # Encode JPEG
                ret, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    self.latest_jpeg = buffer.tobytes()

            time.sleep(0.001)

    def get_frame(self):
        with self.lock:
            return self.latest_jpeg

stream_manager = VideoStreamManager()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

conn_manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/video_feed")
async def video_feed():
    def frame_generator():
        while True:
            frame_bytes = stream_manager.get_frame()
            if frame_bytes is not None:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            time.sleep(0.015)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await conn_manager.connect(websocket)
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.08)
                msg = json.loads(data)
                action = msg.get("action")

                if action == "set_mode":
                    stream_manager.current_mode = int(msg.get("mode", 1))
                elif action == "toggle_mouse":
                    stream_manager.mouse.toggle()
                elif action == "clear_canvas":
                    stream_manager.canvas.clear()
                elif action == "set_color":
                    color_name = msg.get("color")
                    for p in stream_manager.canvas.PALETTE:
                        if p["name"].lower() == color_name.lower():
                            stream_manager.canvas.current_color = p["color"]
                            stream_manager.canvas.current_color_name = p["name"]
            except asyncio.TimeoutError:
                pass

            await websocket.send_json(stream_manager.latest_data)

    except WebSocketDisconnect:
        conn_manager.disconnect(websocket)
    except Exception:
        conn_manager.disconnect(websocket)

@app.post("/api/set_mode")
async def api_set_mode(request: Request):
    data = await request.json()
    mode = int(data.get("mode", 1))
    stream_manager.current_mode = mode
    return {"status": "ok", "mode": mode}

@app.post("/api/toggle_mouse")
async def api_toggle_mouse():
    state = stream_manager.mouse.toggle()
    return {"status": "ok", "is_enabled": state}

@app.post("/api/clear_canvas")
async def api_clear_canvas():
    stream_manager.canvas.clear()
    return {"status": "ok", "message": "Canvas cleared"}

@app.post("/api/save_canvas")
async def api_save_canvas():
    drawings_dir = os.path.join(BASE_DIR, "static", "drawings")
    path = stream_manager.canvas.save_drawing(drawings_dir)
    filename = os.path.basename(path)
    return {"status": "ok", "file_url": f"/static/drawings/{filename}"}

if __name__ == "__main__":
    import uvicorn
    # Dedicated Port 8050 for Hand Tracking Studio
    server_port = int(os.getenv("PORT", "8050"))
    uvicorn.run("main:app", host="127.0.0.1", port=server_port, reload=False)
