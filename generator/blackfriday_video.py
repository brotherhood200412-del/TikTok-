#!/usr/bin/env python3
"""
"Black Friday" – 7 Deals. Links kauft alles ("SAVED" $500, SPENT $2,000), rechts wischt alles weg.
Oben: BLACK-FRIDAY-Schild mit Countdown statt Kalender.

    python3 generator/blackfriday_video.py skripte/zimmer/19_black_friday.json
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import F_BLACK, F_BOLD, SR, clamp, ease_out_back, ease_out_cubic, font  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import (CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, SHELF, draw_box, draw_sneaker, draw_tv,  # noqa: E402
                          draw_watch, paste_scaled, room_overlay, seg, spaced, sprite)
from wecker_video import person_fat  # noqa: E402
from scroll_video import draw_phone_screen  # noqa: E402
from zz_base import StageBase, fit_sprite, run  # noqa: E402

S = 1.15
F0 = FL - 10
FIG = 250
TOTAL_SECONDS = 6 * 3600


def money(v):
    return f"${v:,.0f}"


# ----------------------------------------------------------------- Produkte
def draw_airfryer(d, x, y):
    d.rounded_rectangle((x - 34, y - 80, x + 34, y), 14, fill=(40, 40, 46), outline=OUT, width=4)
    d.rounded_rectangle((x - 22, y - 60, x + 22, y - 24), 6, fill=(90, 90, 100))
    d.ellipse((x - 6, y - 74, x + 6, y - 62), fill=(255, 140, 40))


def draw_headphones(d, x, y):
    d.arc((x - 30, y - 56, x + 30, y + 4), 180, 360, fill=(30, 30, 36), width=8)
    for sx in (x - 30, x + 30):
        d.rounded_rectangle((sx - 10, y - 26, sx + 10, y + 4), 6, fill=(220, 60, 80), outline=OUT, width=3)


def draw_hoodie(d, x, y):
    d.polygon([(x - 46, y - 70), (x - 18, y - 84), (x + 18, y - 84), (x + 46, y - 70), (x + 40, y - 40), (x + 30, y - 46),
               (x + 30, y + 20), (x - 30, y + 20), (x - 30, y - 46), (x - 40, y - 40)], fill=(255, 150, 40), outline=OUT)
    d.arc((x - 18, y - 92, x + 18, y - 64), 0, 180, fill=OUT, width=3)


def draw_gaming_chair(d, x, y):
    d.rounded_rectangle((x - 40, y - 210, x + 40, y - 90), 16, fill=(40, 40, 48), outline=OUT, width=4)
    d.rectangle((x - 30, y - 200, x + 30, y - 150), fill=(220, 50, 70))
    d.rounded_rectangle((x - 46, y - 100, x + 46, y - 76), 8, fill=(40, 40, 48), outline=OUT, width=4)
    d.line([(x, y - 76), (x, y - 20)], fill=(60, 60, 70), width=8)
    d.line([(x - 36, y - 6), (x + 36, y - 6)], fill=(60, 60, 70), width=7)


ITEMS = {
    "TV": lambda d, x0: draw_tv(d, x0 + 330, 900),
    "SNEAKERS": lambda d, x0: draw_sneaker(d, x0 + 345, SHELF[2]),
    "AIR FRYER": lambda d, x0: draw_airfryer(d, x0 + 70, F0),
    "HEADPHONES": lambda d, x0: draw_headphones(d, x0 + 430, SHELF[2] - 4),
    "HOODIE": lambda d, x0: draw_hoodie(d, x0 + 70, 900),
    "GAMING CHAIR": lambda d, x0: draw_gaming_chair(d, x0 + 410, F0),
    "SMARTWATCH": lambda d, x0: draw_watch(d, x0 + 395, SHELF[2] - 20, 0.8),
}


def deal_card(name, was, now, mode, t_local):
    """mode: 'buy' (BUY-Knopf gedrückt) oder 'skip' (X)."""
    w, h = 300, 214
    img = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((10, 10, 10 + w, 10 + h), 20, fill=(252, 250, 246), outline=OUT, width=5)
    d.rounded_rectangle((10, 10, 10 + w, 56), 20, fill=(20, 20, 24))
    d.rectangle((10, 36, 10 + w, 56), fill=(20, 20, 24))
    paste_scaled(img, fit_sprite(name, 30, (255, 255, 255), w - 30), 10 + w / 2, 33, 1, 1)
    was_spr = sprite(f"WAS {money(was)}", 26, (130, 130, 140), F_BOLD)
    paste_scaled(img, was_spr, 10 + w / 2, 80, 1, 1)
    d = ImageDraw.Draw(img)
    ww = was_spr.width - 80
    d.line([(10 + w / 2 - ww / 2, 80), (10 + w / 2 + ww / 2, 80)], fill=RED, width=4)
    paste_scaled(img, sprite(f"NOW {money(now)}", 46, RED), 10 + w / 2, 122, 1, 1)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((26, 152, 150, 202), 14, fill=GOLD, outline=OUT, width=3)
    paste_scaled(img, sprite(f"SAVE {money(was - now)}", 20, (30, 30, 36)), 88, 177, 1, 1)
    d = ImageDraw.Draw(img)
    if mode == "buy":
        pressed = t_local > 0
        d.rounded_rectangle((166, 152, 296, 202), 14, fill=(255, 255, 255) if pressed else (60, 200, 110), outline=OUT, width=3)
        paste_scaled(img, sprite("BUY", 28, (30, 30, 36)), 231, 177, 1, 1)
    else:
        d.rounded_rectangle((166, 152, 296, 202), 14, fill=(80, 80, 92), outline=OUT, width=3)
        paste_scaled(img, sprite("✕ SKIP" if False else "SKIP", 26, (240, 240, 245)), 231, 177, 1, 1)
    return img


def draw_statement(d, x, y):
    d.rectangle((x - 70, y - 90, x + 70, y + 90), fill=(250, 250, 245), outline=OUT, width=4)
    d.rectangle((x - 70, y - 90, x + 70, y - 60), fill=(30, 30, 40))
    for k in range(5):
        d.line([(x - 54, y - 40 + k * 16), (x + 54, y - 40 + k * 16)], fill=(170, 170, 175), width=3)


def countdown_sign(remaining, final_alpha=1.0, ended=False):
    w, h = 560, 210
    img = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((20, 20, 20 + w, 20 + h), 26, fill=(20, 20, 24), outline=(230, 40, 60), width=8)
    paste_scaled(img, sprite("BLACK FRIDAY", 50, (255, 255, 255)), 20 + w / 2, 66, 1, 1)
    if ended:
        paste_scaled(img, sprite("SALE ENDED", 64, (230, 40, 60)), 20 + w / 2, 160, 1, 1)
        return img
    paste_scaled(img, sprite(spaced("SALE ENDS IN"), 22, (230, 40, 60), F_BOLD), 20 + w / 2, 104, 1, 1)
    hh = int(remaining // 3600)
    mm = int(remaining % 3600 // 60)
    ss = int(remaining % 60)
    txt = f"{hh:02d}:{mm:02d}:{ss:02d}"
    cw = 46
    x = 20 + w / 2 - cw * len(txt) / 2 + cw / 2
    for ch in txt:
        paste_scaled(img, sprite(ch, 76, (255, 220, 80)), x, 168, 1, 1)
        x += cw
    return img


# ----------------------------------------------------------------- stage
class Stage(StageBase):
    door = False

    def setup(self):
        c = self.cfg
        self.name, self.was, self.now = c["item"], c["was"], c["now"]
        self.sp0, self.sv0 = c["_prev_spent"], c["_prev_saved"]
        self.sp1, self.sv1 = self.sp0 + self.now, self.sv0 + (self.was - self.now)
        self.bought_before = c["_bought"]
        self.t_card, self.t_buy, self.t_box = 0.3, 1.3, 2.2

    def schedule(self):
        s = self.sfx
        s(self.t_card, "notif", 0.45)
        s(self.t_card + 0.05, "pop_big", 0.35)
        s(self.t_buy, "tick", 0.5)
        s(self.t_buy + 0.05, "cash", 0.45)
        s(self.t_buy + 0.2, "swish", 0.35)
        s(self.t_buy + 0.1, "swish", 0.3)
        s(self.t_box, "whoosh", 0.3)
        s(self.t_box + 0.4, "thud", 0.45)
        s(self.t_box + 0.9, "pop_big", 0.35)
        s(self.t_box + 1.0, "sparkle", 0.3)
        for k in range(3):
            s(4.2 + k * 0.4, "tick", 0.15)
        if self.final:
            s(5.2, "whoosh", 0.35)
            s(5.6, "paper", 0.4)
            s(5.7, "fail", 0.45)
            s(7.6, "powerdown", 0.3)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def bought_now(self, t):
        return self.bought_before + ([self.name] if t > self.t_box + 0.9 else [])

    # ---- links: kauft
    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        bought = self.bought_now(t)
        for name in bought:
            ITEMS[name](d, x0)
        n_boxes = len(self.bought_before)
        for k in range(min(n_boxes, 8)):
            draw_box(d, x0 + 150 + (k % 3) * 52 - 26, F0 - (k // 3) * 60, 74, 60)
        fx = x0 + FIG
        hands, mood, look, bob = [None, None], 0.7, 0.3, 0.0
        phone = t < self.t_buy + 0.6
        if phone:
            hands[1] = (fx + 30 * S, F0 - 205 * S)
        if self.t_box + 0.9 < t < self.t_box + 2.4:
            ph = (t - self.t_box - 0.9) * 8
            hands = [(fx - 60 * S, F0 - (220 + 50 * math.sin(ph)) * S), (fx + 60 * S, F0 - (220 - 50 * math.sin(ph)) * S)]
            bob = abs(math.sin(ph)) * 8
            mood = 1.0
        if t > 4.6:
            mood = 0.3 - 0.15 * self.i
            hands[1] = (fx + 30 * S, F0 - 205 * S)
            phone = True
        if self.final and t > 5.6:
            mood = -0.9
            hands = [(fx - 30 * S, F0 - 175 * S), (fx + 30 * S, F0 - 175 * S)]
            phone = False
        info = person_fat(d, fx, F0, 0.1, tuple(hands), mood=mood, look=look, bob=bob, s=S)
        d = ImageDraw.Draw(c)
        if phone:
            h = info["hands"][1]
            draw_phone_screen(d, h[0] + 4, h[1] - 26, 34, 56, t, scroll=t > 4.6)
        # Paket
        if self.t_box < t < self.t_box + 1.0:
            p = ease_out_cubic(seg(t, self.t_box, self.t_box + 0.4))
            k = n_boxes
            bx = x0 + 150 + (k % 3) * 52 - 26
            by = lerp(CEIL + 40, F0 - (k // 3) * 60, p)
            draw_box(d, bx, by, 74, 60, flaps=smooth(seg(t, self.t_box + 0.6, self.t_box + 0.9)))
        # Deal-Karte
        a = ease_out_back(seg(t, self.t_card, self.t_card + 0.35))
        fly = smooth(seg(t, self.t_buy + 0.3, self.t_buy + 0.7))
        if a > 0.02 and fly < 1:
            card = deal_card(self.name, self.was, self.now, "buy", t - self.t_buy)
            paste_scaled(c, card, x0 + RW / 2 + fly * 60, CEIL + 230 + fly * 260, a * (1 - 0.7 * fly), 1 - fly)
        self.float_text(c, f"-{money(self.now)}", RED, fx + 70, info["head"][1] - 80, t - self.t_buy, 48, 1.0)
        if self.t_buy + 0.3 < t < self.t_buy + 1.6:
            self.float_text(c, "ADDED TO CART", GOLD, x0 + RW / 2, CEIL + 160, t - self.t_buy - 0.3, 30, 1.0, 15)
        if self.final and t > 5.2:
            p = ease_out_cubic(seg(t, 5.2, 5.6))
            draw_statement(d, x0 + 360, lerp(CEIL + 40, CEIL + 300, p))
            if t > 5.6:
                paste_scaled(c, sprite("BALANCE", 24, (240, 240, 245)), x0 + 360, CEIL + 225, 1, 1)
                paste_scaled(c, sprite("$2,000", 40, RED), x0 + 360, CEIL + 330, ease_out_back(seg(t, 5.6, 5.9)), 1)

    def after_left(self, c, t):
        c.alpha_composite(room_overlay("L", (0, 0, 0), 4 + self.i * 7), (ROOMS["L"], CEIL))

    # ---- rechts: wischt weg
    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        # Pflanze + Bücher als ruhiges Zimmer
        d.polygon([(x0 + 330 - 24, SHELF[2] - 40), (x0 + 330 + 24, SHELF[2] - 40), (x0 + 330 + 18, SHELF[2]), (x0 + 330 - 18, SHELF[2])], fill=(196, 110, 70), outline=OUT)
        for k, (dx, dy) in enumerate(((-18, -60), (16, -70), (0, -90), (-10, -78), (12, -52))):
            d.ellipse((x0 + 330 + dx - 18, SHELF[2] + dy - 12, x0 + 330 + dx + 18, SHELF[2] + dy + 12), fill=GREEN, outline=OUT, width=2)
        fx = x0 + FIG
        hands, mood, look = [None, None], 0.6, 0.3
        phone = t < self.t_buy + 0.6
        if phone:
            hands[1] = (fx + 30 * S, F0 - 205 * S)
        tea = t > 2.2
        if tea:
            ph = ((t - 2.2) % 3.0) / 3.0
            up = math.sin(math.pi * clamp(ph * 3)) ** 2 if ph < 0.34 else 0
            hands[1] = (fx + lerp(52, 20, up) * S, F0 - lerp(150, 225, up) * S)
            mood = 0.8
        if self.final and t > 6.0:
            hands = [(fx - 62 * S, F0 - 285 * S), (fx + 62 * S, F0 - 285 * S)]
            mood = 1.0
            tea = False
        info = person_fat(d, fx, F0, 0.1, tuple(hands), mood=mood, look=look, s=S)
        d = ImageDraw.Draw(c)
        if phone:
            h = info["hands"][1]
            draw_phone_screen(d, h[0] + 4, h[1] - 26, 34, 56, t, scroll=False)
        if tea:
            h = info["hands"][1]
            d.rounded_rectangle((h[0] - 6, h[1] - 32, h[0] + 22, h[1] - 4), 4, fill=(250, 250, 245), outline=OUT, width=3)
            d.arc((h[0] + 16, h[1] - 26, h[0] + 30, h[1] - 12), -90, 90, fill=OUT, width=3)
        a = ease_out_back(seg(t, self.t_card, self.t_card + 0.35))
        fly = smooth(seg(t, self.t_buy + 0.1, self.t_buy + 0.5))
        if a > 0.02 and fly < 1:
            card = deal_card(self.name, self.was, self.now, "skip", t - self.t_buy)
            paste_scaled(c, card, x0 + RW / 2 + fly * 500, CEIL + 230, a, 1 - fly)
        self.float_text(c, "NOT NEEDED", (210, 230, 215), x0 + RW / 2, CEIL + 230, t - self.t_buy - 0.2, 36, 1.0, 15)

    def draw_hud(self, c, t):
        gt = self.start + t
        dur = self.data["_dur"]
        remaining = max(0.0, TOTAL_SECONDS * (1 - gt / (dur - 3.5)))
        fade = 1 - (smooth(seg(t, 7.9, 8.2)) if self.final else 0)
        if fade > 0:
            paste_scaled(c, countdown_sign(remaining, ended=remaining <= 0), 540, 330, 1, fade)
            paste_scaled(c, sprite(spaced(self.data.get("subtitle", "SAME $2,000 IN THE BANK")), 28, (170, 170, 186), F_BOLD), 540, 486, 1, fade)
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=64, s2=72)
        after = t > self.t_buy
        sp = self.sp1 if after else self.sp0
        sv = self.sv1 if after else self.sv0
        bump = 1 + 0.15 * (1 - smooth(seg(t, self.t_buy, self.t_buy + 0.3))) if after else 1
        self.draw_counter(c, "L", "SPENT", money(sp), RED if sp > 0 else (235, 235, 240), bump=bump)
        paste_scaled(c, sprite(f'"SAVED" {money(sv)}', 30, GOLD), ROOMS["L"] + RW / 2, 1366, 1, 1 if sv > 0 else 0.4)
        self.draw_counter(c, "R", "STILL HAS", "$2,000", GREEN)


def build_lib(rng):
    from skins_video import build_lib as skins_lib
    return skins_lib(rng)


def build(data):
    stages, t = [], 0.0
    sp = sv = 0
    bought = []
    n = len(data["stages"])
    data["_dur"] = sum(float(s.get("dur", 9.0)) for s in data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_spent"], sc["_prev_saved"], sc["_bought"] = sp, sv, list(bought)
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        sp, sv = st.sp1, st.sv1
        bought.append(sc["item"])
    return stages, t


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p, build, build_lib)
