#!/usr/bin/env python3
"""
"The Wedding" – $30,000 Traumhochzeit vs. $5,000 Hochzeit + $25,000 investiert. 30 Jahre.

    python3 generator/wedding_video.py skripte/zimmer/15_the_wedding.json
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import F_BOLD, SR, clamp, ease_out_back, ease_out_cubic, lowpass, sine_sweep  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, SHELF, WOOD, draw_jar, paste_scaled, radial, seg, sprite  # noqa: E402
from wecker_video import person_fat  # noqa: E402
from auto_video import draw_banknote  # noqa: E402
from zz_base import StageBase, fit_sprite, run  # noqa: E402

F0 = FL - 10
SG, SB = 1.0, 0.95
GX, BX = 175, 268
SUIT = (40, 40, 52)
BRIDE_SHIRT = (226, 112, 146)
HAIR_G0, HAIR_B0, GRAY = (72, 52, 40), (120, 76, 44), (205, 205, 210)
BURST = radial(220, (255, 230, 160), 200)
BUBBLES = ["We'll invest next year!", "Next year. Promise.", "Maybe next year...", "Is it too late now?", "We should have...", "If only..."]


def money(v):
    return f"${v:,.0f}"


def head_y(fy, s, fat=0.1):
    return fy - (84 + 8 + 92 + 36 + 6 * fat) * s


# ----------------------------------------------------------------- props
def draw_arch(d, x0, big):
    cx, top = x0 + (GX + BX) / 2, F0 - (330 if big else 300)
    w = 190 if big else 150
    d.arc((cx - w / 2, top, cx + w / 2, top + w), 180, 360, fill=(240, 236, 228), width=12 if big else 8)
    d.line([(cx - w / 2, top + w / 2), (cx - w / 2, F0)], fill=(240, 236, 228), width=12 if big else 8)
    d.line([(cx + w / 2, top + w / 2), (cx + w / 2, F0)], fill=(240, 236, 228), width=12 if big else 8)
    cols = [(255, 120, 150), (255, 200, 210), (250, 240, 245), (240, 90, 120)]
    n = 16 if big else 6
    for k in range(n):
        a = math.pi + math.pi * k / (n - 1)
        fx_, fy_ = cx + math.cos(a) * w / 2, top + w / 2 + math.sin(a) * w / 2
        r = 14 if big else 10
        d.ellipse((fx_ - r, fy_ - r, fx_ + r, fy_ + r), fill=cols[k % 4], outline=OUT, width=2)


def draw_string_lights(d, x0, t):
    pts = []
    for k in range(13):
        u = k / 12
        pts.append((x0 + 20 + u * 436, CEIL + 70 + math.sin(math.pi * u) * 40))
    d.line(pts, fill=(60, 60, 70), width=3)
    for k, (px, py) in enumerate(pts[1:-1]):
        on = 0.6 + 0.4 * math.sin(t * 5 + k)
        col = (int(255 * on), int(220 * on), int(140 * on))
        d.ellipse((px - 7, py + 2, px + 7, py + 16), fill=col)


def draw_cake(d, x, y, tiers):
    w0 = 90 if tiers > 1 else 64
    for k in range(tiers):
        w = w0 - k * 22
        h = 34
        top = y - (k + 1) * h
        d.rectangle((x - w / 2, top, x + w / 2, top + h), fill=(252, 248, 240), outline=OUT, width=3)
        d.line([(x - w / 2 + 4, top + 8), (x + w / 2 - 4, top + 8)], fill=(255, 170, 190), width=4)
    tt = y - tiers * 34
    d.ellipse((x - 6, tt - 12, x + 6, tt), fill=(255, 120, 150))


def draw_table(d, x, w=90):
    d.rectangle((x - w / 2, F0 - 82, x + w / 2, F0 - 70), fill=(250, 250, 248), outline=OUT, width=3)
    d.polygon([(x - w / 2, F0 - 70), (x + w / 2, F0 - 70), (x + w / 2 + 6, F0), (x - w / 2 - 6, F0)], fill=(245, 240, 236), outline=OUT)


def draw_small_cake(d, x, y, flame):
    d.rectangle((x - 30, y - 30, x + 30, y), fill=(250, 240, 230), outline=OUT, width=3)
    d.line([(x - 26, y - 22), (x + 26, y - 22)], fill=(255, 150, 180), width=4)
    d.rectangle((x - 3, y - 50, x + 3, y - 30), fill=(120, 190, 255))
    if flame > 0.05:
        d.ellipse((x - 5 * flame, y - 66, x + 5 * flame, y - 50), fill=(255, 200, 70))


def draw_photo(d, x0, fancy):
    if fancy:
        d.rectangle((x0 + 26, 848, x0 + 136, 958), fill=GOLD, outline=OUT, width=3)
        d.rectangle((x0 + 36, 858, x0 + 126, 948), fill=(60, 70, 110))
    else:
        d.rectangle((x0 + 30, 860, x0 + 110, 940), fill=WOOD, outline=OUT, width=3)
        d.rectangle((x0 + 38, 868, x0 + 102, 932), fill=(60, 70, 110))
    cx = x0 + (81 if fancy else 70)
    for dx in (-14, 14):
        d.ellipse((cx + dx - 9, 878, cx + dx + 9, 896), fill=(246, 246, 250))
        d.rectangle((cx + dx - 11, 898, cx + dx + 11, 930), fill=(40, 40, 52) if dx < 0 else (250, 250, 252))


def draw_bubble(c, x, y, text, a):
    if a <= 0.02:
        return
    spr = fit_sprite(text, 32, (32, 32, 40), 360, F_BOLD)
    w, h = spr.width - 20, 64
    img = Image.new("RGBA", (int(w + 20), 100), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, img.width - 4, 4 + h), 22, fill=(250, 250, 252), outline=OUT, width=4)
    d.polygon([(img.width / 2 - 14, 4 + h - 2), (img.width / 2 + 14, 4 + h - 2), (img.width / 2 - 20, 4 + h + 24)], fill=(250, 250, 252), outline=OUT)
    d.line([(img.width / 2 - 12, 4 + h - 3), (img.width / 2 + 12, 4 + h - 3)], fill=(250, 250, 252), width=5)
    paste_scaled(img, spr, img.width / 2, 4 + h / 2, 1, 1)
    paste_scaled(c, img, x, y, 0.6 + 0.4 * a, clamp(a * 2))


def draw_heart(d, x, y, r, col=(255, 80, 120)):
    d.ellipse((x - r, y - r * 0.9, x, y + r * 0.1), fill=col)
    d.ellipse((x, y - r * 0.9, x + r, y + r * 0.1), fill=col)
    d.polygon([(x - r * 0.98, y - r * 0.25), (x + r * 0.98, y - r * 0.25), (x, y + r)], fill=col)


def draw_couple(c, d, x0, t, age, wedding, hug, cake=None, flame=1.0, mood=0.8):
    gx, bx = x0 + GX, x0 + BX
    hair_g = tuple(int(lerp(a, b, age)) for a, b in zip(HAIR_G0, GRAY))
    hair_b = tuple(int(lerp(a, b, age)) for a, b in zip(HAIR_B0, GRAY))
    hy_b = head_y(F0, SB)
    if wedding:  # Schleier hinter dem Kopf
        d.polygon([(bx + 4, hy_b - 30), (bx + 54, hy_b + 10), (bx + 60, hy_b + 150), (bx - 10, hy_b + 40)], fill=(240, 244, 250), outline=(200, 205, 215))
    hands_g, hands_b = [None, None], [None, None]
    lean = 0.0
    if hug > 0:
        hands_g[1] = (lerp(gx + 30, bx - 10, hug), F0 - 190 * SG)
        hands_b[0] = (lerp(bx - 30, gx + 10, hug), F0 - 185 * SB)
        lean = 0.12 * hug
    if cake is not None:
        cx = (gx + bx) / 2
        hands_g[1] = (cx - 26, F0 - 150)
        hands_b[0] = (cx + 26, F0 - 150)
    ig = person_fat(d, gx + 8 * hug, F0, 0.1, tuple(hands_g), mood=mood, look=0.5 + 0.5 * hug, s=SG,
                    shirt=SUIT if wedding else (80, 118, 235), hair=hair_g, lean=lean)
    ib = person_fat(d, bx - 8 * hug, F0, 0.1, tuple(hands_b), mood=mood, look=-0.5 - 0.5 * hug, s=SB,
                    shirt=(250, 250, 252) if wedding else BRIDE_SHIRT, long_hair=hair_b, lean=-lean)
    if wedding:
        hipy = F0 - 92 * SB
        d.polygon([(bx - 26, hipy - 50), (bx + 26, hipy - 50), (bx + 62, F0), (bx - 62, F0)], fill=(252, 252, 255), outline=OUT)
        hx, hy = ig["head"]
        d.polygon([(hx - 14, hy + ig["r"] + 8), (hx, hy + ig["r"] + 14), (hx - 14, hy + ig["r"] + 20)], fill=(20, 20, 24))
        d.polygon([(hx + 14, hy + ig["r"] + 8), (hx, hy + ig["r"] + 14), (hx + 14, hy + ig["r"] + 20)], fill=(20, 20, 24))
        bh = ib["hands"][1]
        for k, col in enumerate(((255, 120, 150), (255, 220, 230), (250, 90, 120))):
            d.ellipse((bh[0] - 10 + k * 8, bh[1] - 14, bh[0] + 6 + k * 8, bh[1] + 2), fill=col, outline=OUT, width=1)
    else:
        hipy = F0 - 92 * SB
        d.polygon([(bx - 30, hipy - 10), (bx + 30, hipy - 10), (bx + 42, hipy + 45), (bx - 42, hipy + 45)], fill=(150, 80, 120), outline=OUT)
    if cake is not None:
        draw_small_cake(d, (gx + bx) / 2, F0 - 150, flame)
    return ig, ib


# ----------------------------------------------------------------- stage
class Stage(StageBase):
    door = False

    def setup(self):
        c = self.cfg
        self.intro = c.get("intro", False)
        self.label = str(c["label"])
        self.header = c.get("header", "YEAR")
        self.v0, self.v1 = c["_prev_inv"], c["inv"]
        self.maxv = self.data["_max_inv"]
        self.age = c.get("age", 0.0)
        self.bubble = BUBBLES[min(self.i - 1, len(BUBBLES) - 1)] if self.i > 0 else ""
        rnd = random.Random(self.i * 5 + 2)
        self.conf = [(rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(0.7, 1.3), rnd.choice([(255, 120, 150), (255, 220, 120), (150, 210, 255), (255, 255, 255)])) for _ in range(30)]
        self.fireworks = [(4.9, 0.25, 0.25), (5.4, 0.7, 0.2), (5.9, 0.45, 0.3), (6.4, 0.2, 0.22), (6.8, 0.75, 0.28)]

    def schedule(self):
        s = self.sfx
        if self.intro:
            s(0.1, "bells", 0.5)
            for k in range(5):
                s(1.0 + k * 0.7, "cash", 0.35)
            s(1.5, "beep", 0.25)
            s(3.2, "paper", 0.3)
            s(3.45, "clink", 0.5)
            s(3.55, "cash", 0.35)
            s(4.6, "cheer", 0.5)
            for tt, _, _ in self.fireworks:
                s(tt, "firework", 0.4)
            s(7.2, "pop", 0.4)
            s(7.25, "sparkle", 0.4)
            return
        s(0.05, "page", 0.5)
        s(1.0, "clink", 0.4)
        s(1.2, "sparkle", 0.3)
        s(1.3, "pop", 0.3)
        s(3.8, "pop_big", 0.35)
        s(5.9, "swish", 0.4)
        s(6.1, "cheer", 0.25)
        for k in range(3):
            s(6.3 + k * 0.25, "pop", 0.25)
        if self.final:
            s(7.2, "cash", 0.45)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def inv_now(self, t):
        if self.intro:
            return 25000 if t > 3.5 else 0
        return lerp(self.v0, self.v1, smooth(seg(t, 0.6, 2.4)))

    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        if self.intro:
            draw_string_lights(d, x0, t)
            draw_arch(d, x0, True)
            draw_table(d, x0 + 412, 96)
            draw_cake(d, x0 + 412, F0 - 82, 3)
            hug = smooth(seg(t, 7.0, 7.4))
            draw_couple(c, d, x0, t, 0.0, True, hug, mood=1.0)
            d = ImageDraw.Draw(c)
            tags = [("VENUE -$12,000", 1.0), ("FOOD -$9,000", 1.7), ("BAND -$4,000", 2.4), ("DRESS -$3,000", 3.1), ("CAKE -$2,000", 3.8)]
            for k, (txt, tt) in enumerate(tags):
                self.float_text(c, txt, RED, x0 + 150 + (k % 2) * 160, CEIL + 300 + (k % 3) * 70, t - tt, 34, 1.2, 25)
            a = ease_out_back(seg(t, 4.6, 5.0))
            if a > 0:
                paste_scaled(c, sprite("-$30,000", 70, RED), x0 + RW / 2, CEIL + 170, a, clamp(a * 2) * (1 - smooth(seg(t, 8.6, 9.2))))
            for tt, u, v in self.fireworks:
                k = t - tt
                if 0 < k < 1.2:
                    e = ease_out_cubic(k / 1.2)
                    paste_scaled(c, BURST, x0 + 40 + u * 400, CEIL + 120 + v * 300, 0.4 + e, (1 - e) * 0.9)
            if t > 4.6:
                d = ImageDraw.Draw(c)
                for u, v, sp, col in self.conf:
                    k = ((t - 4.6) * 0.5 * sp + v) % 1
                    d.rectangle((x0 + 20 + u * 436 - 4, CEIL + 40 + k * 600 - 3, x0 + 20 + u * 436 + 4, CEIL + 40 + k * 600 + 3), fill=col)
            if t > 7.2:
                self.hearts(c, x0 + (GX + BX) / 2, F0 - 300, t - 7.2)
            return
        draw_photo(d, x0, True)
        self.anniversary(c, d, x0, t, left=True)

    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        glow = smooth(seg(t, 7.2, 7.8)) * (0.75 + 0.25 * math.sin(t * 4)) if self.final else 0
        d = draw_jar(c, d, x0 + 400, SHELF[2], self.inv_now(t) / self.maxv, glow)
        if self.intro:
            draw_arch(d, x0, False)
            draw_table(d, x0 + 412, 70)
            draw_cake(d, x0 + 412, F0 - 82, 1)
            hug = smooth(seg(t, 7.0, 7.4))
            ig, ib = draw_couple(c, d, x0, t, 0.0, True, hug, mood=1.0)
            d = ImageDraw.Draw(c)
            self.float_text(c, "-$5,000", (235, 235, 240), x0 + 230, CEIL + 300, t - 1.5, 44, 1.4, 25)
            p = seg(t, 3.1, 3.45)
            if 0 < p < 1:
                draw_banknote(d, lerp(x0 + 230, x0 + 400, p), lerp(F0 - 220, SHELF[2] - 170, p) - math.sin(math.pi * p) * 80, 1.2)
            self.float_text(c, "+$25,000 INVESTED", GREEN, x0 + 300, SHELF[2] - 220, t - 3.45, 36, 2.0, 20)
            if t > 7.2:
                self.hearts(c, x0 + (GX + BX) / 2, F0 - 300, t - 7.2)
            return
        draw_photo(d, x0, False)
        self.anniversary(c, d, x0, t, left=False)
        if self.v1 > self.v0:
            self.float_text(c, f"+{money(self.v1 - self.v0)}", GREEN, x0 + 400, SHELF[2] - 200, t - 1.0, 42, 1.3)

    def anniversary(self, c, d, x0, t, left):
        cake = None
        flame = 1.0
        if 3.8 < t < 6.4:
            cake = True
            flame = 1 - smooth(seg(t, 5.9, 6.1))
        hug = smooth(seg(t, 6.5, 6.9))
        mood = 0.8
        if left and 1.2 < t < 3.6:
            mood = 0.2 if self.i < 3 else -0.3
        if cake and ease_out_back(seg(t, 3.8, 4.1)) < 0.5:
            cake = None
        draw_couple(c, d, x0, t, self.age, False, hug, cake=cake, flame=flame, mood=mood)
        if left:
            a = smooth(seg(t, 1.2, 1.45)) * (1 - smooth(seg(t, 3.4, 3.7)))
            draw_bubble(c, x0 + GX + 20, F0 - 330, self.bubble, a)
        if t > 6.6:
            self.hearts(c, x0 + (GX + BX) / 2, F0 - 300, t - 6.6)

    def hearts(self, c, x, y, k):
        d = ImageDraw.Draw(c)
        for j in range(3):
            kk = k - j * 0.25
            if 0 < kk < 1.4:
                draw_heart(d, x - 30 + j * 30 + math.sin(kk * 4 + j) * 8, y - kk * 90, 14 * (1 - kk / 2))

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, self.header, self.label, self.cfg.get("_prev_label"), self.data.get("subtitle", "SAME LOVE · SAME $30,000"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=66, s2=72)
        v = self.inv_now(t)
        self.draw_counter(c, "L", "INVESTED", "$0", (235, 235, 240))
        self.draw_counter(c, "R", "INVESTED", money(v), GREEN if v > 0 else (235, 235, 240))


def build_lib(rng):
    from food_video import build_lib as food_lib
    lib = food_lib(rng)

    def nz(n):
        return rng.normal(0, 1, n)

    n = int(2.4 * SR)
    t = np.arange(n) / SR
    bells = np.zeros(n)
    for k, f0 in enumerate((784, 659, 523, 659, 784, 1047)):
        i0 = int(k * 0.32 * SR)
        tt = t[: n - i0]
        bells[i0:] += sum(np.sin(2 * np.pi * f0 * m * tt) * a for m, a in ((1, 1), (2.76, 0.4), (5.4, 0.2))) * np.exp(-tt / 0.6)
    lib["bells"] = bells * 0.25
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    whistle = sine_sweep(600, 1800, 0.4) * 0.3
    fw = np.zeros(n)
    fw[: len(whistle)] += whistle * np.linspace(0.2, 1, len(whistle))
    m = int(0.8 * SR)
    src = nz(m)
    crack = (src - lowpass(src, 1500)) * (rng.random(m) < 0.03) * 3 + lowpass(nz(m), 500) * np.exp(-np.arange(m) / (0.08 * SR)) * 1.5
    fw[int(0.4 * SR):int(0.4 * SR) + m] += crack * np.exp(-np.arange(m) / (0.3 * SR))
    lib["firework"] = fw * 0.6
    n = int(2.0 * SR)
    t = np.arange(n) / SR
    src = nz(n)
    crowd = lowpass(src, 2500) - lowpass(src, 300)
    lib["cheer"] = crowd * np.sin(np.pi * t / t[-1]) ** 1.5 * (0.8 + 0.2 * np.sin(2 * np.pi * 7 * t)) * 0.9
    return lib


def build(data):
    stages, t = [], 0.0
    pv = 0
    prev = None
    data["_max_inv"] = max(s["inv"] for s in data["stages"])
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_inv"], sc["_prev_label"] = pv, prev
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        pv, prev = sc["inv"], str(sc["label"])
    return stages, t


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p, build, build_lib)
