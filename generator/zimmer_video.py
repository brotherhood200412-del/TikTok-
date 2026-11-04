#!/usr/bin/env python3
"""
"Zwei Zimmer" – Vergleichs-Video ohne Sprecher (mit vs. ohne Mindset)
=====================================================================
Zwei gleiche Wohnungen nebeneinander. Gleiches Gehalt, anderes Verhalten.
Oben läuft das Jahr ab (Abreißkalender), unten zählt "SAVED" mit.
Keine Musik – nur leise Soundeffekte (Musik wird in TikTok hinzugefügt).

    python3 generator/zimmer_video.py skripte/zimmer/07_one_year_salary.json
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
from make_video import (F_BLACK, F_BOLD, F_SEMI, FPS, H, SR, W, build_sfx, clamp,  # noqa: E402
                        ease_out_back, ease_out_cubic, env_exp, font, lowpass, sine_sweep, text_sprite,
                        paste_scaled)
from figuren_video import extra_sfx, lerp, smooth  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "videos")

# ----------------------------------------------------------------- layout
B_TOP, CEIL, FL, B_BOT = 536, 560, 1340, 1378
S = 1.3  # Figuren-/Objekt-Skalierung
ROOMS = {"L": 54, "R": 550}          # linke Innenkante der Zimmer
RW = 476                              # Zimmerbreite
OUT = (16, 16, 22)
SKIN = (246, 246, 250)
SHIRT = (80, 118, 235)
PANTS = (44, 48, 66)
GOLD = (255, 198, 64)
RED = (255, 84, 104)
GREEN = (72, 226, 140)
WALL = (66, 62, 72)
WOOD = (92, 66, 50)


def seg(t, a, b):
    return clamp((t - a) / (b - a))


def rx(room, lx):
    return ROOMS[room] + lx


_spr = {}


def sprite(text, size, color, path=F_BLACK):
    key = (text, size, color, path)
    if key not in _spr:
        _spr[key] = text_sprite(text, font(path, size), color)[0]
    return _spr[key]


def spaced(text, n=1):
    return (" " * n).join(text)


# ----------------------------------------------------------------- drawing primitives
def capsule(d, p1, p2, w, fill, ow=4):
    for col, ww in ((OUT, w + 2 * ow), (fill, w)):
        d.line([p1, p2], fill=col, width=int(ww))
        r = ww / 2
        for p in (p1, p2):
            d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=col)


def circle(d, x, y, r, fill, ow=4):
    d.ellipse((x - r - ow, y - r - ow, x + r + ow, y + r + ow), fill=OUT)
    d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def person(d, x, fy, lean=0.0, hands=(None, None), walk=0.0, sit=0.0, mood=0.0, look=0.0, head_drop=0.0,
           watch=False, s=S):
    """Figur mit Gesicht. look: -1 links, +1 rechts. sit: 0 stehen, 1 am Boden sitzen."""
    leg = 84 * s
    hipy = lerp(fy - leg - 8 * s, fy - 30 * s, sit)
    hip = (x, hipy)
    if sit < 0.5:
        sw = math.sin(walk) * 20 * s
        for fx in (x - 14 * s + sw, x + 14 * s - sw):
            capsule(d, (x + (fx - x) * 0.3, hipy), (fx, fy - 10 * s), 22 * s, PANTS)
            d.ellipse((fx - 15 * s, fy - 16 * s, fx + (15 + look * 6) * s, fy + 1), fill=OUT)
    else:
        dx = look if look else 1
        for k in (-1, 1):
            knee = (x + (dx * 40 + k * 7) * s, hipy - 34 * s)
            foot = (x + (dx * 80 + k * 9) * s, fy - 10 * s)
            capsule(d, hip, knee, 22 * s, PANTS)
            capsule(d, knee, foot, 22 * s, PANTS)
    up = (math.sin(lean), -math.cos(lean))
    perp = (math.cos(lean), math.sin(lean))
    neck = (hip[0] + up[0] * 92 * s, hip[1] + up[1] * 92 * s)
    capsule(d, (hip[0] + up[0] * 14 * s, hip[1] + up[1] * 14 * s), neck, 62 * s, SHIRT)
    sh = (hip[0] + up[0] * 78 * s, hip[1] + up[1] * 78 * s)
    hand_pts = []
    for side, h in zip((-1, 1), hands):
        sp = (sh[0] + perp[0] * side * 24 * s, sh[1] + perp[1] * side * 24 * s)
        if h is None:
            h = (sp[0] + side * 12 * s, sp[1] + 82 * s)
        capsule(d, sp, h, 17 * s, SHIRT)
        hand_pts.append(h)
    hc = (neck[0] + (up[0] * 40 + look * 4 + head_drop * look * 8) * s, neck[1] + (up[1] * 40 + head_drop * 16) * s)
    circle(d, hc[0], hc[1], 37 * s, SKIN)
    ex, ey = look * 7 * s, hc[1] + (-4 + head_drop * 6) * s
    for sg in (-1, 1):
        d.ellipse((hc[0] + ex + (sg * 12 - 4.5) * s, ey - 5.5 * s, hc[0] + ex + (sg * 12 + 4.5) * s, ey + 5.5 * s), fill=OUT)
    mx, my = hc[0] + ex * 0.8, hc[1] + (16 + head_drop * 4) * s
    lw = max(3, int(4 * s))
    if mood > 0.25:
        d.arc((mx - 13 * s, my - 12 * s, mx + 13 * s, my + 8 * s), 20, 160, fill=OUT, width=lw)
    elif mood < -0.25:
        d.arc((mx - 11 * s, my - 2 * s, mx + 11 * s, my + 14 * s), 205, 335, fill=OUT, width=lw)
    else:
        d.line((mx - 9 * s, my + s, mx + 9 * s, my + s), fill=OUT, width=lw)
    for i, h in enumerate(hand_pts):
        circle(d, h[0], h[1], 10 * s, SKIN, 3)
        if watch and i == 0:
            d.ellipse((h[0] - 9 * s, h[1] - 22 * s, h[0] + 9 * s, h[1] - 6 * s), fill=GOLD, outline=OUT, width=3)
    return dict(head=hc, hands=hand_pts, hip=hip)


def draw_box(d, x, y, w=96, h=68, flaps=0.0):
    x0, x1, y0 = x - w / 2, x + w / 2, y - h
    if flaps > 0:
        o = flaps * 34
        d.polygon([(x0, y0), (x0 - o * 0.6, y0 - o), (x0 + w * 0.35, y0 - o * 0.8), (x - 2, y0)], fill=(170, 125, 78), outline=OUT)
        d.polygon([(x1, y0), (x1 + o * 0.6, y0 - o), (x1 - w * 0.35, y0 - o * 0.8), (x + 2, y0)], fill=(170, 125, 78), outline=OUT)
    d.rectangle((x0, y0, x1, y), fill=(192, 146, 92), outline=OUT, width=4)
    if flaps <= 0:
        d.rectangle((x - 9, y0 + 2, x + 9, y - 2), fill=(226, 198, 142))


def draw_envelope(c, d, x, y, s=1.0):
    if s < 0.08:
        return
    w, h = 92 * s, 60 * s
    d.rectangle((x - w / 2, y - h / 2, x + w / 2, y + h / 2), fill=(250, 250, 245), outline=OUT, width=4)
    d.line([(x - w / 2 + 3, y - h / 2 + 3), (x, y + 4 * s), (x + w / 2 - 3, y - h / 2 + 3)], fill=OUT, width=3)
    d.ellipse((x - 13 * s, y + 2 * s, x + 13 * s, y + 26 * s), fill=GREEN, outline=OUT, width=2)
    d.text((x, y + 14 * s), "$", font=font(F_BLACK, int(20 * s)), fill=OUT, anchor="mm")


def draw_tv(d, x, y):  # x center, y Mitte
    d.rectangle((x - 70, y - 42, x + 70, y + 42), fill=(20, 22, 30), outline=OUT, width=5)
    d.rectangle((x - 62, y - 34, x + 62, y + 34), fill=(70, 130, 220))
    d.polygon([(x - 62, y + 34), (x - 10, y - 34), (x + 20, y - 34), (x - 30, y + 34)], fill=(110, 165, 240))


def draw_sneaker(d, x, y, s=1.0):  # y = Sohle
    pts = [(-34, 0), (34, 0), (36, -10), (14, -14), (-2, -30), (-28, -30), (-34, -16)]
    d.polygon([(x + px * s, y + py * s) for px, py in pts], fill=RED, outline=OUT)
    d.rectangle((x - 34 * s, y - 7 * s, x + 36 * s, y), fill=(245, 245, 245), outline=OUT)


def draw_phone(d, x, y, s=1.0):
    d.rounded_rectangle((x - 15 * s, y - 26 * s, x + 15 * s, y + 26 * s), 6, fill=(25, 25, 32), outline=OUT, width=3)
    d.rectangle((x - 11 * s, y - 21 * s, x + 11 * s, y + 19 * s), fill=(120, 190, 255))


def draw_console(d, x, y):  # y Boden
    d.rounded_rectangle((x - 44, y - 26, x + 44, y), 6, fill=(30, 30, 40), outline=OUT, width=4)
    d.line([(x - 30, y - 13), (x + 30, y - 13)], fill=(90, 200, 255), width=4)


def draw_watch(d, x, y, s=1.0):
    d.rectangle((x - 9 * s, y - 30 * s, x + 9 * s, y + 30 * s), fill=(60, 50, 45), outline=OUT, width=3)
    d.ellipse((x - 18 * s, y - 18 * s, x + 18 * s, y + 18 * s), fill=GOLD, outline=OUT, width=4)
    d.ellipse((x - 11 * s, y - 11 * s, x + 11 * s, y + 11 * s), fill=(250, 245, 230))


def draw_bags(d, x, y, s=1.0):  # y Boden
    for i, col in enumerate(((235, 80, 110), (255, 200, 80), (90, 175, 245))):
        bx = x + (i - 1) * 34 * s
        h = (64 - i * 8) * s
        d.arc((bx - 12 * s, y - h - 16 * s, bx + 12 * s, y - h + 10 * s), 180, 360, fill=OUT, width=4)
        d.polygon([(bx - 20 * s, y - h), (bx + 20 * s, y - h), (bx + 24 * s, y), (bx - 24 * s, y)], fill=col, outline=OUT)


def draw_gifts(d, x, y, n=3):
    specs = [(-40, 70, 62, (230, 70, 90)), (36, 60, 54, (70, 200, 130)), (-2, 52, 46, (255, 196, 70)),
             (-70, 44, 40, (120, 150, 255)), (66, 40, 38, (230, 70, 90))]
    stack = 0
    for i, (ox, w, h, col) in enumerate(specs[:n]):
        by = y if i < 2 or i > 2 else y - 62
        if i == 2:
            by = y - 60
        d.rectangle((x + ox - w / 2, by - h, x + ox + w / 2, by), fill=col, outline=OUT, width=4)
        d.rectangle((x + ox - 5, by - h, x + ox + 5, by), fill=(250, 240, 220))
        d.ellipse((x + ox - 12, by - h - 10, x + ox, by - h + 2), outline=(250, 240, 220), width=4)
        d.ellipse((x + ox, by - h - 10, x + ox + 12, by - h + 2), outline=(250, 240, 220), width=4)
        stack += 1


def draw_wallet(d, x, y, open_=0.0, s=S):
    d.rounded_rectangle((x - 30 * s, y - 20 * s, x + 30 * s, y + 20 * s), 6, fill=(120, 80, 50), outline=OUT, width=4)
    if open_ > 0:
        d.rectangle((x - 22 * s, y - (14 + open_ * 10) * s, x + 22 * s, y - 6 * s), fill=(40, 28, 20), outline=OUT, width=3)


def draw_moth(d, x, y, flap, s=2.2):
    """Motte (leeres Portemonnaie): zwei flatternde Flügel, Körper, Fühler."""
    f = 0.35 + 0.65 * abs(math.sin(flap))
    for sg in (-1, 1):
        tip_up = (x + sg * 22 * s, y - 16 * s * f)
        tip_lo = (x + sg * 16 * s, y + 10 * s * f)
        d.polygon([(x + sg * 2 * s, y - 6 * s), tip_up, (x + sg * 26 * s * f, y), tip_lo, (x + sg * 2 * s, y + 6 * s)],
                  fill=(196, 186, 165), outline=OUT)
        d.ellipse((x + sg * 13 * s - 3 * s, y - 5 * s, x + sg * 13 * s + 3 * s, y + 1 * s), fill=(120, 110, 95))
    d.ellipse((x - 4 * s, y - 10 * s, x + 4 * s, y + 11 * s), fill=(95, 88, 80), outline=OUT, width=2)
    for sg in (-1, 1):
        d.line([(x, y - 9 * s), (x + sg * 7 * s, y - 18 * s)], fill=OUT, width=3)


def draw_coin(d, x, y, r=14):
    d.ellipse((x - r, y - r, x + r, y + r), fill=GOLD, outline=(150, 100, 20), width=3)


def draw_card(d, x, y, s=S):
    d.rounded_rectangle((x - 30 * s, y - 19 * s, x + 30 * s, y + 19 * s), 5, fill=(30, 30, 40), outline=OUT, width=3)
    d.rectangle((x - 30 * s, y - 10 * s, x + 30 * s, y - 4 * s), fill=(200, 200, 210))
    d.rectangle((x - 22 * s, y + 4 * s, x - 8 * s, y + 12 * s), fill=GOLD)


def draw_jar(c, d, x, y, level, glow=0.0):  # y Boden
    w, h = 112, 165
    x0, x1, y0 = x - w / 2, x + w / 2, y - h
    if glow > 0:
        paste_scaled(c, GLOW_GOLD, x, y - h / 2, 1.0, glow)
        d = ImageDraw.Draw(c)
    d.rounded_rectangle((x0, y0, x1, y), 18, fill=(40, 48, 60), outline=(210, 225, 240), width=5)
    lv = clamp(level) * (h - 16)
    if lv > 2:
        top = y - 8 - lv
        d.rounded_rectangle((x0 + 8, top, x1 - 8, y - 8), 10, fill=GOLD)
        yy = y - 22
        while yy > top + 6:
            d.line([(x0 + 12, yy), (x1 - 12, yy)], fill=(215, 160, 40), width=2)
            yy -= 14
    d.rectangle((x0 + 6, y0 - 16, x1 - 6, y0 + 2), fill=(170, 140, 110), outline=OUT, width=4)
    d.line([(x0 + 16, y0 + 18), (x0 + 16, y - 26)], fill=(235, 245, 255), width=5)
    return d


def draw_plant(d, x, y, s):  # y = Unterkante Topf
    d.polygon([(x - 24, y - 40), (x + 24, y - 40), (x + 18, y), (x - 18, y)], fill=(196, 110, 70), outline=OUT)
    if s <= 0:
        return
    d.line([(x, y - 40), (x, y - 40 - 70 * s)], fill=(40, 120, 70), width=5)
    leaves = [(-1, 0.35), (1, 0.5), (-1, 0.68), (1, 0.82), (0, 1.0)]
    for sg, f in leaves:
        if s < f * 0.9:
            continue
        ly = y - 40 - 70 * s * f
        lx = x + sg * 22 * s
        rr = 16 * min(1.3, s)
        d.ellipse((lx - rr * 1.3, ly - rr * 0.8, lx + rr * 1.3, ly + rr * 0.8), fill=GREEN, outline=OUT, width=3)


BOOK_COLS = [(230, 90, 90), (90, 160, 240), (250, 200, 80), (120, 210, 150), (190, 130, 240), (240, 150, 90),
             (100, 200, 220), (230, 230, 240)]


def draw_books(d, x, y, n):  # y = Regalbrett
    for i in range(n):
        bx = x + i * 15
        h = 46 + (i * 7) % 14
        d.rectangle((bx, y - h, bx + 12, y), fill=BOOK_COLS[i % len(BOOK_COLS)], outline=OUT, width=2)


def draw_book_open(d, x, y, s=S):
    d.polygon([(x - 34 * s, y - 22 * s), (x, y - 16 * s), (x, y + 18 * s), (x - 34 * s, y + 12 * s)], fill=(250, 248, 240), outline=OUT, width=3)
    d.polygon([(x + 34 * s, y - 22 * s), (x, y - 16 * s), (x, y + 18 * s), (x + 34 * s, y + 12 * s)], fill=(240, 236, 225), outline=OUT, width=3)
    for k in range(3):
        d.line([(x - 28 * s, y + (-10 + k * 8) * s), (x - 6 * s, y + (-6 + k * 8) * s)], fill=(170, 170, 170), width=2)


def radial(size, color, max_a):
    ys, xs = np.mgrid[0:size, 0:size]
    rr = np.sqrt((xs - size / 2) ** 2 + (ys - size / 2) ** 2) / (size / 2)
    arr = np.zeros((size, size, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = (np.clip(1 - rr, 0, 1) ** 2 * max_a).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


GLOW_GOLD = radial(320, GOLD, 140)

# ----------------------------------------------------------------- static room/background
SKY = {"JAN": ((14, 22, 52), (40, 62, 110), "snow"), "MAR": ((36, 44, 64), (72, 88, 110), "rain"),
       "MAY": ((58, 46, 110), (232, 140, 150), "stars"), "JUL": ((70, 56, 140), (255, 160, 90), "sun"),
       "SEP": ((48, 38, 88), (205, 112, 92), "stars"), "NOV": ((24, 24, 44), (74, 62, 72), "leaves"),
       "DEC": ((10, 16, 44), (30, 46, 92), "snow")}
WIN = (150, 640, 320, 800)  # lokal im Zimmer
LAMP_X = 360
SHELF = (300, 470, 985)
DOOR = (14, 112)


def build_base(month):
    img = Image.new("RGBA", (W, H))
    arr = np.zeros((H, W, 3), np.float32)
    yy = np.linspace(0, 1, H)[:, None]
    arr[:] = (np.array((10, 11, 18)) * (1 - yy) + np.array((18, 16, 26)) * yy)[:, None, :] if False else 0
    top, bot = np.array((9, 10, 18), np.float32), np.array((20, 17, 28), np.float32)
    arr[:] = (top[None, None, :] * (1 - yy[..., None]) + bot[None, None, :] * yy[..., None])
    img = Image.fromarray(arr.astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img)
    # Gebäude
    d.rectangle((30, B_TOP, 1050, B_BOT), fill=(34, 34, 42), outline=OUT, width=4)
    d.polygon([(10, B_TOP), (540, B_TOP - 70), (1070, B_TOP)], fill=(30, 30, 38), outline=OUT)
    c0, c1, sty = SKY[month]
    for room in ("L", "R"):
        x0 = ROOMS[room]
        d.rectangle((x0, CEIL, x0 + RW, FL), fill=WALL)
        # Fenster
        wx0, wy0, wx1, wy1 = x0 + WIN[0], WIN[1], x0 + WIN[2], WIN[3]
        for i in range(wy1 - wy0):
            f = i / (wy1 - wy0)
            d.line([(wx0, wy0 + i), (wx1, wy0 + i)], fill=tuple(int(lerp(a, b, f)) for a, b in zip(c0, c1)))
        if sty == "sun":
            d.ellipse((wx0 + 90, wy1 - 50, wx0 + 140, wy1 - 0), fill=(255, 210, 120))
        rnd = random.Random(5)
        bx = wx0
        while bx < wx1:
            bw = rnd.randint(16, 32)
            bh = rnd.randint(20, 70)
            d.rectangle((bx, wy1 - bh, min(wx1, bx + bw), wy1), fill=(18, 18, 28))
            for k in range(2):
                if rnd.random() < 0.6:
                    lx = bx + 4 + rnd.randint(0, max(1, bw - 10))
                    ly = wy1 - bh + 8 + k * 16
                    if lx + 4 < wx1:
                        d.rectangle((lx, ly, lx + 4, ly + 5), fill=(255, 220, 140))
            bx += bw + 2
        d.rectangle((wx0, wy0, wx1, wy1), outline=(220, 215, 205), width=8)
        d.line([((wx0 + wx1) / 2, wy0), ((wx0 + wx1) / 2, wy1)], fill=(220, 215, 205), width=6)
        d.rectangle((wx0 - 10, wy1, wx1 + 10, wy1 + 10), fill=(220, 215, 205), outline=OUT, width=2)
        # Regal
        d.rectangle((x0 + SHELF[0], SHELF[2], x0 + SHELF[1], SHELF[2] + 10), fill=WOOD, outline=OUT, width=3)
        # Tür-Rahmen
        d.rectangle((x0 + DOOR[0] - 6, FL - 304, x0 + DOOR[1] + 6, FL), fill=(48, 44, 52))
        # Boden + Leiste
        d.rectangle((x0, FL - 10, x0 + RW, FL), fill=(58, 46, 40))
        # Lampe
        lx = x0 + LAMP_X
        d.line([(lx, CEIL), (lx, CEIL + 50)], fill=OUT, width=3)
        d.polygon([(lx - 34, CEIL + 82), (lx + 34, CEIL + 82), (lx + 18, CEIL + 50), (lx - 18, CEIL + 50)],
                  fill=(230, 200, 140), outline=OUT)
    # Lichtkegel
    cone = np.zeros((H, W, 4), np.uint8)
    ys, xs = np.mgrid[0:H, 0:W]
    for room in ("L", "R"):
        lx = ROOMS[room] + LAMP_X
        f = np.clip((ys - (CEIL + 82)) / (FL - CEIL - 82), 0, 1)
        half = 34 + f * 210
        inside = (np.abs(xs - lx) < half) & (ys > CEIL + 82) & (ys < FL) & (xs > ROOMS[room]) & (xs < ROOMS[room] + RW)
        a = np.where(inside, np.clip(1 - np.abs(xs - lx) / np.maximum(half, 1), 0, 1) ** 0.7 * (38 - 18 * f), 0)
        cone[..., 3] = np.maximum(cone[..., 3], a.astype(np.uint8))
    cone[..., :3] = (255, 220, 160)
    img.alpha_composite(Image.fromarray(cone, "RGBA"))
    d = ImageDraw.Draw(img)
    # Zwischenwand + Boden-Platte
    d.rectangle((ROOMS["L"] + RW, CEIL, ROOMS["R"], FL), fill=(34, 34, 42))
    d.rectangle((30, FL, 1050, B_BOT), fill=(40, 40, 50), outline=OUT, width=3)
    d.rectangle((30, B_TOP, 1050, CEIL), fill=(40, 40, 50), outline=OUT, width=3)
    return img


def room_overlay(room, color, alpha):
    ov = Image.new("RGBA", (RW, FL - CEIL), color + (int(alpha),))
    return ov


# ----------------------------------------------------------------- stage (ein Monat)
ITEM_INSTALL = {"tv": ("L", 225, 885), "sneakers": ("L", 345, SHELF[2]), "console": ("L", 170, FL - 10),
                "bags": ("L", 400, FL - 10)}
PILE = [(415, 0), (415, 1), (325, 0), (370, 2), (325, 1), (415, 2), (300, 2)]
BOX_W, BOX_H = 92, 72


class Month:
    def __init__(self, idx, cfg, start, prev_saved, n_months):
        self.i, self.cfg, self.start = idx, cfg, start
        self.m = cfg["month"]
        self.final = idx == n_months - 1
        self.dur = float(cfg.get("dur", 9.0))
        self.prev, self.saved = prev_saved, cfg["saved"]
        self.ev = []
        self.base = build_base(self.m)
        self.dark = room_overlay("L", (0, 0, 0), 12 + idx * 15)
        self.warm = room_overlay("R", (255, 190, 110), 4 + idx * 5)
        self.item = cfg.get("item")
        self.price = cfg.get("price", "")
        self.taps = cfg.get("taps", [])
        self.zoom = cfg.get("zoom")
        rnd = random.Random(idx * 13 + 1)
        self.parts = [(rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(0.6, 1.4)) for _ in range(26)]
        self.schedule()

    def sfx(self, t, name, g=1.0):
        if 0 <= t < self.dur:
            self.ev.append((t, name, g))

    def schedule(self):
        s = self.sfx
        if self.i > 0:
            s(0.05, "page", 0.55)
        else:
            s(0.1, "pop_big", 0.4)
        s(1.2, "cash", 0.35)
        s(1.22, "clink", 0.3)
        # Rechts: Münzen ins Glas
        for k in range(5):
            s(2.75 + k * 0.22, "clink", 0.42)
        if self.final:
            s(3.95, "ding", 0.55)
        for st in (1.95, 2.3, 4.0, 4.3):
            s(st, "step", 0.25)
        if self.i % 2 == 0:
            s(4.7, "grow", 0.3)
        else:
            s(4.75, "pop", 0.35)
        s(6.9, "page", 0.25)
        # Links
        if self.final:
            s(2.2, "swipe", 0.5)
            s(2.35, "beep", 0.4)
            for k in range(3):
                s(2.7 + k * 0.18, "thud", 0.35)
            s(3.35, "fail", 0.45)
            s(4.2, "buzz", 0.18)
            s(5.5, "pop_big", 0.45)
            s(6.7, "ding", 0.5)
        else:
            s(1.9, "dingdong", 0.45)
            s(2.25, "slide", 0.5)
            s(3.1, "pop_big", 0.5)
            s(3.25, "beep", 0.4)
            s(4.2, "thud", 0.25)
            for k, _ in enumerate(self.taps):
                tt = 4.6 + k * 0.4
                s(tt, "tick", 0.35)
                s(tt + 0.05, "beep", 0.2)
            s(6.2, "flutter", 0.4)
            s(6.5, "fail", 0.22)

    # ---- helpers
    def installed(self, t):
        """Gegenstände, die schon im linken Zimmer stehen."""
        items = [m for m in self.cfg["_prev_items"]]
        if not self.final and t >= 4.2 and self.item in ITEM_INSTALL:
            items.append(self.item)
        return items

    def zoom_at(self, t):
        if not self.zoom:
            return 1.0, (540, 960)
        side, a, b = self.zoom
        z = 1 + 0.32 * smooth((t - a) / 0.5) * (1 - smooth((t - b + 0.5) / 0.5))
        cx = 300 if side == "L" else 790
        return z, (cx, 1060)

    # ---- draw
    def draw(self, c, t, gt):
        c.alpha_composite(self.base)
        d = ImageDraw.Draw(c)
        self.draw_window_fx(d, gt)
        self.draw_left(c, t)
        c.alpha_composite(self.dark, (ROOMS["L"], CEIL))
        if self.final and t > 4.0:
            fl = 0.5 + 0.5 * math.sin(t * 23) * math.sin(t * 7.3)
            if fl > 0.6:
                c.alpha_composite(room_overlay("L", (0, 0, 0), 60), (ROOMS["L"], CEIL))
        c.alpha_composite(self.warm, (ROOMS["R"], CEIL))
        self.draw_right(c, t)
        self.draw_hud(c, t)

    def draw_window_fx(self, d, gt):
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
                elif sty in ("stars", "sun") and v < 0.55:
                    b = int(150 + 100 * math.sin(gt * sp * 3 + u * 9))
                    x, y = wx0 + u * (wx1 - wx0), wy0 + v * 0.6 * (wy1 - wy0)
                    d.ellipse((x - 1.6, y - 1.6, x + 1.6, y + 1.6), fill=(b, b, min(255, b + 20)))

    def draw_door(self, d, x0, open_):
        dx0, dx1 = x0 + DOOR[0], x0 + DOOR[1]
        d.rectangle((dx0, FL - 298, dx1, FL - 10), fill=(14, 12, 16))
        wdt = (dx1 - dx0) * (1 - 0.82 * open_)
        d.rectangle((dx0, FL - 298, dx0 + wdt, FL - 10), fill=(120, 86, 64), outline=OUT, width=4)
        if open_ < 0.5:
            d.ellipse((dx0 + wdt - 22, FL - 160, dx0 + wdt - 10, FL - 148), fill=GOLD)

    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        final = self.final
        F0 = FL - 10

        def hp(dx, h):
            return (fx + dx * S, F0 - h * S)

        door_open = 0 if final else smooth((t - 1.95) / 0.25) * (1 - smooth((t - 2.85) / 0.25))
        self.draw_door(d, x0, door_open)
        for it in self.installed(t):
            if it not in ITEM_INSTALL:
                continue
            _, lx, ly = ITEM_INSTALL[it]
            if it == "tv":
                draw_tv(d, x0 + lx, ly)
            elif it == "sneakers":
                draw_sneaker(d, x0 + lx, ly)
            elif it == "console":
                draw_console(d, x0 + lx, ly)
            elif it == "bags":
                draw_bags(d, x0 + lx, ly, 1.2)
        n_pile = self.i + (1 if (not final and t >= 4.2) else 0)
        for k in range(min(n_pile, len(PILE))):
            px, row = PILE[k]
            draw_box(d, x0 + px, F0 - row * BOX_H, BOX_W, BOX_H)
        fx = x0 + 245
        look, mood, hands, sit, head_drop, lean = 0.0, 0.0, [None, None], 0.0, 0.0, 0.0
        has_watch = "watch" in self.cfg["_prev_items"] or (self.item == "watch" and t > 4.2)
        catch_h = 195
        env_y = None
        if 0.55 < t < 1.75:
            p = ease_out_cubic(seg(t, 0.55, 1.2))
            env_y = lerp(CEIL + 30, F0 - catch_h * S, p)
            hands[1] = hp(40, lerp(130, catch_h - 10, seg(t, 0.85, 1.2)))
            mood = 0.6 if t > 1.2 else 0
        if not final:
            if 2.2 < t < 4.4:
                bx = lerp(x0 + 70, x0 + 140, ease_out_cubic(seg(t, 2.2, 2.9)))
                by = F0
                if t > 3.5:
                    k = seg(t, 3.5, 4.2)
                    px, row = PILE[min(self.i, len(PILE) - 1)]
                    bx = lerp(bx, x0 + px, smooth(k))
                    by = F0 - row * BOX_H * smooth(k) - math.sin(math.pi * k) * 70
                if t < 4.2:
                    draw_box(d, bx, by, BOX_W, BOX_H, flaps=smooth(seg(t, 3.0, 3.2)) * (1 - smooth(seg(t, 3.45, 3.55))))
            if 2.9 < t < 4.4:
                look = -1
                hands[0] = hp(-55, 100) if t < 3.5 else None
                mood = 0.8 if t > 3.2 else 0.3
            if 3.05 < t < 4.3 and self.item:
                p = ease_out_back(seg(t, 3.05, 3.45))
                ix, iy = x0 + 140, F0 - BOX_H - 10 - 90 * p
                if t > 3.6 and self.item in ITEM_INSTALL:
                    q = smooth(seg(t, 3.6, 4.2))
                    _, lx, ly = ITEM_INSTALL[self.item]
                    ix, iy = lerp(ix, x0 + lx, q), lerp(iy, ly, q)
                self.draw_item(d, ix, iy, max(0.2, p))
            if 4.4 < t < 5.9:
                look = 0.5
                hands[1] = hp(30, 200)
                mood = 0.5
            if 5.8 < t < 7.6:
                look = 1
                hands[1] = hp(52, 140)
            mood = mood if t < 6.3 else -0.8
            head_drop = smooth(seg(t, 6.6, 7.4)) * min(1, 0.3 + self.i * 0.12)
        else:
            if 1.8 < t < 2.6:
                hands[1] = hp(50, 150)
                mood = 0.4
            n = sum(1 for k in range(3) if t > 2.6 + k * 0.18)
            if n:
                draw_gifts(d, x0 + 120, F0, n)
            mood = -0.8 if t > 3.3 else mood
            sit = smooth(seg(t, 3.7, 4.4))
            head_drop = sit
            look = -0.3 if sit > 0.5 else look
            lean = 0.25 * sit
        info = person(d, fx, F0, lean, tuple(hands), sit=sit, mood=mood, look=look, head_drop=head_drop,
                      watch=has_watch)
        head_top = info["head"][1] - 48 * S
        if env_y is not None:
            if t < 1.2:
                draw_envelope(c, d, fx + 40 * S, env_y, S)
            else:
                h = info["hands"][1]
                draw_envelope(c, d, h[0], h[1] - 34, S * (1 - smooth(seg(t, 1.5, 1.75))))
                self.float_text(c, "+$3,000", GOLD, fx, head_top - 40, t - 1.2)
        if not final:
            if 3.25 < t < 4.6:
                self.float_text(c, self.price, RED, x0 + 150, head_top - 30, t - 3.25, big=True)
            if 4.4 < t < 5.9:
                h = info["hands"][1]
                draw_phone(d, h[0] + 6, h[1] - 22, S)
                for k, tx in enumerate(self.taps):
                    tt = 4.6 + k * 0.4
                    if t > tt:
                        self.float_text(c, tx, RED, fx + 80 + (k % 2) * 50, head_top - 10 - k * 12, t - tt)
            if 5.8 < t < 7.6:
                h = info["hands"][1]
                draw_wallet(d, h[0] + 18, h[1], open_=smooth(seg(t, 6.0, 6.25)))
            if 6.15 < t < 8.4:
                k = t - 6.15
                draw_moth(d, fx + 90 + k * 60 + math.sin(k * 6) * 30, F0 - 190 * S - k * 210, k * 30)
        else:
            if 1.8 < t < 2.7:
                h = info["hands"][1]
                draw_card(d, h[0] + 12, h[1] - 8)
            if 2.35 < t < 3.9:
                self.float_text(c, self.price, RED, x0 + 150, CEIL + 190, t - 2.35, big=True)

    def draw_item(self, d, x, y, s):
        it = self.item
        if it == "tv":
            draw_tv(d, x, y)
        elif it == "sneakers":
            draw_sneaker(d, x, y + 20, s)
        elif it == "phone":
            draw_phone(d, x, y, 1.4 * s)
        elif it == "console":
            draw_console(d, x, y + 20)
        elif it == "watch":
            draw_watch(d, x, y, s)
        elif it == "bags":
            draw_bags(d, x, y + 40, s)

    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        F0 = FL - 10
        self.draw_door(d, x0, 0)
        grow_now = self.i % 2 == 0 and t > 4.6
        ps = 0.35 + 0.12 * self.i + (0.12 * smooth(seg(t, 4.6, 5.3)) if grow_now else 0)
        draw_plant(d, x0 + 330, SHELF[2], ps)
        nb = 1 + (self.i + 1) // 2 + (1 if (self.i % 2 == 1 and t > 4.75) else 0)
        draw_books(d, x0 + 375, SHELF[2], nb)
        level_now = self.value_right(t) / max(1, self.cfg["_max_saved"])
        glow = smooth(seg(t, 3.9, 4.6)) * (0.75 + 0.25 * math.sin(t * 4)) if self.final else 0.0
        jar_cx = x0 + 405
        d = draw_jar(c, d, jar_cx, F0, level_now, glow)
        home, jar_x = x0 + 215, x0 + 285
        fx, look, hands, mood, walk = home, 0.0, [None, None], 0.45, 0.0

        def hp(dx, h):
            return (fx + dx * S, F0 - h * S)

        if 0.55 < t < 1.75:
            hands[0] = hp(-40, lerp(130, 185, seg(t, 0.85, 1.2)))
            mood = 0.7 if t > 1.2 else 0.3
        if 1.9 < t < 2.6:
            fx = lerp(home, jar_x, smooth(seg(t, 1.9, 2.6)))
            walk = (t - 1.9) * 14
            look = 1
        elif 2.6 <= t < 3.95:
            fx = jar_x
            look = 1
            hands[1] = hp(62, 205)
            mood = 0.8
        elif 3.95 <= t < 4.5:
            fx = lerp(jar_x, home, smooth(seg(t, 3.95, 4.5)))
            walk = (t - 3.95) * 14
            look = -0.5
        elif t >= 4.5:
            fx = home
            if t < 5.4:
                look = 1
                hands[1] = (x0 + 318, SHELF[2] - 34)
            else:
                look = 0.2
                hands = [hp(-28, 150), hp(28, 150)]
                mood = 0.6
        info = person(d, fx, F0, 0.0, tuple(hands), walk=walk, mood=mood, look=look,
                      head_drop=0.35 if t >= 5.4 else 0.0)
        head_top = info["head"][1] - 48 * S
        if 0.55 < t < 1.75:
            if t < 1.2:
                p = ease_out_cubic(seg(t, 0.55, 1.2))
                draw_envelope(c, d, home - 40 * S, lerp(CEIL + 30, F0 - 195 * S, p), S)
            else:
                h = info["hands"][0]
                draw_envelope(c, d, h[0], h[1] - 34, S * (1 - smooth(seg(t, 1.5, 1.75))))
                self.float_text(c, "+$3,000", GOLD, home, head_top - 40, t - 1.2)
        hand = (jar_x + 62 * S, F0 - 205 * S)
        for k in range(5):
            ta = 2.6 + k * 0.22
            p = seg(t, ta, ta + 0.2)
            if 0 < p < 1:
                cx = lerp(hand[0], jar_cx, p)
                cy = lerp(hand[1], F0 - 150, p) - math.sin(math.pi * p) * 40
                draw_coin(d, cx, cy)
        if t >= 5.4:
            draw_book_open(d, fx, F0 - 158 * S)
        if 2.65 < t < 4.3 and self.saved > self.prev:
            self.float_text(c, f"+${self.saved - self.prev:,}", GREEN, jar_cx, F0 - 230, t - 2.65)

    def value_right(self, t):
        return lerp(self.prev, self.saved, smooth(seg(t, 2.6, 3.8)))

    def float_text(self, c, text, color, x, y, k, big=False):
        if k < 0:
            return
        a = clamp(k * 6) * (1 - smooth((k - 1.0) / 0.4))
        if a <= 0:
            return
        spr = sprite(text, 58 if big else 42, color)
        paste_scaled(c, spr, x, y - k * 55, 0.6 + 0.4 * ease_out_back(clamp(k * 4)), a)

    def calendar_sprite(self, t):
        w, h = 300, 230
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        x0, y0, x1, y1 = 30, 30, 270, 200
        d.rounded_rectangle((x0, y0, x1, y1), 16, fill=(244, 241, 234), outline=OUT, width=5)
        d.rounded_rectangle((x0, y0, x1, y0 + 46), 16, fill=(205, 62, 76), outline=OUT, width=5)
        d.rectangle((x0 + 4, y0 + 28, x1 - 4, y0 + 44), fill=(205, 62, 76))
        for ox in (-70, 70):
            d.rounded_rectangle((150 + ox - 8, y0 - 18, 150 + ox + 8, y0 + 18), 6, fill=(200, 200, 210), outline=OUT, width=3)
        pop = ease_out_back(seg(t, 0.0, 0.35)) if self.i == 0 else 1
        paste_scaled(img, sprite(self.m, 92, (32, 32, 40)), 150, (y0 + 46 + y1) / 2 + 4, pop, 1)
        if self.i > 0 and t < 0.6:
            k = smooth(t / 0.55)
            hgt = (y1 - y0 - 46) * (1 - k)
            top = y0 + 46
            if hgt > 2:
                d = ImageDraw.Draw(img)
                d.rectangle((x0 + 4, top, x1 - 4, top + hgt), fill=(250, 248, 242), outline=(180, 175, 165), width=2)
                spr = sprite(self.cfg["_prev_month"], 92, (32, 32, 40))
                sp = spr.resize((spr.width, max(1, int(spr.height * max(0.05, 1 - k)))))
                paste_scaled(img, sp, 150, top + hgt / 2, 1, 1 - k)
        return img

    def draw_hud(self, c, t):
        fade = 1 - (smooth(seg(t, 5.0, 5.35)) if self.final else 0)
        if fade > 0:
            paste_scaled(c, self.calendar_sprite(t), 540, 330, 1, fade)
            paste_scaled(c, sprite(spaced("SAME SALARY"), 34, (170, 170, 186), F_BOLD), 540, 466, 1, fade)
        if self.final:
            a1 = ease_out_back(seg(t, 5.4, 5.8))
            a2 = ease_out_back(seg(t, 6.6, 7.0))
            if a1 > 0:
                paste_scaled(c, sprite(self.cfg["punch1"], 64, (245, 245, 250)), 540, 330, 0.7 + 0.3 * a1, clamp(a1 * 2))
            if a2 > 0:
                paste_scaled(c, sprite(self.cfg["punch2"], 78, GOLD), 540, 425, 0.7 + 0.3 * a2, clamp(a2 * 2))
        for room, val, col in (("L", self.value_left(t), RED), ("R", self.value_right(t), GREEN)):
            cxr = ROOMS[room] + RW / 2
            paste_scaled(c, sprite(spaced("SAVED"), 30, (150, 150, 166), F_BOLD), cxr, 1414, 1, 1)
            txt = (f"-${abs(val):,.0f}" if val < 0 else f"${val:,.0f}")
            colr = col if (room == "R" or val < 0) else (235, 235, 240)
            shake = 0
            if room == "L" and not self.final and 6.2 < t < 6.8:
                shake = math.sin(t * 70) * 6
                colr = RED
            paste_scaled(c, sprite(txt, 72, colr), cxr + shake, 1474, 1, 1)
        if self.cfg.get("_watermark"):
            paste_scaled(c, sprite(self.cfg["_watermark"], 30, (130, 130, 145), F_SEMI), 540, 1534, 1, 0.8)

    def value_left(self, t):
        if self.final:
            return -int(self.cfg.get("debt", 0)) if t > 3.3 else 0
        return 0


# ----------------------------------------------------------------- audio (nur Effekte)
def build_lib(rng):
    lib = extra_sfx(build_sfx(rng), rng)

    def nz(n):
        return rng.normal(0, 1, n)

    n = int(0.22 * SR)
    src = nz(n)
    hp = src - lowpass(src, 1800)
    tt = np.linspace(0, 1, n)
    lib["page"] = hp * np.sin(np.pi * tt) ** 1.2 * 0.7
    n = int(1.3 * SR)
    t = np.arange(n) / SR
    dd = np.zeros(n)
    for f0, st in ((659.3, 0.0), (523.3, 0.42)):
        i0 = int(st * SR)
        tt = t[: n - i0]
        dd[i0:] += (np.sin(2 * np.pi * f0 * tt) + 0.3 * np.sin(2 * np.pi * 2 * f0 * tt)) * np.exp(-tt / 0.35)
    lib["dingdong"] = dd * 0.45
    n = int(0.6 * SR)
    tt = np.linspace(0, 1, n)
    lib["slide"] = lowpass(nz(n), 500) * np.sin(np.pi * tt) * 1.6
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    bp = np.zeros(n)
    for st in (0.0, 0.11):
        i0 = int(st * SR)
        m = int(0.07 * SR)
        bp[i0:i0 + m] += np.sin(2 * np.pi * 1850 * t[:m]) * np.minimum(1, (m - np.arange(m)) / 200)
    lib["beep"] = bp * 0.4
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    lib["flutter"] = lowpass(nz(n), 2200) * (0.5 + 0.5 * np.sin(2 * np.pi * 24 * t)) * np.exp(-t / 0.5) * 0.7
    n = int(0.28 * SR)
    src = nz(n)
    tt = np.linspace(0, 1, n)
    lib["swipe"] = (src - lowpass(src, 900)) * np.sin(np.pi * tt) ** 2 * 0.8
    return lib


def build_audio(months, dur, path, seed):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    lib = build_lib(rng)
    fx = np.zeros(n)
    for mo in months:
        for t, name, g in mo.ev:
            i = int((mo.start + t) * SR)
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
    months, t, prev_saved, prev_items, prev_m = [], 0.0, 0, [], None
    n = len(data["months"])
    max_saved = max(m["saved"] for m in data["months"])
    for i, mc in enumerate(data["months"]):
        mc = dict(mc)
        mc["_prev_items"] = list(prev_items)
        mc["_prev_month"] = prev_m
        mc["_max_saved"] = max_saved
        mc["_watermark"] = data.get("watermark", "")
        if i == n - 1:
            mc.setdefault("punch1", data.get("punch1", ""))
            mc.setdefault("punch2", data.get("punch2", ""))
        mo = Month(i, mc, t, prev_saved, n)
        months.append(mo)
        t += mo.dur
        prev_saved = mc["saved"]
        if mc.get("item") in ITEM_INSTALL or mc.get("item") == "watch":
            prev_items.append(mc["item"])
        prev_m = mc["month"]
    return months, t


def render_frame(months, mi, gt, dur):
    mo = months[mi]
    lt = gt - mo.start
    c = Image.new("RGBA", (W, H))
    mo.draw(c, lt, gt)
    z, (cx, cy) = mo.zoom_at(lt)
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
    months, dur = build(data)
    nframes = int(round(dur * FPS))
    os.makedirs(OUT_DIR, exist_ok=True)
    wav = os.path.join(OUT_DIR, f".{name}.wav")
    mp4 = os.path.join(OUT_DIR, f"{name}.mp4")
    build_audio(months, dur, wav, seed)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
           "-movflags", "+faststart", "-t", f"{dur:.3f}", mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    mi = 0
    cover_t = months[-1].start + 8.0
    for fi in range(nframes):
        gt = fi / FPS
        while mi < len(months) - 1 and gt >= months[mi].start + months[mi].dur:
            mi += 1
        arr = render_frame(months, mi, gt, dur)
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
