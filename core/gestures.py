import math
from typing import Dict, List, Tuple

class GestureAnalyzer:
    """
    Robust, Rotation-Invariant Gesture Analyzer.
    Determines finger states and classifies gestures accurately in real-time.
    """
    TIP_IDS = [4, 8, 12, 16, 20]
    PIP_IDS = [2, 6, 10, 14, 18]
    MCP_IDS = [1, 5, 9, 13, 17]

    def __init__(self):
        pass

    def get_fingers_up(self, hand: Dict) -> List[int]:
        """
        Determines which fingers are extended (1) or folded (0) using
        distance-to-wrist and relative joint vectors (rotation-invariant).
        """
        lms = hand["landmarks"]
        fingers = []

        # Wrist point (0)
        wx, wy = lms[0][0], lms[0][1]

        # 1. Thumb State:
        # Distance from thumb tip (4) to Index MCP (5) and Pinky MCP (17)
        d_tip_pinky = math.hypot(lms[4][0] - lms[17][0], lms[4][1] - lms[17][1])
        d_ip_pinky  = math.hypot(lms[3][0] - lms[17][0], lms[3][1] - lms[17][1])
        d_tip_index = math.hypot(lms[4][0] - lms[5][0],  lms[4][1] - lms[5][1])
        d_mcp_index = math.hypot(lms[2][0] - lms[5][0],  lms[2][1] - lms[5][1])

        if (d_tip_pinky > d_ip_pinky * 1.15) and (d_tip_index > d_mcp_index * 1.1):
            fingers.append(1)
        else:
            fingers.append(0)

        # 2. Four Fingers (Index, Middle, Ring, Pinky):
        # When extended, distance from Wrist (0) to Tip is significantly larger than Wrist to PIP
        for i in range(1, 5):
            tip_id = self.TIP_IDS[i]
            pip_id = self.PIP_IDS[i]

            d_wrist_tip = math.hypot(lms[tip_id][0] - wx, lms[tip_id][1] - wy)
            d_wrist_pip = math.hypot(lms[pip_id][0] - wx, lms[pip_id][1] - wy)

            # Upright screen check + distance check for extreme robustness
            is_dist_extended = d_wrist_tip > d_wrist_pip * 1.12
            is_upright_extended = lms[tip_id][1] < lms[pip_id][1]

            if is_dist_extended or is_upright_extended:
                fingers.append(1)
            else:
                fingers.append(0)

        return fingers

    def analyze_gesture(self, hand: Dict) -> Dict:
        """Recognizes high-level gestures and returns Arabic and English metadata."""
        lms = hand["landmarks"]
        fingers = self.get_fingers_up(hand)
        count = sum(fingers)
        thumb, index, middle, ring, pinky = fingers

        # Pinch detection (Thumb 4 and Index 8)
        dist_pinch = math.hypot(lms[4][0] - lms[8][0], lms[4][1] - lms[8][1])
        is_pinching = dist_pinch < 32

        gesture_name = "Unknown"
        gesture_ar = "غير محدد"
        emoji = "❓"

        if count == 0:
            gesture_name = "Fist"
            gesture_ar = "قبضة مغلقة"
            emoji = "✊"
        elif count == 5:
            gesture_name = "Open Palm"
            gesture_ar = "كف مفتوح"
            emoji = "✋"
        elif is_pinching and (middle == 1 and ring == 1 and pinky == 1):
            gesture_name = "OK Sign"
            gesture_ar = "إشارة تمام"
            emoji = "👌"
        elif is_pinching:
            gesture_name = "Pinch"
            gesture_ar = "قرص / تحديد"
            emoji = "🤏"
        elif thumb == 1 and index == 0 and middle == 0 and ring == 0 and pinky == 0:
            if lms[4][1] < lms[0][1]:
                gesture_name = "Thumbs Up"
                gesture_ar = "إعجاب"
                emoji = "👍"
            else:
                gesture_name = "Thumbs Down"
                gesture_ar = "عدم إعجاب"
                emoji = "👎"
        elif index == 1 and middle == 0 and ring == 0 and pinky == 0:
            gesture_name = "Pointing"
            gesture_ar = "إشارة السبابة"
            emoji = "👉"
        elif index == 1 and middle == 1 and ring == 0 and pinky == 0:
            gesture_name = "Peace / Victory"
            gesture_ar = "إشارة النصر"
            emoji = "✌️"
        elif index == 1 and pinky == 1 and middle == 0 and ring == 0:
            gesture_name = "Rock On"
            gesture_ar = "إشارة الروك"
            emoji = "🤘"
        elif thumb == 1 and index == 1 and pinky == 1 and middle == 0 and ring == 0:
            gesture_name = "Love / Spider-Man"
            gesture_ar = "إشارة الحب"
            emoji = "🤟"
        elif count == 3 and index == 1 and middle == 1 and ring == 1:
            gesture_name = "Three Fingers"
            gesture_ar = "ثلاثة أصابع"
            emoji = "3️⃣"
        elif count == 4 and index == 1 and middle == 1 and ring == 1 and pinky == 1:
            gesture_name = "Four Fingers"
            gesture_ar = "أربعة أصابع"
            emoji = "4️⃣"
        else:
            gesture_name = f"{count} Fingers"
            gesture_ar = f"{count} أصابع"
            emoji = f"{count}️⃣"

        return {
            "name": gesture_name,
            "name_ar": gesture_ar,
            "emoji": emoji,
            "fingers": fingers,
            "count": count,
            "is_pinching": is_pinching,
            "pinch_distance": round(dist_pinch, 1)
        }
