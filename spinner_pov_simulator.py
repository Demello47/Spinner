#!/usr/bin/env python3
"""
spinner_pov_simulator.py
------------------------
Simple simulator for how spinner images/animations will look before writing them.

Important preview mapping:
- Top row in the source image is shown on the OUTER side of the spinner
- Bottom row is shown closer to the center
"""

import argparse
import math
from pathlib import Path
import tkinter as tk
from tkinter import ttk

try:
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    print("Pillow is not installed.")
    print("Install it with:")
    print("  python.exe -m pip install pillow")
    raise SystemExit(2)

IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
BG = (8, 12, 18)
LED_ON = (0, 220, 255)
LED_GLOW = (0, 120, 160)
GUIDE = (28, 36, 46)

def collect_frames(input_path: Path):
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        raise FileNotFoundError(f"Not found: {input_path}")
    frames = sorted(
        [p for p in input_path.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS],
        key=lambda p: p.name.lower()
    )
    if not frames:
        raise FileNotFoundError(f"No supported images found in: {input_path}")
    return frames

def normalize_frame(path: Path, pad128=True):
    im = Image.open(path).convert("L")
    if im.width == 12 and im.height > 12:
        im = im.transpose(Image.Transpose.ROTATE_90)
    if im.height != 12:
        new_w = max(1, round(im.width * (12 / im.height)))
        im = im.resize((new_w, 12), Image.Resampling.NEAREST)
    im = im.point(lambda p: 0 if p < 128 else 255, mode="1").convert("L")
    if pad128:
        if im.width > 128:
            im = im.crop((0, 0, 128, 12))
        elif im.width < 128:
            padded = Image.new("L", (128, 12), 255)
            padded.paste(im, (0, 0))
            im = padded
    return im

def render_linear_preview(frame_im, scale=6):
    rgb = Image.new("RGB", frame_im.size, BG)
    src = frame_im.load()
    dst = rgb.load()
    for x in range(frame_im.width):
        for y in range(frame_im.height):
            dst[x, y] = LED_ON if src[x, y] == 0 else BG
    return rgb.resize((frame_im.width * scale, frame_im.height * scale), Image.Resampling.NEAREST)

def render_pov(frame_im, canvas_size=520):
    img = Image.new("RGB", (canvas_size, canvas_size), BG)
    draw = ImageDraw.Draw(img)

    cx = canvas_size // 2
    cy = canvas_size // 2
    steps = frame_im.width
    inner_r = 70
    spacing = 15

    for y in range(12):
        r = inner_r + (11 - y) * spacing
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=GUIDE)

    draw.ellipse((cx-42, cy-42, cx+42, cy+42), outline=(80, 90, 105), fill=(18, 22, 28))

    px = frame_im.load()
    for x in range(steps):
        angle = -math.pi/2 + (2 * math.pi * x / steps)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        for y in range(12):
            if px[x, y] == 0:
                # FIX: top rows now map to the outside
                r = inner_r + (11 - y) * spacing
                px_x = cx + r * cos_a
                px_y = cy + r * sin_a

                gr = 5
                draw.ellipse((px_x-gr, px_y-gr, px_x+gr, px_y+gr), fill=LED_GLOW)
                cr = 2
                draw.ellipse((px_x-cr, px_y-cr, px_x+cr, px_y+cr), fill=LED_ON)
    return img

class SimulatorApp:
    def __init__(self, root, frames, fps=8, pad128=True):
        self.root = root
        self.root.title("Spinner POV Simulator")

        self.frame_paths = frames
        self.frames = [normalize_frame(p, pad128=pad128) for p in self.frame_paths]
        self.index = 0
        self.playing = True
        self.fps = max(1, fps)
        self.tk_linear = None
        self.tk_pov = None

        self.build_ui()
        self.update_view()
        self.schedule_next()

        self.root.bind("<space>", self.toggle_play)
        self.root.bind("<Left>", self.prev_frame)
        self.root.bind("<Right>", self.next_frame)
        self.root.bind("<Up>", self.fps_up)
        self.root.bind("<Down>", self.fps_down)

    def build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")
        self.info_var = tk.StringVar()
        ttk.Label(top, textvariable=self.info_var).pack(side="left", padx=(0, 10))
        ttk.Button(top, text="⏯ Play/Pause", command=self.toggle_play).pack(side="left", padx=4)
        ttk.Button(top, text="⏮ Prev", command=self.prev_frame).pack(side="left", padx=4)
        ttk.Button(top, text="⏭ Next", command=self.next_frame).pack(side="left", padx=4)
        ttk.Button(top, text="FPS -", command=self.fps_down).pack(side="left", padx=4)
        ttk.Button(top, text="FPS +", command=self.fps_up).pack(side="left", padx=4)

        main = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        main.pack(fill="both", expand=True)

        left = ttk.LabelFrame(main, text="Source frame")
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))

        right = ttk.LabelFrame(main, text="POV simulation")
        right.pack(side="left", fill="both", expand=True, padx=(5, 0))

        self.linear_label = ttk.Label(left)
        self.linear_label.pack(padx=10, pady=10)

        self.pov_label = ttk.Label(right)
        self.pov_label.pack(padx=10, pady=10)

        ttk.Label(self.root, text="Keys: Space=play/pause, Left/Right=prev/next, Up/Down=FPS +/-").pack(pady=(0, 10))

    def schedule_next(self):
        delay = int(1000 / self.fps)
        self.root.after(delay, self.tick)

    def tick(self):
        if self.playing and len(self.frames) > 1:
            self.index = (self.index + 1) % len(self.frames)
            self.update_view()
        self.schedule_next()

    def update_view(self):
        frame = self.frames[self.index]
        linear = render_linear_preview(frame, scale=6)
        pov = render_pov(frame, canvas_size=520)

        self.tk_linear = ImageTk.PhotoImage(linear)
        self.tk_pov = ImageTk.PhotoImage(pov)

        self.linear_label.configure(image=self.tk_linear)
        self.pov_label.configure(image=self.tk_pov)

        current_name = self.frame_paths[self.index].name
        self.info_var.set(
            f"Frame {self.index + 1}/{len(self.frames)} | FPS: {self.fps} | "
            f"{current_name} | size: {frame.width}x{frame.height}"
        )

    def toggle_play(self, event=None):
        self.playing = not self.playing

    def prev_frame(self, event=None):
        self.playing = False
        self.index = (self.index - 1) % len(self.frames)
        self.update_view()

    def next_frame(self, event=None):
        self.playing = False
        self.index = (self.index + 1) % len(self.frames)
        self.update_view()

    def fps_up(self, event=None):
        self.fps += 1
        self.update_view()

    def fps_down(self, event=None):
        if self.fps > 1:
            self.fps -= 1
        self.update_view()

def main():
    ap = argparse.ArgumentParser(description="Simulate how spinner images/animations will look before writing them to the device.")
    ap.add_argument("--input", required=True, help="Path to one image or a folder of frames")
    ap.add_argument("--fps", type=int, default=8, help="Animation FPS")
    ap.add_argument("--no-pad128", action="store_true", help="Do not pad narrow images to 128 columns")
    args = ap.parse_args()

    input_path = Path(args.input).expanduser()
    frames = collect_frames(input_path)

    root = tk.Tk()
    SimulatorApp(root, frames, fps=args.fps, pad128=(not args.no_pad128))
    root.mainloop()

if __name__ == "__main__":
    main()
