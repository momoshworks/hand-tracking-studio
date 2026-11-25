import time
import math
import numpy as np
import ctypes
from typing import Dict, Tuple, Optional

# Windows Native API Constants for 0ms ultra-low latency mouse events
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP   = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP  = 0x0010
MOUSEEVENTF_WHEEL    = 0x0800

try:
    import pyautogui
    pyautogui.PAUSE = 0.0 # CRITICAL: remove the default 0.1s sleep that capped FPS to 10!
    pyautogui.FAILSAFE = True
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

class VirtualMouse:
    """
    Ultra-Fast, Low-Latency Virtual Mouse Controller:
    - Direct Windows Win32 API calls (0ms lag, zero sleep calls).
    - Velocity-Adaptive Exponential Smoothing: instant response when moving, stable when hovering.
    - Pinch to Left Click.
    - Middle-thumb pinch or double finger for Right Click.
    - Two-finger drag for vertical scrolling.
    """
    def __init__(self, frame_w: int = 640, frame_h: int = 480, margin: int = 70):
        self.frame_w = frame_w
        self.frame_h = frame_h
        self.margin = margin

        # Get real screen dimensions
        user32 = ctypes.windll.user32
        self.screen_w = user32.GetSystemMetrics(0)
        self.screen_h = user32.GetSystemMetrics(1)

        self.prev_x = self.screen_w // 2
        self.prev_y = self.screen_h // 2
        self.is_enabled = False # Safety toggle

        self.is_left_down = False
        self.last_click_time = 0
        self.click_cooldown = 0.18 # seconds

        self.last_scroll_y = None

    def toggle(self, state: Optional[bool] = None) -> bool:
        if state is not None:
            self.is_enabled = state
        else:
            self.is_enabled = not self.is_enabled
        return self.is_enabled

    def _win_move(self, x: int, y: int):
        """Native Windows cursor movement in <0.001 ms."""
        ctypes.windll.user32.SetCursorPos(int(x), int(y))

    def _win_click(self, is_right: bool = False):
        """Native Windows mouse click."""
        down_flag = MOUSEEVENTF_RIGHTDOWN if is_right else MOUSEEVENTF_LEFTDOWN
        up_flag = MOUSEEVENTF_RIGHTUP if is_right else MOUSEEVENTF_LEFTUP
        ctypes.windll.user32.mouse_event(down_flag, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(up_flag, 0, 0, 0, 0)

    def _win_scroll(self, amount: int):
        """Native Windows mouse wheel scroll."""
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(amount), 0)

    def update(self, hand: Dict, img=None) -> Dict:
        lms = hand["landmarks"]
        # Index tip: 8, Thumb tip: 4, Middle tip: 12
        x8, y8 = lms[8][0], lms[8][1]
        x4, y4 = lms[4][0], lms[4][1]
        x12, y12 = lms[12][0], lms[12][1]

        # Map active rectangular box to full desktop resolution
        target_x = np.interp(x8, (self.margin, self.frame_w - self.margin), (0, self.screen_w))
        target_y = np.interp(y8, (self.margin, self.frame_h - self.margin), (0, self.screen_h))

        # Velocity-adaptive smoothing:
        # If moving fast, reduce smooth to 1.2 (instant reaction); if holding still, increase to 2.5
        dx = abs(target_x - self.prev_x)
        dy = abs(target_y - self.prev_y)
        velocity = math.hypot(dx, dy)
        smooth_factor = 1.2 if velocity > 25 else 2.2

        curr_x = self.prev_x + (target_x - self.prev_x) / smooth_factor
        curr_y = self.prev_y + (target_y - self.prev_y) / smooth_factor
        self.prev_x, self.prev_y = curr_x, curr_y

        dist_thumb_index = math.hypot(x8 - x4, y8 - y4)
        dist_thumb_middle = math.hypot(x12 - x4, y12 - y4)
        dist_index_middle = math.hypot(x12 - x8, y12 - y8)

        action = "Moving"
        now = time.time()

        # Check for Left Click (Pinch Index + Thumb)
        if dist_thumb_index < 30:
            action = "Left Click"
            if self.is_enabled and (now - self.last_click_time > self.click_cooldown):
                self._win_click(is_right=False)
                self.last_click_time = now

        # Check for Right Click (Pinch Middle + Thumb)
        elif dist_thumb_middle < 30:
            action = "Right Click"
            if self.is_enabled and (now - self.last_click_time > self.click_cooldown):
                self._win_click(is_right=True)
                self.last_click_time = now

        # Check for Scroll Mode: Two fingers (Index + Middle) up together
        elif dist_index_middle < 45 and y8 < lms[6][1] and y12 < lms[10][1]:
            action = "Scrolling"
            if self.last_scroll_y is not None:
                delta_y = y8 - self.last_scroll_y
                if abs(delta_y) > 4:
                    scroll_amount = int(-delta_y * 15)
                    if self.is_enabled:
                        self._win_scroll(scroll_amount)
            self.last_scroll_y = y8
        else:
            self.last_scroll_y = None
            if self.is_enabled:
                self._win_move(curr_x, curr_y)

        return {
            "screen_x": int(curr_x),
            "screen_y": int(curr_y),
            "action": action,
            "is_enabled": self.is_enabled,
            "target": (int(curr_x), int(curr_y))
        }
