#!/usr/bin/env python3
"""
"Food Delivery vs. Cooking" – jeden Abend 25 $ Lieferung vs. 8 $ selbst kochen (+17 $ investiert), 10 Jahre.

    python3 generator/food_video.py skripte/zimmer/14_food_delivery.json
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import SR, clamp, ease_out_back, ease_out_cubic, lowpass  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, SHELF, WOOD, draw_coin, draw_jar, room_overlay, seg, sprite  # noqa: E402
from wecker_video import draw_food, person_fat  # noqa: E402
from scroll_video import draw_phone_screen  # noqa: E402
from job_video import SIT_DY, draw_couch_back, draw_couch_front, draw_door_anim  # noqa: E402
from zz_base import StageBase, run  # noqa: E402

S = 1.15
F0 = FL - 10
DINNERS = ["burger", "pizza", "burger", "pizza", "burger", "pizza", "burger"]


def money(v):
    return f"${v:,.0f}"


def draw_pizza_box(d, x, y, w=96):
    d.rectangle((x - w / 2, y - 14, x + w / 2, y), fill=(214, 170, 110), outline=OUT, width=3)
    d.line([(x - w / 2 + 6, y - 8), (x + w / 2 - 6, y - 8)], fill=(190, 60, 50), width=3)


def draw_delivery_bag(d, x, y, s=1.0):
    d.polygon([(x - 30 * s, y - 64 * s), (x + 30 * s, y - 64 * s), (x + 34 * s, y), (x - 34 * s, y)], fill=(236, 120, 60), outline=OUT)
    d.arc((x - 16 * s, y - 84 * s, x + 16 * s, y - 52 * s), 180, 360, fill=OUT, width=4)
    d.ellipse((x - 12 * s, y - 42 * s, x + 12 * s, y - 18 * s), fill=(255, 240, 220), outline=OUT, width=2)


def draw_kitchen(d, x0, steam_t=None):
    # Arbeitsplatte + Herd
    d.rectangle((x0 + 232, F0 - 104, x0 + 470, F0), fill=(200, 196, 188), outline=OUT, width=4)
    d.rectangle((x0 + 226, F0 - 112, x0 + 474, F0 - 98), fill=(90, 92, 104), outline=OUT, width=3)
    for k in range(3):
        d.rectangle((x0 + 252 + k * 72, F0 - 82, x0 + 306 + k * 72, F0 - 18), fill=(176, 172, 164), outline=OUT, width=2)
        d.ellipse((x0 + 273 + k * 72, F0 - 54, x0 + 285 + k * 72, F0 - 44), fill=(90, 92, 104))


def draw_pan(d, x, y, items, t):
    d.line([(x + 46, y - 6), (x + 92, y - 14)], fill=(40, 40, 46), width=8)
    d.chord((x - 48, y - 30, x + 48, y + 8), 0, 180, fill=(50, 50, 58), outline=OUT, width=3)
    cols = [(110, 200, 110), (240, 90, 80), (250, 200, 80), (190, 120, 70)]
    for k in range(items):
        ix = x - 30 + (k * 23) % 60 + math.sin(t * 6 + k) * 3
        d.ellipse((ix - 8, y - 14, ix + 8, y - 2), fill=cols[k % 4], outline=OUT, width=1)


def draw_bowl(d, x, y):
    d.chord((x - 30, y - 20, x + 30, y + 26), 0, 180, fill=(250, 250, 248), outline=OUT, width=3)
    for px, col in ((-14, (110, 200, 110)), (0, (240, 90, 80)), (14, (250, 200, 80))):
        d.ellipse((x + px - 9, y - 4, x + px + 9, y + 8), fill=col, outline=OUT, width=1)


class Stage(StageBase):
    door = True

    def setup(self):
        c = self.cfg
        self.label = str(c["year"])
        self.s0, self.s1 = c["_prev_spent"], c["spent"]
        self.v0, self.v1 = c["_prev_inv"], c["inv"]
        self.maxv = self.data["_max_inv"]
        self.dinner = DINNERS[self.i % len(DINNERS)]
        self.fat_l = 0.1 + 0.06 * self.i
        self.dark = room_overlay("L", (0, 0, 0), 8 + self.i * 9)
        rnd = random.Random(self.i + 4)
        self.steam = [(rnd.uniform(-30, 30), rnd.uniform(0, 1), rnd.uniform(0.7, 1.3)) for _ in range(6)]

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        # links
        for k, tt in enumerate((0.7, 0.95, 1.2)):
            s(tt, "tick", 0.4)
            s(tt + 0.02, "beep", 0.18)
        s(1.45, "dingdong", 0.45)
        s(1.65, "door", 0.35)
        s(1.8, "slide", 0.35)
        s(2.1, "paper", 0.4)
        for st in (2.05, 2.25, 2.55, 2.75):
            s(st, "step", 0.25)
        s(2.95, "thud", 0.3)
        for k in range(4):
            s(3.2 + k * 0.6, "crunch", 0.35)
        s(5.85, "thud", 0.3)
        # rechts
        s(0.7, "paper", 0.35)
        s(1.0, "sizzle", 0.4)
        for tt in (1.2, 1.6, 2.0):
            s(tt, "pop", 0.25)
        s(3.8, "pop", 0.3)
        for k in range(3):
            s(5.7 + k * 0.18, "clink", 0.42)
        if self.final:
            s(6.6, "cash", 0.45)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def spent_now(self, t):
        return lerp(self.s0, self.s1, smooth(seg(t, 0.7, 6.4)))

    def inv_now(self, t):
        return lerp(self.v0, self.v1, smooth(seg(t, 0.7, 6.4)))

    # ---- links: Lieferung
    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        door_open = smooth(seg(t, 1.5, 1.65)) * (1 - smooth(seg(t, 2.0, 2.2)))
        draw_door_anim(d, x0, door_open)
        n_boxes = min(22, 1 + self.i * 3 + (1 if t > 5.9 else 0))
        for k in range(n_boxes):
            draw_pizza_box(d, x0 + 158 + (k % 2) * 4 - 2, F0 - k * 14, 84)
        draw_couch_back(d, x0)
        # Bewegung: stehen -> Tüte holen -> aufs Sofa
        if t < 2.0:
            fx, walking, sit = x0 + 330, False, 0.0
        elif t < 2.4:
            fx, walking, sit = lerp(x0 + 330, x0 + 230, smooth(seg(t, 2.0, 2.4))), True, 0.0
        elif t < 2.8:
            fx, walking, sit = lerp(x0 + 230, x0 + 330, smooth(seg(t, 2.4, 2.8))), True, 0.0
        else:
            fx, walking, sit = x0 + 330, False, smooth(seg(t, 2.8, 3.0))
        hands, look, mood, mouth_o = [None, None], 0.3, 0.6, False
        phone = 0.55 < t < 1.45
        if phone:
            hands[1] = (fx + 30 * S, F0 - 200 * S)
        holding_bag = 2.15 < t < 3.05
        if holding_bag:
            hands[0] = (fx - 40 * S, F0 + SIT_DY * sit - 120 * S)
            look = -0.6
        eating = 3.1 < t < 5.6
        if eating:
            ph = ((t - 3.1) % 0.6) / 0.6
            up = math.sin(math.pi * ph) ** 2
            hands[1] = (fx + lerp(50, 18, up) * S, F0 + SIT_DY - lerp(150, 225, up) * S)
            mood = 0.8
        if t > 5.8:
            mood = 0.0 if self.i < 3 else -0.6
            hands[0] = (fx - 10 * S, F0 + SIT_DY - 120 * S)
            look = -0.2
        fy = F0 + SIT_DY * sit
        lay = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        info = person_fat(ld, fx, fy, self.fat_l, tuple(hands), walk=(t - 2.0) * 14 if walking else 0, mood=mood, look=look,
                          mouth_o=mouth_o, s=S)
        if phone:
            h = info["hands"][1]
            draw_phone_screen(ld, h[0] + 4, h[1] - 26, 34, 56, t, scroll=False)
        if holding_bag:
            h = info["hands"][0]
            draw_delivery_bag(ld, h[0], h[1] + 40, 0.8)
        if eating:
            h = info["hands"][1]
            draw_food(ld, self.dinner, h[0] + 6, h[1] - 18)
        c.alpha_composite(lay, (x0, CEIL), (x0, CEIL, x0 + RW, F0 - 2))
        d = ImageDraw.Draw(c)
        draw_couch_front(d, x0)
        if 1.8 < t < 2.2:
            bx = lerp(x0 + 60, x0 + 205, ease_out_cubic(seg(t, 1.8, 2.15)))
            draw_delivery_bag(d, bx, F0)
        if 3.05 < t < 5.9:
            draw_delivery_bag(d, x0 + 250, F0 - 92, 0.6)
        hy = info["head"][1]
        for k, (tt, txt) in enumerate(((0.75, "-$18"), (1.0, "FEE -$4"), (1.25, "TIP -$3"))):
            self.float_text(c, txt, RED, fx + 30 + k * 26, hy - 90 - k * 40, t - tt, 38, 0.9, 25)
        if 5.85 < t < 6.4:
            p = seg(t, 5.85, 6.1)
            draw_pizza_box(d, lerp(x0 + 300, x0 + 158, p), lerp(F0 - 200, F0 - (n_boxes - 1) * 14, p) - math.sin(math.pi * p) * 60, 84)

    def after_left(self, c, t):
        c.alpha_composite(self.dark, (ROOMS["L"], CEIL))

    # ---- rechts: kochen
    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        draw_door_anim(d, x0, 0)
        glow = smooth(seg(t, 6.6, 7.2)) * (0.75 + 0.25 * math.sin(t * 4)) if self.final else 0
        d = draw_jar(c, d, x0 + 400, SHELF[2], self.inv_now(t) / self.maxv, glow)
        draw_kitchen(d, x0)
        n_items = sum(1 for tt in (1.2, 1.6, 2.0) if t > tt) if t < 3.8 else 0
        draw_pan(d, x0 + 300, F0 - 112, n_items, t)
        if 1.0 < t < 3.8:
            for dx, ph, sp in self.steam:
                k = ((t - 1.0) * 0.7 * sp + ph) % 1
                r = 8 + k * 14
                g = int(235 - k * 60)
                d.ellipse((x0 + 300 + dx - r, F0 - 140 - k * 120 - r, x0 + 300 + dx + r, F0 - 140 - k * 120 + r), fill=(g, g, g + 5))
        if t < 1.0:
            draw_delivery_bag(d, x0 + 440, F0 - 112, 0.6)
        fx = x0 + 178
        hands, look, mood = [None, None], 1.0, 0.6
        if 0.55 < t < 1.0:
            hands[1] = (fx + 40 * S, F0 - 140 * S)
        stirring = 1.0 < t < 3.7
        if stirring:
            ph = (t - 1.0) * 6
            hands[1] = (x0 + 300 + math.cos(ph) * 18, F0 - 140 + math.sin(ph) * 8)
            mood = 0.8
        eating = 3.8 < t < 5.5
        if eating:
            ph = ((t - 3.8) % 0.6) / 0.6
            up = math.sin(math.pi * ph) ** 2
            hands[0] = (fx - 10 * S, F0 - 150 * S)
            hands[1] = (fx + lerp(40, 18, up) * S, F0 - lerp(150, 225, up) * S)
            mood = 0.9
        if 5.6 < t < 6.3:
            hands[1] = (fx + 60 * S, F0 - 215 * S)
            look = 1
        if t > 6.4:
            mood = 0.9
            if self.final and t > 6.8:
                hands = [(fx - 62 * S, F0 - 285 * S), (fx + 62 * S, F0 - 285 * S)]
        info = person_fat(d, fx, F0, 0.1, tuple(hands), mood=mood, look=look, s=S)
        d = ImageDraw.Draw(c)
        if stirring:
            h = info["hands"][1]
            d.line([(h[0], h[1]), (h[0] + 8, h[1] + 30)], fill=WOOD, width=6)
        if eating:
            h0 = info["hands"][0]
            draw_bowl(d, h0[0] + 20, h0[1])
        self.float_text(c, "-$8", (220, 220, 230), fx + 10, info["head"][1] - 90, t - 0.7, 38, 0.9, 25)
        if 5.6 < t < 6.4:
            for k in range(3):
                p = seg(t, 5.65 + k * 0.18, 5.85 + k * 0.18)
                if 0 < p < 1:
                    h = info["hands"][1]
                    draw_coin(d, lerp(h[0], x0 + 400, p), lerp(h[1], SHELF[2] - 170, p) - math.sin(math.pi * p) * 60)
        self.float_text(c, "+$17", GREEN, x0 + 400, SHELF[2] - 200, t - 5.7, 44, 0.9)

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, "YEAR", self.label, str(self.cfg["_prev_year"]) if self.cfg["_prev_year"] else None,
                           self.data.get("subtitle", "SAME DINNER · EVERY NIGHT"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=62, s2=70)
        sp = self.spent_now(t)
        iv = self.inv_now(t)
        self.draw_counter(c, "L", "SPENT", money(sp), RED if sp > 0 else (235, 235, 240))
        self.draw_counter(c, "R", "INVESTED", money(iv), GREEN if iv > 0 else (235, 235, 240))


def build_lib(rng):
    from job_video import build_lib as job_lib
    lib = job_lib(rng)
    n = int(2.8 * SR)
    t = np.arange(n) / SR
    src = rng.normal(0, 1, n)
    hp = src - lowpass(src, 3000)
    crackle = (rng.random(n) < 0.006) * rng.normal(0, 2.0, n)
    lib["sizzle"] = (hp * 0.35 + crackle) * np.minimum(1, t / 0.15) * np.minimum(1, (2.8 - t) / 0.4) * 0.7
    return lib


def build(data):
    stages, t = [], 0.0
    ps = pv = 0
    py = None
    data["_max_inv"] = max(s["inv"] for s in data["stages"])
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_spent"], sc["_prev_inv"], sc["_prev_year"] = ps, pv, py
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        ps, pv, py = sc["spent"], sc["inv"], sc["year"]
    return stages, t


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p, build, build_lib)
