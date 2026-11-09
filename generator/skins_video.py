#!/usr/bin/env python3
"""
"Gaming Skins" – von 12 bis 32 jeden Monat 40 $ für Skins vs. investieren.
Gleiches Spiel, gleicher Spaß. Am Ende: SERVER SHUTDOWN – alle Skins weg.

    python3 generator/skins_video.py skripte/zimmer/18_gaming_skins.json
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
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, SHELF, WOOD, draw_coin, draw_jar, paste_scaled, radial, room_overlay, seg, sprite  # noqa: E402
from wecker_video import person_fat  # noqa: E402
from scroll_video import draw_phone_screen  # noqa: E402
from zz_base import StageBase, fit_sprite, run  # noqa: E402

F0 = FL - 10
FIG = 286
SKIN_COLS = [(255, 90, 90), (90, 200, 255), (255, 200, 60), (170, 90, 255), (60, 220, 140), (255, 140, 40),
             (240, 240, 240), (40, 40, 40), (255, 110, 200), (120, 230, 255), (200, 160, 80), (90, 120, 255)]
DEFAULT = (130, 145, 170)
HAIR = (72, 52, 40)


def money(v):
    return f"${v:,.0f}"


def mini_hero(d, x, y, col, s=1.0, jump=0.0):
    y = y - jump
    d.rectangle((x - 7 * s, y - 20 * s, x + 7 * s, y), fill=col, outline=OUT, width=1)
    d.ellipse((x - 7 * s, y - 34 * s, x + 7 * s, y - 20 * s), fill=(246, 246, 250), outline=OUT, width=1)
    d.rectangle((x - 7 * s, y - 34 * s, x + 7 * s, y - 29 * s), fill=col)


def draw_monitor(c, d, x0, t, mode, hero_col, shop_sel=0, victory=0.0, shut=0.0):
    mx0, my0, mx1, my1 = x0 + 352, F0 - 272, x0 + 470, F0 - 132
    d.rectangle((x0 + 404, F0 - 132, x0 + 418, F0 - 110), fill=(50, 52, 62))
    d.rectangle((x0 + 386, F0 - 114, x0 + 436, F0 - 108), fill=(50, 52, 62))
    d.rectangle((mx0, my0, mx1, my1), fill=(18, 18, 24), outline=OUT, width=5)
    sx0, sy0, sx1, sy1 = mx0 + 6, my0 + 6, mx1 - 6, my1 - 6
    if shut > 0:
        g = int(40 * (1 - shut))
        d.rectangle((sx0, sy0, sx1, sy1), fill=(g, g, g + 4))
        if shut > 0.3:
            paste_scaled(c, sprite("SERVER", 20, RED), (sx0 + sx1) / 2, sy0 + 34, 1, clamp((shut - 0.3) * 3))
            paste_scaled(c, sprite("SHUTDOWN", 20, RED), (sx0 + sx1) / 2, sy0 + 58, 1, clamp((shut - 0.3) * 3))
            paste_scaled(c, sprite("SKINS: 0", 18, (220, 220, 230)), (sx0 + sx1) / 2, sy0 + 96, 1, clamp((shut - 0.5) * 3))
        return
    if mode == "shop":
        d.rectangle((sx0, sy0, sx1, sy1), fill=(36, 24, 60))
        for k in range(4):
            cx = sx0 + 26 + (k % 2) * 52
            cy = sy0 + 34 + (k // 2) * 52
            sel = k == shop_sel
            d.rounded_rectangle((cx - 22, cy - 22, cx + 22, cy + 22), 5, fill=(70, 50, 110) if not sel else (110, 80, 170),
                                outline=GOLD if sel else (90, 70, 130), width=3 if sel else 1)
            mini_hero(d, cx, cy + 14, SKIN_COLS[(shop_sel * 3 + k) % len(SKIN_COLS)] if not sel else hero_col, 0.8)
        return
    # Spiel
    d.rectangle((sx0, sy0, sx1, sy0 + (sy1 - sy0) * 0.7), fill=(110, 180, 250))
    d.rectangle((sx0, sy0 + (sy1 - sy0) * 0.7, sx1, sy1), fill=(80, 170, 90))
    gy = sy0 + (sy1 - sy0) * 0.7
    hx = sx0 + 30 + (math.sin(t * 1.4) * 0.5 + 0.5) * 40
    jump = max(0, math.sin(t * 5)) * 16
    mini_hero(d, hx, gy, hero_col, 1.0, jump)
    ex = sx1 - 20 - ((t * 30) % 60)
    d.ellipse((ex - 8, gy - 14, ex + 8, gy), fill=(230, 60, 60), outline=OUT, width=1)
    for k in range(3):
        cx = sx0 + 20 + k * 30 + ((t * 20) % 30)
        d.ellipse((cx - 4, sy0 + 20 + k * 6 - 4, cx + 4, sy0 + 20 + k * 6 + 4), fill=(255, 220, 80))
    if victory > 0:
        paste_scaled(c, sprite("VICTORY", 22, GOLD), (sx0 + sx1) / 2, sy0 + 26, 0.6 + 0.4 * victory, clamp(victory * 2))


def draw_desk(d, x0):
    d.rectangle((x0 + 222, F0 - 108, x0 + 470, F0 - 94), fill=WOOD, outline=OUT, width=4)
    d.rectangle((x0 + 236, F0 - 94, x0 + 462, F0), fill=(120, 88, 66), outline=OUT, width=4)
    d.line([(x0 + 244, F0 - 52), (x0 + 454, F0 - 52)], fill=(98, 70, 52), width=3)
    d.rectangle((x0 + 270, F0 - 116, x0 + 340, F0 - 108), fill=(40, 42, 52), outline=OUT, width=2)
    d.ellipse((x0 + 350, F0 - 118, x0 + 364, F0 - 106), fill=(40, 42, 52), outline=OUT, width=2)


def draw_chair(d, x0):
    d.rounded_rectangle((x0 + FIG - 48, F0 - 250, x0 + FIG + 48, F0 - 120), 16, fill=(200, 50, 70), outline=OUT, width=4)
    d.rectangle((x0 + FIG - 40, F0 - 240, x0 + FIG + 40, F0 - 228), fill=(40, 40, 50))


def draw_locker(d, x0, n, gray=0.0):
    d.rectangle((x0 + 24, 846, x0 + 236, 1000), fill=(30, 26, 40), outline=(210, 205, 195), width=5)
    for k in range(min(n, 18)):
        cx = x0 + 44 + (k % 6) * 34
        cy = 900 + (k // 6) * 46
        col = SKIN_COLS[k % len(SKIN_COLS)]
        col = tuple(int(lerp(v, 70, gray)) for v in col)
        mini_hero(d, cx, cy, col, 1.0)


def draw_poster(d, x0):
    d.rectangle((x0 + 30, 852, x0 + 140, 990), fill=(60, 40, 90), outline=(210, 205, 195), width=4)
    mini_hero(d, x0 + 85, 960, (120, 230, 255), 2.4)


class Stage(StageBase):
    door = False

    def setup(self):
        c = self.cfg
        self.age = c["age"]
        self.label = str(self.age)
        self.s0, self.s1 = c["_prev_spent"], c["spent"]
        self.v0, self.v1 = c["_prev_inv"], c["inv"]
        self.maxv = self.data["_max_inv"]
        self.sc = lerp(0.8, 1.15, clamp((self.age - 13) / 9))
        self.skins0 = self.i * 2
        self.t_shut = 1.6

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        s(0.7, "blip", 0.35)
        s(1.2, "tick", 0.45)
        s(1.25, "cash", 0.4)
        s(1.3, "sparkle", 0.45)
        s(0.75, "tick", 0.4)
        s(0.85, "clink", 0.42)
        s(1.0, "clink", 0.42)
        s(2.0, "typing", 0.3)
        for k in range(6):
            s(2.2 + k * 0.5, "blip", 0.18)
        if not self.final:
            s(5.4, "victory", 0.45)
            s(6.4, "pop", 0.3)
            s(6.5, "ding", 0.3)
        else:
            s(self.t_shut, "powerdown", 0.6)
            s(self.t_shut + 0.8, "fail", 0.45)
            s(3.0, "groan", 0.35)
            s(6.2, "cash", 0.45)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def spent_now(self, t):
        return lerp(self.s0, self.s1, smooth(seg(t, 0.7, 6.0)))

    def inv_now(self, t):
        return lerp(self.v0, self.v1, smooth(seg(t, 0.7, 6.0)))

    def seated(self, c, x0, hands, mood, look, head_drop=0.0, extra=None):
        fy = F0 - 40 + 92 * self.sc
        lay = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        info = person_fat(ld, x0 + FIG, fy, 0.1, tuple(hands), mood=mood, look=look, head_drop=head_drop, s=self.sc, hair=HAIR)
        if extra:
            extra(ld, info)
        c.alpha_composite(lay, (x0, CEIL), (x0, CEIL, x0 + RW, F0 - 2))
        return info

    def play_hands(self, x0, t):
        ph = t * 14
        return [(x0 + 300 + math.sin(ph) * 3, F0 - 118), (x0 + 356 + math.cos(ph * 1.2) * 4, F0 - 118)]

    # ---- links
    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        n_sk = self.skins0 + (1 if t > 1.25 else 0) + (1 if (t > 6.4 and not self.final) else 0)
        shut = smooth(seg(t, self.t_shut, self.t_shut + 1.0)) if self.final else 0.0
        draw_locker(d, x0, n_sk, gray=shut)
        draw_chair(d, x0)
        hero_col = SKIN_COLS[(n_sk - 1) % len(SKIN_COLS)] if n_sk > 0 else DEFAULT
        mode = "shop" if 0.6 < t < 1.9 else "game"
        draw_monitor(c, d, x0, t, mode, hero_col, shop_sel=self.i % 4,
                     victory=ease_out_back(seg(t, 5.4, 5.7)) * (1 - smooth(seg(t, 6.2, 6.4))) if not self.final else 0,
                     shut=shut)
        d = ImageDraw.Draw(c)
        hands, mood, look, head_drop = self.play_hands(x0, t), 0.6, 0.8, 0.0
        if mode == "shop":
            mood = 0.9
        if 5.4 < t < 6.3 and not self.final:
            hands = [(x0 + FIG - 55 * self.sc, F0 - 40 - 200 * self.sc), (x0 + FIG + 55 * self.sc, F0 - 40 - 200 * self.sc)]
            mood = 1.0
        if self.final and t > self.t_shut + 0.5:
            mood = -0.9
            head_drop = smooth(seg(t, 2.4, 3.2)) * 0.9
            hands = [None, None]
        self.seated(c, x0, hands, mood, look, head_drop)
        d = ImageDraw.Draw(c)
        draw_desk(d, x0)
        self.float_text(c, "-$40", RED, x0 + 410, F0 - 300, t - 1.25, 46, 0.9)
        if 1.25 < t < 2.4:
            self.float_text(c, "NEW SKIN!", GOLD, x0 + 300, F0 - 360, t - 1.3, 38, 0.9, 20)
        if not self.final and t > 6.4:
            self.float_text(c, f"SKINS: {n_sk}", (230, 230, 240), x0 + 130, 830, t - 6.4, 34, 1.5, 15)
        if self.final and t > self.t_shut + 0.9:
            self.float_text(c, "ALL SKINS GONE", RED, x0 + RW / 2, CEIL + 160, t - self.t_shut - 0.9, 40, 4.0, 5)

    def after_left(self, c, t):
        c.alpha_composite(room_overlay("L", (0, 0, 0), 6 + self.i * 6), (ROOMS["L"], CEIL))

    # ---- rechts
    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        draw_poster(d, x0)
        glow = smooth(seg(t, 6.2, 6.8)) * (0.75 + 0.25 * math.sin(t * 4)) if self.final else 0
        d = draw_jar(c, d, x0 + 400, SHELF[2], self.inv_now(t) / self.maxv, glow)
        draw_chair(d, x0)
        draw_monitor(c, d, x0, t, "game", DEFAULT,
                     victory=ease_out_back(seg(t, 5.4, 5.7)) * (1 - smooth(seg(t, 6.2, 6.4))))
        d = ImageDraw.Draw(c)
        hands, mood, look = self.play_hands(x0, t), 0.7, 0.8
        phone = 0.6 < t < 1.2
        if phone:
            hands = [None, (x0 + FIG + 34 * self.sc, F0 - 40 - 205 * self.sc)]
            look = 0.2
        if 5.4 < t < 6.3 or (self.final and t > 6.2):
            hands = [(x0 + FIG - 55 * self.sc, F0 - 40 - 200 * self.sc), (x0 + FIG + 55 * self.sc, F0 - 40 - 200 * self.sc)]
            mood = 1.0

        def extra(ld, info):
            if phone:
                h = info["hands"][1]
                draw_phone_screen(ld, h[0] + 4, h[1] - 24, 32, 52, t, scroll=False)

        info = self.seated(c, x0, hands, mood, look, extra=extra)
        d = ImageDraw.Draw(c)
        draw_desk(d, x0)
        for k, ta in enumerate((0.8, 0.95)):
            p = seg(t, ta, ta + 0.22)
            if 0 < p < 1:
                draw_coin(d, lerp(x0 + 330, x0 + 400, p), lerp(F0 - 260, SHELF[2] - 170, p) - math.sin(math.pi * p) * 60)
        self.float_text(c, "+$40", GREEN, x0 + 400, SHELF[2] - 200, t - 0.9, 44, 0.9)
        if self.v1 > self.v0 and not self.final:
            self.float_text(c, f"+{money(self.v1 - self.v0)}", GREEN, x0 + 330, 820, t - 6.4, 38, 1.2)

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, "AGE", self.label, str(self.cfg["_prev_age"]) if self.cfg["_prev_age"] else None,
                           self.data.get("subtitle", "SAME GAME · SAME $40 A MONTH"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=64, s2=74)
        sp = self.spent_now(t)
        iv = self.inv_now(t)
        self.draw_counter(c, "L", "SPENT ON SKINS", money(sp), RED if sp > 0 else (235, 235, 240))
        self.draw_counter(c, "R", "INVESTED", money(iv), GREEN if iv > 0 else (235, 235, 240))


def build_lib(rng):
    from party_video import build_lib as party_lib
    lib = party_lib(rng)

    def sq(f, dur):
        n = int(dur * SR)
        t = np.arange(n) / SR
        return np.sign(np.sin(2 * np.pi * f * t))

    n = int(0.12 * SR)
    lib["blip"] = (sq(880, 0.06).tolist() + sq(1320, 0.06).tolist())
    lib["blip"] = np.array(lib["blip"]) * 0.12
    notes = [523, 659, 784, 1047]
    v = []
    for k, f in enumerate(notes):
        dur = 0.11 if k < 3 else 0.35
        seg_ = sq(f, dur) * np.exp(-np.arange(int(dur * SR)) / ((0.08 if k < 3 else 0.2) * SR))
        v.extend(seg_.tolist())
    lib["victory"] = np.array(v) * 0.14
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    lib["powerdown"] = (sine_sweep(900, 60, 1.2) * np.exp(-t / 0.6) * 0.5 + lowpass(rng.normal(0, 1, n), 800) * np.exp(-t / 0.2) * 0.5)
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
