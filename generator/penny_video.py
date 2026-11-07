#!/usr/bin/env python3
"""
"Penny Doubling" – $1,000,000 sofort vs. 1 Cent, der sich 30 Tage lang täglich verdoppelt.
Links: Million sofort, feiert, lacht. Rechts: 1 Cent ... x2 ... x2 ... und dann explodiert der Geldberg.

    python3 generator/penny_video.py skripte/zimmer/12_penny_doubling.json
"""
import math
import os
import random
import sys

import numpy as np
from PIL import ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import SR, clamp, ease_out_back, ease_out_cubic, lowpass  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, ROOMS, RW, paste_scaled, radial, seg, sprite  # noqa: E402
from wecker_video import person_fat  # noqa: E402
from zz_base import StageBase, fit_sprite, run  # noqa: E402

S = 1.15
F0 = FL - 10
FIG_X = 405
PILE_X0, PILE_X1 = 22, 330
BUNDLE_W, BUNDLE_H = 42, 15
MAX_ROWS = 46
MILLION = 1_000_000
GLOW = radial(300, GOLD, 130)


def cents(v):
    return f"${v:,.2f}"


def val(day):
    return 0.01 * 2 ** (day - 1)


# ----------------------------------------------------------------- Geld zeichnen
def draw_bundle(d, x, y):
    d.rectangle((x, y - BUNDLE_H, x + BUNDLE_W - 2, y), fill=(118, 196, 128), outline=(30, 70, 40), width=2)
    d.rectangle((x + BUNDLE_W / 2 - 6, y - BUNDLE_H, x + BUNDLE_W / 2 + 4, y), fill=(240, 236, 220))


def draw_coin(d, x, y, r=9):
    d.ellipse((x - r, y - r * 0.55, x + r, y + r * 0.55), fill=(222, 160, 70), outline=(120, 70, 20), width=2)


def draw_bill(d, x, y, ang=0.0, s=1.0):
    w, h = 40 * s, 20 * s
    ca, sa = math.cos(ang), math.sin(ang)
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    d.polygon([(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts], fill=(130, 205, 140), outline=(30, 70, 40))


def draw_money(d, x0, v, y_floor=F0):
    """Geldberg je nach Betrag: Münzen < $100, Scheine < $10k, Bündel ab $10k."""
    if v <= 0:
        return y_floor
    width = PILE_X1 - PILE_X0
    if v < 100:
        n = max(1, int(round(v)))
        n = min(n, 60)
        for k in range(n):
            cx = x0 + PILE_X0 + 30 + (k % 12) * 22 + (k // 12 % 2) * 11
            cy = y_floor - 6 - (k // 12) * 8
            draw_coin(d, cx, cy)
        return y_floor - 10 - (n // 12) * 8
    if v < 10_000:
        n = int(v // 100)
        cols = 5
        top = y_floor
        for k in range(n):
            col = k % cols
            row = k // cols
            bx = x0 + PILE_X0 + 20 + col * 50
            by = y_floor - row * 6
            d.rectangle((bx, by - 8, bx + 44, by), fill=(130, 205, 140), outline=(30, 70, 40), width=1)
            top = min(top, by - 8)
        return top
    n = int(v // 10_000)
    per_row = width // BUNDLE_W
    rows = min(MAX_ROWS, math.ceil(n / per_row))
    top = y_floor
    k = 0
    for r in range(rows):
        in_row = min(per_row, n - k)
        if in_row <= 0:
            break
        off = (r % 2) * BUNDLE_W / 2
        start = x0 + PILE_X0 + off + (per_row - in_row) * BUNDLE_W / 2
        for j in range(in_row):
            if start + j * BUNDLE_W + BUNDLE_W > x0 + PILE_X1 + BUNDLE_W / 2:
                continue
            draw_bundle(d, start + j * BUNDLE_W, y_floor - r * BUNDLE_H)
        k += in_row
        top = y_floor - (r + 1) * BUNDLE_H
    return top


def draw_crown(d, x, y, s=1.0):
    pts = [(-30, 0), (30, 0), (34, -30), (16, -12), (0, -38), (-16, -12), (-34, -30)]
    d.polygon([(x + px * s, y + py * s) for px, py in pts], fill=GOLD, outline=OUT)
    for px in (-34, 0, 34):
        d.ellipse((x + px * s - 5 * s, y - (30 if px else 38) * s - 5 * s, x + px * s + 5 * s, y - (30 if px else 38) * s + 5 * s), fill=(240, 80, 90))


def draw_sign(c, x, y, text, color):
    spr = fit_sprite(text, 30, color, 200)
    d = ImageDraw.Draw(c)
    w = max(spr.width - 20, 120)
    d.rectangle((x - w / 2, y - 30, x + w / 2, y + 30), fill=(30, 28, 34), outline=(210, 205, 195), width=5)
    paste_scaled(c, spr, x, y, 1, 1)


def draw_briefcase(d, x, y, open_):
    d.rounded_rectangle((x - 60, y - 70, x + 60, y), 8, fill=(110, 72, 44), outline=OUT, width=4)
    d.rounded_rectangle((x - 18, y - 84, x + 18, y - 70), 5, outline=OUT, width=5)
    if open_ > 0:
        lid = 70 * open_
        d.polygon([(x - 60, y - 70), (x + 60, y - 70), (x + 60, y - 70 - lid), (x - 60, y - 70 - lid)], fill=(90, 58, 34), outline=OUT)


def draw_champagne(d, x, y, cork_t):
    d.rounded_rectangle((x - 12, y - 70, x + 12, y), 6, fill=(40, 110, 60), outline=OUT, width=3)
    d.rectangle((x - 6, y - 92, x + 6, y - 70), fill=(40, 110, 60), outline=OUT, width=2)
    d.rectangle((x - 12, y - 40, x + 12, y - 22), fill=(240, 220, 160))
    if cork_t >= 0:
        cy = y - 100 - cork_t * 400
        if cork_t < 1:
            d.rectangle((x - 5 + cork_t * 60, cy - 8, x + 5 + cork_t * 60, cy + 4), fill=(200, 160, 100), outline=OUT)
        if cork_t < 1.2:
            for k in range(6):
                r = 6 + k * 3 * min(1, cork_t * 3)
                d.ellipse((x - r + k * 4, y - 100 - k * 14 * min(1, cork_t * 3) - r, x + r + k * 4, y - 100 - k * 14 * min(1, cork_t * 3) + r), fill=(250, 250, 240))


# ----------------------------------------------------------------- stage
class Stage(StageBase):
    warm_room = "R"

    def setup(self):
        c = self.cfg
        self.day = c["day"]
        self.label = str(self.day)
        self.prev_day = c["_prev_day"]
        k = 0 if self.prev_day is None else self.day - self.prev_day
        self.k = k
        span = 4.0
        self.pops = [1.0 + (j + 1) * span / max(1, k) - (span / max(1, k)) * 0.5 for j in range(k)]
        self.v_start = val(self.prev_day) if self.prev_day else val(1)
        self.v_end = val(self.day)
        self.cross_t = None
        for j, tp in enumerate(self.pops):
            if self.v_start * 2 ** j < MILLION <= self.v_start * 2 ** (j + 1):
                self.cross_t = tp
        self.right_leads_before = self.v_start > MILLION
        rnd = random.Random(self.i * 17 + 3)
        self.rain = [(rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(0.7, 1.4), rnd.uniform(0, 6)) for _ in range(24)]

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        for j, tp in enumerate(self.pops):
            s(tp, f"note{min(7, j if self.k < 8 else int(j * 8 / self.k))}", 0.5)
            s(tp, "pop", 0.25)
            if self.v_start * 2 ** (j + 1) >= 10_000:
                s(tp + 0.05, "clink", 0.3)
        if self.cross_t:
            s(self.cross_t + 0.2, "whoosh", 0.45)
            s(self.cross_t + 0.55, "ding", 0.6)
            s(self.cross_t + 0.7, "gasp", 0.5)
        if self.i == 0:
            s(0.55, "thud", 0.6)
            s(1.0, "cash", 0.6)
            s(1.0, "sparkle", 0.4)
            s(4.6, "cork", 0.55)
            s(2.6, "tick", 0.35)
        elif self.i <= 3:
            s(5.6, "laugh", 0.5)
            s(6.3, "laugh", 0.4)
            s(3.0, "cash", 0.25)
        elif self.i == 4:
            s(6.0, "gasp", 0.35)
        if self.final:
            s(5.4, "cash", 0.5)
            s(6.0, "sparkle", 0.5)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def right_value(self, t):
        v = self.v_start
        for tp in self.pops:
            if t >= tp:
                v *= 2
        return v

    def leader_right(self, t):
        if self.right_leads_before:
            return True
        return self.cross_t is not None and t >= self.cross_t + 0.55

    # ---- links: $1,000,000 sofort
    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        draw_sign(c, x0 + 130, 900, "$1M TODAY", GOLD)
        d = ImageDraw.Draw(c)
        first = self.i == 0
        if first and t < 1.0:
            p = ease_out_cubic(seg(t, 0.25, 0.55))
            draw_briefcase(d, x0 + 170, lerp(CEIL + 60, F0, p), 0)
        else:
            if first:
                grow = ease_out_back(seg(t, 1.0, 1.6))
                draw_money(d, x0, MILLION * clamp(grow), F0)
                if t < 2.5:
                    draw_briefcase(d, x0 + 170, F0, smooth(seg(t, 0.8, 1.0)))
            else:
                draw_money(d, x0, MILLION, F0)
        fx = x0 + FIG_X
        hands, look, mood, mouth_o, head_drop, shake, bob = [None, None], 0.0, 0.7, False, 0.0, 0.0, 0.0
        if first:
            if 1.5 < t < 4.2:
                ph = (t - 1.5) * 6
                up1, up2 = 0.5 + 0.5 * math.sin(ph), 0.5 - 0.5 * math.sin(ph)
                hands = [(fx - 60 * S, F0 - (150 + 130 * up1) * S), (fx + 60 * S, F0 - (150 + 130 * up2) * S)]
                bob = abs(math.sin(ph)) * 10
                mood = 1.0
            if 4.4 < t < 6.5:
                hands[1] = (fx + 48 * S, F0 - 210 * S)
                mood = 1.0
        elif self.i <= 3:
            if 2.8 < t < 4.6:  # Geld in die Luft werfen
                hands = [(fx - 50 * S, F0 - 270 * S), (fx + 50 * S, F0 - 270 * S)]
                mood = 1.0
            if 5.5 < t < 7.4:  # lacht den Rechten aus
                hands[1] = (fx + 80 * S, F0 - 205 * S)
                look = 1
                mouth_o = int(t * 8) % 2 == 0
                shake = math.sin(t * 40) * 3
                mood = 1.0
        elif self.i == 4:
            look = 1
            mood = 0.0 if t < 5.6 else -0.5
        else:
            look = 1
            mood = -0.8
            if self.cross_t and t > self.cross_t + 0.6:
                mouth_o = True
            if self.final:
                mouth_o = t < 6.0
                head_drop = smooth(seg(t, 6.0, 7.0)) * 0.9
        info = person_fat(d, fx, F0, 0.1, tuple(hands), mood=mood, look=look, mouth_o=mouth_o, head_drop=head_drop,
                          shake=shake, bob=bob, s=S)
        d = ImageDraw.Draw(c)
        if first:
            if 1.0 < t < 2.4:
                e = ease_out_cubic(seg(t, 1.0, 1.8))
                paste_scaled(c, GLOW, x0 + 170, F0 - 120, 0.6 + e, 1 - e)
                d = ImageDraw.Draw(c)
                for k in range(10):
                    a = -math.pi / 2 + (k - 4.5) * 0.25
                    r = e * 260
                    draw_bill(d, x0 + 170 + math.cos(a) * r, F0 - 80 + math.sin(a) * r + e * e * 140, ang=k + t * 4)
            self.float_text(c, "$1,000,000", GOLD, x0 + 200, F0 - 380, t - 1.0, 56, 1.4, 30)
            if 4.4 < t < 6.5:
                h = info["hands"][1]
                draw_champagne(d, h[0] + 6, h[1] + 30, t - 4.6 if t > 4.6 else -1)
        elif self.i <= 3:
            if 2.8 < t < 5.6:
                for u, v, sp, ph in self.rain:
                    k = (t - 2.8) * 0.9 * sp + v
                    if k % 1 < 0.95:
                        y = CEIL + 40 + (k % 1) * (F0 - CEIL - 60)
                        draw_bill(d, x0 + 40 + u * 400 + math.sin(t * 2 + ph) * 20, y, ang=t * 3 + ph, s=0.8)
            if 5.5 < t < 7.6:
                self.float_text(c, "HA HA", (245, 245, 250), fx + 10, info["head"][1] - 100, t - 5.55, 48, 1.4, 20)
        if self.i == 4 and t > 5.6:
            self.float_text(c, "?", (245, 245, 250), fx + 30, info["head"][1] - 100, t - 5.6, 70, 2.0, 10)
        if self.cross_t and t > self.cross_t + 0.6:
            self.float_text(c, "!?", (245, 245, 250), fx + 30, info["head"][1] - 100, t - self.cross_t - 0.6, 70, 2.0, 10)
        if not self.leader_right(t) and not (self.cross_t and self.cross_t < t < self.cross_t + 0.55):
            hx, hy = info["head"]
            draw_crown(d, hx, hy - info["r"] - 6, 1.0)
        self._left_head = info["head"], info["r"]

    # ---- rechts: 1 Cent, verdoppelt
    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        draw_sign(c, x0 + 130, 900, "1¢ x2 DAILY", (130, 220, 160))
        d = ImageDraw.Draw(c)
        v = self.right_value(t)
        last_pop = max([tp for tp in self.pops if tp <= t], default=None)
        top = draw_money(d, x0, v if v >= 1 else 0, F0)
        fx = x0 + FIG_X
        hands, look, mood, head_drop, bob = [None, None], -0.6, 0.0, 0.0, 0.0
        first = self.i == 0
        if first:
            hands[1] = (fx + 32 * S, F0 - 170 * S)
            look = 0.6
            head_drop = 0.3
            mood = 0.0
        else:
            mood = clamp(-0.2 + self.i * 0.25, -1, 1)
            if self.i >= 5:
                ph = (t * 5)
                bob = abs(math.sin(ph)) * (16 if self.final and t > 5.0 else 8)
                if self.final and t > 5.0 or (self.cross_t and t > self.cross_t + 0.55):
                    hands = [(fx - 62 * S, F0 - 285 * S), (fx + 62 * S, F0 - 285 * S)]
                mood = 1.0
        info = person_fat(d, fx, F0, 0.1, tuple(hands), mood=mood, look=look, head_drop=head_drop, bob=bob, s=S)
        d = ImageDraw.Draw(c)
        if first:
            h = info["hands"][1]
            draw_coin(d, h[0] + 4, h[1] - 18, 12)
            self.float_text(c, "1¢", (235, 200, 140), h[0] + 4, h[1] - 60, t - 1.0, 54, 2.0, 15)
        if last_pop is not None:
            k = t - last_pop
            self.float_text(c, "x2", GOLD, x0 + (PILE_X0 + PILE_X1) / 2, min(top, F0 - 30) - 50, k, 62, 0.35, 60)
            if v >= 10_000 and k < 0.3:
                e = k / 0.3
                paste_scaled(c, GLOW, x0 + (PILE_X0 + PILE_X1) / 2, top + 40, 0.5 + e, (1 - e) * 0.8)
                d = ImageDraw.Draw(c)
        # Geldregen am Ende
        if self.final and t > 5.0:
            for u, vv, sp, ph in self.rain:
                kk = (t - 5.0) * 0.8 * sp + vv
                y = CEIL + 30 + (kk % 1) * (F0 - CEIL - 50)
                draw_bill(d, x0 + 30 + u * 420 + math.sin(t * 2 + ph) * 20, y, ang=t * 3 + ph, s=0.85)
        # Krone
        hx, hy = info["head"]
        if self.leader_right(t):
            if self.cross_t and t < self.cross_t + 1.0 and not self.right_leads_before:
                pass
            draw_crown(d, hx, hy - info["r"] - 6 - bob * 0, 1.0)
        elif self.cross_t and self.cross_t < t < self.cross_t + 0.55:
            (lhx, lhy), lr = self._left_head
            p = smooth(seg(t, self.cross_t, self.cross_t + 0.55))
            draw_crown(d, lerp(lhx, hx, p), lerp(lhy - lr - 6, hy - info["r"] - 6, p) - math.sin(math.pi * p) * 160, 1.2)

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, "DAY", self.label, str(self.prev_day) if self.prev_day else None,
                           self.data.get("subtitle", "WHICH WOULD YOU TAKE?"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=64, s2=60)
        lv = MILLION * (clamp(ease_out_back(seg(t, 1.0, 1.6))) if self.i == 0 else 1)
        self.draw_counter(c, "L", "BALANCE", cents(lv) if self.i == 0 and t < 1.6 else "$1,000,000.00",
                          GOLD if not self.leader_right(t) else (235, 235, 240))
        v = self.right_value(t)
        last_pop = max([tp for tp in self.pops if tp <= t], default=None)
        bump = 1 + 0.18 * (1 - smooth((t - last_pop) / 0.25)) if last_pop is not None and t - last_pop < 0.25 else 1
        self.draw_counter(c, "R", "BALANCE", cents(v), GOLD if self.leader_right(t) else GREEN, bump=bump)


# ----------------------------------------------------------------- audio
def build_lib(rng):
    from auto_video import build_lib as car_lib
    lib = car_lib(rng)

    def nz(n):
        return rng.normal(0, 1, n)

    n = int(0.9 * SR)
    t = np.arange(n) / SR
    cork = np.zeros(n)
    m = int(0.03 * SR)
    cork[:m] = nz(m) * 1.5
    fizz = nz(n)
    cork += (fizz - lowpass(fizz, 4000)) * np.exp(-t / 0.35) * 0.4
    lib["cork"] = cork * 0.7
    n = int(0.7 * SR)
    t = np.arange(n) / SR
    la = np.zeros(n)
    for k in range(3):
        a = int(k * 0.2 * SR)
        mm = int(0.13 * SR)
        tt = np.arange(mm) / SR
        f = 230 - k * 15
        voice = np.sign(np.sin(2 * np.pi * f * tt)) * 0.4
        src = lowpass(voice + nz(mm) * 0.3, 1400) - lowpass(voice, 300)
        la[a:a + mm] += src * np.sin(np.pi * tt / tt[-1])
    lib["laugh"] = la * 1.2
    n = int(0.4 * SR)
    t = np.linspace(0, 1, n)
    src = nz(n)
    lib["gasp"] = (lowpass(src, 2500) - lowpass(src, 500)) * t ** 1.5 * np.exp(-((t - 0.75) ** 2) / 0.03) * 1.6
    return lib


def build(data):
    stages, t = [], 0.0
    prev = None
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_day"] = prev
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        prev = sc["day"]
    return stages, t


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p, build, build_lib)
