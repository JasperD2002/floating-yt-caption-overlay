#!/usr/bin/env python3
"""
YouTube Caption Overlay
=======================
Displays YouTube closed captions in a borderless, always-on-top,
resizable overlay window with transparent background and text outline.

Receives captions from a Chrome extension via WebSocket.
No browser flags, no separate Chrome window, no screen capture needed.

Requirements:
    pip install websockets

Setup:
    1. Load the extension in Chrome:
       - Go to chrome://extensions
       - Enable "Developer mode" (top-right)
       - Click "Load unpacked" and select yt_caption_extension/
    2. Run this script:
       python yt_caption_overlay.py
    3. Play any YouTube video and turn on CC.

    Drag the overlay by clicking on the caption text.
    Resize by dragging the bottom-right corner handle.
    Right-click for Close / Toggle Always-on-Top.
"""

import asyncio
import json
import queue
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont

try:
    import websockets
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install websockets")
    input("\nPress Enter to exit...")
    sys.exit(1)

WS_HOST = "127.0.0.1"
WS_PORT = 9876
TRANSPARENT = "#010101"

# Pick the best available font for CJK + Latin mixed text
_CANDIDATE_FONTS = [
    "Yu Gothic UI", "Yu Gothic", "Meiryo UI", "Meiryo",
    "Noto Sans CJK JP", "MS Gothic", "Segoe UI",
]
_BEST_FONT = None

def _pick_font():
    global _BEST_FONT
    if _BEST_FONT:
        return _BEST_FONT
    available = tkfont.families()
    for name in _CANDIDATE_FONTS:
        if name in available:
            _BEST_FONT = (name, 22, "bold")
            return _BEST_FONT
    _BEST_FONT = ("Segoe UI", 22, "bold")
    return _BEST_FONT

OUTLINE_OFFSETS = [
    (-2, -2), (0, -2), (2, -2),
    (-2,  0),          (2,  0),
    (-2,  2), (0,  2), (2,  2),
]


class CaptionOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("YouTube Caption Overlay")
        self.root.configure(bg=TRANSPARENT)

        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        win_w, win_h = 800, 120
        x = (sw - win_w) // 2
        y = sh - win_h - 80
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")

        self.root.resizable(True, True)
        self.root.minsize(200, 40)

        self.canvas = tk.Canvas(
            self.root, bg=TRANSPARENT, highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self._drag_data = {"x": 0, "y": 0}

        self.resize_canvas = tk.Canvas(
            self.root, width=16, height=16, bg=TRANSPARENT,
            highlightthickness=0, cursor="size_nw_se",
        )
        self.resize_canvas.place(relx=1.0, rely=1.0, anchor="se")
        self.resize_canvas.create_line(16, 4, 4, 16, fill="white", width=2)
        self.resize_canvas.create_line(16, 10, 10, 16, fill="white", width=2)
        self.resize_canvas.create_line(16, 0, 0, 16, fill="#666", width=1)
        self.resize_canvas.bind("<Button-1>", self._resize_start)
        self.resize_canvas.bind("<B1-Motion>", self._resize_move)
        self._resize_data = {"x": 0, "y": 0, "w": 0, "h": 0}

        self.canvas.bind("<Configure>", self._redraw)
        self.root.bind("<Button-3>", self._show_menu)

        self.caption_queue: queue.Queue = queue.Queue()
        self.current_text = ""
        self.connected = False

        self.running = True
        self.ws_thread = threading.Thread(target=self._run_server, daemon=True)
        self.ws_thread.start()

        self._poll_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    # -----------------------------------------------------------------
    # drag
    # -----------------------------------------------------------------
    def _drag_start(self, event):
        self._drag_data["x"] = event.x_root - self.root.winfo_x()
        self._drag_data["y"] = event.y_root - self.root.winfo_y()

    def _drag_move(self, event):
        x = event.x_root - self._drag_data["x"]
        y = event.y_root - self._drag_data["y"]
        self.root.geometry(f"+{x}+{y}")

    # -----------------------------------------------------------------
    # resize
    # -----------------------------------------------------------------
    def _resize_start(self, event):
        self._resize_data["x"] = event.x_root
        self._resize_data["y"] = event.y_root
        self._resize_data["w"] = self.root.winfo_width()
        self._resize_data["h"] = self.root.winfo_height()

    def _resize_move(self, event):
        dw = event.x_root - self._resize_data["x"]
        dh = event.y_root - self._resize_data["y"]
        new_w = max(200, self._resize_data["w"] + dw)
        new_h = max(40, self._resize_data["h"] + dh)
        self.root.geometry(f"{new_w}x{new_h}")

    # -----------------------------------------------------------------
    # text rendering
    # -----------------------------------------------------------------
    def _redraw(self, _event=None):
        self.canvas.delete("caption")
        if not self.current_text:
            return

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10 or h < 10:
            return

        cx, cy = w // 2, h // 2

        for dx, dy in OUTLINE_OFFSETS:
            self.canvas.create_text(
                cx + dx, cy + dy,
                text=self.current_text,
                font=_pick_font(),
                fill="black",
                width=w - 20,
                anchor="center",
                tags="caption",
            )

        self.canvas.create_text(
            cx, cy,
            text=self.current_text,
            font=_pick_font(),
            fill="white",
            width=w - 20,
            anchor="center",
            tags="caption",
        )

    # -----------------------------------------------------------------
    # context menu
    # -----------------------------------------------------------------
    def _show_menu(self, event):
        topmost = self.root.attributes("-topmost")
        menu = tk.Menu(self.root, tearoff=0, bg="#222", fg="white",
                       activebackground="#444", activeforeground="white")
        menu.add_command(
            label=f"{'✓' if topmost else '  '} Always on Top",
            command=self._toggle_topmost,
        )
        menu.add_separator()
        menu.add_command(label="Close", command=self._close)
        menu.post(event.x_root, event.y_root)

    def _toggle_topmost(self):
        cur = self.root.attributes("-topmost")
        self.root.attributes("-topmost", not cur)

    # -----------------------------------------------------------------
    # UI update loop
    # -----------------------------------------------------------------
    def _poll_ui(self):
        try:
            while True:
                text = self.caption_queue.get_nowait()
                self.current_text = text
                self._redraw()
        except queue.Empty:
            pass
        if self.running:
            self.root.after(100, self._poll_ui)

    def _close(self):
        self.running = False
        self.root.quit()

    # -----------------------------------------------------------------
    # WebSocket server (runs on daemon thread with its own event loop)
    # -----------------------------------------------------------------
    def _run_server(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._serve())

    async def _handle_client(self, ws):
        self.connected = True
        self.caption_queue.put("")
        async for raw in ws:
            try:
                msg = json.loads(raw)
                if msg.get("type") == "caption":
                    text = msg.get("text", "").strip()
                    if text:
                        self.caption_queue.put(text)
                elif msg.get("type") == "hello":
                    pass
            except json.JSONDecodeError:
                pass
        self.connected = False

    async def _serve(self):
        self.caption_queue.put(
            "Waiting for extension to connect...\n"
            "Load the extension in Chrome and play a YouTube video with CC."
        )
        async with websockets.serve(
            self._handle_client, WS_HOST, WS_PORT,
            ping_interval=None,
        ):
            await asyncio.Future()

    # -----------------------------------------------------------------
    # entry point
    # -----------------------------------------------------------------
    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self._close()


if __name__ == "__main__":
    try:
        app = CaptionOverlay()
        app.run()
    except Exception as e:
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
