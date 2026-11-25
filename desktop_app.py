"""
Hand Tracking AI Studio - High-Performance Desktop App (Ultra-Fast 60 FPS)
All-in-One: Gestures + Virtual Mouse + Air Canvas + 3D Landmarks
"""
import cv2
import time
import os
import sys

# Ensure local core imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.detector import HandDetector
from core.gestures import GestureAnalyzer
from core.mouse_ctrl import VirtualMouse
from core.canvas_ctrl import AirCanvas
from core.audio_ctrl import VolumeController

class HandStudioApp:
    MODES = {
        1: "GESTURES & COUNTER",
        2: "VIRTUAL MOUSE",
        3: "AIR CANVAS",
        4: "VOLUME CONTROLLER"
    }

    def __init__(self, camera_id=0, width=640, height=480):
        # 640x480 gives optimal 60 FPS throughput on standard USB webcams
        self.width = width
        self.height = height
        self.camera_id = camera_id

        # Core Engines (video tracking mode, 0ms lag mouse)
        self.detector = HandDetector(mode=False, max_hands=1, detection_con=0.5, track_con=0.5)
        self.analyzer = GestureAnalyzer()
        self.mouse = VirtualMouse(frame_w=width, frame_h=height, margin=60)
        self.canvas = AirCanvas(width=width, height=height)
        self.audio = VolumeController()

        self.current_mode = 1
        self.p_time = time.time()
        self.fps = 0

    def draw_hud(self, img, gesture_info, mouse_info, hands):
        # Top-left info box
        overlay = img.copy()
        cv2.rectangle(overlay, (8, 8), (320, 150), (15, 15, 20), cv2.FILLED)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
        cv2.rectangle(img, (8, 8), (320, 150), (0, 255, 200), 1)

        # Title & Mode
        cv2.putText(img, "HAND TRACKING AI STUDIO", (16, 28), cv2.FONT_HERSHEY_DUPLEX, 0.52, (0, 255, 200), 1)
        mode_str = f"MODE [{self.current_mode}]: {self.MODES[self.current_mode]}"
        cv2.putText(img, mode_str, (16, 52), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1)

        # FPS (Color-coded: Green for >30, Yellow for >20, Red for <20)
        fps_val = int(self.fps)
        fps_col = (0, 255, 0) if fps_val >= 28 else (0, 215, 255)
        cv2.putText(img, f"FPS: {fps_val}", (245, 28), cv2.FONT_HERSHEY_PLAIN, 1.2, fps_col, 2)

        if gesture_info:
            g_name = gesture_info.get("name", "None")
            g_ar = gesture_info.get("name_ar", "")
            f_count = gesture_info.get("count", 0)
            cv2.putText(img, f"Gesture: {g_name} ({f_count})", (16, 80), cv2.FONT_HERSHEY_DUPLEX, 0.52, (0, 215, 255), 1)
            cv2.putText(img, f"Ar: {g_ar}", (16, 102), cv2.FONT_HERSHEY_DUPLEX, 0.5, (180, 180, 255), 1)

        if self.current_mode == 2:
            m_state = "ACTIVE" if self.mouse.is_enabled else "OFF (Press M)"
            m_col = (0, 255, 0) if self.mouse.is_enabled else (0, 120, 255)
            cv2.putText(img, f"Mouse: {m_state}", (16, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.5, m_col, 1)

        # Bottom Bar: Shortcuts reminder
        cv2.rectangle(img, (0, self.height - 28), (self.width, self.height), (12, 12, 16), cv2.FILLED)
        shortcuts = "Keys: [1-4] Modes  |  [M] Mouse Toggle  |  [C] Clear Canvas  |  [Q] Exit"
        cv2.putText(img, shortcuts, (15, self.height - 9), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)

    def run(self):
        print("="*60)
        print("⚡ High-Speed Hand Tracking AI Studio is Starting...")
        print("Press [1-4] to switch modes, [M] for mouse toggle, [Q] to quit.")
        print("="*60)

        # DirectShow with hardware MJPG gives lowest latency on Windows
        cap = cv2.VideoCapture(self.camera_id, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.camera_id)

        # Crucial camera optimizations:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) # Eliminates frame queue delay

        if not cap.isOpened():
            print(f"❌ Error: Could not open camera {self.camera_id}.")
            return

        while True:
            success, frame = cap.read()
            if not success:
                continue

            # Process hand detection (temporal tracking)
            img = self.detector.process_frame(frame, flip=True)
            hands = self.detector.get_all_hands(img)

            gesture_info = None
            mouse_info = None

            if len(hands) > 0:
                primary = hands[0]
                gesture_info = self.analyzer.analyze_gesture(primary)

                # MODE 1: Gestures & Counter
                if self.current_mode == 1:
                    img = self.detector.draw_landmarks(img, custom_style=True)
                    lms = primary["landmarks"]
                    for idx, tip_id in enumerate([4, 8, 12, 16, 20]):
                        is_up = gesture_info["fingers"][idx]
                        col = (0, 255, 0) if is_up else (0, 0, 255)
                        cv2.circle(img, (lms[tip_id][0], lms[tip_id][1]), 6, col, cv2.FILLED)

                # MODE 2: Virtual Mouse
                elif self.current_mode == 2:
                    m = self.mouse.margin
                    cv2.rectangle(img, (m, m), (self.width - m, self.height - m), (100, 100, 120), 1)
                    mouse_info = self.mouse.update(primary, img)
                    tx, ty = primary["landmarks"][8][0], primary["landmarks"][8][1]
                    cv2.circle(img, (tx, ty), 8, (255, 0, 255), 2)
                    cv2.putText(img, mouse_info["action"], (tx + 12, ty), cv2.FONT_HERSHEY_PLAIN, 1.2, (255, 255, 0), 1)

                # MODE 3: Air Canvas
                elif self.current_mode == 3:
                    self.canvas.draw_palette(img)
                    self.canvas.update(primary, img)
                    img = self.canvas.blend(img)

                # MODE 4: Volume Controller
                elif self.current_mode == 4:
                    self.audio.update(primary, img)

            else:
                if self.current_mode == 3:
                    self.canvas.draw_palette(img)
                    img = self.canvas.blend(img)

            # Smoothed FPS computation
            c_time = time.time()
            dt = c_time - self.p_time
            if dt > 0:
                current_fps = 1.0 / dt
                self.fps = 0.85 * self.fps + 0.15 * current_fps if self.fps > 0 else current_fps
            self.p_time = c_time

            self.draw_hud(img, gesture_info, mouse_info, hands)
            cv2.imshow("Hand Tracking AI Studio", img)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                break
            elif key == ord('1'):
                self.current_mode = 1
            elif key == ord('2'):
                self.current_mode = 2
            elif key == ord('3'):
                self.current_mode = 3
            elif key == ord('4'):
                self.current_mode = 4
            elif key == ord('m') or key == ord('M'):
                self.mouse.toggle()
            elif key == ord('c') or key == ord('C'):
                self.canvas.clear()
            elif key == ord('s') or key == ord('S'):
                if self.current_mode == 3:
                    self.canvas.save_drawing()

        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    app = HandStudioApp()
    app.run()
