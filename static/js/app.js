/**
 * Hand Tracking AI Studio - Client Application
 * WebSocket Real-Time Communication & UI Controller
 */

class HandStudioClient {
    constructor() {
        this.socket = null;
        this.currentMode = 1;
        this.modeNames = {
            1: "كاشف الإيماءات والأصابع",
            2: "الفأرة الافتراضية",
            3: "لوحة الرسم بالهواء",
            4: "التحكم بالصوت"
        };

        this.initDOMElements();
        this.initEventListeners();
        this.connectWebSocket();
    }

    initDOMElements() {
        // Status & Headers
        this.connStatus = document.getElementById("connStatus");
        this.statusText = document.getElementById("statusText");
        this.fpsVal = document.getElementById("fpsVal");
        this.activeModeLabel = document.getElementById("activeModeLabel");
        this.hudGesture = document.getElementById("hudGesture");
        this.hudFps = document.getElementById("hudFps");
        this.videoFeed = document.getElementById("videoFeed");

        // Modes Buttons
        this.modeButtons = document.querySelectorAll(".mode-btn");

        // Gesture Telemetry
        this.gestureEmoji = document.getElementById("gestureEmoji");
        this.gestureAr = document.getElementById("gestureAr");
        this.gestureEn = document.getElementById("gestureEn");
        this.fingerCount = document.getElementById("fingerCount");

        this.fingerPills = {
            thumb: document.getElementById("fingerThumb"),
            index: document.getElementById("fingerIndex"),
            middle: document.getElementById("fingerMiddle"),
            ring: document.getElementById("fingerRing"),
            pinky: document.getElementById("fingerPinky")
        };

        // Mouse Controls
        this.mouseToggle = document.getElementById("mouseToggle");
        this.mouseStateLabel = document.getElementById("mouseStateLabel");
        this.mouseActionLabel = document.getElementById("mouseActionLabel");
        this.mouseCoordsLabel = document.getElementById("mouseCoordsLabel");

        // Canvas Controls
        this.colorDots = document.querySelectorAll(".color-dot");
        this.btnClearCanvas = document.getElementById("btnClearCanvas");
        this.btnSaveCanvas = document.getElementById("btnSaveCanvas");
        this.saveResult = document.getElementById("saveResult");

        // Volume Controls
        this.volFill = document.getElementById("volFill");
        this.volPercent = document.getElementById("volPercent");
        this.volDist = document.getElementById("volDist");

        this.btnRefreshStream = document.getElementById("btnRefreshStream");
    }

    initEventListeners() {
        // Mode switching buttons
        this.modeButtons.forEach(btn => {
            btn.addEventListener("click", () => {
                const mode = parseInt(btn.dataset.mode);
                this.setMode(mode);
            });
        });

        // Mouse toggle
        this.mouseToggle.addEventListener("change", () => {
            this.sendWSMessage({ action: "toggle_mouse" });
        });

        // Canvas Palette
        this.colorDots.forEach(dot => {
            dot.addEventListener("click", () => {
                this.colorDots.forEach(d => d.classList.remove("active"));
                dot.classList.add("active");
                const color = dot.dataset.color;
                this.sendWSMessage({ action: "set_color", color: color });
            });
        });

        // Clear Canvas
        this.btnClearCanvas.addEventListener("click", () => {
            this.sendWSMessage({ action: "clear_canvas" });
        });

        // Save Canvas
        this.btnSaveCanvas.addEventListener("click", async () => {
            try {
                this.saveResult.textContent = "جاري حفظ الصورة...";
                const res = await fetch("/api/save_canvas", { method: "POST" });
                const data = await res.json();
                if (data.status === "ok") {
                    this.saveResult.innerHTML = `تم الحفظ بنجاح! <a href="${data.file_url}" target="_blank" style="color:var(--accent-cyan); text-decoration:underline;">عرض الصورة</a>`;
                }
            } catch (err) {
                this.saveResult.textContent = "حدث خطأ أثناء الحفظ.";
            }
        });

        // Refresh Stream
        this.btnRefreshStream.addEventListener("click", () => {
            this.videoFeed.src = "/video_feed?t=" + new Date().getTime();
        });
    }

    setMode(mode) {
        this.currentMode = mode;
        this.modeButtons.forEach(b => {
            b.classList.toggle("active", parseInt(b.dataset.mode) === mode);
        });
        this.activeModeLabel.textContent = this.modeNames[mode] || "وضع مخصص";
        this.sendWSMessage({ action: "set_mode", mode: mode });
    }

    connectWebSocket() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            this.connStatus.classList.add("connected");
            this.statusText.textContent = "متصل لحظياً";
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.updateTelemetry(data);
            } catch (e) {
                console.error("Error parsing WS data:", e);
            }
        };

        this.socket.onclose = () => {
            this.connStatus.classList.remove("connected");
            this.statusText.textContent = "انقطع الاتصال - إعادة المحاولة...";
            setTimeout(() => this.connectWebSocket(), 2000);
        };

        this.socket.onerror = (err) => {
            console.error("WS error:", err);
            this.socket.close();
        };
    }

    sendWSMessage(msg) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(msg));
        }
    }

    updateTelemetry(data) {
        // FPS & Mode
        if (data.fps !== undefined) {
            this.fpsVal.textContent = data.fps;
            this.hudFps.textContent = `${data.fps} FPS`;
        }

        // Gesture data
        if (data.gesture) {
            const g = data.gesture;
            this.gestureEmoji.textContent = g.emoji || "👋";
            this.gestureAr.textContent = g.name_ar || "لا توجد يد";
            this.gestureEn.textContent = g.name || "None";
            this.fingerCount.textContent = g.count || 0;
            this.hudGesture.textContent = `${g.emoji || '👋'} ${g.name_ar || 'لا توجد يد'}`;

            if (g.fingers && g.fingers.length === 5) {
                const keys = ["thumb", "index", "middle", "ring", "pinky"];
                keys.forEach((key, idx) => {
                    const isUp = g.fingers[idx] === 1;
                    if (this.fingerPills[key]) {
                        this.fingerPills[key].classList.toggle("active", isUp);
                    }
                });
            }
        }

        // Mouse Telemetry
        if (data.mouse) {
            const m = data.mouse;
            this.mouseToggle.checked = m.is_enabled;
            if (m.is_enabled) {
                this.mouseStateLabel.textContent = "مُفعّل (نشط)";
                this.mouseStateLabel.className = "on";
            } else {
                this.mouseStateLabel.textContent = "مُعطّل (للحماية)";
                this.mouseStateLabel.className = "off";
            }
            this.mouseActionLabel.textContent = m.action || "ثابت";
            this.mouseCoordsLabel.textContent = `${m.x || 0}, ${m.y || 0}`;
        }

        // Volume Telemetry
        if (data.volume) {
            const v = data.volume;
            const pct = Math.max(0, Math.min(100, v.percent || 0));
            this.volFill.style.width = `${pct}%`;
            this.volPercent.textContent = `${pct}%`;
            this.volDist.textContent = `${v.dist || 0} px`;
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    window.handStudio = new HandStudioClient();
});
