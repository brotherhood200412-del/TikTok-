#!/usr/bin/env python3
"""
Gemeinsame Basis für alle "Zwei Zimmer"-Videos (ohne Sprecher, ohne Musik).
Eine Video-Datei definiert nur noch ihre Stage-Klasse + build()-Funktion.
"""
import json
import math
import os
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import F_BOLD, F_SEMI, FPS, H, SR, W, clamp, ease_out_back, font  # noqa: E402
from figuren_video import smooth  # noqa: E402
from zimmer_video import CEIL, GOLD, ROOMS, RW, SKY, WIN, build_base, paste_scaled, room_overlay, seg, spaced, sprite  # noqa: E402
from rauchen_video import year_calendar  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "videos")
SKIES = ["JAN", "MAR", "MAY", "JUL", "SEP", "NOV", "DEC"]


def fit_sprite(text, size, color, max_w, path=None):
    from make_video import F_BLACK
    path = path or F_BLACK
    while size > 20 and font(path, size).getlength(text) > max_w:
        size -= 2
    return sprite(text, size, color, path)


class StageBase:
    door = False
    warm_room = "R"

    def __init__(self, i, cfg, start, n, data):
        self.i, self.cfg, self.start, self.data = i, cfg, start, data
        self.n = n
        self.final = i == n - 1
        self.dur = float(cfg.get("dur", 9.0))
        self.sky = cfg.get("sky", SKIES[i % len(SKIES)])
        self.base = build_base(self.sky, door=self.door)
        self.warm = room_overlay(self.warm_room, (255, 190, 110), 4 + i * 6) if self.warm_room else None
        self.zoom = cfg.get("zoom")
        rnd = random.Random(i * 7 + 13)
        self.parts = [(rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(0.6, 1.4)) for _ in range(26)]
        self.ev = []
        self.setup()
        self.schedule()

    def setup(self):
        pass

    def schedule(self):
        pass

    def sfx(self, t, name, g=1.0):
        if 0 <= t < self.dur:
            self.ev.append((t, name, g))

    # ---- Kamera
    def zoom_at(self, t):
        if not self.zoom:
            return 1.0, (540, 960)
        side, a, b = self.zoom
        z = 1 + 0.32 * smooth((t - a) / 0.5) * (1 - smooth((t - b + 0.5) / 0.5))
        return z, ((300 if side == "L" else 790), 1040)

    # ---- Helfer
    def float_text(self, c, text, color, x, y, k, size=40, life=1.0, rise=45):
        if k < 0:
            return
        a = clamp(k * 6) * (1 - smooth((k - life) / 0.4))
        if a > 0:
            paste_scaled(c, sprite(text, size, color), x, y - k * rise, 0.6 + 0.4 * ease_out_back(clamp(k * 4)), a)

    def draw_window_fx(self, d, gt):
        sty = SKY[self.sky][2]
        for room in ("L", "R"):
            x0 = ROOMS[room]
            wx0, wy0, wx1, wy1 = x0 + WIN[0] + 6, WIN[1] + 6, x0 + WIN[2] - 6, WIN[3] - 6
            for u, v, sp in self.parts:
                if sty == "snow":
                    x = wx0 + ((u + 0.03 * math.sin(gt * sp * 2)) % 1) * (wx1 - wx0)
                    y = wy0 + ((v + gt * 0.12 * sp) % 1) * (wy1 - wy0)
                    d.ellipse((x - 2.5, y - 2.5, x + 2.5, y + 2.5), fill=(240, 245, 255))
                elif sty == "rain":
                    x = wx0 + u * (wx1 - wx0)
                    y = wy0 + ((v + gt * 0.9 * sp) % 1) * (wy1 - wy0 - 12)
                    d.line([(x, y), (x - 2, y + 11)], fill=(170, 190, 220), width=2)
                elif sty == "leaves":
                    x = wx0 + ((u + gt * 0.05 * sp) % 1) * (wx1 - wx0)
                    y = wy0 + ((v + gt * 0.1 * sp) % 1) * (wy1 - wy0)
                    d.ellipse((x - 4, y - 2.5, x + 4, y + 2.5), fill=(230, 130, 50))
                elif v < 0.55:
                    b = int(150 + 100 * math.sin(gt * sp * 3 + u * 9))
                    x, y = wx0 + u * (wx1 - wx0), wy0 + v * 0.6 * (wy1 - wy0)
                    d.ellipse((x - 1.6, y - 1.6, x + 1.6, y + 1.6), fill=(b, b, min(255, b + 20)))

    def draw_calendar(self, c, t, header, label, prev_label, subtitle, fade_at=7.9):
        fade = 1 - (smooth(seg(t, fade_at, fade_at + 0.3)) if self.final else 0)
        if fade > 0:
            paste_scaled(c, year_calendar(self.i, label, prev_label or label, t, header), 540, 330, 1, fade)
            paste_scaled(c, sprite(spaced(subtitle), 28, (170, 170, 186), F_BOLD), 540, 466, 1, fade)

    def draw_punch(self, c, t, p1, p2, t1=8.3, t2=9.3, s1=66, s2=74):
        a1 = ease_out_back(seg(t, t1, t1 + 0.4))
        a2 = ease_out_back(seg(t, t2, t2 + 0.4))
        if a1 > 0:
            paste_scaled(c, fit_sprite(p1, s1, (245, 245, 250), 1000), 540, 330, 0.7 + 0.3 * a1, clamp(a1 * 2))
        if a2 > 0:
            paste_scaled(c, fit_sprite(p2, s2, GOLD, 1000), 540, 428, 0.7 + 0.3 * a2, clamp(a2 * 2))

    def draw_counter(self, c, room, label, text, color, bump=1.0, shake=0.0):
        cxr = ROOMS[room] + RW / 2
        paste_scaled(c, sprite(spaced(label), 28, (150, 150, 166), F_BOLD), cxr, 1414, 1, 1)
        paste_scaled(c, fit_sprite(text, 72, color, RW - 30), cxr + shake, 1474, bump, 1)

    def draw_watermark(self, c):
        if self.data.get("watermark"):
            paste_scaled(c, sprite(self.data["watermark"], 30, (130, 130, 145), F_SEMI), 540, 1534, 1, 0.8)

    def compose(self, c, t, gt):
        """Standard-Reihenfolge; Unterklassen implementieren draw_left/draw_right/draw_hud."""
        c.alpha_composite(self.base)
        self.draw_window_fx(ImageDraw.Draw(c), gt)
        self.draw_left(c, t)
        self.after_left(c, t)
        if self.warm is not None:
            c.alpha_composite(self.warm, (ROOMS[self.warm_room], CEIL))
        self.draw_right(c, t)
        self.draw_hud(c, t)
        self.draw_watermark(c)

    def after_left(self, c, t):
        pass

    def draw(self, c, t, gt):
        self.compose(c, t, gt)


# ----------------------------------------------------------------- Audio + Render
def mix_audio(stages, dur, path, lib):
    n = int(dur * SR)
    fx = np.zeros(n)
    for st in stages:
        for t, name, g in st.ev:
            i = int((st.start + t) * SR)
            sig = lib[name]
            j = min(n, i + len(sig))
            if 0 <= i < n:
                fx[i:j] += sig[: j - i] * g
    fx = np.tanh(fx * 1.2) / np.tanh(1.2)
    fx = fx / max(1e-6, np.max(np.abs(fx))) * 0.7
    fo = int(0.6 * SR)
    fx[-fo:] *= np.linspace(1, 0, fo)
    pcm = (fx * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(np.stack([pcm, pcm], axis=1).tobytes())


def render_frame(stages, si, gt, dur):
    st = stages[si]
    lt = gt - st.start
    c = Image.new("RGBA", (W, H))
    st.draw(c, lt, gt)
    z, (cx, cy) = st.zoom_at(lt)
    rgb = c.convert("RGB")
    if z > 1.001:
        cw, ch = W / z, H / z
        x0 = clamp(cx - cw / 2, 0, W - cw)
        y0 = clamp(cy - ch / 2, 0, H - ch)
        rgb = rgb.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
    arr = np.asarray(rgb, np.float32)
    fade = smooth(gt / 0.3) * smooth((dur - gt) / 0.6)
    return (arr * fade).astype(np.uint8)


def run(path, build_fn, lib_fn, cover_offset=10.0):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    name = os.path.splitext(os.path.basename(path))[0]
    seed = sum(map(ord, name))
    stages, dur = build_fn(data)
    nframes = int(round(dur * FPS))
    os.makedirs(OUT_DIR, exist_ok=True)
    wav = os.path.join(OUT_DIR, f".{name}.wav")
    mp4 = os.path.join(OUT_DIR, f"{name}.mp4")
    mix_audio(stages, dur, wav, lib_fn(np.random.default_rng(seed)))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
           "-movflags", "+faststart", "-t", f"{dur:.3f}", mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    si = 0
    cover_t = stages[-1].start + cover_offset
    for fi in range(nframes):
        gt = fi / FPS
        while si < len(stages) - 1 and gt >= stages[si].start + stages[si].dur:
            si += 1
        arr = render_frame(stages, si, gt, dur)
        if abs(gt - cover_t) < 0.5 / FPS:
            Image.fromarray(arr).save(os.path.join(OUT_DIR, f"{name}_cover.png"))
        proc.stdin.write(arr.tobytes())
        if fi % 300 == 0:
            print(f"[{name}] {fi}/{nframes}", flush=True)
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    with open(os.path.join(OUT_DIR, f"{name}_caption.txt"), "w", encoding="utf-8") as f:
        f.write(data.get("caption", "") + "\n")
    print(f"[{name}] fertig: {mp4} ({dur:.1f} s)", flush=True)
