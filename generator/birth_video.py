#!/usr/bin/env python3
"""
"$1 a Day From Birth" – links wird der Dollar jeden Tag ausgegeben, rechts jeden Tag investiert.
AGE 1 -> 65. Rechts: $481,746.

    python3 generator/birth_video.py skripte/zimmer/20_one_dollar_from_birth.json
"""
import math
import os
import random
import sys

import numpy as np
from PIL import ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import SR, clamp, ease_out_back, ease_out_cubic  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, SHELF, SKIN, WOOD, capsule, circle, draw_coin, draw_jar, room_overlay, seg, sprite  # noqa: E402
from wecker_video import draw_food, person_fat  # noqa: E402
from job_video import draw_tie  # noqa: E402
from party_video import draw_mug  # noqa: E402
from zz_base import StageBase, run  # noqa: E402

F0 = FL - 10
FIG = 240
AGES = {
    1: dict(s=0.6, fat=0.3, shirt=(250, 210, 90), hair=(120, 90, 60), item="TOY"),
    5: dict(s=0.62, fat=0.2, shirt=(230, 90, 90), hair=(90, 64, 44), item="CANDY"),
    10: dict(s=0.78, fat=0.1, shirt=(80, 190, 120), hair=(80, 58, 42), item="SODA"),
    18: dict(s=1.0, fat=0.1, shirt=(120, 124, 140), hair=(72, 52, 40), item="SNACKS"),
    30: dict(s=1.15, fat=0.1, shirt=(80, 118, 235), hair=(72, 52, 40), item="COFFEE"),
    45: dict(s=1.15, fat=0.25, shirt=(80, 118, 235), hair=(140, 130, 125), item="CANDY BAR", tie=True),
    65: dict(s=1.1, fat=0.2, shirt=(150, 110, 80), hair=(215, 215, 220), item="GUM", cane=True),
}
DAYS = (0.7, 1.6, 2.5)


def money(v):
    return f"${v:,.0f}"


def draw_item(d, kind, x, y):
    if kind == "TOY":
        d.line([(x, y), (x, y + 26)], fill=(240, 120, 160), width=6)
        d.ellipse((x - 14, y - 26, x + 14, y + 2), fill=(250, 200, 80), outline=OUT, width=3)
    elif kind == "CANDY":
        d.line([(x, y), (x, y + 30)], fill=(250, 250, 250), width=4)
        d.ellipse((x - 15, y - 28, x + 15, y + 2), fill=(255, 110, 170), outline=OUT, width=3)
        d.arc((x - 9, y - 22, x + 9, y - 4), 0, 300, fill=(255, 255, 255), width=3)
    elif kind == "SODA":
        draw_food(d, "soda", x, y - 4)
    elif kind == "SNACKS":
        draw_food(d, "chips", x, y - 4)
    elif kind == "COFFEE":
        draw_mug(d, x, y + 4)
    elif kind == "CANDY BAR":
        d.rectangle((x - 22, y - 10, x + 22, y + 10), fill=(120, 60, 160), outline=OUT, width=3)
        d.rectangle((x - 6, y - 10, x + 6, y + 10), fill=(250, 210, 80))
    else:
        d.rectangle((x - 18, y - 8, x + 18, y + 8), fill=(120, 220, 200), outline=OUT, width=3)


def draw_crib(d, x0):
    x1, x2, top = x0 + 130, x0 + 350, F0 - 120
    d.rectangle((x1, top, x2, top + 12), fill=(240, 236, 228), outline=OUT, width=3)
    d.rectangle((x1, F0 - 20, x2, F0 - 8), fill=(240, 236, 228), outline=OUT, width=3)
    for k in range(10):
        bx = x1 + 10 + k * 22
        d.line([(bx, top + 12), (bx, F0 - 20)], fill=(240, 236, 228), width=5)
    for lx in (x1, x2 - 10):
        d.rectangle((lx, top, lx + 10, F0), fill=(240, 236, 228), outline=OUT, width=2)


def draw_wrappers(d, x0, n, seed=3):
    rnd = random.Random(seed)
    cols = [(255, 110, 170), (220, 40, 50), (240, 180, 60), (120, 60, 160), (120, 220, 200), (250, 250, 245)]
    for k in range(min(n, 60)):
        x = x0 + 30 + rnd.uniform(0, 150)
        y = F0 - 4 - (k // 12) * 7 - rnd.uniform(0, 4)
        w = rnd.uniform(10, 18)
        d.polygon([(x - w, y), (x + w * 0.8, y - 5), (x + w, y + 2), (x - w * 0.6, y + 4)], fill=cols[k % len(cols)], outline=OUT)


def parent_hand(d, x, y):
    capsule(d, (x + 30, CEIL), (x, y - 14), 24, (60, 64, 80))
    circle(d, x, y - 6, 13, SKIN, 3)


class Stage(StageBase):
    door = False

    def setup(self):
        c = self.cfg
        self.age = c["age"]
        self.label = str(self.age)
        self.p = AGES[self.age]
        self.sp0, self.sp1 = c["_prev_spent"], c["spent"]
        self.v0, self.v1 = c["_prev_inv"], c["inv"]
        self.maxv = self.data["_max_inv"]
        self.parent = self.age < 18

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        for tt in DAYS:
            s(tt, "beep", 0.2)
            s(tt + 0.05, "pop", 0.25)
            s(tt + 0.5, "crunch", 0.25)
            s(tt + 0.35, "clink", 0.45)
        s(3.4, "whoosh", 0.4)
        s(3.45, "pop_big", 0.4)
        s(5.6, "sparkle", 0.3)
        if self.age == 18:
            s(0.4, "ding", 0.3)
        if self.final:
            s(6.2, "cash", 0.5)
            s(6.3, "sparkle", 0.5)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def spent_now(self, t):
        return lerp(self.sp0, self.sp1, smooth(seg(t, 0.7, 5.6)))

    def inv_now(self, t):
        return lerp(self.v0, self.v1, smooth(seg(t, 0.7, 5.6)))

    def person(self, d, x, hands, mood, look, head_drop=0.0, bob=0.0):
        p = self.p
        return person_fat(d, x, F0, p["fat"], tuple(hands), mood=mood, look=look, head_drop=head_drop, bob=bob, s=p["s"],
                          shirt=p["shirt"], hair=p["hair"])

    def extras(self, d, info, x):
        if self.p.get("tie"):
            draw_tie(d, info, self.p["s"])
        if self.p.get("cane") and info["hands"][0][1] > F0 - 160 * self.p["s"]:
            h = info["hands"][0]
            d.line([(h[0], h[1]), (h[0] - 6, F0)], fill=(90, 60, 40), width=7)
            d.arc((h[0] - 4, h[1] - 12, h[0] + 18, h[1] + 8), 180, 360, fill=(90, 60, 40), width=7)

    # ---- links: Dollar wird ausgegeben
    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        n_wr = self.i * 6 + sum(1 for tt in DAYS if t > tt + 0.8)
        draw_wrappers(d, x0, n_wr)
        s = self.p["s"]
        fx = x0 + FIG + (40 if self.age == 1 else 0)
        hands, mood, look = [None, None], 0.7, 0.3
        if self.p.get("cane"):
            hands[0] = (fx - 46 * s, F0 - 120 * s)
        item_hand = None
        for tt in DAYS:
            if tt < t < tt + 0.8:
                k = (t - tt) / 0.8
                up = math.sin(math.pi * clamp((k - 0.3) / 0.5)) ** 2 if k > 0.3 else 0
                hands[1] = (fx + lerp(58, 20, up) * s, F0 - lerp(150, 225, up) * s)
                item_hand = True
                mood = 0.9
        if t > 6.2:
            mood = 0.0 if self.age < 45 else -0.5
            look = -0.6
        info = self.person(d, fx, hands, mood, look)
        self.extras(d, info, fx)
        if self.age == 1:
            draw_crib(d, x0)
        if item_hand:
            h = info["hands"][1]
            draw_item(d, self.p["item"], h[0] + 6, h[1] - 16)
        for tt in DAYS:
            self.float_text(c, f"-$1 {self.p['item']}", RED, fx + 30, info["head"][1] - 90, t - tt, 34, 0.7, 30)
        a = ease_out_back(seg(t, 3.4, 3.7)) * (1 - smooth(seg(t, 5.2, 5.6)))
        if a > 0.02:
            from zimmer_video import paste_scaled
            paste_scaled(c, sprite("EVERY DAY", 40, (240, 240, 250)), x0 + RW / 2, CEIL + 150, a, clamp(a * 2))

    def after_left(self, c, t):
        c.alpha_composite(room_overlay("L", (0, 0, 0), 4 + self.i * 6), (ROOMS["L"], CEIL))

    # ---- rechts: Dollar wird investiert
    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        glow = smooth(seg(t, 6.2, 6.8)) * (0.75 + 0.25 * math.sin(t * 4)) if self.final else 0
        d = draw_jar(c, d, x0 + 400, SHELF[2], self.inv_now(t) / self.maxv, glow)
        s = self.p["s"]
        fx = x0 + FIG + (40 if self.age == 1 else 0)
        hands, mood, look = [None, None], 0.7, 0.4
        if self.p.get("cane"):
            hands[0] = (fx - 46 * s, F0 - 120 * s)
        tossing = False
        if not self.parent:
            for tt in DAYS:
                if tt < t < tt + 0.4:
                    hands[1] = (fx + 60 * s, F0 - 220 * s)
                    tossing = True
        if t > 6.2:
            mood = 0.9
            if self.final and t > 6.4:
                hands = [(fx - 62 * s, F0 - 285 * s), (fx + 62 * s, F0 - 285 * s)]
            elif self.age == 1:
                ph = (t - 6.2) * 8
                hands = [(fx - (20 + 10 * math.sin(ph)) * s, F0 - 200 * s), (fx + (20 + 10 * math.sin(ph)) * s, F0 - 200 * s)]
        info = self.person(d, fx, hands, mood, look)
        self.extras(d, info, fx)
        if self.age == 1:
            draw_crib(d, x0)
        for tt in DAYS:
            if self.parent:
                p = seg(t, tt, tt + 0.35)
                q = seg(t, tt + 0.35, tt + 0.7)
                if 0 < p < 1 or (0 < q < 1):
                    hx = x0 + 400
                    hy = lerp(CEIL + 60, SHELF[2] - 190, ease_out_cubic(p)) if q <= 0 else lerp(SHELF[2] - 190, CEIL + 60, smooth(q))
                    parent_hand(d, hx, hy)
                    if q <= 0:
                        draw_coin(d, hx, hy + 10)
                if 0.25 < (t - tt) < 0.4:
                    draw_coin(d, x0 + 400, lerp(SHELF[2] - 180, SHELF[2] - 160, (t - tt - 0.25) / 0.15))
            else:
                p = seg(t, tt + 0.1, tt + 0.35)
                if 0 < p < 1:
                    h = info["hands"][1]
                    draw_coin(d, lerp(h[0], x0 + 400, p), lerp(h[1], SHELF[2] - 170, p) - math.sin(math.pi * p) * 60)
            self.float_text(c, "+$1", GREEN, x0 + 400, SHELF[2] - 210, t - tt - 0.35, 42, 0.6, 30)
        a = ease_out_back(seg(t, 3.4, 3.7)) * (1 - smooth(seg(t, 5.2, 5.6)))
        if a > 0.02:
            from zimmer_video import paste_scaled
            paste_scaled(c, sprite("x365", 64, GOLD), x0 + 300, SHELF[2] - 120, a, clamp(a * 2))
        if self.v1 > self.v0:
            self.float_text(c, f"+{money(self.v1 - self.v0)}", GREEN, x0 + 330, 820, t - 5.6, 40, 1.2)
        if self.age == 18:
            self.float_text(c, "NOW HE DOES IT HIMSELF", (230, 230, 240), x0 + RW / 2, CEIL + 150, t - 0.4, 30, 1.8, 10)

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, "AGE", self.label, str(self.cfg["_prev_age"]) if self.cfg["_prev_age"] else None,
                           self.data.get("subtitle", "SAME $1 · EVERY DAY"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=64, s2=96)
        sp = self.spent_now(t)
        iv = self.inv_now(t)
        self.draw_counter(c, "L", "SPENT", money(sp), RED if sp > 0 else (235, 235, 240))
        self.draw_counter(c, "R", "INVESTED", money(iv), GREEN if iv > 0 else (235, 235, 240))


def build_lib(rng):
    from skins_video import build_lib as skins_lib
    return skins_lib(rng)


def build(data):
    stages, t = [], 0.0
    ps = pv = 0
    pa = None
    data["_max_inv"] = max(s["inv"] for s in data["stages"])
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_spent"], sc["_prev_inv"], sc["_prev_age"] = ps, pv, pa
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        ps, pv, pa = sc["spent"], sc["inv"], sc["age"]
    return stages, t


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p, build, build_lib)
