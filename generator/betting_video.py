#!/usr/bin/env python3
"""
"Sports Betting vs. Investing" – beide schauen dasselbe Spiel. Links wettet er 50 $/Woche,
rechts investiert er sie. 10 Jahre.

    python3 generator/betting_video.py skripte/zimmer/16_sports_betting.json
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
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, paste_scaled, radial, room_overlay, seg, sprite  # noqa: E402
from wecker_video import person_fat  # noqa: E402
from job_video import SIT_DY, draw_couch_back, draw_couch_front  # noqa: E402
from auto_video import draw_chart  # noqa: E402
from zz_base import StageBase, fit_sprite, run  # noqa: E402

S = 1.15
F0 = FL - 10
SEAT = 330
GOAL_T = 3.5
TV_GLOW = radial(300, (120, 220, 140), 70)


def money(v):
    return f"${v:,.0f}"


def draw_tv_game(c, d, x0, t, flash):
    d.rectangle((x0 + 22, F0 - 62, x0 + 172, F0), fill=(90, 66, 52), outline=OUT, width=4)
    d.rectangle((x0 + 26, F0 - 196, x0 + 168, F0 - 92), fill=(20, 20, 26), outline=OUT, width=5)
    d.rectangle((x0 + 92, F0 - 92, x0 + 102, F0 - 62), fill=(40, 40, 48))
    sx0, sy0, sx1, sy1 = x0 + 34, F0 - 188, x0 + 160, F0 - 100
    d.rectangle((sx0, sy0, sx1, sy1), fill=(60, 160, 80))
    d.line([((sx0 + sx1) / 2, sy0), ((sx0 + sx1) / 2, sy1)], fill=(230, 240, 230), width=2)
    d.ellipse(((sx0 + sx1) / 2 - 14, (sy0 + sy1) / 2 - 14, (sx0 + sx1) / 2 + 14, (sy0 + sy1) / 2 + 14), outline=(230, 240, 230), width=2)
    for gx in (sx0, sx1):
        d.rectangle((gx - 4, (sy0 + sy1) / 2 - 16, gx + 4, (sy0 + sy1) / 2 + 16), outline=(250, 250, 250), width=2)
    if t < GOAL_T:
        bx = (sx0 + sx1) / 2 + math.sin(t * 2.3) * 40 + (t / GOAL_T) * 10
        by = (sy0 + sy1) / 2 + math.sin(t * 3.1) * 22
    else:
        bx = sx1 - 6
        by = (sy0 + sy1) / 2
    d.ellipse((bx - 5, by - 5, bx + 5, by + 5), fill=(255, 255, 255), outline=OUT, width=1)
    for k in range(4):
        px = (sx0 + sx1) / 2 + math.sin(t * 1.7 + k * 1.6) * 50
        py = (sy0 + sy1) / 2 + math.cos(t * 1.3 + k) * 26
        d.ellipse((px - 4, py - 4, px + 4, py + 4), fill=(230, 60, 60) if k % 2 else (60, 100, 230))
    if flash > 0:
        paste_scaled(c, sprite("GOAL!", 30, (255, 255, 255)), (sx0 + sx1) / 2, sy0 + 16, 1, flash)
    paste_scaled(c, TV_GLOW, x0 + 97, F0 - 144, 1.1, 0.4)


def draw_app(d, x, y, kind, pressed):
    d.rounded_rectangle((x - 18, y - 30, x + 18, y + 30), 6, fill=(22, 22, 30), outline=OUT, width=3)
    if kind == "bet":
        d.rectangle((x - 14, y - 25, x + 14, y + 25), fill=(30, 60, 40))
        for k in range(3):
            d.rectangle((x - 11, y - 20 + k * 11, x + 11, y - 13 + k * 11), fill=(60, 110, 70))
        d.rounded_rectangle((x - 12, y + 12, x + 12, y + 22), 3, fill=(255, 210, 60) if not pressed else (255, 255, 255))
    else:
        d.rectangle((x - 14, y - 25, x + 14, y + 25), fill=(20, 30, 50))
        d.line([(x - 10, y + 6), (x - 3, y), (x + 3, y + 3), (x + 10, y - 10)], fill=GREEN, width=3)
        d.rounded_rectangle((x - 12, y + 12, x + 12, y + 22), 3, fill=GREEN if not pressed else (255, 255, 255))


def draw_slip(d, x, y, s=1.0):
    d.rectangle((x - 16 * s, y - 22 * s, x + 16 * s, y + 22 * s), fill=(248, 246, 238), outline=OUT, width=2)
    for k in range(3):
        d.line([(x - 10 * s, y - 12 * s + k * 7 * s), (x + 10 * s, y - 12 * s + k * 7 * s)], fill=(170, 170, 170), width=2)
    d.line([(x - 10 * s, y + 6 * s), (x + 10 * s, y + 18 * s)], fill=RED, width=3)
    d.line([(x + 10 * s, y + 6 * s), (x - 10 * s, y + 18 * s)], fill=RED, width=3)


def draw_popcorn(d, x, y):
    d.polygon([(x - 18, y - 30), (x + 18, y - 30), (x + 13, y + 14), (x - 13, y + 14)], fill=(240, 240, 240), outline=OUT)
    for k in range(3):
        d.rectangle((x - 14 + k * 11, y - 30, x - 9 + k * 11, y + 14), fill=(220, 60, 60))
    for k in range(6):
        d.ellipse((x - 18 + k * 7, y - 40 - (k % 2) * 6, x - 8 + k * 7, y - 28 - (k % 2) * 6), fill=(255, 245, 210), outline=OUT, width=1)


def banner(c, x, y, text, color, a):
    if a <= 0.02:
        return
    paste_scaled(c, fit_sprite(text, 58, color, 400), x, y, 0.6 + 0.4 * a, clamp(a * 2))


class Stage(StageBase):
    door = False

    def setup(self):
        c = self.cfg
        self.label = str(c["year"])
        self.s0, self.s1 = c["_prev_spent"], c["spent"]
        self.v0, self.v1 = c["_prev_inv"], c["inv"]
        self.maxv = self.data["_max_inv"]
        self.win = c.get("win", False)
        self.dark = room_overlay("L", (0, 0, 0), 8 + self.i * 9)
        self.slips0 = self.i * 2

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        s(0.6, "whistle", 0.35)
        s(0.9, "tick", 0.45)
        s(0.95, "beep", 0.3)
        s(1.0, "heartbeat", 0.4)
        s(GOAL_T, "cheer", 0.45)
        if self.win:
            s(GOAL_T + 0.1, "cash", 0.5)
        else:
            s(GOAL_T + 0.1, "fail", 0.4)
            s(GOAL_T + 0.25, "groan", 0.4)
        s(5.0, "tick", 0.45)
        s(5.05, "beep", 0.3)
        s(5.1, "heartbeat", 0.3)
        s(6.1, "whistle", 0.3)
        s(6.15, "fail", 0.4)
        s(6.3, "groan", 0.35)
        for k in range(5):
            s(1.4 + k * 0.45, "crunch", 0.2)
        s(6.3, "ding", 0.35)
        if self.final:
            s(7.0, "cash", 0.45)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def spent_now(self, t):
        return lerp(self.s0, self.s1, smooth(seg(t, 0.9, 6.2)))

    def inv_now(self, t):
        return lerp(self.v0, self.v1, smooth(seg(t, 0.9, 6.4)))

    def sit_person(self, c, x0, hands, mood, look, lean=0.0, head_drop=0.0, mouth_o=False, shake=0.0, extra=None):
        lay = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        info = person_fat(ld, x0 + SEAT, F0 + SIT_DY, 0.1, tuple(hands), mood=mood, look=look, lean=lean,
                          head_drop=head_drop, mouth_o=mouth_o, shake=shake, s=S)
        if extra:
            extra(ld, info)
        c.alpha_composite(lay, (x0, CEIL), (x0, CEIL, x0 + RW, F0 - 2))
        return info

    # ---- links: wetten
    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        n_sl = self.slips0 + (1 if t > 3.7 and not self.win else 0) + (1 if t > 6.3 else 0)
        for k in range(min(n_sl, 16)):
            draw_slip(d, x0 + 236 + (k % 8) * 27, 880 + (k // 8) * 52 + (k % 2) * 6, 0.62)
        flash = 1 - smooth(seg(t, GOAL_T + 0.6, GOAL_T + 1.0)) if t > GOAL_T else 0
        draw_tv_game(c, d, x0, t, flash)
        d = ImageDraw.Draw(c)
        draw_couch_back(d, x0)
        hands, mood, look, lean, head_drop, mouth_o, shake = [None, None], 0.0, -0.7, 0.0, 0.0, False, 0.0
        phone = 0.55 < t < 1.1 or 4.8 < t < 5.2
        if phone:
            hands[1] = (x0 + SEAT + 30 * S, F0 + SIT_DY - 200 * S)
            look = 0.3
            mood = 0.5
        tense = 1.1 < t < GOAL_T or 5.2 < t < 6.1
        if tense:
            lean = -0.12
            mood = -0.2
            mouth_o = int(t * 3) % 3 == 0
            hands = [(x0 + SEAT - 30 * S, F0 + SIT_DY - 190 * S), (x0 + SEAT + 30 * S, F0 + SIT_DY - 190 * S)]
        r1 = GOAL_T < t < 4.7
        if r1:
            if self.win:
                hands = [(x0 + SEAT - 62 * S, F0 + SIT_DY - 285 * S), (x0 + SEAT + 62 * S, F0 + SIT_DY - 285 * S)]
                mood = 1.0
            else:
                mood = -0.9
                mouth_o = True
                hands = [(x0 + SEAT - 44 * S, F0 + SIT_DY - 240 * S), (x0 + SEAT + 44 * S, F0 + SIT_DY - 240 * S)]
        if t > 6.15:
            mood = -0.9
            head_drop = smooth(seg(t, 6.2, 6.6)) * 0.9
            hands = [(x0 + SEAT - 26 * S, F0 + SIT_DY - 205 * S), (x0 + SEAT + 26 * S, F0 + SIT_DY - 205 * S)]

        def extra(ld, info):
            if phone:
                h = info["hands"][1]
                draw_app(ld, h[0] + 4, h[1] - 26, "bet", (0.88 < t < 1.0) or (4.98 < t < 5.1))
            if tense and self.i >= 2:
                hx, hy = info["head"]
                for k in range(2):
                    ph = ((t * 1.5) + k / 2) % 1
                    ld.ellipse((hx + (info["r"] + 4) * (1 if k else -1) - 5, hy - 10 + ph * 40 - 8,
                                hx + (info["r"] + 4) * (1 if k else -1) + 5, hy - 10 + ph * 40 + 6), fill=(130, 200, 255))

        info = self.sit_person(c, x0, hands, mood, look, lean, head_drop, mouth_o, shake, extra)
        d = ImageDraw.Draw(c)
        draw_couch_front(d, x0)
        hy = info["head"][1]
        self.float_text(c, "-$50", RED, x0 + SEAT + 40, hy - 90, t - 0.92, 44, 0.9)
        self.float_text(c, "-$50", RED, x0 + SEAT + 40, hy - 90, t - 5.02, 44, 0.9)
        a1 = ease_out_back(seg(t, GOAL_T, GOAL_T + 0.3)) * (1 - smooth(seg(t, 4.6, 4.9)))
        if self.win:
            banner(c, x0 + RW / 2, CEIL + 200, "WON +$120", GOLD, a1)
        else:
            banner(c, x0 + RW / 2, CEIL + 200, "LOST", RED, a1)
        a2 = ease_out_back(seg(t, 6.1, 6.4)) * (1 - smooth(seg(t, 7.6, 7.9)))
        banner(c, x0 + RW / 2, CEIL + 200, "LOST", RED, a2)

    def after_left(self, c, t):
        c.alpha_composite(self.dark, (ROOMS["L"], CEIL))

    # ---- rechts: investieren
    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        p = self.inv_now(t) / self.maxv
        draw_chart(d, x0 + 228, 852, x0 + 452, 1000, p)
        if self.final and t > 7.0:
            e = smooth(seg(t, 7.0, 7.6))
            paste_scaled(c, radial(260, GOLD, 120), x0 + 340, 926, 1.0, e * (0.7 + 0.3 * math.sin(t * 4)))
            d = ImageDraw.Draw(c)
        flash = 1 - smooth(seg(t, GOAL_T + 0.6, GOAL_T + 1.0)) if t > GOAL_T else 0
        draw_tv_game(c, d, x0, t, flash)
        d = ImageDraw.Draw(c)
        draw_couch_back(d, x0)
        hands, mood, look = [None, None], 0.6, -0.6
        phone = 0.55 < t < 1.1
        if phone:
            hands[1] = (x0 + SEAT + 30 * S, F0 + SIT_DY - 200 * S)
            look = 0.3
        pop = (1.2 < t < GOAL_T) or (4.7 < t < 6.0)
        if pop:
            ph = ((t - 1.2) % 0.45) / 0.45
            up = math.sin(math.pi * ph) ** 2
            hands[0] = (x0 + SEAT - 40 * S, F0 + SIT_DY - 150 * S)
            hands[1] = (x0 + SEAT + lerp(44, 18, up) * S, F0 + SIT_DY - lerp(160, 225, up) * S)
            mood = 0.7
        if GOAL_T < t < 4.6:
            hands = [(x0 + SEAT - 62 * S, F0 + SIT_DY - 285 * S), (x0 + SEAT + 62 * S, F0 + SIT_DY - 285 * S)]
            mood = 1.0
        if t > 6.3:
            hands = [(x0 + SEAT - 46 * S, F0 + SIT_DY - 262 * S), (x0 + SEAT + 46 * S, F0 + SIT_DY - 262 * S)]
            mood = 0.9
            look = 0.0
            if self.final and t > 7.0:
                hands = [(x0 + SEAT - 62 * S, F0 + SIT_DY - 285 * S), (x0 + SEAT + 62 * S, F0 + SIT_DY - 285 * S)]

        def extra(ld, info):
            if phone:
                h = info["hands"][1]
                draw_app(ld, h[0] + 4, h[1] - 26, "invest", 0.88 < t < 1.0)
            if pop:
                h = info["hands"][0]
                draw_popcorn(ld, h[0] + 6, h[1])

        info = self.sit_person(c, x0, hands, mood, look, extra=extra)
        d = ImageDraw.Draw(c)
        draw_couch_front(d, x0)
        self.float_text(c, "+$50 INVESTED", GREEN, x0 + SEAT, info["head"][1] - 100, t - 0.92, 38, 1.1)
        if self.v1 > self.v0:
            self.float_text(c, f"+{money(self.v1 - self.v0)}", GREEN, x0 + 340, 820, t - 6.3, 40, 1.2)

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, "YEAR", self.label, str(self.cfg["_prev_year"]) if self.cfg["_prev_year"] else None,
                           self.data.get("subtitle", "SAME GAME · SAME $50 A WEEK"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=64, s2=78)
        sp = self.spent_now(t)
        iv = self.inv_now(t)
        self.draw_counter(c, "L", "SPENT ON BETS", money(sp), RED if sp > 0 else (235, 235, 240))
        self.draw_counter(c, "R", "INVESTED", money(iv), GREEN if iv > 0 else (235, 235, 240))


def build_lib(rng):
    from wedding_video import build_lib as wed_lib
    lib = wed_lib(rng)

    def nz(n):
        return rng.normal(0, 1, n)

    n = int(0.6 * SR)
    t = np.arange(n) / SR
    tr = np.sin(2 * np.pi * 2900 * t) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 28 * t)))
    env = np.zeros(n)
    env[: int(0.18 * SR)] = 1
    env[int(0.26 * SR): int(0.55 * SR)] = 1
    lib["whistle"] = lowpass(tr * env, 6000) * 0.35
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    src = nz(n)
    crowd = lowpass(src, 900) - lowpass(src, 150)
    lib["groan"] = crowd * np.sin(np.pi * t / t[-1]) ** 2 * 1.4
    n = int(2.4 * SR)
    hb = np.zeros(n)
    for k in range(4):
        for off, g in ((0.0, 1.0), (0.18, 0.7)):
            i0 = int((k * 0.6 + off) * SR)
            m = int(0.12 * SR)
            if i0 + m < n:
                hb[i0:i0 + m] += sine_sweep(70, 40, 0.12) * np.exp(-np.arange(m) / (0.03 * SR)) * g
    lib["heartbeat"] = hb * 1.2
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
