import cv2
import numpy as np
import time
import os
from typing import Dict, List, Tuple

class AirCanvas:
    """
    Air Canvas / Virtual Painter:
    - Draw freely in the air using the index finger.
    - Two fingers up (Index + Middle) to select colors or move without drawing.
    - Top palette with multiple vibrant neon colors and Eraser.
    - Export canvas to high-res PNG.
    - Smooth anti-aliased strokes.
    """
    PALETTE = [
        {"name": "Cyan", "color": (255, 255, 0), "rgb": "#00ffff"},
        {"name": "Magenta", "color": (255, 0, 255), "rgb": "#ff00ff"},
        {"name": "Green", "color": (0, 255, 128), "rgb": "#80ff00"},
        {"name": "Yellow", "color": (0, 215, 255), "rgb": "#ffd700"},
        {"name": "White", "color": (255, 255, 255), "rgb": "#ffffff"},
        {"name": "Eraser", "color": (0, 0, 0), "rgb": "#000000"}
    ]

    def __init__(self, width: int = 640, height: int = 480):
        self.width = width
        self.height = height
        self.canvas = np.zeros((height, width, 3), dtype=np.uint8)
        self.brush_thickness = 7
        self.eraser_thickness = 40
        self.current_color = self.PALETTE[0]["color"]
        self.current_color_name = self.PALETTE[0]["name"]
        self.prev_pt = None
        self.header_height = 65

    def clear(self):
        """Clears the whole drawing canvas."""
        self.canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self.prev_pt = None

    def draw_palette(self, img):
        """Draws interactive neon top header with color swatches."""
        num_items = len(self.PALETTE) + 1 # +1 for "Clear" button
        item_w = self.width // num_items

        # Top background banner
        cv2.rectangle(img, (0, 0), (self.width, self.header_height), (25, 25, 30), cv2.FILLED)
        cv2.line(img, (0, self.header_height), (self.width, self.header_height), (80, 80, 90), 2)

        for i, item in enumerate(self.PALETTE):
            x1, x2 = i * item_w + 8, (i + 1) * item_w - 8
            y1, y2 = 10, self.header_height - 10
            
            # Active selection highlight
            is_active = (item["name"] == self.current_color_name)
            if is_active:
                cv2.rectangle(img, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), (255, 255, 255), 2)

            if item["name"] == "Eraser":
                cv2.rectangle(img, (x1, y1), (x2, y2), (60, 60, 70), cv2.FILLED)
                cv2.putText(img, "ERASE", (x1 + 6, y2 - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
            else:
                cv2.rectangle(img, (x1, y1), (x2, y2), item["color"], cv2.FILLED)
                cv2.putText(img, item["name"][:3], (x1 + 8, y2 - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)

        # Clear All Button at the end
        cx1, cx2 = num_items * item_w - item_w + 8, self.width - 8
        cy1, cy2 = 10, self.header_height - 10
        cv2.rectangle(img, (cx1, cy1), (cx2, cy2), (40, 40, 180), cv2.FILLED)
        cv2.putText(img, "CLEAR", (cx1 + 6, cy2 - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        return img

    def update(self, hand: Dict, img):
        """
        Processes index & middle finger coordinates for selection or drawing.
        """
        lms = hand["landmarks"]
        # Index tip: 8, Middle tip: 12
        x8, y8 = lms[8][0], lms[8][1]
        x12, y12 = lms[12][0], lms[12][1]

        # Finger up states: Index (8 < 6) and Middle (12 < 10)
        index_up = y8 < lms[6][1]
        middle_up = y12 < lms[10][1]

        mode = "Hover"

        # 1. Selection Mode (Both Index and Middle fingers up)
        if index_up and middle_up:
            self.prev_pt = None
            mode = "Selection"
            # Visual indicator (circle around both tips)
            cv2.circle(img, (x8, y8), 10, (200, 200, 200), 2)
            cv2.circle(img, (x12, y12), 10, (200, 200, 200), 2)

            # Check if clicked inside header
            if y8 < self.header_height:
                num_items = len(self.PALETTE) + 1
                item_w = self.width // num_items
                idx = x8 // item_w

                if idx < len(self.PALETTE):
                    self.current_color = self.PALETTE[idx]["color"]
                    self.current_color_name = self.PALETTE[idx]["name"]
                elif idx >= len(self.PALETTE):
                    self.clear()

        # 2. Drawing Mode (Only Index finger up)
        elif index_up and not middle_up:
            mode = "Drawing"
            # Draw cursor ring on video
            cv2.circle(img, (x8, y8), self.brush_thickness, self.current_color, cv2.FILLED)

            if y8 > self.header_height:
                if self.prev_pt is None:
                    self.prev_pt = (x8, y8)

                thickness = self.eraser_thickness if self.current_color_name == "Eraser" else self.brush_thickness
                cv2.line(self.canvas, self.prev_pt, (x8, y8), self.current_color, thickness, cv2.LINE_AA)
                self.prev_pt = (x8, y8)
        else:
            self.prev_pt = None

        return mode

    def blend(self, img) -> np.ndarray:
        """
        Combines webcam frame with the painted canvas.
        """
        # Convert canvas to grayscale to create mask
        img_gray = cv2.cvtColor(self.canvas, cv2.COLOR_BGR2GRAY)
        _, img_inv = cv2.threshold(img_gray, 20, 255, cv2.THRESH_BINARY_INV)
        img_inv = cv2.cvtColor(img_inv, cv2.COLOR_GRAY2BGR)

        # Black-out area of drawing in original image, then add canvas
        img = cv2.bitwise_and(img, img_inv)
        img = cv2.bitwise_or(img, self.canvas)
        return img

    def save_drawing(self, output_dir: str = "drawings") -> str:
        """Saves current canvas to a timestamped PNG file."""
        os.makedirs(output_dir, exist_ok=True)
        filename = f"drawing_{int(time.time())}.png"
        path = os.path.join(output_dir, filename)
        cv2.imwrite(path, self.canvas)
        return path
