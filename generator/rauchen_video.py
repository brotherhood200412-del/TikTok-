#!/usr/bin/env python3
"""
"Cigarettes vs. Running" – Zwei-Zimmer-Vergleich über 10 Jahre, ohne Sprecher, ohne Musik
=========================================================================================
Gleiche 10 $ am Tag. Links: Zigaretten, Husten, verrauchtes Zimmer, keine Puste.
Rechts: Geld ins Glas, Laufband, Wasser, Medaillen.

    python3 generator/rauchen_video.py skripte/zimmer/09_cigarettes_vs_running.json
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
from make_video import F_BLACK, F_BOLD, F_SEMI, FPS, H, SR, W, clamp, ease_out_back, ease_out_cubic, lowpass, sine_sweep  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import (CEIL, DOOR, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, SHELF, SKIN, SKY, WIN, WOOD,  # noqa: E402
                          build_base, build_lib, draw_coin, draw_jar, paste_scaled, room_overlay, seg, spaced, sprite)
from wecker_video import draw_food, draw_medal, person_fat  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "videos")

S = 1.2
F0 = FL - 10
TM_X0, TM_X1, TM_H = 165, 430, 24       # Laufband (lokal)
RUN_X = 290
HOME_L, HOME_R = 245, 225
JAR_X = 400
SICK_SKIN = (196, 198, 186)


def fmt_money(v):
    return f"${v:,.0f}"


# ----------------------------------------------------------------- props
def draw_door(d, x0):
    dx0, dx1 = x0 + DOOR[0], x0 + DOOR[1]
    d.rectangle((dx0, FL - 298, dx1, FL - 10), fill=(120, 86, 64), outline=OUT, width=4)
    d.ellipse((dx1 - 22, FL - 160, dx1 - 10, FL - 148), fill=GOLD)


def draw_table_ashtray(d, x0, butts):
    tx0, tx1, top = x0 + 335, x0 + 425, F0 - 92
    d.rectangle((tx0, top, tx1, top + 12), fill=WOOD, outline=OUT, width=3)
    for lx in (tx0 + 8, tx1 - 16):
        d.rectangle((lx, top + 12, lx + 8, F0), fill=(70, 50, 38), outline=OUT, width=2)
    cx = (tx0 + tx1) / 2
    d.ellipse((cx - 34, top - 18, cx + 34, top + 4), fill=(90, 92, 100), outline=OUT, width=3)
    rnd = random.Random(2)
    for k in range(min(butts, 26)):
        bx = cx + rnd.uniform(-26, 22)
        by = top - 12 - (k // 9) * 6 + rnd.uniform(-3, 3)
        d.line([(bx, by), (bx + 12, by - 3)], fill=(240, 236, 226), width=5)
        d.line([(bx + 8, by - 2), (bx + 12, by - 3)], fill=(220, 150, 60), width=5)


def draw_packs(d, x0, n):
    rnd = random.Random(9)
    for k in range(n):
        px = x0 + 135 + (k % 6) * 30 + rnd.uniform(-4, 4)
        py = F0 - (k // 6) * 16
        ang = rnd.uniform(-0.3, 0.3)
        w, h = 26, 16
        pts = [(-w / 2, 0), (w / 2, 0), (w / 2, -h), (-w / 2, -h)]
        ca, sa = math.cos(ang), math.sin(ang)
        q = [(px + x * ca - y * sa, py + x * sa + y * ca) for x, y in pts]
        d.polygon(q, fill=(235, 235, 235), outline=OUT)
        d.line([q[3], q[2]], fill=(220, 50, 60), width=6)


def draw_cig_pack(d, x, y, s=1.0):
    d.rectangle((x - 16 * s, y - 24 * s, x + 16 * s, y + 18 * s), fill=(240, 240, 240), outline=OUT, width=3)
    d.rectangle((x - 16 * s, y - 24 * s, x + 16 * s, y - 10 * s), fill=(220, 50, 60), outline=OUT, width=2)


def draw_cigarette(d, hx, hy, glow, toward=1):
    ex, ey = hx + toward * 30, hy - 8
    d.line([(hx, hy), (ex, ey)], fill=(245, 242, 232), width=7)
    d.line([(hx, hy), (hx + toward * 9, hy - 2.4)], fill=(215, 150, 70), width=7)
    r = 4 + 3 * glow
    d.ellipse((ex - r, ey - r, ex + r, ey + r), fill=(255, int(120 + 100 * glow), 40))
    return ex, ey


def draw_lighter(d, x, y, flame):
    d.rounded_rectangle((x - 9, y - 6, x + 9, y + 24), 3, fill=(60, 130, 230), outline=OUT, width=2)
    if flame > 0.05:
        d.ellipse((x - 6 * flame, y - 6 - 20 * flame, x + 6 * flame, y - 4), fill=(255, 190, 60))


def draw_treadmill(c, d, x0, km_text, running, t):
    bx0, bx1 = x0 + TM_X0, x0 + TM_X1
    d.rounded_rectangle((bx0, F0 - TM_H, bx1, F0), 10, fill=(44, 44, 54), outline=OUT, width=4)
    d.rectangle((bx0 + 12, F0 - TM_H + 4, bx1 - 30, F0 - TM_H + 10), fill=(30, 30, 36))
    off = (t * 220) % 40 if running else 0
    xx = bx1 - 34 - off
    while xx > bx0 + 14:
        d.line([(xx, F0 - TM_H + 5), (xx, F0 - TM_H + 9)], fill=(90, 90, 100), width=2)
        xx -= 40
    d.line([(bx1 - 18, F0 - TM_H), (bx1 - 6, F0 - 200)], fill=(70, 70, 82), width=10)
    d.rounded_rectangle((bx1 - 60, F0 - 232, bx1 + 30, F0 - 190), 8, fill=(26, 26, 34), outline=OUT, width=4)
    paste_scaled(c, sprite(km_text, 24, GREEN), bx1 - 15, F0 - 211, 1, 1)
    d = ImageDraw.Draw(c)
    d.line([(bx1 - 60, F0 - 196), (bx1 - 120, F0 - 170)], fill=(70, 70, 82), width=8)
    return d


def year_calendar(i, label, prev_label, t):
    w, h = 300, 230
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 30, 30, 270, 200
    d.rounded_rectangle((x0, y0, x1, y1), 16, fill=(244, 241, 234), outline=OUT, width=5)
    d.rounded_rectangle((x0, y0, x1, y0 + 46), 16, fill=(205, 62, 76), outline=OUT, width=5)
    d.rectangle((x0 + 4, y0 + 28, x1 - 4, y0 + 44), fill=(205, 62, 76))
    paste_scaled(img, sprite(spaced("YEAR"), 26, (250, 245, 240), F_BOLD), 150, y0 + 25, 1, 1)
    for ox in (-90, 90):
        d.rounded_rectangle((150 + ox - 8, y0 - 18, 150 + ox + 8, y0 + 18), 6, fill=(200, 200, 210), outline=OUT, width=3)
    pop = ease_out_back(seg(t, 0.0, 0.35)) if i == 0 else 1
    paste_scaled(img, sprite(label, 104, (32, 32, 40)), 150, (y0 + 46 + y1) / 2 + 4, pop, 1)
    if i > 0 and t < 0.6:
        k = smooth(t / 0.55)
        hgt = (y1 - y0 - 46) * (1 - k)
        top = y0 + 46
        if hgt > 2:
            d = ImageDraw.Draw(img)
            d.rectangle((x0 + 4, top, x1 - 4, top + hgt), fill=(250, 248, 242), outline=(180, 175, 165), width=2)
            spr = sprite(prev_label, 104, (32, 32, 40))
            sp = spr.resize((spr.width, max(1, int(spr.height * max(0.05, 1 - k)))))
            paste_scaled(img, sp, 150, top + hgt / 2, 1, 1 - k)
    return img


# ----------------------------------------------------------------- stage
class Stage:
    def __init__(self, i, cfg, start, n, data):
        self.i, self.cfg, self.start, self.data = i, cfg, start, data
        self.n = n
        self.final = i == n - 1
        self.label = str(cfg["year"])
        self.dur = float(cfg.get("dur", 9.0))
        sky = cfg.get("sky", ["JAN", "MAR", "MAY", "JUL", "SEP", "NOV", "DEC"][i % 7])
        self.sky = sky
        self.base = build_base(sky, door=True)
        self.warm = room_overlay("R", (255, 190, 110), 4 + i * 6)
        self.sp0, self.sp1 = cfg["_prev_spent"], cfg["spent"]
        self.sv0, self.sv1 = cfg["_prev_saved"], cfg["saved"]
        self.km = cfg.get("km", 5.0)
        self.health = i / max(1, n - 1)          # 0 -> 1 (links wird es schlimmer)
        self.cough_d = 0.7 + 0.14 * i
        self.zoom = cfg.get("zoom")
        rnd = random.Random(i * 5 + 11)
        self.parts = [(rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(0.6, 1.4)) for _ in range(26)]
        self.ev = []
        self.t_medal = 7.6
        self.exhales = [1.7, 2.7, 5.25]
        self.schedule()

    def sfx(self, t, name, g=1.0):
        if 0 <= t < self.dur:
            self.ev.append((t, name, g))

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        # Links
        s(0.6, "pop", 0.35)
        s(0.65, "beep", 0.25)
        s(0.95, "flick", 0.5)
        for tt in (1.25, 2.25, 4.8):
            s(tt, "inhale", 0.35)
        for tt in self.exhales:
            s(tt, "swish", 0.22)
        nc = 2 + self.i // 2
        for k in range(nc):
            s(3.25 + k * (self.cough_d / nc), "cough", 0.55)
        for st in (6.3, 6.6, 6.9):
            s(st, "step", 0.25)
        for k in range(3):
            s(7.1 + k * 0.5, "pant", 0.35)
        # Rechts
        s(0.62, "clink", 0.45)
        s(0.82, "clink", 0.45)
        s(1.0, "step", 0.3)
        s(1.2, "step", 0.3)
        s(1.35, "hum", 0.25)
        for k in range(int((5.3 - 1.35) / 0.19)):
            s(1.4 + k * 0.19, "step", 0.2)
        s(5.25, "pop_big", 0.35)
        s(5.45, "step", 0.3)
        for k in range(2):
            s(6.0 + k * 0.5, "glug", 0.3)
        s(self.t_medal, "ding", 0.5)
        if self.final:
            s(self.t_medal + 0.1, "cash", 0.4)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

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

    def smoke(self, d, x, y, k, big=1.0):
        """Rauchwolke, k = Sekunden seit Ausstoß."""
        if k < 0 or k > 2.2:
            return
        for j in range(4):
            kk = k - j * 0.08
            if kk < 0:
                continue
            r = (10 + kk * 26) * big
            g = int(lerp(200, 120, clamp(kk / 2.2)))
            a = 1 - kk / 2.2
            cx = x + 24 + kk * 30 + j * 8 + math.sin(kk * 3 + j) * 10
            cy = y - 6 - kk * 70 - j * 10
            col = (int(g * a + 40 * (1 - a)), int(g * a + 40 * (1 - a)), int(g * a + 46 * (1 - a)))
            d.ellipse((cx - r, cy - r * 0.8, cx + r, cy + r * 0.8), fill=col)

    # ---- draw
    def draw(self, c, t, gt):
        c.alpha_composite(self.base)
        self.draw_window_fx(ImageDraw.Draw(c), gt)
        self.draw_left(c, t)
        haze = 14 + self.i * 11 + 14 * smooth(seg(t, 1.0, 6.0))
        c.alpha_composite(room_overlay("L", (150, 150, 155), haze), (ROOMS["L"], CEIL))
        c.alpha_composite(room_overlay("L", (0, 0, 0), 8 + self.i * 9), (ROOMS["L"], CEIL))
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

    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        draw_door(d, x0)
        draw_packs(d, x0, self.i * 2 + (1 if t > 0.6 else 0))
        draw_table_ashtray(d, x0, 3 + self.i * 4 + (1 if t > 3.1 else 0) + (1 if t > 6.0 else 0))
        skin = tuple(int(lerp(a, b, self.health)) for a, b in zip(SKIN, SICK_SKIN))
        fx = x0 + HOME_L
        hands, look, mood, lean, shake, mouth_o, head_drop, walk, bob = [None, None], 0.3, 0.0, 0.0, 0.0, False, 0.0, 0.0, 0.0
        cig, glow, lighter, pack = False, 0.0, -1.0, False
        mouth_hand = False
        # Schachtel kaufen
        if 0.55 < t < 0.95:
            pack = True
            hands[0] = (fx - 46 * S, F0 - 150 * S)
            mood = 0.3
        # Anzünden
        if 0.9 < t < 1.2:
            lighter = smooth(seg(t, 0.95, 1.05))
            hands[1] = (fx + 28 * S, F0 - 218 * S)
            hands[0] = (fx + 4 * S, F0 - 200 * S)
            cig = True
        # Rauchen (2 Züge), später nochmal
        for t0, t1 in ((1.2, 3.15), (4.55, 6.05)):
            if t0 < t < t1:
                cig = True
                ph = ((t - t0) % 1.0)
                up = smooth(ph / 0.3) * (1 - smooth((ph - 0.45) / 0.3))
                glow = up
                hands[1] = (fx + lerp(55, 28, up) * S, F0 - lerp(150, 218, up) * S)
                mouth_hand = up > 0.6
                mood = 0.2 if self.i < 3 else -0.3
        # Husten
        cend = 3.2 + self.cough_d
        if 3.2 < t < cend:
            shake = math.sin(t * 60) * 5
            lean = 0.16
            mouth_o = True
            mood = -0.8
            hands[1] = (fx + 30 * S, F0 - 205 * S)
            cig = False
        # Versuch zu laufen -> keine Puste
        if 6.2 < t < 7.0:
            k = seg(t, 6.2, 7.0)
            fx = lerp(fx, x0 + 300, smooth(k))
            walk = (t - 6.2) * 12
            bob = abs(math.sin((t - 6.2) * 12)) * 6
            mood = 0.0
            look = 1
        elif t >= 7.0:
            fx = x0 + 300
            lean = 0.38
            hands = [(fx - 18 * S + 30, F0 - 92 * S), (fx + 34 * S + 30, F0 - 92 * S)]
            mood = -0.8
            mouth_o = True
            look = 0.8
            head_drop = 0.4
        info = person_fat(d, fx, F0, 0.12, tuple(hands), walk=walk, bob=bob, mood=mood, look=look, lean=lean,
                          shake=shake, mouth_o=mouth_o, head_drop=head_drop, s=S, skin=skin)
        mx, my = info["mouth"]
        if pack:
            h = info["hands"][0]
            draw_cig_pack(d, h[0], h[1] - 20, 1.1)
            self.float_text(c, "-$10", RED, fx - 30, info["head"][1] - 90, t - 0.6, 46, 0.8)
        if lighter >= 0 and 0.9 < t < 1.2:
            h = info["hands"][0]
            draw_lighter(d, h[0] + 6, h[1] - 10, lighter)
        if cig:
            h = info["hands"][1]
            draw_cigarette(d, h[0] + 4, h[1] - 6, glow)
        for te in self.exhales:
            self.smoke(d, mx, my, t - te, 1.0 + 0.15 * self.i)
        if 3.2 < t < cend + 0.6:
            for k in range(3):
                kk = t - 3.25 - k * (self.cough_d / 3)
                if 0 < kk < 0.6:
                    r = 6 + kk * 30
                    d.ellipse((mx + 14 + kk * 60 - r, my - kk * 20 - r, mx + 14 + kk * 60 + r, my - kk * 20 + r),
                              fill=(170, 170, 175))
            self.float_text(c, "*cough*", (210, 210, 220), mx + 40, my - 90, t - 3.25, 36, self.cough_d)
        if t > 7.0:
            for k in range(3):
                kk = (t - 7.1 - k * 0.5)
                if 0 < kk < 0.45:
                    r = 5 + kk * 26
                    d.ellipse((mx + 12 + kk * 40 - r, my + 4 - r, mx + 12 + kk * 40 + r, my + 4 + r), fill=(190, 195, 205))
            self.float_text(c, "*out of breath*", (210, 210, 220), x0 + RW / 2, info["head"][1] - 110, t - 7.2, 32, 1.3)

    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        draw_door(d, x0)
        n_med = self.i + (1 if t > self.t_medal else 0)
        d.line([(x0 + 22, 872), (x0 + 220, 872)], fill=WOOD, width=6)
        for k in range(min(n_med, 7)):
            draw_medal(d, x0 + 38 + k * 27, 905)
        glow = smooth(seg(t, self.t_medal, self.t_medal + 0.6)) * (0.75 + 0.25 * math.sin(t * 4)) if self.final else 0
        d = draw_jar(c, d, x0 + JAR_X, SHELF[2], self.saved_now(t) / max(1, self.data["_max_saved"]), glow)
        running = 1.35 < t < 5.3
        km = self.km * smooth(seg(t, 1.35, 5.3))
        d = draw_treadmill(c, d, x0, f"{km:.1f} km", running, t)
        fx, fy = x0 + HOME_R, F0
        hands, look, mood, walk, bob = [None, None], 0.0, 0.6, 0.0, 0.0
        sweat, bottle, coin_hand = False, False, False
        if 0.55 < t < 0.95:
            hands[1] = (fx + 50 * S, F0 - 205 * S)
            coin_hand = True
            look = 1
        if 0.95 < t < 1.35:
            k = smooth(seg(t, 0.95, 1.35))
            fx = lerp(x0 + HOME_R, x0 + RUN_X, k)
            fy = F0 - TM_H * smooth(seg(t, 1.15, 1.35))
            walk = (t - 0.95) * 14
            look = 1
        elif running:
            fx, fy = x0 + RUN_X, F0 - TM_H
            tt = t - 1.35
            walk = tt * 17
            bob = abs(math.sin(tt * 17)) * 10
            sw = math.sin(tt * 17)
            hands = [(fx - (36 + 16 * sw) * S, F0 - (158 - 12 * sw) * S), (fx + (36 - 16 * sw) * S, F0 - (158 + 12 * sw) * S)]
            sweat = True
            look = 1
            mood = 0.6
        elif 5.3 <= t < 5.7:
            k = smooth(seg(t, 5.3, 5.7))
            fx = lerp(x0 + RUN_X, x0 + HOME_R, k)
            fy = F0 - TM_H * (1 - smooth(seg(t, 5.3, 5.5)))
            walk = (t - 5.3) * 14
            look = -0.5
        elif 5.7 <= t < 7.0:
            ph = ((t - 5.8) % 0.5) / 0.5 if t > 5.8 else 0
            up = math.sin(math.pi * ph) ** 2
            hands[1] = (fx + lerp(58, 22, up) * S, F0 - lerp(150, 225, up) * S)
            bottle = True
            mood = 0.7
        elif t >= 7.0:
            sway = math.sin((t - 7.0) * 3)
            hands = [(fx - (20 - 25 * sway) * S, F0 - 300 * S), (fx + (20 + 25 * sway) * S, F0 - 300 * S)]
            mood = 0.9
            look = 0.2
        info = person_fat(d, fx, fy, 0.12, tuple(hands), walk=walk, bob=bob, mood=mood, look=look, s=S)
        if coin_hand:
            for k, ta in enumerate((0.6, 0.8)):
                p = seg(t, ta, ta + 0.22)
                if 0 < p < 1:
                    h = info["hands"][1]
                    draw_coin(d, lerp(h[0], x0 + JAR_X, p), lerp(h[1], SHELF[2] - 170, p) - math.sin(math.pi * p) * 60)
            self.float_text(c, "+$10", GREEN, x0 + JAR_X, SHELF[2] - 200, t - 0.62, 42, 0.8)
        if bottle:
            h = info["hands"][1]
            draw_food(d, "water", h[0] + 6, h[1] - 18)
        if sweat:
            hx, hy = info["head"]
            for k in range(3):
                ph = ((t * 1.7) + k / 3) % 1
                sg = -1 if k % 2 else 1
                x = hx + sg * (info["r"] + 6 + ph * 30)
                y = hy - 10 + ph * 40 - math.sin(math.pi * ph) * 20
                d.ellipse((x - 5, y - 8, x + 5, y + 6), fill=(130, 200, 255))
        if t > 5.2:
            self.float_text(c, f"+{self.km:g} km", GREEN, x0 + TM_X1 - 40, F0 - 280, t - 5.25, 40, 0.9)

    def spent_now(self, t):
        return lerp(self.sp0, self.sp1, smooth(seg(t, 0.6, 6.0)))

    def saved_now(self, t):
        return lerp(self.sv0, self.sv1, smooth(seg(t, 0.62, 6.0)))

    def draw_hud(self, c, t):
        fade = 1 - (smooth(seg(t, 7.9, 8.2)) if self.final else 0)
        if fade > 0:
            paste_scaled(c, year_calendar(self.i, self.label, self.cfg["_prev_label"], t), 540, 330, 1, fade)
            paste_scaled(c, sprite(spaced(self.data.get("subtitle", "SAME $10 A DAY")), 30, (170, 170, 186), F_BOLD),
                         540, 466, 1, fade)
        if self.final:
            a1 = ease_out_back(seg(t, 8.3, 8.7))
            a2 = ease_out_back(seg(t, 9.3, 9.7))
            if a1 > 0:
                paste_scaled(c, sprite(self.data["punch1"], 62, (245, 245, 250)), 540, 330, 0.7 + 0.3 * a1, clamp(a1 * 2))
            if a2 > 0:
                paste_scaled(c, sprite(self.data["punch2"], 74, GOLD), 540, 425, 0.7 + 0.3 * a2, clamp(a2 * 2))
        for room, label, val, colr in (("L", "SPENT", self.spent_now(t), RED), ("R", "SAVED", self.saved_now(t), GREEN)):
            cxr = ROOMS[room] + RW / 2
            paste_scaled(c, sprite(spaced(label), 30, (150, 150, 166), F_BOLD), cxr, 1414, 1, 1)
            paste_scaled(c, sprite(fmt_money(val), 72, colr if val > 0 else (235, 235, 240)), cxr, 1474, 1, 1)
        if self.data.get("watermark"):
            paste_scaled(c, sprite(self.data["watermark"], 30, (130, 130, 145), F_SEMI), 540, 1534, 1, 0.8)


# ----------------------------------------------------------------- audio
def build_lib3(rng):
    from wecker_video import build_lib2
    lib = build_lib2(rng)

    def nz(n):
        return rng.normal(0, 1, n)

    n = int(0.7 * SR)
    out = np.zeros(n)
    for k in range(2):
        a = int(k * 0.26 * SR)
        m = int(0.22 * SR)
        src = nz(m)
        bp = lowpass(src, 2600) - lowpass(src, 260)
        env = np.minimum(1, np.arange(m) / (0.004 * SR)) * np.exp(-np.arange(m) / (0.07 * SR))
        tone = np.sin(2 * np.pi * 170 * np.arange(m) / SR) * np.exp(-np.arange(m) / (0.05 * SR)) * 0.5
        out[a:a + m] += (bp * 1.4 + tone) * env * (1 - 0.3 * k)
    lib["cough"] = out * 0.8
    n = int(0.35 * SR)
    t = np.linspace(0, 1, n)
    src = nz(n)
    lib["pant"] = (lowpass(src, 1600) - lowpass(src, 200)) * np.sin(np.pi * t) ** 2 * 1.3
    n = int(0.4 * SR)
    src = nz(n)
    fl = np.zeros(n)
    m = int(0.02 * SR)
    fl[:m] += src[:m] * 2.0
    fl += (src - lowpass(src, 3000)) * np.exp(-np.arange(n) / (0.12 * SR)) * 0.5
    lib["flick"] = fl * 0.6
    n = int(0.6 * SR)
    t = np.linspace(0, 1, n)
    src = nz(n)
    crackle = (rng.random(n) < 0.004) * rng.normal(0, 1.5, n)
    lib["inhale"] = ((src - lowpass(src, 1500)) * t ** 1.5 * 0.5 + crackle) * np.sin(np.pi * t) * 0.7
    n = int(4.0 * SR)
    t = np.arange(n) / SR
    hum = (np.sin(2 * np.pi * 58 * t) * 0.5 + np.sin(2 * np.pi * 116 * t) * 0.3 + lowpass(nz(n), 500) * 0.6)
    env = np.minimum(1, t / 0.3) * np.minimum(1, (4.0 - t) / 0.3)
    lib["hum"] = hum * env * 0.5
    return lib


def build_audio(stages, dur, path, seed):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    lib = build_lib3(rng)
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
    psp = psv = 0
    prev = None
    data["_max_saved"] = max(m["saved"] for m in data["stages"])
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_spent"], sc["_prev_saved"], sc["_prev_label"] = psp, psv, prev
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        psp, psv, prev = sc["spent"], sc["saved"], str(sc["year"])
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
