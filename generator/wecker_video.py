#!/usr/bin/env python3
"""
"Alarm 6:00" – Zwei-Zimmer-Vergleich (Snooze vs. Training), ohne Sprecher, ohne Musik
=====================================================================================
Beide starten übergewichtig. Links: Snooze, Snacks, Handy. Rechts: aufstehen,
trainieren, gesund essen – und er wird Monat für Monat schlanker.

    python3 generator/wecker_video.py skripte/zimmer/08_alarm_6am.json
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
from zimmer_video import (CEIL, FL, GOLD, GREEN, OUT, PANTS, RED, ROOMS, RW, SHELF, SHIRT, SKIN, WOOD,  # noqa: E402
                          build_base, build_lib, capsule, circle, draw_phone, paste_scaled, room_overlay, seg,
                          spaced, sprite)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "videos")

S = 1.15
F0 = FL - 10
BED_X0, BED_X1 = 14, 222
BED_TOP = F0 - 92
NS_X0, NS_X1, NS_TOP = 228, 282, F0 - 84
CLOCK_X = 255
SPOT = 372
SCALE_X = 405
WAKE_X = 318
BLANKET = (86, 132, 214)


# ----------------------------------------------------------------- figure (mit Körperfülle)
def person_fat(d, x, fy, fat=0.0, hands=(None, None), walk=0.0, stance=0.0, mood=0.0, look=0.0,
               head_drop=0.0, bob=0.0, s=S):
    leg = 84 * s
    hipy = fy - leg - 8 * s - bob
    lw = (22 + 12 * fat) * s
    spread = (14 + 12 * fat) * s + stance * s
    sw = math.sin(walk) * 18 * s
    for sg, fx in ((-1, x - spread + sw), (1, x + spread - sw)):
        capsule(d, (x + sg * spread * 0.45, hipy), (fx, fy - 10 * s - bob * 0.2), lw, PANTS)
        d.ellipse((fx - 15 * s, fy - 16 * s - bob * 0.2, fx + (15 + look * 6) * s, fy + 1 - bob * 0.2), fill=OUT)
    tw = (62 + 54 * fat) * s
    neck = (x, hipy - 92 * s)
    capsule(d, (x, hipy - 14 * s - 6 * fat * s), neck, tw, SHIRT)
    if fat > 0.3:  # Bauch-Linie
        d.arc((x - tw * 0.34, hipy - 70 * s, x + tw * 0.34, hipy - 8 * s), 20, 160, fill=(58, 90, 200), width=3)
    sh_y = hipy - 78 * s
    sh_off = (24 + 22 * fat) * s
    aw = (17 + 8 * fat) * s
    hand_pts = []
    for side, h in zip((-1, 1), hands):
        sp = (x + side * sh_off, sh_y)
        if h is None:
            h = (sp[0] + side * (12 + 14 * fat) * s, sp[1] + 82 * s)
        capsule(d, sp, h, aw, SHIRT)
        hand_pts.append(h)
    r = (37 + 4 * fat) * s
    hc = (x + (look * 4 + head_drop * look * 8) * s, neck[1] - (36 + 6 * fat) * s + head_drop * 14 * s)
    circle(d, hc[0], hc[1], r, SKIN)
    if fat > 0.4:  # Pausbacken
        for sg in (-1, 1):
            d.ellipse((hc[0] + sg * r * 0.55 - 7 * s, hc[1] + 6 * s, hc[0] + sg * r * 0.55 + 7 * s, hc[1] + 16 * s),
                      fill=(250, 200, 200))
    ex, ey = look * 7 * s, hc[1] + (-4 + head_drop * 6) * s
    for sg in (-1, 1):
        d.ellipse((hc[0] + ex + (sg * 12 - 4.5) * s, ey - 5.5 * s, hc[0] + ex + (sg * 12 + 4.5) * s, ey + 5.5 * s), fill=OUT)
    mx, my = hc[0] + ex * 0.8, hc[1] + (16 + head_drop * 4) * s
    lwid = max(3, int(4 * s))
    if mood > 0.25:
        d.arc((mx - 13 * s, my - 12 * s, mx + 13 * s, my + 8 * s), 20, 160, fill=OUT, width=lwid)
    elif mood < -0.25:
        d.arc((mx - 11 * s, my - 2 * s, mx + 11 * s, my + 14 * s), 205, 335, fill=OUT, width=lwid)
    else:
        d.line((mx - 9 * s, my + s, mx + 9 * s, my + s), fill=OUT, width=lwid)
    for h in hand_pts:
        circle(d, h[0], h[1], 10 * s, SKIN, 3)
    return dict(head=hc, hands=hand_pts, r=r)


# ----------------------------------------------------------------- props
def draw_bed(d, x0, sleeper_fat=None, arm_to=None, blanket_flat=False):
    d.rectangle((x0 + BED_X1 - 14, F0 - 170, x0 + BED_X1, F0), fill=WOOD, outline=OUT, width=4)
    d.rectangle((x0 + BED_X0, BED_TOP + 24, x0 + BED_X1 - 14, F0 - 18), fill=WOOD, outline=OUT, width=4)
    for lx in (BED_X0 + 6, BED_X1 - 30):
        d.rectangle((x0 + lx, F0 - 18, x0 + lx + 12, F0), fill=(70, 50, 38), outline=OUT, width=2)
    d.rounded_rectangle((x0 + BED_X0 + 2, BED_TOP, x0 + BED_X1 - 14, BED_TOP + 28), 8, fill=(232, 236, 245), outline=OUT, width=4)
    d.ellipse((x0 + 150, BED_TOP - 22, x0 + 206, BED_TOP + 8), fill=(250, 250, 255), outline=OUT, width=4)
    info = None
    if sleeper_fat is not None:
        r = (33 + 4 * sleeper_fat) * S
        hx, hy = x0 + 176, BED_TOP - 22
        circle(d, hx, hy, r, SKIN)
        for sg in (-1, 1):
            d.arc((hx + sg * 12 * S - 7, hy - 6, hx + sg * 12 * S + 7, hy + 6), 20, 160, fill=OUT, width=3)
        d.ellipse((hx - 5, hy + 12, hx + 5, hy + 20), fill=OUT)
        info = (hx, hy, r)
    bulge = 12 if (blanket_flat or sleeper_fat is None) else (30 + 48 * sleeper_fat) * S
    pts = []
    for i in range(21):
        u = i / 20
        pts.append((x0 + BED_X0 + 4 + u * 148, BED_TOP + 14 - bulge * math.sin(math.pi * u) ** 0.8))
    pts += [(x0 + BED_X0 + 152, BED_TOP + 34), (x0 + BED_X0 + 4, BED_TOP + 34)]
    d.polygon(pts, fill=BLANKET, outline=OUT)
    if arm_to is not None and sleeper_fat is not None:
        st = (x0 + 158, BED_TOP + 2)
        capsule(d, st, arm_to, (17 + 8 * sleeper_fat) * S, SHIRT)
        circle(d, arm_to[0], arm_to[1], 10 * S, SKIN, 3)
    return info


def draw_nightstand(d, x0):
    d.rectangle((x0 + NS_X0, NS_TOP, x0 + NS_X1, F0), fill=(110, 82, 62), outline=OUT, width=4)
    d.line([(x0 + NS_X0 + 6, NS_TOP + 40), (x0 + NS_X1 - 6, NS_TOP + 40)], fill=OUT, width=3)
    d.ellipse((x0 + (NS_X0 + NS_X1) / 2 - 4, NS_TOP + 18, x0 + (NS_X0 + NS_X1) / 2 + 4, NS_TOP + 26), fill=GOLD)


def draw_clock(c, d, x, y, text, color, ring=0.0, t=0.0):
    sx = math.sin(t * 90) * 4 * ring
    d.rounded_rectangle((x - 38 + sx, y - 46, x + 38 + sx, y), 8, fill=(26, 26, 34), outline=OUT, width=4)
    paste_scaled(c, sprite(text, 30, color), x + sx, y - 23, 1, 1)
    if ring > 0:
        d = ImageDraw.Draw(c)
        for sg in (-1, 1):
            for k in range(2):
                rr = 16 + k * 12
                d.arc((x + sg * 46 - rr + sx, y - 23 - rr, x + sg * 46 + rr + sx, y - 23 + rr),
                      -50 if sg > 0 else 130, 50 if sg > 0 else 230, fill=(255, 230, 120), width=4)
    return d


def draw_scale(d, x, display=None):
    d.rounded_rectangle((x - 50, F0 - 16, x + 50, F0), 6, fill=(225, 228, 236), outline=OUT, width=4)
    d.rectangle((x - 16, F0 - 13, x + 16, F0 - 5), fill=(40, 40, 50))


def draw_food(d, kind, x, y):
    if kind == "donut":
        d.ellipse((x - 22, y - 22, x + 22, y + 22), fill=(205, 140, 80), outline=OUT, width=3)
        d.ellipse((x - 19, y - 19, x + 19, y + 12), fill=(250, 130, 190))
        d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(66, 62, 72), outline=OUT, width=2)
    elif kind == "pizza":
        d.polygon([(x - 26, y - 20), (x + 26, y - 20), (x, y + 28)], fill=(250, 200, 90), outline=OUT)
        d.rectangle((x - 28, y - 26, x + 28, y - 18), fill=(200, 130, 60), outline=OUT)
        for px, py in ((-8, -8), (8, -6), (0, 8)):
            d.ellipse((x + px - 5, y + py - 5, x + px + 5, y + py + 5), fill=(210, 60, 60))
    elif kind == "burger":
        d.chord((x - 26, y - 26, x + 26, y + 4), 180, 360, fill=(220, 150, 70), outline=OUT, width=3)
        d.rectangle((x - 26, y - 11, x + 26, y - 3), fill=(110, 200, 90))
        d.rectangle((x - 26, y - 3, x + 26, y + 7), fill=(120, 70, 40), outline=OUT)
        d.rounded_rectangle((x - 26, y + 7, x + 26, y + 17), 5, fill=(220, 150, 70), outline=OUT, width=3)
    elif kind == "chips":
        d.polygon([(x - 22, y - 30), (x + 22, y - 30), (x + 18, y + 26), (x - 18, y + 26)], fill=(230, 60, 70), outline=OUT)
        d.ellipse((x - 10, y - 10, x + 10, y + 8), fill=(255, 210, 80))
    elif kind == "soda":
        d.rounded_rectangle((x - 15, y - 28, x + 15, y + 28), 6, fill=(220, 40, 50), outline=OUT, width=3)
        d.rectangle((x - 15, y - 4, x + 15, y + 6), fill=(250, 250, 250))
    elif kind == "water":
        d.rounded_rectangle((x - 13, y - 30, x + 13, y + 30), 6, fill=(120, 200, 255), outline=OUT, width=3)
        d.rectangle((x - 7, y - 40, x + 7, y - 30), fill=(60, 120, 230), outline=OUT, width=2)
    elif kind == "salad":
        d.chord((x - 30, y - 22, x + 30, y + 26), 0, 180, fill=(240, 240, 245), outline=OUT, width=3)
        for px in (-16, -4, 8, 18):
            d.ellipse((x + px - 10, y - 8, x + px + 10, y + 8), fill=GREEN if px % 8 else (240, 90, 80), outline=OUT, width=2)
    elif kind == "apple":
        d.ellipse((x - 20, y - 18, x + 20, y + 20), fill=(230, 60, 70), outline=OUT, width=3)
        d.line([(x, y - 18), (x + 4, y - 30)], fill=(90, 60, 40), width=4)
        d.ellipse((x + 4, y - 30, x + 18, y - 22), fill=GREEN)


def draw_dumbbell(d, x, y):
    d.line([(x - 22, y), (x + 22, y)], fill=(60, 60, 70), width=6)
    for sg in (-1, 1):
        d.rounded_rectangle((x + sg * 22 - 7, y - 15, x + sg * 22 + 7, y + 15), 3, fill=(40, 40, 50), outline=OUT, width=2)


def draw_medal(d, x, y):
    d.polygon([(x - 10, y - 30), (x - 2, y - 30), (x + 4, y - 8), (x - 4, y - 8)], fill=(220, 60, 70))
    d.polygon([(x + 10, y - 30), (x + 2, y - 30), (x - 4, y - 8), (x + 4, y - 8)], fill=(70, 120, 230))
    d.ellipse((x - 13, y - 12, x + 13, y + 14), fill=GOLD, outline=OUT, width=3)


def draw_trash(d, x0, n):
    """Snack-Müll vor dem Bett (wächst jeden Monat)."""
    rnd = random.Random(4)
    for k in range(n):
        x = x0 + 30 + rnd.uniform(0, 170)
        kind = rnd.choice(["can", "bag", "box"])
        if kind == "can":
            d.rounded_rectangle((x - 9, F0 - 30, x + 9, F0), 4, fill=(220, 40, 50), outline=OUT, width=2)
        elif kind == "bag":
            d.polygon([(x - 14, F0 - 22), (x + 16, F0 - 26), (x + 14, F0), (x - 14, F0)], fill=(240, 180, 60), outline=OUT)
        else:
            d.rectangle((x - 26, F0 - 12, x + 26, F0), fill=(196, 150, 96), outline=OUT, width=2)


def draw_mat(d, x0):
    d.rounded_rectangle((x0 + 300, F0 - 6, x0 + 470, F0 + 2), 3, fill=(80, 190, 130), outline=OUT, width=2)


def calendar_sprite(i, month, prev_month, t):
    w, h = 300, 230
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 30, 30, 270, 200
    d.rounded_rectangle((x0, y0, x1, y1), 16, fill=(244, 241, 234), outline=OUT, width=5)
    d.rounded_rectangle((x0, y0, x1, y0 + 46), 16, fill=(205, 62, 76), outline=OUT, width=5)
    d.rectangle((x0 + 4, y0 + 28, x1 - 4, y0 + 44), fill=(205, 62, 76))
    for ox in (-70, 70):
        d.rounded_rectangle((150 + ox - 8, y0 - 18, 150 + ox + 8, y0 + 18), 6, fill=(200, 200, 210), outline=OUT, width=3)
    pop = ease_out_back(seg(t, 0.0, 0.35)) if i == 0 else 1
    paste_scaled(img, sprite(month, 92, (32, 32, 40)), 150, (y0 + 46 + y1) / 2 + 4, pop, 1)
    if i > 0 and t < 0.6:
        k = smooth(t / 0.55)
        hgt = (y1 - y0 - 46) * (1 - k)
        top = y0 + 46
        if hgt > 2:
            d = ImageDraw.Draw(img)
            d.rectangle((x0 + 4, top, x1 - 4, top + hgt), fill=(250, 248, 242), outline=(180, 175, 165), width=2)
            spr = sprite(prev_month, 92, (32, 32, 40))
            sp = spr.resize((spr.width, max(1, int(spr.height * max(0.05, 1 - k)))))
            paste_scaled(img, sp, 150, top + hgt / 2, 1, 1 - k)
    return img


# ----------------------------------------------------------------- stage
WORKOUTS = ["jacks", "dumbbell", "run"]
JUNK = ["donut", "pizza", "burger", "chips", "soda", "donut", "pizza"]
HEALTHY = ["water", "salad", "apple", "water", "salad", "apple", "water"]


class Stage:
    def __init__(self, i, cfg, start, n, data):
        self.i, self.cfg, self.start = i, cfg, start
        self.final = i == n - 1
        self.m = cfg["month"]
        self.dur = float(cfg.get("dur", 9.0))
        self.data = data
        self.base = build_base(self.m, door=False)
        self.dark = room_overlay("L", (0, 0, 0), 10 + i * 13)
        self.warm = room_overlay("R", (255, 190, 110), 4 + i * 6)
        self.wL0, self.wL1 = cfg["_prevL"], cfg["left"]
        self.wR0, self.wR1 = cfg["_prevR"], cfg["right"]
        self.start_w = data["start_weight"]
        self.goal_w = data["goal_weight"]
        self.workout = cfg.get("workout", WORKOUTS[i % 3])
        self.junk = cfg.get("junk", JUNK[i % len(JUNK)])
        self.healthy = cfg.get("healthy", HEALTHY[i % len(HEALTHY)])
        self.zoom = cfg.get("zoom")
        rnd = random.Random(i * 7 + 3)
        self.parts = [(rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(0.6, 1.4)) for _ in range(26)]
        self.ev = []
        self.t_weigh = 7.7
        self.schedule()

    def sfx(self, t, name, g=1.0):
        if 0 <= t < self.dur:
            self.ev.append((t, name, g))

    def schedule(self):
        s = self.sfx
        if self.i > 0:
            s(0.05, "page", 0.5)
        else:
            s(0.1, "pop_big", 0.35)
        s(0.45, "alarm", 0.6)
        s(1.25, "tick", 0.5)            # rechts: Wecker aus
        s(1.38, "tick", 0.5)            # links: Snooze
        s(1.4, "pop", 0.3)
        s(1.5, "swish", 0.45)           # rechts springt auf
        s(1.0, "snore", 0.25)
        s(2.7, "alarm", 0.4)
        s(3.05, "tick", 0.5)
        s(3.1, "pop", 0.3)
        s(3.3, "snore", 0.22)
        s(4.35, "alarm", 0.35)
        s(4.45, "swish", 0.45)          # links springt auf (zu spät)
        s(4.5, "pop_big", 0.35)
        for st in (1.65, 1.85, 4.6, 4.8, 7.05, 7.25):
            s(st, "step", 0.3)
        # Training rechts
        if self.workout == "jacks":
            for k in range(9):
                s(2.15 + k * 0.31, "swish", 0.28)
        elif self.workout == "dumbbell":
            for k in range(6):
                s(2.3 + k * 0.45, "clank", 0.35)
        else:
            for k in range(14):
                s(2.15 + k * 0.2, "step", 0.25)
        # Essen
        for k in range(4):
            s(5.25 + k * 0.5, "crunch", 0.4)
        for k in range(2):
            s(5.45 + k * 0.6, "glug" if self.healthy == "water" else "crunch", 0.3)
        s(self.t_weigh - 0.3, "beep", 0.3)
        s(self.t_weigh, "ding", 0.5)
        if self.wL1 > self.wL0:
            s(self.t_weigh + 0.1, "fail", 0.28)
        if self.final:
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    # ---- helpers
    def fat_R(self, t):
        w = lerp(self.wR0, self.wR1, smooth(seg(t, 2.0, 7.6)))
        return clamp((w - self.goal_w) / (self.start_w - self.goal_w)) * 0.95 + 0.05

    def fat_L(self, t):
        w = lerp(self.wL0, self.wL1, smooth(seg(t, 4.5, 7.6)))
        return 1.0 + clamp((w - self.start_w) / 10) * 0.15

    def zoom_at(self, t):
        if not self.zoom:
            return 1.0, (540, 960)
        side, a, b = self.zoom
        z = 1 + 0.32 * smooth((t - a) / 0.5) * (1 - smooth((t - b + 0.5) / 0.5))
        return z, ((300 if side == "L" else 790), 1060)

    def float_text(self, c, text, color, x, y, k, size=40, life=1.0):
        if k < 0:
            return
        a = clamp(k * 6) * (1 - smooth((k - life) / 0.4))
        if a > 0:
            paste_scaled(c, sprite(text, size, color), x, y - k * 45, 0.6 + 0.4 * ease_out_back(clamp(k * 4)), a)

    def zzz(self, c, x, y, t, t0, t1):
        if not (t0 < t < t1):
            return
        for k in range(3):
            ph = ((t - t0) * 0.8 + k / 3) % 1
            a = math.sin(math.pi * ph)
            paste_scaled(c, sprite("z", int(26 + 10 * k), (200, 210, 255)), x + 20 + ph * 40 + k * 8, y - 30 - ph * 80, 1, a)

    # ---- draw
    def draw(self, c, t, gt):
        c.alpha_composite(self.base)
        self.draw_window_fx(ImageDraw.Draw(c), gt)
        self.draw_room(c, t, "L")
        c.alpha_composite(self.dark, (ROOMS["L"], CEIL))
        c.alpha_composite(self.warm, (ROOMS["R"], CEIL))
        self.draw_room(c, t, "R")
        self.draw_hud(c, t)

    def draw_window_fx(self, d, gt):
        from zimmer_video import SKY, WIN
        sty = SKY[self.m][2]
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

    def draw_room(self, c, t, room):
        d = ImageDraw.Draw(c)
        x0 = ROOMS[room]
        L = room == "L"
        # Einrichtung
        if L:
            draw_trash(d, x0, self.i * 2 + (1 if t > 6.9 else 0))
        else:
            draw_mat(d, x0)
            d.line([(x0 + 22, 872), (x0 + 220, 872)], fill=WOOD, width=6)
            n_med = self.i + (1 if t > self.t_weigh else 0)
            for k in range(min(n_med, 7)):
                draw_medal(d, x0 + 38 + k * 27, 905)
            draw_dumbbell(d, x0 + 330, F0 - 15) if self.workout != "dumbbell" or t < 2.0 or t > 5.0 else None
        draw_nightstand(d, x0)
        draw_scale(d, x0 + SCALE_X)
        # Wecker
        if L:
            if t < 1.38:
                txt, col, ring = "6:00", RED, 1.0 if 0.45 < t < 1.38 else 0
            elif t < 4.3:
                txt, col, ring = "6:09", RED, 1.0 if 2.7 < t < 3.05 else 0
            else:
                txt, col, ring = "8:47", RED, 1.0 if 4.3 < t < 4.6 else 0
                if 4.6 < t < 6.0 and int(t * 4) % 2 == 0:
                    txt = "8:47"
        else:
            txt, col, ring = "6:00", GREEN, 1.0 if 0.45 < t < 1.25 else 0
        d = draw_clock(c, d, x0 + CLOCK_X, NS_TOP, txt, col, ring, t)
        # Schlaf / Aufstehen
        wake = 4.45 if L else 1.5
        fat = self.fat_L(t) if L else self.fat_R(t)
        if t < wake:
            arm = None
            if L:
                if 1.1 < t < 1.6:
                    arm = (x0 + CLOCK_X - 10, NS_TOP - 30)
                if 2.85 < t < 3.3:
                    arm = (x0 + CLOCK_X - 10, NS_TOP - 30)
            elif 1.05 < t < 1.45:
                arm = (x0 + CLOCK_X - 10, NS_TOP - 30)
            info = draw_bed(d, x0, fat, arm)
            if L:
                self.zzz(c, info[0], info[1], t, 1.6, 2.7)
                self.zzz(c, info[0], info[1], t, 3.3, 4.3)
                self.float_text(c, "SNOOZE", RED, x0 + CLOCK_X, NS_TOP - 80, t - 1.4, 36, 0.8)
                self.float_text(c, "SNOOZE", RED, x0 + CLOCK_X, NS_TOP - 80, t - 3.1, 36, 0.8)
            else:
                self.zzz(c, info[0], info[1], t, 0.0, 0.45)
            if L:
                self.zzz(c, info[0], info[1], t, 0.0, 0.45)
            return
        draw_bed(d, x0, None, blanket_flat=True)
        d = ImageDraw.Draw(c)
        p_pop = ease_out_back(seg(t, wake, wake + 0.3))
        if L:
            self.draw_left_awake(c, d, x0, t, fat, p_pop)
        else:
            self.draw_right_awake(c, d, x0, t, fat, p_pop)

    def weigh_pos(self, x0, t, from_x):
        k = smooth(seg(t, 7.0, 7.4))
        return lerp(from_x, x0 + SCALE_X, k), (t > 7.0 and t < 7.4), k

    def draw_left_awake(self, c, d, x0, t, fat, p_pop):
        fx = lerp(x0 + WAKE_X, x0 + SPOT, smooth(seg(t, 4.5, 4.9)))
        walk = (t - 4.5) * 14 if 4.5 < t < 4.9 else 0
        hands, look, mood, head_drop, fy = [None, None], 0.0, -0.3, 0.0, F0
        food = None
        if 5.0 < t < 6.95:
            ph = (t - 5.0) % 0.5 / 0.5
            up = math.sin(math.pi * ph) ** 2
            look = 0.2
            mood = 0.4
            food = True
            hands[1] = (fx + lerp(60, 22, up) * S, F0 - lerp(150, 225, up) * S)
            hands[0] = (fx - 52 * S, F0 - 175 * S)
        if t >= 7.0:
            fx, walking, k = self.weigh_pos(x0, t, x0 + SPOT)
            walk = (t - 7.0) * 14 if walking else 0
            fy = F0 - 14 * smooth(seg(t, 7.3, 7.45))
            mood = -0.8 if t > self.t_weigh else -0.2
            head_drop = smooth(seg(t, self.t_weigh + 0.2, self.t_weigh + 0.8)) * 0.8
        info = person_fat(d, fx, fy, fat, tuple(hands), walk=walk, mood=mood, look=look, head_drop=head_drop,
                          s=S * (0.85 + 0.15 * p_pop))
        if 4.45 < t < 5.2:
            self.float_text(c, "!", RED, fx + 50, info["head"][1] - 70, t - 4.45, 60, 0.5)
        if food:
            h = info["hands"][1]
            draw_food(d, self.junk, h[0] + 6, h[1] - 18)
            h0 = info["hands"][0]
            draw_phone(d, h0[0], h0[1] - 22, S)
        if t > self.t_weigh:
            self.weight_bubble(c, info, self.wL1, RED if self.wL1 > self.start_w else (235, 235, 240), t)

    def draw_right_awake(self, c, d, x0, t, fat, p_pop):
        fx = lerp(x0 + WAKE_X, x0 + SPOT, smooth(seg(t, 1.6, 2.0)))
        walk = (t - 1.6) * 14 if 1.6 < t < 2.0 else 0
        hands, look, mood, stance, bob, fy = [None, None], 0.0, 0.6, 0.0, 0.0, F0
        dumb = False
        sweat = False
        if 2.1 < t < 5.0:
            sweat = True
            tt = t - 2.1
            if self.workout == "jacks":
                up = 0.5 - 0.5 * math.cos(tt * 2 * math.pi / 0.62)
                hands = [(fx - (40 + 55 * up) * S, F0 - (130 + 140 * up) * S), (fx + (40 + 55 * up) * S, F0 - (130 + 140 * up) * S)]
                stance = 28 * up
                bob = 14 * math.sin(math.pi * up)
            elif self.workout == "dumbbell":
                up = 0.5 - 0.5 * math.cos(tt * 2 * math.pi / 0.9)
                hands = [(fx - 46 * S, F0 - lerp(110, 200, up) * S), (fx + 46 * S, F0 - lerp(110, 200, up) * S)]
                dumb = True
            else:
                walk = tt * 16
                bob = abs(math.sin(tt * 16)) * 12
                hands = [(fx - (38 + 14 * math.sin(tt * 16)) * S, F0 - 150 * S), (fx + (38 - 14 * math.sin(tt * 16)) * S, F0 - 150 * S)]
            mood = 0.5
        food = False
        if 5.1 < t < 6.7:
            ph = (t - 5.1) % 0.6 / 0.6
            up = math.sin(math.pi * ph) ** 2
            food = True
            hands = [None, (fx + lerp(60, 22, up) * S, F0 - lerp(150, 225, up) * S)]
            mood = 0.7
        if t >= 7.0:
            fx, walking, k = self.weigh_pos(x0, t, x0 + SPOT)
            walk = (t - 7.0) * 14 if walking else 0
            fy = F0 - 14 * smooth(seg(t, 7.3, 7.45))
            mood = 0.9 if t > self.t_weigh else 0.5
            if self.final and t > self.t_weigh + 0.2:
                hands = [(fx - 70 * S, F0 - 290 * S), (fx + 70 * S, F0 - 290 * S)]
        info = person_fat(d, fx, fy, fat, tuple(hands), walk=walk, mood=mood, look=look, stance=stance, bob=bob,
                          s=S * (0.85 + 0.15 * p_pop))
        if dumb:
            for h in info["hands"]:
                draw_dumbbell(d, h[0], h[1])
        if food:
            h = info["hands"][1]
            draw_food(d, self.healthy, h[0] + 6, h[1] - 18)
        if sweat:
            hx, hy = info["head"]
            for k in range(3):
                ph = ((t * 1.7) + k / 3) % 1
                sg = -1 if k % 2 else 1
                x = hx + sg * (info["r"] + 6 + ph * 30)
                y = hy - 10 + ph * 40 - math.sin(math.pi * ph) * 20
                d.ellipse((x - 5, y - 8, x + 5, y + 6), fill=(130, 200, 255))
        if t > self.t_weigh:
            self.weight_bubble(c, info, self.wR1, GREEN, t)

    def weight_bubble(self, c, info, w, color, t):
        a = ease_out_back(seg(t, self.t_weigh, self.t_weigh + 0.35))
        if a > 0:
            hx, hy = info["head"]
            paste_scaled(c, sprite(f"{w} kg", 44, color), hx, hy - info["r"] - 50, a, clamp(a * 2))

    def draw_hud(self, c, t):
        fade = 1 - (smooth(seg(t, 7.9, 8.2)) if self.final else 0)
        if fade > 0:
            paste_scaled(c, calendar_sprite(self.i, self.m, self.cfg["_prev_month"], t), 540, 330, 1, fade)
            paste_scaled(c, sprite(spaced(self.data.get("subtitle", "SAME ALARM · 6:00")), 30, (170, 170, 186), F_BOLD),
                         540, 466, 1, fade)
        if self.final:
            a1 = ease_out_back(seg(t, 8.3, 8.7))
            a2 = ease_out_back(seg(t, 9.3, 9.7))
            if a1 > 0:
                paste_scaled(c, sprite(self.data["punch1"], 66, (245, 245, 250)), 540, 330, 0.7 + 0.3 * a1, clamp(a1 * 2))
            if a2 > 0:
                paste_scaled(c, sprite(self.data["punch2"], 74, GOLD), 540, 425, 0.7 + 0.3 * a2, clamp(a2 * 2))
        for room in ("L", "R"):
            w0, w1 = (self.wL0, self.wL1) if room == "L" else (self.wR0, self.wR1)
            w = w1 if t > self.t_weigh else w0
            if room == "R":
                colr = GREEN if w < self.start_w else (235, 235, 240)
            else:
                colr = RED if w > self.start_w else (235, 235, 240)
            cxr = ROOMS[room] + RW / 2
            paste_scaled(c, sprite(spaced("WEIGHT"), 30, (150, 150, 166), F_BOLD), cxr, 1414, 1, 1)
            bump = 1 + 0.15 * (1 - smooth(seg(t, self.t_weigh, self.t_weigh + 0.3))) if t > self.t_weigh else 1
            paste_scaled(c, sprite(f"{w} kg", 72, colr), cxr, 1474, bump, 1)
        if self.data.get("watermark"):
            paste_scaled(c, sprite(self.data["watermark"], 30, (130, 130, 145), F_SEMI), 540, 1534, 1, 0.8)


# ----------------------------------------------------------------- audio
def build_lib2(rng):
    lib = build_lib(rng)
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    gate = np.zeros(n)
    for k in range(8):
        a = int((k * 0.11 + (0.12 if k >= 4 else 0)) * SR)
        b = a + int(0.075 * SR)
        gate[a:min(b, n)] = 1
    lib["alarm"] = np.sign(np.sin(2 * np.pi * 2350 * t)) * 0.3 * lowpass(gate, 300)
    n = int(1.3 * SR)
    t = np.arange(n) / SR
    saw = 2 * ((80 * t) % 1) - 1
    env = np.sin(np.pi * np.clip(t / 1.1, 0, 1)) ** 2
    lib["snore"] = lowpass(saw * 0.6 + rng.normal(0, 0.5, n), 420) * env * 0.9
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    lib["clank"] = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((880, 0.6), (1420, 0.5), (2230, 0.35), (3170, 0.2))) * np.exp(-t / 0.06) * 0.5
    n = int(0.5 * SR)
    g = np.zeros(n)
    for k in range(3):
        a = int(k * 0.14 * SR)
        m = int(0.09 * SR)
        g[a:a + m] += sine_sweep(260, 520, 0.09) * env_exp(m, 0.03)
    lib["glug"] = g * 0.7
    n = int(0.25 * SR)
    src = rng.normal(0, 1, n)
    hp = src - lowpass(src, 2200)
    env = np.zeros(n)
    for k in range(4):
        a = int(k * 0.05 * SR)
        m = int(0.03 * SR)
        env[a:a + m] += np.exp(-np.arange(m) / (0.008 * SR))
    lib["crunch"] = hp * env * 0.8
    return lib


def build_audio(stages, dur, path, seed):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    lib = build_lib2(rng)
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
    pl = pr = data["start_weight"]
    prev_m = None
    n = len(data["months"])
    for i, mc in enumerate(data["months"]):
        mc = dict(mc)
        mc["_prevL"], mc["_prevR"], mc["_prev_month"] = pl, pr, prev_m
        st = Stage(i, mc, t, n, data)
        stages.append(st)
        t += st.dur
        pl, pr, prev_m = mc["left"], mc["right"], mc["month"]
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
