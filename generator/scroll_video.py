#!/usr/bin/env python3
"""
"Scroll vs. Post" – Zwei-Zimmer-Vergleich über 365 Tage, ohne Sprecher, ohne Musik
==================================================================================
Gleiches Handy, gleiche 2 Stunden am Tag. Links: im Bett scrollen (und dabei die
Videos des Rechten liken). Rechts: jeden Tag ein Video aufnehmen und posten.

    python3 generator/scroll_video.py skripte/zimmer/10_scroll_vs_post.json
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
from make_video import F_BLACK, F_BOLD, F_SEMI, FPS, H, SR, W, clamp, ease_out_back, ease_out_cubic, env_exp, lowpass, sine_sweep  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import (CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, SHIRT, SKIN, SKY, WIN, WOOD,  # noqa: E402
                          build_base, capsule, circle, paste_scaled, radial, room_overlay, seg, spaced, sprite)
from wecker_video import BED_TOP, CLOCK_X, NS_TOP, draw_bed, draw_clock, draw_nightstand, person_fat  # noqa: E402
from rauchen_video import draw_door, year_calendar  # noqa: E402
import wecker_video  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "videos")

S = 1.2
F0 = FL - 10
BLUE_GLOW = radial(260, (90, 160, 255), 120)
RING_GLOW = radial(220, (255, 245, 220), 110)
HEART = (255, 70, 110)
TRI_X = 400            # Stativ (lokal, rechts)
CREATOR_X = 245
PLAQUES = [(100, "100"), (1000, "1K"), (5000, "5K"), (10000, "10K")]


def fmt_int(v):
    return f"{v:,.0f}"


def draw_heart(d, x, y, r, col=HEART):
    d.ellipse((x - r, y - r * 0.9, x, y + r * 0.1), fill=col)
    d.ellipse((x, y - r * 0.9, x + r, y + r * 0.1), fill=col)
    d.polygon([(x - r * 0.98, y - r * 0.25), (x + r * 0.98, y - r * 0.25), (x, y + r)], fill=col)


def draw_phone_screen(d, x, y, w, h, t, scroll=True, glow=True):
    d.rounded_rectangle((x - w / 2, y - h / 2, x + w / 2, y + h / 2), 6, fill=(22, 22, 30), outline=OUT, width=3)
    sx0, sy0, sx1, sy1 = x - w / 2 + 4, y - h / 2 + 5, x + w / 2 - 4, y + h / 2 - 5
    d.rectangle((sx0, sy0, sx1, sy1), fill=(40, 60, 110) if glow else (30, 30, 40))
    if scroll:
        cols = [(250, 120, 160), (120, 200, 255), (255, 210, 90), (140, 230, 160)]
        bh = (sy1 - sy0) * 0.55
        off = (t * 1.6 % 1) * (bh + 4)
        k = 0
        yy = sy1 - off
        while yy > sy0 - bh:
            top, bot = max(sy0, yy - bh), min(sy1, yy)
            if bot > top:
                d.rectangle((sx0 + 2, top, sx1 - 2, bot), fill=cols[(k + int(t * 1.6)) % 4])
            yy -= bh + 4
            k += 1


def draw_tripod(c, d, x0, light_on, rec_blink, phone_on_tripod):
    x = x0 + TRI_X
    top = F0 - 230
    for dx in (-34, 0, 34):
        d.line([(x, top + 40), (x + dx, F0)], fill=(50, 50, 60), width=6)
    d.line([(x, top + 40), (x, top + 10)], fill=(50, 50, 60), width=8)
    if light_on > 0:
        paste_scaled(c, RING_GLOW, x, top - 10, 1.0, light_on)
        d = ImageDraw.Draw(c)
    d.ellipse((x - 48, top - 58, x + 48, top + 38), outline=(250, 245, 230) if light_on > 0.5 else (120, 120, 130), width=12)
    if phone_on_tripod:
        d.rounded_rectangle((x - 16, top - 36, x + 16, top + 18), 5, fill=(22, 22, 30), outline=OUT, width=3)
        if rec_blink:
            d.ellipse((x - 7, top - 26, x + 7, top - 12), fill=RED)
    return d


def draw_plaque(d, x, y, text_spr, c, pop):
    if pop <= 0.25:
        return
    w, h = 74 * pop, 92 * pop
    d.rectangle((x - w / 2, y - h / 2, x + w / 2, y + h / 2), fill=(40, 34, 28), outline=GOLD, width=4)
    d.rectangle((x - w / 2 + 8, y - h / 2 + 8, x + w / 2 - 8, y + h / 2 - 8), fill=(70, 58, 40))
    paste_scaled(c, text_spr, x, y, pop, 1)


# ----------------------------------------------------------------- stage
class Stage:
    def __init__(self, i, cfg, start, n, data):
        self.i, self.cfg, self.start, self.data = i, cfg, start, data
        self.final = i == n - 1
        self.label = str(cfg["day"])
        self.dur = float(cfg.get("dur", 9.0))
        self.sky = cfg.get("sky", ["JAN", "MAR", "MAY", "JUL", "SEP", "NOV", "DEC"][i % 7])
        self.base = build_base(self.sky, door=True)
        self.dark = room_overlay("L", (0, 0, 10), 40 + i * 10)
        self.warm = room_overlay("R", (255, 190, 110), 4 + i * 6)
        self.h0, self.h1 = cfg["_prev_hours"], cfg["hours"]
        self.f0, self.f1 = cfg["_prev_followers"], cfg["followers"]
        self.zoom = cfg.get("zoom")
        rnd = random.Random(i * 3 + 5)
        self.parts = [(rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(0.6, 1.4)) for _ in range(26)]
        self.likes = [1.3 + k * 1.1 + rnd.uniform(-0.2, 0.2) for k in range(4)]
        self.notif = [5.6 + k * 0.22 for k in range(9)]
        self.t_post = 5.3
        self.t_count = (5.5, 7.5)
        self.new_plaques = [p for p in PLAQUES if self.f0 < p[0] <= self.f1]
        self.ev = []
        self.schedule()

    def sfx(self, t, name, g=1.0):
        if 0 <= t < self.dur:
            self.ev.append((t, name, g))

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        # Links: scrollen
        k = 0.4
        while k < 8.6:
            s(k, "flickup", 0.18)
            k += 0.62
        for tl in self.likes:
            s(tl, "pop", 0.3)
        s(4.0, "yawn", 0.3)
        s(6.0, "swish", 0.3)
        s(6.5, "pop_big", 0.35)
        # Rechts
        s(0.55, "tick", 0.5)
        s(0.6, "lighton", 0.35)
        s(1.1, "beep", 0.35)
        for st in (0.75, 0.95, 3.95, 4.15):
            s(st, "step", 0.25)
        for kk in range(4):
            s(4.35 + kk * 0.22, "tick", 0.3)
        s(self.t_post, "whoosh", 0.45)
        s(self.t_post + 0.05, "beep", 0.3)
        for tn in self.notif:
            s(tn, "notif", 0.32)
        for j, _ in enumerate(self.new_plaques):
            s(7.7 + j * 0.25, "ding", 0.5)
        if self.final:
            s(7.9, "cash", 0.4)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def zoom_at(self, t):
        if not self.zoom:
            return 1.0, (540, 960)
        side, a, b = self.zoom
        z = 1 + 0.32 * smooth((t - a) / 0.5) * (1 - smooth((t - b + 0.5) / 0.5))
        return z, ((300 if side == "L" else 790), 1040)

    def float_text(self, c, text, color, x, y, k, size=40, life=1.0, rise=45):
        if k < 0:
            return
        a = clamp(k * 6) * (1 - smooth((k - life) / 0.4))
        if a > 0:
            paste_scaled(c, sprite(text, size, color), x, y - k * rise, 0.6 + 0.4 * ease_out_back(clamp(k * 4)), a)

    def followers_now(self, t):
        return lerp(self.f0, self.f1, ease_out_cubic(seg(t, *self.t_count)))

    def hours_now(self, t):
        return lerp(self.h0, self.h1, smooth(seg(t, 0.4, 8.0)))

    # ---- draw
    def draw(self, c, t, gt):
        c.alpha_composite(self.base)
        self.draw_window_fx(ImageDraw.Draw(c), gt)
        self.draw_left(c, t)
        c.alpha_composite(self.warm, (ROOMS["R"], CEIL))
        self.draw_right(c, t)
        self.draw_hud(c, t)

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

    def clock_text(self, t):
        mins = 22 * 60 + int(210 * smooth(seg(t, 0.3, 8.6)))
        return f"{(mins // 60) % 24}:{mins % 60:02d}"

    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        draw_door(d, x0)
        draw_nightstand(d, x0)
        # Handy über dem Gesicht
        sway = math.sin(t * 2.2) * 4
        ph = (x0 + 140 + sway, BED_TOP - 112)
        info = draw_bed(d, x0, 0.12, arm_to=(ph[0] + 6, ph[1] + 30))
        c.alpha_composite(self.dark, (ROOMS["L"], CEIL))
        d = ImageDraw.Draw(c)
        # Kopf wach drüberzeichnen (Augen offen, schaut aufs Handy)
        hx, hy, r = info
        circle(d, hx, hy, r, SKIN)
        tired = clamp(self.i / 6)
        for sg in (-1, 1):
            ex, ey = hx + sg * 12 * wecker_video.S - 6, hy - 6
            if 3.9 < t < 4.5:
                d.line([(ex - 5, ey), (ex + 5, ey)], fill=OUT, width=3)
            else:
                d.ellipse((ex - 4.5, ey - 5.5, ex + 4.5, ey + 5.5), fill=OUT)
                if tired > 0.2:  # müde Lider
                    d.rectangle((ex - 6, ey - 7, ex + 6, ey - 7 + 6 * tired), fill=SKIN)
                    d.arc((ex - 7, ey + 2, ex + 7, ey + 12), 20, 160, fill=(150, 140, 160), width=2)
        if 3.9 < t < 4.5:
            d.ellipse((hx - 9, hy + 8, hx + 7, hy + 24), fill=OUT)
        else:
            d.line([(hx - 10, hy + 15), (hx + 6, hy + 15)], fill=OUT, width=3)
        d = draw_clock(c, d, x0 + CLOCK_X + 14, NS_TOP, self.clock_text(t), RED if t > 4.5 else (235, 235, 240), 0, t)
        paste_scaled(c, BLUE_GLOW, ph[0], ph[1] + 60, 1.0, 0.75)
        d = ImageDraw.Draw(c)
        d.line([(x0 + 158, BED_TOP + 2), (ph[0] + 6, ph[1] + 30)], fill=SHIRT, width=int(17 * 1.15))
        circle(d, ph[0] + 6, ph[1] + 30, 10 * 1.15, SKIN, 3)
        draw_phone_screen(d, ph[0], ph[1], 40, 66, t)
        for tl in self.likes:
            k = t - tl
            if 0 < k < 1.0:
                a = 1 - k
                draw_heart(d, ph[0] + 30 + k * 20, ph[1] - 20 - k * 70, 12 + 6 * a)
        if 3.9 < t < 4.6:
            self.float_text(c, "*yawn*", (200, 205, 220), hx - 10, hy - 70, t - 3.95, 32, 0.5)
        # Großes Handy-Fenster: er schaut das Video des Rechten
        pa = ease_out_back(seg(t, 6.0, 6.35)) * (1 - smooth(seg(t, 8.5, 8.85)))
        if pa > 0.02:
            self.draw_watch_panel(c, x0, t, pa, ph)
        self.float_text(c, "+2h", (150, 170, 220), x0 + 360, BED_TOP - 150, t - 0.6, 40, 1.2, 30)

    def draw_watch_panel(self, c, x0, t, pa, ph):
        pw, phh = 230 * pa, 330 * pa
        cx, cy = x0 + 330, CEIL + 270
        img = Image.new("RGBA", (int(230) + 20, int(330) + 20), (0, 0, 0, 0))
        dd = ImageDraw.Draw(img)
        X0, Y0, X1, Y1 = 10, 10, 240, 340
        dd.rounded_rectangle((X0, Y0, X1, Y1), 22, fill=(20, 20, 28), outline=(230, 230, 240), width=5)
        dd.rounded_rectangle((X0 + 10, Y0 + 14, X1 - 10, Y1 - 14), 14, fill=(52, 48, 62))
        # Mini-Ausgabe des Rechten im Video
        person_fat(dd, 118, 300, 0.12, (None, (152, 200)), mood=0.8, look=0.3, s=0.62)
        dd.ellipse((185, 60, 225, 100), outline=(255, 245, 220), width=5)
        paste_scaled(img, sprite(f"{fmt_int(self.followers_now(t))} followers", 22, (240, 240, 250), F_BOLD), 125, 42, 1, 1)
        if t > 6.5:
            k = t - 6.5
            draw_heart(dd, 205, 280 - min(k, 0.8) * 60, 16)
        dd.polygon([(80, 330), (120, 330), (70, 346)], fill=(230, 230, 240))
        spr = img.resize((max(1, int(img.width * pa)), max(1, int(img.height * pa))))
        paste_scaled(c, spr, cx, cy, 1, clamp(pa * 1.5))

    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        draw_door(d, x0)
        # Plaketten an der Wand
        d.line([(x0 + 18, 862), (x0 + 240, 862)], fill=WOOD, width=6)
        for j, (thr, txt) in enumerate(PLAQUES):
            if self.f0 >= thr:
                pop = 1.0
            elif self.f1 >= thr:
                pop = ease_out_back(seg(t, 7.7 + self.new_plaques.index((thr, txt)) * 0.25, 8.0 + self.new_plaques.index((thr, txt)) * 0.25))
            else:
                continue
            draw_plaque(d, x0 + 50 + j * 56, 920, sprite(txt, 26 if len(txt) > 2 else 24, GOLD), c, pop * 0.72)
            d = ImageDraw.Draw(c)
        light = smooth(seg(t, 0.55, 0.7))
        on_tripod = not (4.15 < t < 7.9)
        recording = 1.1 < t < 3.85
        d = draw_tripod(c, d, x0, light, recording and int(t * 3) % 2 == 0, on_tripod)
        fx = x0 + CREATOR_X
        hands, look, mood, mouth_o, walk = [None, None], 1.0, 0.6, False, 0.0
        phone_hand = False
        if 0.7 < t < 1.1:
            look = 0.6
        if recording:
            tt = t - 1.1
            mouth_o = int(tt * 7) % 2 == 0
            g = math.sin(tt * 5)
            hands = [(fx - (30 + 20 * g) * S, F0 - (170 + 25 * g) * S), (fx + (40 - 18 * g) * S, F0 - (180 - 20 * g) * S)]
            mood = 0.8
        if 3.9 < t < 4.2:
            fx = lerp(x0 + CREATOR_X, x0 + 320, smooth(seg(t, 3.9, 4.2)))
            walk = (t - 3.9) * 14
        elif 4.2 <= t < 7.9:
            fx = x0 + 320
            hands = [None, (fx + 26 * S, F0 - 175 * S)]
            phone_hand = True
            look = 0.3
            mood = 0.6 if t < self.t_post else 0.95
        elif t >= 7.9:
            fx = x0 + 320
            if self.final:
                hands = [(fx - 70 * S, F0 - 285 * S), (fx + 70 * S, F0 - 285 * S)]
                mood = 1.0
        info = person_fat(d, fx, F0, 0.12, tuple(hands), walk=walk, mood=mood, look=look, mouth_o=mouth_o, s=S)
        if phone_hand:
            h = info["hands"][1]
            draw_phone_screen(d, h[0] + 4, h[1] - 26, 34, 56, t, scroll=False)
            if t < self.t_post:
                self.float_text(c, "EDITING", (200, 205, 220), fx, info["head"][1] - 95, t - 4.3, 30, 0.8, 10)
            self.float_text(c, "POSTED", GREEN, fx, info["head"][1] - 95, t - self.t_post, 44, 0.8, 30)
            for k, tn in enumerate(self.notif):
                kk = t - tn
                if 0 < kk < 1.1:
                    hx = h[0] + 20 + (k % 3) * 22
                    draw_heart(d, hx, h[1] - 60 - kk * 120, 13)
        if self.f1 > self.f0:
            self.float_text(c, f"+{fmt_int(self.f1 - self.f0)}", GREEN, x0 + 400, F0 - 420, t - 5.6, 50, 1.6, 30)

    def draw_hud(self, c, t):
        fade = 1 - (smooth(seg(t, 7.9, 8.2)) if self.final else 0)
        if fade > 0:
            paste_scaled(c, year_calendar(self.i, self.label, self.cfg["_prev_label"], t, "DAY"), 540, 330, 1, fade)
            paste_scaled(c, sprite(spaced(self.data.get("subtitle", "SAME PHONE · 2 HOURS A DAY")), 28, (170, 170, 186), F_BOLD),
                         540, 466, 1, fade)
        if self.final:
            a1 = ease_out_back(seg(t, 8.3, 8.7))
            a2 = ease_out_back(seg(t, 9.3, 9.7))
            if a1 > 0:
                paste_scaled(c, sprite(self.data["punch1"], 70, (245, 245, 250)), 540, 330, 0.7 + 0.3 * a1, clamp(a1 * 2))
            if a2 > 0:
                paste_scaled(c, sprite(self.data["punch2"], 82, GOLD), 540, 430, 0.7 + 0.3 * a2, clamp(a2 * 2))
        hrs = self.hours_now(t)
        fol = self.followers_now(t)
        for room, label, txt, colr in (("L", "SCROLLED", f"{hrs:,.0f} h", (150, 170, 230)),
                                       ("R", "FOLLOWERS", fmt_int(fol), GREEN if fol > 0 else (235, 235, 240))):
            cxr = ROOMS[room] + RW / 2
            paste_scaled(c, sprite(spaced(label), 30, (150, 150, 166), F_BOLD), cxr, 1414, 1, 1)
            paste_scaled(c, sprite(txt, 72, colr), cxr, 1474, 1, 1)
        if self.data.get("watermark"):
            paste_scaled(c, sprite(self.data["watermark"], 30, (130, 130, 145), F_SEMI), 540, 1534, 1, 0.8)


# ----------------------------------------------------------------- audio
def build_lib4(rng):
    from wecker_video import build_lib2
    lib = build_lib2(rng)
    n = int(0.12 * SR)
    src = rng.normal(0, 1, n)
    tt = np.linspace(0, 1, n)
    lib["flickup"] = (src - lowpass(src, 2500)) * np.sin(np.pi * tt) ** 2 * 0.6
    n = int(0.32 * SR)
    t = np.arange(n) / SR
    nt = np.zeros(n)
    for f0, st in ((1318.5, 0.0), (1975.5, 0.08)):
        i0 = int(st * SR)
        tt = t[: n - i0]
        nt[i0:] += np.sin(2 * np.pi * f0 * tt) * np.exp(-tt / 0.07)
    lib["notif"] = nt * 0.5
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    f = 260 - 120 * (t / t[-1])
    lib["yawn"] = (lowpass(rng.normal(0, 1, n), 900) * 0.6 + np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3) * np.sin(np.pi * t / t[-1]) ** 2 * 0.8
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    lib["lighton"] = (np.sin(2 * np.pi * 120 * t) * 0.3 + rng.normal(0, 0.15, n)) * np.minimum(1, t / 0.02) * np.exp(-t / 0.12)
    return lib


def build_audio(stages, dur, path, seed):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    lib = build_lib4(rng)
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


# ----------------------------------------------------------------- render
def build(data):
    stages, t = [], 0.0
    ph = pf = 0
    prev = None
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_hours"], sc["_prev_followers"], sc["_prev_label"] = ph, pf, prev
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        ph, pf, prev = sc["hours"], sc["followers"], str(sc["day"])
    return stages, t


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


def render(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    name = os.path.splitext(os.path.basename(path))[0]
    seed = sum(map(ord, name))
    stages, dur = build(data)
    nframes = int(round(dur * FPS))
    os.makedirs(OUT_DIR, exist_ok=True)
    wav = os.path.join(OUT_DIR, f".{name}.wav")
    mp4 = os.path.join(OUT_DIR, f"{name}.mp4")
    build_audio(stages, dur, wav, seed)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
           "-movflags", "+faststart", "-t", f"{dur:.3f}", mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    si = 0
    cover_t = stages[-1].start + 10.0
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for p in sys.argv[1:]:
        render(p)
