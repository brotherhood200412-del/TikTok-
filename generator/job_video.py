#!/usr/bin/env python3
"""
"Same Job, 5 Years" – gleicher Job, gleiches Startgehalt.
Links: nach Feierabend Sofa, TV, Chips, einschlafen. Rechts: lernt abends am Laptop,
Zertifikate, Beförderungen. SALARY: $30,000 -> $33,100 vs. $30,000 -> $90,000.

    python3 generator/job_video.py skripte/zimmer/13_same_job_5_years.json
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
from zimmer_video import CEIL, DOOR, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, WOOD, paste_scaled, radial, seg, sprite  # noqa: E402
from wecker_video import draw_food, person_fat  # noqa: E402
from scroll_video import draw_phone_screen  # noqa: E402
from penny_video import draw_sign  # noqa: E402
from zz_base import StageBase, fit_sprite, run  # noqa: E402

S = 1.15
F0 = FL - 10
SEAT_X = 330
SIT_DY = 36 + 70          # Figur so tief, dass die Hüfte auf Sitzhöhe ist
GLOW_BLUE = radial(300, (110, 170, 255), 90)
GLOW_GOLD = radial(300, GOLD, 120)
CONF_COLS = [(255, 90, 110), (255, 210, 80), (90, 200, 255), (120, 230, 150), (200, 140, 255)]


def money(v):
    return f"${v:,.0f}"


# ----------------------------------------------------------------- props
def draw_door_anim(d, x0, open_):
    dx0, dx1 = x0 + DOOR[0], x0 + DOOR[1]
    d.rectangle((dx0, FL - 298, dx1, FL - 10), fill=(14, 12, 16))
    w = (dx1 - dx0) * (1 - 0.8 * open_)
    d.rectangle((dx0, FL - 298, dx0 + w, FL - 10), fill=(120, 86, 64), outline=OUT, width=4)
    if open_ < 0.5:
        d.ellipse((dx0 + w - 22, FL - 160, dx0 + w - 10, FL - 148), fill=GOLD)


def draw_couch_back(d, x0):
    d.rounded_rectangle((x0 + 205, F0 - 178, x0 + 468, F0 - 70), 22, fill=(150, 70, 80), outline=OUT, width=4)


def draw_couch_front(d, x0):
    d.rounded_rectangle((x0 + 210, F0 - 92, x0 + 464, F0), 14, fill=(170, 84, 94), outline=OUT, width=4)
    d.line([(x0 + 218, F0 - 46), (x0 + 456, F0 - 46)], fill=(140, 64, 74), width=3)
    for ax in (x0 + 196, x0 + 444):
        d.rounded_rectangle((ax, F0 - 128, ax + 32, F0 - 22), 12, fill=(150, 70, 80), outline=OUT, width=4)


def draw_tv(c, d, x0, on, t):
    d.rectangle((x0 + 22, F0 - 62, x0 + 172, F0), fill=(90, 66, 52), outline=OUT, width=4)
    d.rectangle((x0 + 26, F0 - 196, x0 + 168, F0 - 92), fill=(20, 20, 26), outline=OUT, width=5)
    d.rectangle((x0 + 92, F0 - 92, x0 + 102, F0 - 62), fill=(40, 40, 48))
    if on:
        cols = [(90, 150, 255), (255, 120, 150), (120, 230, 170), (255, 210, 90)]
        ccol = cols[int(t * 2.5) % 4]
        d.rectangle((x0 + 34, F0 - 188, x0 + 160, F0 - 100), fill=ccol)
        d.ellipse((x0 + 70 + 20 * math.sin(t * 3), F0 - 170, x0 + 110 + 20 * math.sin(t * 3), F0 - 120), fill=(255, 255, 255))
        paste_scaled(c, GLOW_BLUE, x0 + 97, F0 - 144, 1.1, 0.5)


def draw_chair_back(d, x0):
    d.rounded_rectangle((x0 + SEAT_X - 46, F0 - 236, x0 + SEAT_X + 46, F0 - 110), 16, fill=(44, 46, 58), outline=OUT, width=4)


def draw_desk(d, x0):
    d.rectangle((x0 + 222, F0 - 108, x0 + 470, F0 - 94), fill=WOOD, outline=OUT, width=4)
    for lx in (x0 + 232, x0 + 452):
        d.rectangle((lx, F0 - 94, lx + 12, F0), fill=(70, 50, 38), outline=OUT, width=2)
    d.rectangle((x0 + 236, F0 - 94, x0 + 462, F0), fill=(120, 88, 66), outline=OUT, width=4)
    d.line([(x0 + 244, F0 - 52), (x0 + 454, F0 - 52)], fill=(98, 70, 52), width=3)


def draw_laptop(c, d, x0, on, t, progress, lesson):
    bx = x0 + 420
    d.polygon([(bx - 52, F0 - 108), (bx + 44, F0 - 108), (bx + 40, F0 - 116), (bx - 48, F0 - 116)], fill=(170, 172, 182), outline=OUT)
    d.rectangle((bx - 44, F0 - 206, bx + 40, F0 - 118), fill=(28, 30, 40), outline=OUT, width=4)
    if on:
        sx0, sy0, sx1, sy1 = bx - 38, F0 - 200, bx + 34, F0 - 124
        d.rectangle((sx0, sy0, sx1, sy1), fill=(18, 22, 34))
        cols = [(120, 200, 255), (255, 170, 110), (140, 230, 160), (220, 150, 255)]
        off = (t * 26) % 9
        for k in range(8):
            y = sy0 + 6 + k * 9 - off
            if sy0 + 2 < y < sy1 - 14:
                w = 14 + ((k * 37 + int(t * 3)) % 36)
                indent = (k % 3) * 6
                d.line([(sx0 + 4 + indent, y), (sx0 + 4 + indent + w, y)], fill=cols[k % 4], width=3)
        d.rectangle((sx0 + 2, sy1 - 9, sx1 - 2, sy1 - 3), fill=(50, 54, 70))
        d.rectangle((sx0 + 2, sy1 - 9, sx0 + 2 + (sx1 - sx0 - 4) * progress, sy1 - 3), fill=GREEN)
        paste_scaled(c, GLOW_BLUE, bx - 2, F0 - 160, 0.8, 0.35)


def draw_books(d, x0, n):
    cols = [(230, 90, 90), (90, 160, 240), (250, 200, 80), (120, 210, 150), (190, 130, 240), (240, 150, 90), (100, 200, 220)]
    for k in range(min(n, 9)):
        w = 46 - (k % 3) * 4
        y = F0 - 108 - k * 12
        d.rectangle((x0 + 252 - w / 2 + (k % 2) * 3, y - 11, x0 + 252 + w / 2 + (k % 2) * 3, y), fill=cols[k % len(cols)], outline=OUT, width=2)


def draw_cert(d, x, y, pop=1.0):
    if pop <= 0.2:
        return
    w, h = 52 * pop, 40 * pop
    d.rectangle((x - w / 2, y - h / 2, x + w / 2, y + h / 2), fill=(60, 48, 36), outline=GOLD, width=3)
    d.rectangle((x - w / 2 + 5, y - h / 2 + 5, x + w / 2 - 5, y + h / 2 - 5), fill=(250, 246, 232))
    for k in range(2):
        d.line([(x - w / 3, y - 6 * pop + k * 8 * pop), (x + w / 3, y - 6 * pop + k * 8 * pop)], fill=(170, 165, 150), width=2)
    d.ellipse((x + w / 4 - 5 * pop, y + 4 * pop, x + w / 4 + 5 * pop, y + 14 * pop), fill=(220, 60, 70))


def draw_tie(d, info, s=S):
    hx, hy = info["head"]
    r = info["r"]
    top = hy + r + 2
    d.polygon([(hx - 16 * s, top), (hx, top + 14 * s), (hx + 16 * s, top)], fill=(250, 250, 250), outline=OUT)
    d.polygon([(hx - 6 * s, top + 8 * s), (hx + 6 * s, top + 8 * s), (hx + 9 * s, top + 58 * s), (hx, top + 70 * s), (hx - 9 * s, top + 58 * s)],
              fill=(200, 40, 60), outline=OUT)


# ----------------------------------------------------------------- stage
class Stage(StageBase):
    door = True

    def setup(self):
        c = self.cfg
        self.label = str(c["month"])
        self.sl0, self.sl1 = c["_prev_left"], c["left"]
        self.sr0, self.sr1 = c["_prev_right"], c["right"]
        self.title_l = c.get("title_left", "ASSISTANT")
        self.title_r0, self.title_r1 = c["_prev_title_right"], c.get("title_right", "ASSISTANT")
        self.certs0 = c["_prev_certs"]
        self.certs1 = c.get("certs", self.certs0)
        self.promo = self.sr1 > self.sr0
        self.raise_l = self.sl1 > self.sl0
        self.tie = c.get("tie", False)
        self.fat_l = 0.1 + 0.05 * self.i
        self.t_news = 7.0
        self.t_cert = 5.9
        rnd = random.Random(self.i * 9 + 1)
        self.conf = [(rnd.uniform(-1, 1), rnd.uniform(0.6, 1.2), rnd.choice(CONF_COLS), rnd.uniform(0, 6)) for _ in range(26)]

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        s(0.4, "door", 0.4)
        for st in (0.6, 0.85, 1.1, 1.35):
            s(st, "step", 0.3)
        s(1.45, "thud", 0.35)
        s(1.6, "tick", 0.45)
        s(1.7, "tvchatter", 0.25)
        for k in range(4):
            s(2.2 + k * 0.6, "crunch", 0.32)
        s(4.0, "laugh", 0.3)
        s(6.3, "snore", 0.3)
        s(7.3, "snore", 0.22)
        s(1.7, "typing", 0.35)
        s(3.6, "glug", 0.3)
        s(4.5, "pop", 0.35)
        if self.certs1 > self.certs0:
            s(self.t_cert, "ding", 0.5)
        s(self.t_news, "notif", 0.45)
        if self.promo:
            s(self.t_news + 0.25, "cash", 0.5)
            s(self.t_news + 0.3, "sparkle", 0.45)
        if self.raise_l:
            s(self.t_news + 0.4, "pop", 0.25)
        if self.final:
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def walk_in(self, t, x0):
        """0.4..1.4 rein durch die Tür, 1.4..1.6 hinsetzen."""
        k = smooth(seg(t, 0.45, 1.4))
        x = lerp(x0 + 64, x0 + SEAT_X, k)
        walking = 0.45 < t < 1.4
        sit = smooth(seg(t, 1.4, 1.6))
        return x, walking, sit

    def news(self, c, x, y, title, sub, color, t):
        a = ease_out_back(seg(t, self.t_news, self.t_news + 0.35))
        if a <= 0.02:
            return
        paste_scaled(c, fit_sprite(title, 46, color, 420), x, y, a, clamp(a * 2))
        if sub:
            paste_scaled(c, fit_sprite(sub, 34, (235, 235, 245), 420), x, y + 48, a, clamp(a * 2))

    # ---- links
    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        draw_sign(c, x0 + 385, 905, self.title_l, (200, 200, 215))
        d = ImageDraw.Draw(c)
        door_open = smooth(seg(t, 0.35, 0.5)) * (1 - smooth(seg(t, 1.2, 1.4)))
        draw_door_anim(d, x0, door_open)
        tv_on = t > 1.6 and not (t > 6.2)
        draw_tv(c, d, x0, tv_on or (t > 6.2 and int(t * 3) % 2 == 0), t)
        d = ImageDraw.Draw(c)
        draw_couch_back(d, x0)
        fx, walking, sit = self.walk_in(t, x0)
        hands, look, mood, head_drop, mouth_o = [None, None], -0.6, -0.2, 0.0, False
        if walking:
            mood = -0.5
            look = 1
            head_drop = 0.3
        if t > 1.6:
            look = -0.8
            mood = 0.3
        chips = 1.8 < t < 4.4
        phone = 4.5 < t < 6.1
        if chips:
            ph = ((t - 1.8) % 0.6) / 0.6
            up = math.sin(math.pi * ph) ** 2
            hands[1] = (fx + lerp(50, 18, up) * S, F0 + SIT_DY * sit - lerp(150, 225, up) * S)
        if 3.9 < t < 4.4:
            mouth_o = int(t * 8) % 2 == 0
            mood = 0.9
        if phone:
            hands[1] = (fx + 30 * S, F0 + SIT_DY - 200 * S)
            look = 0.3
        if t > 6.2:
            head_drop = smooth(seg(t, 6.2, 6.8)) * 1.0
            mood = 0.0
            look = -0.3
        fy = F0 + SIT_DY * sit
        lay = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        info = person_fat(ld, fx, fy, self.fat_l, tuple(hands), walk=(t - 0.45) * 14 if walking else 0, mood=mood, look=look,
                          head_drop=head_drop, mouth_o=mouth_o, s=S)
        if chips:
            h = info["hands"][1]
            draw_food(ld, "chips", h[0] + 6, h[1] - 18)
        if phone:
            h = info["hands"][1]
            draw_phone_screen(ld, h[0] + 4, h[1] - 26, 34, 56, t)
        c.alpha_composite(lay, (x0, CEIL), (x0, CEIL, x0 + RW, F0 - 2))
        d = ImageDraw.Draw(c)
        draw_couch_front(d, x0)
        if t > 6.3:
            hx, hy = info["head"]
            for k in range(3):
                ph = ((t - 6.3) * 0.8 + k / 3) % 1
                paste_scaled(c, sprite("z", 26 + 10 * k, (200, 210, 255)), hx + 30 + ph * 40 + k * 8, hy - 40 - ph * 80, 1, math.sin(math.pi * ph))
        if self.raise_l:
            self.news(c, x0 + RW / 2, CEIL + 120, f"+{(self.sl1 - self.sl0) / self.sl0 * 100:.0f}% RAISE", money(self.sl1), (200, 200, 215), t)
        elif self.i > 0:
            self.news(c, x0 + RW / 2, CEIL + 120, "NO RAISE", "", (170, 170, 185), t)

    def after_left(self, c, t):
        c.alpha_composite(self.dark_overlay(), (ROOMS["L"], CEIL))

    def dark_overlay(self):
        from zimmer_video import room_overlay
        return room_overlay("L", (0, 0, 0), 8 + self.i * 10)

    # ---- rechts
    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        title = self.title_r1 if t > self.t_news + 0.2 else self.title_r0
        pop = ease_out_back(seg(t, self.t_news + 0.2, self.t_news + 0.5)) if (self.promo and title == self.title_r1 and self.title_r1 != self.title_r0) else 1
        if pop > 0.05:
            tmp = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
            draw_sign(tmp, 150, 50, title, GOLD if title != "ASSISTANT" else (200, 200, 215))
            paste_scaled(c, tmp, x0 + 385, 905, pop, 1)
            d = ImageDraw.Draw(c)
        n_c = self.certs0 + (self.certs1 - self.certs0 if t > self.t_cert else 0)
        for k in range(min(n_c, 6)):
            pp = ease_out_back(seg(t, self.t_cert, self.t_cert + 0.3)) if k >= self.certs0 else 1
            draw_cert(d, x0 + 160 + (k % 3) * 60 - 100, 870 + (k // 3) * 50, pp)
        door_open = smooth(seg(t, 0.35, 0.5)) * (1 - smooth(seg(t, 1.2, 1.4)))
        draw_door_anim(d, x0, door_open)
        draw_chair_back(d, x0)
        fx, walking, sit = self.walk_in(t, x0)
        hands, look, mood, head_drop = [None, None], 0.8, 0.3, 0.0
        typing = 1.7 < t < 5.6 and not (3.4 < t < 4.0)
        if walking:
            mood = 0.0
            look = 1
            head_drop = 0.15
        if typing:
            ph = t * 18
            hands = [(x0 + 380 + math.sin(ph) * 4, F0 - 118 + abs(math.sin(ph)) * -6),
                     (x0 + 410 + math.cos(ph * 1.3) * 4, F0 - 118 + abs(math.cos(ph * 1.3)) * -6)]
            look = 1
            mood = 0.5
        if 3.4 <= t < 4.0:
            ph = (t - 3.4) / 0.6
            up = math.sin(math.pi * ph)
            hands[1] = (fx + lerp(50, 20, up) * S, F0 + SIT_DY * sit - lerp(140, 220, up) * S)
        if 4.4 < t < 4.8:
            hands[0] = (x0 + 255, F0 - 125)
        if t > self.t_news and self.promo:
            mood = 1.0
            hands = [(fx - 62 * S, F0 + SIT_DY - 280 * S), (fx + 62 * S, F0 + SIT_DY - 280 * S)]
        fy = F0 + SIT_DY * sit
        lay = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        info = person_fat(ld, fx, fy, 0.1, tuple(hands), walk=(t - 0.45) * 14 if walking else 0, mood=mood, look=look,
                          head_drop=head_drop, s=S)
        if self.tie:
            draw_tie(ld, info)
        if 3.4 <= t < 4.0:
            h = info["hands"][1]
            ld.rounded_rectangle((h[0] - 4, h[1] - 34, h[0] + 22, h[1] - 6), 4, fill=(250, 250, 245), outline=OUT, width=3)
            ld.arc((h[0] + 16, h[1] - 28, h[0] + 30, h[1] - 14), -90, 90, fill=OUT, width=3)
        c.alpha_composite(lay, (x0, CEIL), (x0, CEIL, x0 + RW, F0 - 2))
        d = ImageDraw.Draw(c)
        draw_desk(d, x0)
        nb = self.i + (1 if t > 4.5 else 0)
        draw_books(d, x0, nb)
        lesson_p = (self.i + seg(t, 1.7, 5.6)) / 7
        draw_laptop(c, d, x0, t > 1.6, t, lesson_p, self.i)
        d = ImageDraw.Draw(c)
        if self.certs1 > self.certs0 and t > self.t_cert:
            self.float_text(c, "CERTIFIED", GOLD, x0 + 120, 830, t - self.t_cert, 34, 0.9)
        if self.promo:
            if t > self.t_news:
                e = ease_out_cubic(seg(t, self.t_news, self.t_news + 0.8))
                paste_scaled(c, GLOW_GOLD, fx, info["head"][1], 0.5 + e, (1 - e) * 0.8)
                d = ImageDraw.Draw(c)
                for dx, sp, col, ph in self.conf:
                    k = t - self.t_news
                    if k < 2.2:
                        x = fx + dx * 160 * min(1, k * 2) + math.sin(k * 4 + ph) * 10
                        y = CEIL + 100 + k * 260 * sp
                        d.rectangle((x - 5, y - 3, x + 5, y + 3), fill=col)
            self.news(c, x0 + RW / 2, CEIL + 120, "PROMOTED!", f"{self.title_r1} · {money(self.sr1)}", GOLD, t)

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, "MONTH", self.label, str(self.cfg["_prev_month"]) if self.cfg["_prev_month"] else None,
                           self.data.get("subtitle", "SAME JOB · SAME $30K START"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=62, s2=64)
        after = t > self.t_news + 0.3
        sl = self.sl1 if after else self.sl0
        sr = self.sr1 if after else self.sr0
        bl = 1 + 0.12 * (1 - smooth(seg(t, self.t_news + 0.3, self.t_news + 0.6))) if (after and self.raise_l) else 1
        br = 1 + 0.18 * (1 - smooth(seg(t, self.t_news + 0.3, self.t_news + 0.6))) if (after and self.promo) else 1
        self.draw_counter(c, "L", "SALARY", f"{money(sl)}/yr", (235, 235, 240), bump=bl)
        self.draw_counter(c, "R", "SALARY", f"{money(sr)}/yr", GREEN if sr > self.data["start"] else (235, 235, 240), bump=br)


# ----------------------------------------------------------------- audio
def build_lib(rng):
    from penny_video import build_lib as penny_lib
    lib = penny_lib(rng)

    def nz(n):
        return rng.normal(0, 1, n)

    n = int(0.85 * SR)
    t = np.arange(n) / SR
    creak = lowpass(2 * ((np.cumsum(180 + 40 * np.sin(2 * np.pi * 2 * t)) / SR) % 1) - 1, 900) * np.sin(np.pi * t / t[-1]) ** 2 * 0.3
    thud = np.zeros(n)
    m = int(0.25 * SR)
    thud[int(0.55 * SR):int(0.55 * SR) + m] = lowpass(nz(m), 400)[: m] * np.exp(-np.arange(m) / (0.05 * SR)) * 1.4
    lib["door"] = creak + thud
    n = int(4.2 * SR)
    t = np.arange(n) / SR
    src = nz(n)
    voice = lowpass(src, 1800) - lowpass(src, 300)
    am = 0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 2.3 * t) * np.sin(2 * np.pi * 0.7 * t + 1))
    lib["tvchatter"] = voice * am * np.minimum(1, t / 0.2) * np.minimum(1, (4.2 - t) / 0.4) * 0.5
    n = int(3.6 * SR)
    ty = np.zeros(n)
    k = 0.0
    while k < 3.5:
        i0 = int(k * SR)
        m = int(0.012 * SR)
        ty[i0:i0 + m] += (rng.normal(0, 1, m) + np.sin(2 * np.pi * rng.uniform(1800, 2600) * np.arange(m) / SR)) * np.exp(-np.arange(m) / (0.003 * SR))
        k += rng.uniform(0.06, 0.16)
    lib["typing"] = ty * 0.5
    return lib


def build(data):
    stages, t = [], 0.0
    pl = pr = data["start"]
    ptitle = "ASSISTANT"
    pcerts = 0
    pm = None
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_left"], sc["_prev_right"], sc["_prev_title_right"], sc["_prev_certs"], sc["_prev_month"] = pl, pr, ptitle, pcerts, pm
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        pl, pr, pm = sc["left"], sc["right"], sc["month"]
        ptitle = sc.get("title_right", ptitle)
        pcerts = sc.get("certs", pcerts)
    return stages, t


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p, build, build_lib)
