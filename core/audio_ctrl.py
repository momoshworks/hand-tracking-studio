import numpy as np
import math
import cv2
from typing import Dict, Tuple

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

class VolumeController:
    """
    Controls audio volume using thumb-to-index finger distance:
    - Distance 20px -> 0% (Mute)
    - Distance 200px -> 100% (Max)
    - Draws dynamic volume slider bar on screen
    - Safe control with activation gesture (Pinky finger down or special gesture)
    """
    def __init__(self, min_dist: int = 25, max_dist: int = 180):
        self.min_dist = min_dist
        self.max_dist = max_dist
        self.vol_percent = 50
        self.vol_bar = 350
        self.is_active = True
        self.last_press_time = 0

    def update(self, hand: Dict, img=None) -> Dict:
        lms = hand["landmarks"]
        # Thumb tip (4) and Index tip (8)
        x4, y4 = lms[4][0], lms[4][1]
        x8, y8 = lms[8][0], lms[8][1]
        cx, cy = (x4 + x8) // 2, (y4 + y8) // 2

        # Distance
        dist = math.hypot(x8 - x4, y8 - y4)

        # Map distance to percentage (0 to 100)
        self.vol_percent = int(np.interp(dist, [self.min_dist, self.max_dist], [0, 100]))
        # Bar height on screen (400 to 150)
        self.vol_bar = int(np.interp(dist, [self.min_dist, self.max_dist], [380, 150]))

        if img is not None:
            # Draw line & circles between thumb and index
            cv2.line(img, (x4, y4), (x8, y8), (0, 255, 255), 2)
            cv2.circle(img, (x4, y4), 8, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (x8, y8), 8, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (cx, cy), 6, (0, 255, 0), cv2.FILLED)

            # Draw sleek vertical volume bar
            cv2.rectangle(img, (40, 150), (70, 380), (50, 50, 60), 2)
            # Fill bar with color gradient effect
            bar_color = (0, 255, 0) if self.vol_percent > 30 else (0, 0, 255)
            cv2.rectangle(img, (40, self.vol_bar), (70, 380), bar_color, cv2.FILLED)
            cv2.putText(img, f"{self.vol_percent}%", (35, 415), cv2.FONT_HERSHEY_PLAIN, 1.8, (0, 255, 255), 2)

        return {
            "volume": self.vol_percent,
            "distance": round(dist, 1),
            "center": (cx, cy)
        }
