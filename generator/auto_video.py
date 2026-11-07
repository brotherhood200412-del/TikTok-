#!/usr/bin/env python3
"""
"Car on Credit" – Zwei Garagen, gleiche 600 $ im Monat, 6 Jahre.
Links: neues Auto auf Raten (LOAN PAID steigt, Autowert fällt).
Rechts: gebrauchtes Auto bar, 600 $ jeden Monat investiert (PORTFOLIO).

    python3 generator/auto_video.py skripte/zimmer/11_car_on_credit.json
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import SR, clamp, ease_out_back, ease_out_cubic, lowpass, sine_sweep  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, SHELF, draw_jar, paste_scaled, radial, seg, sprite  # noqa: E402
from wecker_video import person_fat  # noqa: E402
from zz_base import StageBase, fit_sprite, run  # noqa: E402

S = 1.15
F0 = FL - 10
LF = F0 - CEIL                 # Boden im Raum-Layer
CAR_X = 25
FIG_X = 412
JAR_X = 400
SPARK = radial(160, (255, 250, 220), 160)


def money(v):
    return f"${v:,.0f}"


# ----------------------------------------------------------------- props (im Raum-Layer, lokale Koordinaten)
def draw_garage_door(d):
    x0, x1, top = 18, 340, LF - 292
    d.rectangle((x0 - 8, top - 8, x1 + 8, LF), fill=(52, 50, 58))
    d.rectangle((x0, top, x1, LF), fill=(132, 134, 146), outline=OUT, width=4)
    yy = top + 36
    while yy < LF - 4:
        d.line([(x0 + 4, yy), (x1 - 4, yy)], fill=(100, 102, 114), width=3)
        yy += 36
    d.rectangle(((x0 + x1) / 2 - 22, LF - 40, (x0 + x1) / 2 + 22, LF - 32), fill=(90, 92, 102))


def draw_car(d, x, kind, dirt=0, scratches=0, rnd_seed=1):
    y = LF
    L = 330
    if kind == "new":
        body, dark, glass = (222, 50, 64), (150, 28, 40), (160, 210, 245)
        roof_top, roof_x = y - 150, (x + 95, x + 120, x + 230, x + 268)
    else:
        body, dark, glass = (120, 156, 146), (84, 110, 102), (150, 180, 190)
        roof_top, roof_x = y - 168, (x + 70, x + 92, x + 238, x + 262)
    a, b, cc, e = roof_x
    d.polygon([(a, y - 98), (b, roof_top), (cc, roof_top), (e, y - 98)], fill=body, outline=OUT)
    d.polygon([(a + 18, y - 100), (b + 10, roof_top + 12), ((b + cc) / 2 - 4, roof_top + 12), ((b + cc) / 2 - 4, y - 100)], fill=glass, outline=OUT)
    d.polygon([((b + cc) / 2 + 4, y - 100), ((b + cc) / 2 + 4, roof_top + 12), (cc - 6, roof_top + 12), (e - 18, y - 100)], fill=glass, outline=OUT)
    d.rounded_rectangle((x, y - 104, x + L, y - 30), 26, fill=body, outline=OUT, width=5)
    d.line([(x + 150, y - 100), (x + 150, y - 40)], fill=dark, width=3)
    d.rectangle((x + 165, y - 78, x + 190, y - 72), fill=dark)
    d.ellipse((x + L - 22, y - 88, x + L - 4, y - 72), fill=(255, 230, 140), outline=OUT, width=2)
    d.rectangle((x + 2, y - 88, x + 14, y - 72), fill=(240, 60, 60), outline=OUT, width=2)
    if kind == "new":
        d.line([(x + 30, y - 92), (x + L - 40, y - 92)], fill=(255, 150, 160), width=4)
    for wx in (x + 78, x + L - 72):
        d.ellipse((wx - 36, y - 68, wx + 36, y + 4), fill=(26, 26, 30), outline=OUT, width=4)
        d.ellipse((wx - 15, y - 47, wx + 15, y - 17), fill=(170, 172, 182))
    import random
    rnd = random.Random(rnd_seed)
    for _ in range(dirt):
        dx, dy = rnd.uniform(20, L - 30), rnd.uniform(-90, -40)
        r = rnd.uniform(5, 11)
        d.ellipse((x + dx - r, y + dy - r * 0.7, x + dx + r, y + dy + r * 0.7), fill=(110, 86, 60))
    for k in range(scratches):
        dx, dy = rnd.uniform(40, L - 60), rnd.uniform(-90, -50)
        d.line([(x + dx, y + dy), (x + dx + 34, y + dy + 10)], fill=(245, 235, 235), width=3)
        d.line([(x + dx + 6, y + dy + 6), (x + dx + 30, y + dy + 14)], fill=(70, 20, 25), width=2)
    if kind == "used":
        for dx, dy in ((40, -50), (290, -46), (120, -40)):
            d.ellipse((x + dx - 7, y + dy - 5, x + dx + 7, y + dy + 5), fill=(150, 96, 50))


def draw_tag(c, x, y, text, color, arrow=False, pop=1.0):
    spr = fit_sprite(text, 38, color, 260)
    w, h = spr.width - 40, 64
    img = Image.new("RGBA", (int(w + 40), 110), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(img.width / 2, 0), (img.width / 2, 22)], fill=(200, 200, 210), width=3)
    d.rounded_rectangle((10, 22, img.width - 10, 22 + h), 12, fill=(248, 246, 240), outline=OUT, width=4)
    paste_scaled(img, spr, img.width / 2, 22 + h / 2, 1, 1)
    paste_scaled(c, img, x, y, pop, 1)
    if arrow:
        d2 = ImageDraw.Draw(c)
        ax, ay = x + img.width / 2 + 10, y + 10
        d2.polygon([(ax - 14, ay - 10), (ax + 14, ay - 10), (ax, ay + 16)], fill=RED, outline=OUT)
        d2.rectangle((ax - 5, ay - 30, ax + 5, ay - 10), fill=RED)


def draw_bill(d, x, y, s=1.0, color=(250, 250, 245), stripe=RED):
    d.rectangle((x - 22 * s, y - 28 * s, x + 22 * s, y + 28 * s), fill=color, outline=OUT, width=3)
    d.rectangle((x - 22 * s, y - 28 * s, x + 22 * s, y - 16 * s), fill=stripe)
    for k in range(3):
        d.line([(x - 14 * s, y - 6 * s + k * 9 * s), (x + 14 * s, y - 6 * s + k * 9 * s)], fill=(160, 160, 165), width=2)


def draw_banknote(d, x, y, s=1.0):
    d.rounded_rectangle((x - 34 * s, y - 18 * s, x + 34 * s, y + 18 * s), 4, fill=(120, 200, 130), outline=OUT, width=3)
    d.ellipse((x - 10 * s, y - 10 * s, x + 10 * s, y + 10 * s), outline=(40, 110, 60), width=3)


def draw_chart(d, x0, y0, x1, y1, p):
    d.rectangle((x0, y0, x1, y1), fill=(22, 26, 34), outline=(210, 205, 195), width=6)
    for k in range(1, 4):
        yy = y0 + (y1 - y0) * k / 4
        d.line([(x0 + 8, yy), (x1 - 8, yy)], fill=(45, 52, 64), width=1)
    if p <= 0.01:
        return
    pts = []
    n = 40
    for i in range(int(n * p) + 1):
        u = i / n
        g = (math.exp(1.6 * u) - 1) / (math.exp(1.6) - 1)
        wig = 0.04 * math.sin(u * 23) * u
        pts.append((x0 + 12 + u * (x1 - x0 - 24), y1 - 12 - (g + wig) * (y1 - y0 - 30)))
    if len(pts) > 1:
        d.line(pts, fill=GREEN, width=5, joint="curve")
        ex, ey = pts[-1]
        d.ellipse((ex - 7, ey - 7, ex + 7, ey + 7), fill=GREEN, outline=OUT, width=2)


def draw_contract(d, x, y, scrib):
    d.rectangle((x - 26, y - 34, x + 26, y + 34), fill=(250, 250, 245), outline=OUT, width=3)
    for k in range(4):
        d.line([(x - 18, y - 22 + k * 10), (x + 18, y - 22 + k * 10)], fill=(170, 170, 175), width=2)
    if scrib > 0:
        pts = [(x - 18 + i * 3, y + 20 + math.sin(i * 1.3) * 5) for i in range(int(12 * scrib) + 1)]
        if len(pts) > 1:
            d.line(pts, fill=(40, 70, 200), width=3)


# ----------------------------------------------------------------- stage
class Stage(StageBase):
    door = False

    def setup(self):
        c = self.cfg
        self.label = c["label"]
        self.header = c.get("header", "YEAR")
        self.intro = c.get("intro", False)
        self.v0, self.v1 = c["_prev_value"], c["value"]
        self.l0, self.l1 = c["_prev_loan"], c["loan"]
        self.p0, self.p1 = c["_prev_port"], c["port"]
        self.maxp = self.data["_max_port"]
        self.bills_t = [0.6, 1.2, 1.8]
        self.t_tag = 5.2
        self.dark = None

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        if self.intro:
            s(0.3, "engine", 0.5)
            s(1.4, "sparkle", 0.5)
            s(0.4, "engine_old", 0.45)
            s(1.9, "scribble", 0.5)
            s(2.25, "beep", 0.3)
            s(1.95, "cash", 0.4)
            s(3.2, "scrub", 0.3)
            return
        for tb in self.bills_t:
            s(tb + 0.33, "paper", 0.4)
            s(tb + 0.38, "fail", 0.12)
            s(tb + 0.55, "clink", 0.35)
        s(3.2, "scrub", 0.3 if self.i <= 2 else 0.0)
        if self.i >= 3:
            s(3.6, "scratch", 0.45)
        s(3.2, "bubbles", 0.35)
        s(self.t_tag, "fail", 0.3)
        s(self.t_tag + 0.05, "beep", 0.2)
        s(5.3, "ding", 0.35)
        if self.final:
            s(6.3, "stamp", 0.5)
            s(6.8, "cash", 0.45)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def value_now(self, t):
        return lerp(self.v0, self.v1, smooth(seg(t, self.t_tag, self.t_tag + 0.4)))

    def loan_now(self, t):
        return lerp(self.l0, self.l1, smooth(seg(t, 0.6, 2.4)))

    def port_now(self, t):
        return lerp(self.p0, self.p1, smooth(seg(t, 0.6, 2.4)))

    def room_layer(self):
        return Image.new("RGBA", (RW, FL - CEIL), (0, 0, 0, 0))

    # ---- links
    def draw_left(self, c, t):
        x0 = ROOMS["L"]
        lay = self.room_layer()
        d = ImageDraw.Draw(lay)
        draw_garage_door(d)
        # Rechnungen an der Wand
        n_bills = 0 if self.intro else (self.i - 1) * 3 + sum(1 for tb in self.bills_t if t > tb + 0.6)
        for k in range(min(n_bills, 18)):
            bx = 40 + (k % 6) * 38
            by = 845 - CEIL + (k // 6) * 40 + (k % 2) * 6
            draw_bill(d, bx, by, 0.62)
        if self.final and t > 6.3:
            a = ease_out_back(seg(t, 6.3, 6.6))
            paste_scaled(lay, sprite("PAID OFF", 40, RED), 140, 900 - CEIL, a, clamp(a * 2))
            d = ImageDraw.Draw(lay)
        if self.intro:
            cx = lerp(-360, CAR_X, ease_out_cubic(seg(t, 0.3, 1.4)))
        else:
            cx = CAR_X
        draw_car(d, cx, "new", dirt=max(0, self.i - 1) * 2, scratches=max(0, self.i - 2) + (1 if (self.i >= 3 and t > 3.6) else 0),
                 rnd_seed=3)
        c.alpha_composite(lay, (x0, CEIL))
        d = ImageDraw.Draw(c)
        if self.intro and 1.4 < t < 2.4:
            e = ease_out_cubic(seg(t, 1.4, 2.0))
            paste_scaled(c, SPARK, x0 + 200, F0 - 120, 0.5 + 1.2 * e, 1 - e)
            d = ImageDraw.Draw(c)
        # Preisschild
        tag_pop = ease_out_back(seg(t, 1.5, 1.85)) if self.intro else 1
        if tag_pop > 0.05:
            draw_tag(c, x0 + 190, F0 - 262, money(self.value_now(t)), (32, 32, 40),
                     arrow=(not self.intro and self.t_tag < t < self.t_tag + 1.2), pop=tag_pop)
            d = ImageDraw.Draw(c)
        if not self.intro and t > self.t_tag:
            self.float_text(c, f"-{money(self.v0 - self.v1)}", RED, x0 + 190, F0 - 330, t - self.t_tag, 44, 1.0)
        # Figur
        fx = x0 + FIG_X
        hands, look, mood, head_drop = [None, None], -0.6, 0.5, 0.0
        sad = self.i >= 3
        if self.intro:
            if 1.8 < t < 2.8:
                hands[0] = (fx - 30 * S, F0 - 170 * S)
                hands[1] = (fx + 10 * S, F0 - 175 * S)
                mood = 0.9
        else:
            if 0.55 < t < 2.4:
                hands[1] = (fx + 36 * S, F0 - lerp(140, 195, seg(t, 0.5, 0.75)) * S)
                mood = 0.0 if self.i < 3 else -0.6
        if 3.1 < t < 5.0:
            if not sad:
                ph = (t - 3.1) * 7
                hands[0] = (x0 + 315 + math.cos(ph) * 18, F0 - 85 + math.sin(ph) * 12)
                mood = 0.9
            else:
                hands[0] = (x0 + 320, F0 - 80)
                mood = -0.7
                look = -1
        if t > 5.4 and not self.intro:
            mood = -0.7 if self.i >= 2 else 0.1
            head_drop = smooth(seg(t, 5.6, 6.3)) * min(1, 0.2 + self.i * 0.15)
            look = -0.8
        info = person_fat(d, fx, F0, 0.1, tuple(hands), mood=mood, look=look, head_drop=head_drop, s=S)
        d = ImageDraw.Draw(c)
        if self.intro and 1.8 < t < 2.8:
            h = info["hands"][0]
            draw_contract(d, h[0] + 20, h[1] - 10, seg(t, 1.9, 2.4))
            self.float_text(c, "72 x $600", RED, fx - 20, info["head"][1] - 100, t - 2.25, 42, 1.0)
        if self.intro:
            self.float_text(c, "NEW", GOLD, x0 + 190, F0 - 120, t - 1.45, 52, 0.8)
        if not self.intro:
            for tb in self.bills_t:
                p = seg(t, tb, tb + 0.33)
                if 0 < p < 1:
                    draw_bill(d, fx + 40 * S, lerp(CEIL + 40, F0 - 220 * S, ease_out_cubic(p)))
                elif tb + 0.33 <= t < tb + 0.6:
                    h = info["hands"][1]
                    draw_bill(d, h[0], h[1] - 30)
                self.float_text(c, "-$600", RED, fx + 20, info["head"][1] - 95, t - tb - 0.35, 40, 0.5, 60)
        if 3.1 < t < 5.0 and not sad:
            for k in range(3):
                ph = (t * 1.3 + k / 3) % 1
                sx, sy = x0 + 80 + k * 90, F0 - 120 - ph * 40
                r = 10 * math.sin(math.pi * ph)
                d.polygon([(sx, sy - r), (sx + r * 0.3, sy), (sx, sy + r), (sx - r * 0.3, sy)], fill=(255, 250, 220))
                d.polygon([(sx - r, sy), (sx, sy + r * 0.3), (sx + r, sy), (sx, sy - r * 0.3)], fill=(255, 250, 220))
        if self.i >= 3 and 3.6 < t < 4.8:
            self.float_text(c, "*scratch*", (220, 220, 230), x0 + 190, F0 - 180, t - 3.6, 32, 0.8)

    # ---- rechts
    def draw_right(self, c, t):
        x0 = ROOMS["R"]
        lay = self.room_layer()
        d = ImageDraw.Draw(lay)
        draw_garage_door(d)
        pch = self.p0 / self.maxp + (self.p1 - self.p0) / self.maxp * smooth(seg(t, 5.2, 5.8))
        draw_chart(d, 32, 842 - CEIL, 250, 1000 - CEIL, 0 if self.intro else pch)
        if self.intro:
            cx = lerp(-360, CAR_X, ease_out_cubic(seg(t, 0.4, 1.7)))
        else:
            cx = CAR_X
        draw_car(d, cx, "used", rnd_seed=5)
        if self.intro and 0.4 < t < 2.2:
            for k in range(4):
                ph = ((t - 0.4) * 1.5 + k / 4) % 1
                r = 8 + ph * 18
                px, py = cx - 10 - ph * 50, LF - 40 - ph * 20
                d.ellipse((px - r, py - r, px + r, py + r), fill=(150, 150, 160))
        c.alpha_composite(lay, (x0, CEIL))
        d = ImageDraw.Draw(c)
        glow = smooth(seg(t, 6.6, 7.2)) * (0.75 + 0.25 * math.sin(t * 4)) if self.final else 0
        d = draw_jar(c, d, x0 + JAR_X, SHELF[2], self.port_now(t) / self.maxp, glow)
        tag_pop = ease_out_back(seg(t, 2.2, 2.55)) if self.intro else 1
        if tag_pop > 0.05:
            draw_tag(c, x0 + 190, F0 - 262, "PAID IN CASH" if not self.intro or t > 2.2 else "", (24, 130, 64), pop=tag_pop)
            d = ImageDraw.Draw(c)
        fx = x0 + FIG_X
        hands, look, mood = [None, None], -0.5, 0.6
        if self.intro:
            if 1.85 < t < 2.6:
                hands[0] = (fx - 50 * S, F0 - 160 * S)
                mood = 0.6
        else:
            if 0.55 < t < 2.4:
                hands[1] = (fx + 36 * S, F0 - lerp(140, 195, seg(t, 0.5, 0.75)) * S)
                mood = 0.7
        if 3.1 < t < 5.0:
            ph = (t - 3.1) * 6
            hands[0] = (x0 + 315 + math.cos(ph) * 20, F0 - 85 + math.sin(ph) * 14)
            mood = 0.9
        if t > 5.4:
            mood = 0.9
            look = -0.2 if t < 6.5 else 0.3
            if self.final and t > 6.8:
                hands = [(fx - 62 * S, F0 - 285 * S), (fx + 62 * S, F0 - 285 * S)]
        info = person_fat(d, fx, F0, 0.1, tuple(hands), mood=mood, look=look, s=S)
        d = ImageDraw.Draw(c)
        if self.intro:
            if 1.85 < t < 2.6:
                h = info["hands"][0]
                draw_banknote(d, h[0] - 8, h[1] - 10)
                draw_banknote(d, h[0] - 2, h[1] - 18)
            self.float_text(c, "$8,000 CASH", (240, 240, 245), fx - 40, info["head"][1] - 100, t - 1.95, 40, 1.0)
            self.float_text(c, "USED", (200, 220, 210), x0 + 190, F0 - 120, t - 1.7, 50, 0.8)
        else:
            for tb in self.bills_t:
                p = seg(t, tb, tb + 0.33)
                if 0 < p < 1:
                    draw_banknote(d, fx + 40 * S, lerp(CEIL + 40, F0 - 220 * S, ease_out_cubic(p)))
                q = seg(t, tb + 0.33, tb + 0.6)
                if 0 < q < 1:
                    h = info["hands"][1]
                    draw_banknote(d, lerp(h[0], x0 + JAR_X, q), lerp(h[1] - 30, SHELF[2] - 170, q) - math.sin(math.pi * q) * 60, 0.8)
                self.float_text(c, "+$600", GREEN, x0 + JAR_X, SHELF[2] - 210, t - tb - 0.55, 40, 0.5, 60)
        if 3.1 < t < 5.0:
            h = info["hands"][0]
            d.rounded_rectangle((h[0] - 16, h[1] - 12, h[0] + 16, h[1] + 12), 5, fill=(250, 220, 80), outline=OUT, width=2)
            for k in range(5):
                ph = (t * 0.9 + k / 5) % 1
                bx = x0 + 120 + k * 45 + math.sin(t * 3 + k) * 10
                by = F0 - 60 - ph * 160
                r = 6 + 6 * ph
                d.ellipse((bx - r, by - r, bx + r, by + r), outline=(235, 245, 255), width=3)

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, self.header, self.label, self.cfg.get("_prev_label"), self.data.get("subtitle", "SAME $600 A MONTH"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"])
        loan = self.loan_now(t)
        port = self.port_now(t)
        self.draw_counter(c, "L", "LOAN PAID", money(loan), RED if loan > 0 else (235, 235, 240))
        self.draw_counter(c, "R", "PORTFOLIO", money(port), GREEN if port > 0 else (235, 235, 240))


# ----------------------------------------------------------------- audio
def build_lib(rng):
    from scroll_video import build_lib4
    lib = build_lib4(rng)

    def nz(n):
        return rng.normal(0, 1, n)

    def engine(f0, f1, dur, rough):
        n = int(dur * SR)
        t = np.arange(n) / SR
        f = np.linspace(f0, f1, n)
        ph = np.cumsum(f) / SR
        saw = 2 * (ph % 1) - 1
        sig = lowpass(saw + nz(n) * rough, 600)
        env = np.minimum(1, t / 0.15) * np.minimum(1, (dur - t) / 0.4)
        return sig * env * 0.9

    lib["engine"] = engine(55, 90, 1.4, 0.3)
    lib["engine_old"] = engine(38, 52, 1.6, 0.8) * (0.8 + 0.2 * np.sign(np.sin(np.arange(int(1.6 * SR)) / SR * 2 * np.pi * 7)))
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    sp = np.zeros(n)
    for k, f0 in enumerate((2637, 3136, 3951, 4699)):
        i0 = int(k * 0.07 * SR)
        tt = t[: n - i0]
        sp[i0:] += np.sin(2 * np.pi * f0 * tt) * np.exp(-tt / 0.18)
    lib["sparkle"] = sp * 0.3
    n = int(0.6 * SR)
    src = nz(n)
    hp = src - lowpass(src, 1500)
    env = np.zeros(n)
    for k in range(6):
        a = int(k * 0.09 * SR)
        m = int(0.06 * SR)
        env[a:a + m] = np.sin(np.linspace(0, np.pi, m))
    lib["scribble"] = hp * env * 0.6
    n = int(1.8 * SR)
    t = np.arange(n) / SR
    src = nz(n)
    lib["scrub"] = (lowpass(src, 3000) - lowpass(src, 900)) * (0.5 + 0.5 * np.sin(2 * np.pi * 4.5 * t)) * np.minimum(1, t / 0.1) * np.minimum(1, (1.8 - t) / 0.2) * 0.6
    n = int(0.35 * SR)
    t = np.linspace(0, 1, n)
    src = nz(n)
    lib["scratch"] = (src - lowpass(src, 3500)) * np.exp(-t * 5) * 0.9 + sine_sweep(2400, 1200, 0.35) * np.exp(-t * 6) * 0.25
    n = int(1.6 * SR)
    b = np.zeros(n)
    for k in range(9):
        a = int(rng.uniform(0, 1.45) * SR)
        m = int(0.05 * SR)
        f = rng.uniform(700, 1400)
        b[a:a + m] += sine_sweep(f, f * 1.6, 0.05) * np.exp(-np.arange(m) / (0.015 * SR))
    lib["bubbles"] = b * 0.5
    n = int(0.25 * SR)
    src = nz(n)
    lib["paper"] = (src - lowpass(src, 2000)) * np.exp(-np.arange(n) / (0.05 * SR)) * 0.5
    n = int(0.5 * SR)
    lib["stamp"] = np.tanh((sine_sweep(160, 50, 0.5) * np.exp(-np.arange(n) / (0.08 * SR)) + lowpass(nz(n), 900) * np.exp(-np.arange(n) / (0.03 * SR))) * 1.5) * 0.9
    return lib


def build(data):
    stages, t = [], 0.0
    pv = data["stages"][0]["value"]
    pl = pp = 0
    prev = None
    data["_max_port"] = max(s["port"] for s in data["stages"])
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_value"], sc["_prev_loan"], sc["_prev_port"], sc["_prev_label"] = pv, pl, pp, prev
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        pv, pl, pp, prev = sc["value"], sc["loan"], sc["port"], sc["label"]
    return stages, t


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p, build, build_lib)
