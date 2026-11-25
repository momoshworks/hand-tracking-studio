import os
import cv2
import math
import time
import urllib.request
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from typing import List, Dict, Tuple, Optional

# Standard 21 Hand Landmark Connections
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # Index
    (5, 9), (9, 10), (10, 11), (11, 12),   # Middle
    (9, 13), (13, 14), (14, 15), (15, 16), # Ring
    (13, 17), (17, 18), (18, 19), (19, 20),# Pinky
    (0, 17)                                # Palm base
]

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"

class HandDetector:
    """
    High-Performance Hand Detector using MediaPipe Tasks Video Tracking Mode.
    Tracks hand landmarks smoothly across frames at 50+ FPS with minimal CPU latency.
    """
    def __init__(self, mode: bool = False, max_hands: int = 1, 
                 detection_con: float = 0.5, track_con: float = 0.5):
        self.max_hands = max_hands
        self.detection_con = detection_con
        self.track_con = track_con

        # Model file
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.model_path = os.path.join(base_dir, "models", "hand_landmarker.task")
        self._ensure_model_exists()

        # Initialize detector in VIDEO tracking mode (massive speedup over IMAGE mode)
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=self.max_hands,
            min_hand_detection_confidence=self.detection_con,
            min_hand_presence_confidence=self.track_con,
            min_tracking_confidence=self.track_con
        )
        self.detector = vision.HandLandmarker.create_from_options(options)
        self.detection_result = None
        self._last_timestamp_ms = 0

    def _ensure_model_exists(self):
        if not os.path.exists(self.model_path):
            print(f"[HandDetector] Downloading model to: {self.model_path} ...")
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            urllib.request.urlretrieve(MODEL_URL, self.model_path)
            print("[HandDetector] Model downloaded.")

    def process_frame(self, img: np.ndarray, flip: bool = True) -> np.ndarray:
        """Processes frame using high-speed temporal tracking."""
        if flip:
            img = cv2.flip(img, 1)

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)

        # Monotonically increasing timestamp in ms
        now_ms = int(time.time() * 1000)
        if now_ms <= self._last_timestamp_ms:
            now_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = now_ms

        self.detection_result = self.detector.detect_for_video(mp_image, now_ms)
        return img

    def draw_landmarks(self, img: np.ndarray, custom_style: bool = True) -> np.ndarray:
        """Fast vectorized drawing for maximum frame rate."""
        if not self.detection_result or not self.detection_result.hand_landmarks:
            return img

        h, w, _ = img.shape

        for hand_landmarks in self.detection_result.hand_landmarks:
            coords = [(int(lm.x * w), int(lm.y * h)) for lm in hand_landmarks]

            # Fast bone lines
            for p1_idx, p2_idx in HAND_CONNECTIONS:
                cv2.line(img, coords[p1_idx], coords[p2_idx], (0, 255, 200), 2)

            # Joint nodes
            for idx, pt in enumerate(coords):
                if idx in [4, 8, 12, 16, 20]:
                    cv2.circle(img, pt, 6, (255, 0, 128), cv2.FILLED)
                else:
                    cv2.circle(img, pt, 3, (0, 255, 200), cv2.FILLED)

        return img

    def get_all_hands(self, img: np.ndarray) -> List[Dict]:
        """Extracts structured landmarks, bounding boxes, and centers."""
        all_hands = []
        if not self.detection_result or not self.detection_result.hand_landmarks:
            return all_hands

        h, w, _ = img.shape
        handedness_list = self.detection_result.handedness or []

        for idx, hand_lms in enumerate(self.detection_result.hand_landmarks):
            label = "Hand"
            score = 0.99
            if idx < len(handedness_list) and len(handedness_list[idx]) > 0:
                label = handedness_list[idx][0].category_name
                score = handedness_list[idx][0].score

            lm_dict = {}
            lm_list = []
            min_x, max_x = w, 0
            min_y, max_y = h, 0

            for id, lm in enumerate(hand_lms):
                cx, cy = int(lm.x * w), int(lm.y * h)
                if cx < min_x: min_x = cx
                if cx > max_x: max_x = cx
                if cy < min_y: min_y = cy
                if cy > max_y: max_y = cy

                lm_dict[id] = (cx, cy, lm.z)
                lm_list.append({"id": id, "x": cx, "y": cy, "z": float(lm.z)})

            xmin = max(0, min_x - 10)
            xmax = min(w, max_x + 10)
            ymin = max(0, min_y - 10)
            ymax = min(h, max_y + 10)
            bbox = (xmin, ymin, xmax - xmin, ymax - ymin)

            all_hands.append({
                "index": idx,
                "label": label,
                "score": float(score),
                "landmarks": lm_dict,
                "lm_list": lm_list,
                "bbox": bbox,
                "center": ((xmin + xmax) // 2, (ymin + ymax) // 2)
            })

        return all_hands

    def get_distance(self, p1: Tuple[int, int], p2: Tuple[int, int], 
                     img=None, draw: bool = False) -> Tuple[float, Tuple[int, int]]:
        x1, y1 = p1
        x2, y2 = p2
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        length = math.hypot(x2 - x1, y2 - y1)

        if draw and img is not None:
            cv2.line(img, (x1, y1), (x2, y2), (255, 255, 0), 2)
            cv2.circle(img, (x1, y1), 5, (0, 255, 255), cv2.FILLED)
            cv2.circle(img, (x2, y2), 5, (0, 255, 255), cv2.FILLED)
            cv2.circle(img, (cx, cy), 4, (0, 0, 255), cv2.FILLED)

        return length, (cx, cy)
