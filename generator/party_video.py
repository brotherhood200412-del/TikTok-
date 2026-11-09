#!/usr/bin/env python3
"""
"Your 20s: Party vs. Build" – 100 $ jedes Wochenende feiern (20-30) vs. investieren.
Finale: 30 Jahre später, $75,003 -> $570,945.

    python3 generator/party_video.py skripte/zimmer/17_party_vs_build.json
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import SR, clamp, ease_out_back, ease_out_cubic, lowpass, sine_sweep  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, SHELF, WIN, draw_coin, draw_jar, paste_scaled, radial, room_overlay, seg, sprite  # noqa: E402
from wecker_video import person_fat  # noqa: E402
from job_video import draw_couch_back, draw_couch_front  # noqa: E402
from betting_video import draw_popcorn  # noqa: E402
from zz_base import StageBase, fit_sprite, run  # noqa: E402

S = 1.15
F0 = FL - 10
SEAT_FY = F0 + 106
HAIR0, GRAY = (72, 52, 40), (205, 205, 210)
NIGHT_END, MORNING = 4.0, 4.3
PARTY_COLS = [(255, 70, 160), (80, 160, 255), (160, 90, 255), (60, 230, 200)]


def money(v):
    return f"${v:,.0f}"


def draw_disco(c, d, x, y, t, x0):
    d.line([(x, CEIL), (x, y - 26)], fill=(80, 80, 90), width=3)
    d.ellipse((x - 26, y - 26, x + 26, y + 26), fill=(200, 205, 215), outline=OUT, width=3)
    for k in range(-2, 3):
        d.line([(x - 24, y + k * 9), (x + 24, y + k * 9)], fill=(150, 155, 170), width=1)
        d.line([(x + k * 9, y - 24), (x + k * 9, y + 24)], fill=(150, 155, 170), width=1)
    lay = Image.new("RGBA", (RW, FL - CEIL), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    for k in range(4):
        a = t * 1.6 + k * math.pi / 2
        col = PARTY_COLS[(k + int(t * 2)) % 4]
        ex = x - x0 + math.cos(a) * 240
        ld.polygon([(x - x0, y - CEIL), (ex - 40, F0 - CEIL), (ex + 40, F0 - CEIL)], fill=col + (60,))
    c.alpha_composite(lay, (x0, CEIL))


def draw_cup(d, x, y, col=(220, 40, 50)):
    d.polygon([(x - 12, y - 26), (x + 12, y - 26), (x + 9, y + 10), (x - 9, y + 10)], fill=col, outline=OUT)
    d.rectangle((x - 12, y - 26, x + 12, y - 20), fill=(250, 250, 250))


def draw_mug(d, x, y):
    d.rounded_rectangle((x - 14, y - 22, x + 12, y + 6), 4, fill=(250, 250, 245), outline=OUT, width=3)
    d.arc((x + 6, y - 16, x + 22, y), -90, 90, fill=OUT, width=3)
    for k in range(2):
        d.arc((x - 10 + k * 10, y - 46, x + 2 + k * 10, y - 26), 200, 340, fill=(220, 220, 230), width=2)


def draw_dizzy(d, hx, hy, t):
    for k in range(4):
        a = t * 4 + k * math.pi / 2
        sx, sy = hx + math.cos(a) * 46, hy - 50 + math.sin(a) * 12
        r = 8
        d.polygon([(sx, sy - r), (sx + r * 0.3, sy), (sx, sy + r), (sx - r * 0.3, sy)], fill=(255, 220, 80))
        d.polygon([(sx - r, sy), (sx, sy + r * 0.3), (sx + r, sy), (sx, sy - r * 0.3)], fill=(255, 220, 80))


class Stage(StageBase):
    door = False

    def setup(self):
        c = self.cfg
        self.label = str(c["age"])
        self.later = c.get("later", False)
        self.s0, self.s1 = c["_prev_spent"], c["spent"]
        self.v0, self.v1 = c["_prev_inv"], c["inv"]
        self.maxv = self.data["_max_inv"]
        self.age_k = clamp((c["age"] - 21) / 39)
        rnd = random.Random(self.i * 3 + 7)
        self.cups = [(rnd.uniform(20, 190), rnd.uniform(-0.6, 0.6)) for _ in range(30)]

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        if self.later:
            s(0.3, "whoosh", 0.5)
            s(0.5, "pop_big", 0.4)
            for k in range(8):
                s(1.2 + k * 0.6, "clink", 0.3)
            s(6.2, "cash", 0.5)
            s(6.3, "sparkle", 0.45)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)
            return
        for k, tt in enumerate((0.8, 1.1, 1.4, 1.7)):
            s(tt, "beep", 0.2)
            s(tt, "pop", 0.2)
        s(0.85, "clink", 0.45)
        s(1.0, "cheer", 0.35)
        for k in range(6):
            s(1.0 + k * 0.5, "thump", 0.45)
        s(2.6, "cheer", 0.3)
        s(NIGHT_END, "whoosh", 0.4)
        s(MORNING + 0.3, "groan", 0.45)
        s(MORNING + 1.6, "groan", 0.35)
        for k in range(4):
            s(1.4 + k * 0.5, "crunch", 0.18)
        s(MORNING + 0.6, "glug", 0.3)
        s(6.4, "ding", 0.3)

    def spent_now(self, t):
        return lerp(self.s0, self.s1, smooth(seg(t, 0.7, 6.0)))

    def inv_now(self, t):
        if self.later:
            return lerp(self.v0, self.v1, smooth(seg(t, 1.2, 6.2)))
        return lerp(self.v0, self.v1, smooth(seg(t, 0.7, 6.0)))

    def hair(self):
        return tuple(int(lerp(a, b, self.age_k)) for a, b in zip(HAIR0, GRAY))

    def morning_window(self, c, x0, t):
        k = smooth(seg(t, NIGHT_END, MORNING + 0.3))
        if k > 0:
            ov = Image.new("RGBA", (WIN[2] - WIN[0] - 12, WIN[3] - WIN[1] - 12), (170, 215, 255, int(220 * k)))
            c.alpha_composite(ov, (x0 + WIN[0] + 6, WIN[1] + 6))

    def seated(self, c, x0, hands, mood, look, head_drop=0.0, extra=None, fy=SEAT_FY, mouth_o=False):
        lay = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        info = person_fat(ld, x0 + 330, fy, 0.1, tuple(hands), mood=mood, look=look, head_drop=head_drop, s=S,
                          hair=self.hair(), mouth_o=mouth_o)
        if extra:
            extra(ld, info)
        c.alpha_composite(lay, (x0, CEIL), (x0, CEIL, x0 + RW, F0 - 2))
        return info

    # ---- links
    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        if self.later:
            draw_couch_back(d, x0)
            hands = [(x0 + 330 - 30 * S, SEAT_FY - 175 * S), (x0 + 330 + 30 * S, SEAT_FY - 175 * S)]

            def album(ld, info):
                h = info["hands"][0]
                ld.rectangle((h[0] - 6, h[1] - 30, h[0] + 70, h[1] + 14), fill=(150, 60, 70), outline=OUT, width=3)
                ld.rectangle((h[0] + 4, h[1] - 22, h[0] + 30, h[1] + 4), fill=(80, 70, 140))

            self.seated(c, x0, hands, -0.4 if t > 3 else 0.2, 0.2, head_drop=0.3, extra=album)
            d = ImageDraw.Draw(c)
            draw_couch_front(d, x0)
            n = 24
            for k in range(n):
                ux, ang = self.cups[k]
                draw_cup(d, x0 + ux, F0 - 10 - (k // 10) * 6)
            return
        night = t < NIGHT_END
        # Becher am Boden (Morgen danach)
        n_cups = min(28, 2 + self.i * 4)
        if not night:
            draw_couch_back(d, x0)
        if night and t > 0.9:
            draw_disco(c, d, x0 + 300, CEIL + 120, t, x0)
            d = ImageDraw.Draw(c)
            # Freunde im Hintergrund
            for k, fx in enumerate((x0 + 120, x0 + 430)):
                ph = t * 6 + k * 2
                person_fat(d, fx, F0, 0.1, ((fx - 50, F0 - 250 + math.sin(ph) * 30), (fx + 50, F0 - 250 - math.sin(ph) * 30)),
                           mood=0.8, s=0.9, shirt=(60, 50, 70), skin=(150, 140, 160), bob=abs(math.sin(ph)) * 8)
        if night:
            fx = x0 + 280
            hands = [None, None]
            bob = 0.0
            mood = 0.8
            if t > 1.0:
                ph = t * 6
                hands = [(fx - 60 * S, F0 - (200 + 70 * math.sin(ph)) * S), (fx + 46 * S, F0 - 175 * S)]
                bob = abs(math.sin(ph)) * 10
                mood = 1.0
            info = person_fat(d, fx, F0, 0.1, tuple(hands), mood=mood, look=0.3, bob=bob, s=S, hair=self.hair(),
                              shirt=(200, 60, 120))
            d = ImageDraw.Draw(c)
            if t > 1.0:
                h = info["hands"][1]
                draw_cup(d, h[0] + 6, h[1] - 8)
            for k, (tt, txt) in enumerate(((0.8, "ENTRY -$20"), (1.1, "DRINKS -$40"), (1.4, "UBER -$25"), (1.7, "FOOD -$15"))):
                self.float_text(c, txt, RED, x0 + 150 + (k % 2) * 170, CEIL + 300 + k * 50, t - tt, 36, 1.4, 20)
        else:
            hands = [(x0 + 330 - 20 * S, SEAT_FY - 215 * S), None]

            def extra(ld, info):
                if t > MORNING:
                    draw_dizzy(ld, info["head"][0], info["head"][1], t)

            info = self.seated(c, x0, hands, -0.9, -0.2, head_drop=0.6, extra=extra)
            d = ImageDraw.Draw(c)
            draw_couch_front(d, x0)
            for k in range(n_cups):
                ux, ang = self.cups[k]
                draw_cup(d, x0 + ux, F0 - 10 - (k // 10) * 6)
            self.float_text(c, "*headache*", (220, 220, 230), x0 + 330, info["head"][1] - 110, t - MORNING - 0.2, 36, 2.5, 10)
            if t < MORNING + 1.2:
                a = smooth(seg(t, NIGHT_END, NIGHT_END + 0.3)) * (1 - smooth(seg(t, MORNING + 0.9, MORNING + 1.2)))
                paste_scaled(c, sprite("SUNDAY 9 AM", 40, (240, 240, 250)), x0 + RW / 2, CEIL + 120, 1, a)

    def after_left(self, c, t):
        x0 = ROOMS["L"]
        if not self.later:
            if t < NIGHT_END and t > 0.9:
                col = PARTY_COLS[int(t * 3) % 4]
                c.alpha_composite(room_overlay("L", col, 40), (x0, CEIL))
            elif t < NIGHT_END:
                c.alpha_composite(room_overlay("L", (0, 0, 20), 60), (x0, CEIL))
            self.morning_window(c, x0, t)
        c.alpha_composite(room_overlay("L", (0, 0, 0), 6 + self.i * 6), (x0, CEIL))

    # ---- rechts
    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        glow = smooth(seg(t, 6.2, 6.8)) * (0.75 + 0.25 * math.sin(t * 4)) if self.final else 0
        d = draw_jar(c, d, x0 + 400, SHELF[2], self.inv_now(t) / self.maxv, glow)
        if self.later:
            draw_couch_back(d, x0)
            hands = [(x0 + 330 - 62 * S, SEAT_FY - 285 * S), (x0 + 330 + 62 * S, SEAT_FY - 285 * S)] if t > 6.2 else [None, None]
            self.seated(c, x0, hands, 0.9, 0.2)
            d = ImageDraw.Draw(c)
            draw_couch_front(d, x0)
            a = ease_out_back(seg(t, 0.3, 0.7)) * (1 - smooth(seg(t, 7.6, 7.9)))
            if a > 0.02:
                paste_scaled(c, sprite("30 YEARS LATER", 46, (240, 240, 250)), 540, CEIL + 120, a, clamp(a * 2))
            self.float_text(c, "COMPOUND INTEREST", GREEN, x0 + 330, SHELF[2] - 230, t - 1.3, 32, 4.0, 10)
            return
        night = t < NIGHT_END
        if night:
            # Filmabend
            d.rectangle((x0 + 22, F0 - 62, x0 + 172, F0), fill=(90, 66, 52), outline=OUT, width=4)
            d.rectangle((x0 + 26, F0 - 196, x0 + 168, F0 - 92), fill=(20, 20, 26), outline=OUT, width=5)
            d.rectangle((x0 + 34, F0 - 188, x0 + 160, F0 - 100), fill=(60, 80, 140))
            d.ellipse((x0 + 70, F0 - 170, x0 + 120, F0 - 120), fill=(250, 220, 120))
            draw_couch_back(d, x0)
            hands = [None, None]
            pop = 1.2 < t < NIGHT_END
            if pop:
                ph = ((t - 1.2) % 0.45) / 0.45
                up = math.sin(math.pi * ph) ** 2
                hands = [(x0 + 330 - 40 * S, SEAT_FY - 150 * S), (x0 + 330 + lerp(44, 18, up) * S, SEAT_FY - lerp(160, 225, up) * S)]
            if 0.6 < t < 1.1:
                hands = [None, (x0 + 330 + 50 * S, SEAT_FY - 210 * S)]

            def extra(ld, info):
                if pop:
                    h = info["hands"][0]
                    draw_popcorn(ld, h[0] + 6, h[1])

            info = self.seated(c, x0, hands, 0.8, -0.5, extra=extra)
            d = ImageDraw.Draw(c)
            draw_couch_front(d, x0)
            if 0.7 < t < 1.2:
                p = seg(t, 0.75, 1.0)
                draw_coin(d, lerp(x0 + 380, x0 + 400, p), lerp(F0 - 260, SHELF[2] - 170, p) - math.sin(math.pi * p) * 60)
            self.float_text(c, "+$100", GREEN, x0 + 400, SHELF[2] - 200, t - 0.85, 44, 1.0)
        else:
            fx = x0 + 230
            hands = [None, (fx + 30 * S, F0 - 185 * S)]
            ph = (t - MORNING) % 2.0
            if ph > 1.2:
                hands = [(fx - 62 * S, F0 - 285 * S), (fx + 62 * S, F0 - 285 * S)]
            info = person_fat(d, fx, F0, 0.1, tuple(hands), mood=0.9, look=0.3, s=S, hair=self.hair())
            d = ImageDraw.Draw(c)
            if ph <= 1.2:
                h = info["hands"][1]
                draw_mug(d, h[0] + 4, h[1] - 10)
            if t < MORNING + 1.2:
                a = smooth(seg(t, NIGHT_END, NIGHT_END + 0.3)) * (1 - smooth(seg(t, MORNING + 0.9, MORNING + 1.2)))
                paste_scaled(c, sprite("SUNDAY 9 AM", 40, (240, 240, 250)), x0 + RW / 2, CEIL + 120, 1, a)
            if self.v1 > self.v0:
                self.float_text(c, f"+{money(self.v1 - self.v0)}", GREEN, x0 + 400, SHELF[2] - 200, t - 6.3, 40, 1.2)
        self.morning_window(c, x0, t)

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, "AGE", self.label, str(self.cfg["_prev_age"]) if self.cfg["_prev_age"] else None,
                           self.data.get("subtitle", "SAME $100 · EVERY WEEKEND"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=64, s2=96)
        sp = self.spent_now(t)
        iv = self.inv_now(t)
        self.draw_counter(c, "L", "SPENT PARTYING", money(sp), RED if sp > 0 else (235, 235, 240))
        self.draw_counter(c, "R", "INVESTED", money(iv), GREEN if iv > 0 else (235, 235, 240))


def build_lib(rng):
    from betting_video import build_lib as bet_lib
    lib = bet_lib(rng)
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    lib["thump"] = lowpass(sine_sweep(110, 42, 0.45) * np.exp(-t / 0.12), 300) * 1.4
    return lib


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
