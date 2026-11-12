#!/usr/bin/env python3
"""
"After the Breakup" – beide werden verlassen. Links: Profil checken, Eis, 3 Uhr nachts "u up?".
Rechts: Training, Lesen, Glow-up. Twist im letzten Jahr: SIE schreibt IHM.

    python3 generator/breakup_video.py skripte/zimmer/24_after_the_breakup.json
"""
import math
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import F_BOLD, clamp, ease_out_back, ease_out_cubic  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, SHELF, SKIN, capsule, circle, draw_book_open, draw_books, paste_scaled, radial, room_overlay, seg, sprite  # noqa: E402
from wecker_video import BED_TOP, CLOCK_X, NS_TOP, draw_bed, draw_clock, draw_dumbbell, draw_nightstand, person_fat  # noqa: E402
from scroll_video import BLUE_GLOW, draw_heart  # noqa: E402
from zz_base import StageBase, fit_sprite, run  # noqa: E402

S = 1.15
F0 = FL - 10
PINK = (255, 120, 160)
GOLD_GLOW = radial(320, GOLD, 120)
SHIRTS = [(130, 130, 142), (110, 120, 150), (80, 118, 235), (60, 90, 200), (40, 40, 52), (30, 30, 40), (20, 20, 28)]
HAIR = (40, 30, 26)


def draw_tub(d, x, y):
    d.polygon([(x - 16, y - 30), (x + 16, y - 30), (x + 12, y), (x - 12, y)], fill=(250, 240, 230), outline=OUT)
    d.rectangle((x - 16, y - 34, x + 16, y - 28), fill=(170, 110, 70), outline=OUT, width=2)
    d.line([(x - 12, y - 18), (x + 12, y - 18)], fill=PINK, width=4)


def draw_mini_phone(d, x, y, glow=True):
    d.rounded_rectangle((x - 20, y - 34, x + 20, y + 34), 6, fill=(22, 22, 30), outline=OUT, width=3)
    d.rectangle((x - 16, y - 28, x + 16, y + 28), fill=(250, 220, 230))
    d.ellipse((x - 10, y - 22, x + 10, y - 2), fill=PINK, outline=OUT, width=2)
    draw_heart(d, x, y + 14, 7, (230, 60, 100))


def chat_panel(lines, title="HER", w=330):
    """lines: [(text, 'me'|'her'|'seen')]"""
    h = 120 + 64 * len(lines)
    img = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((10, 10, 10 + w, 10 + h), 28, fill=(20, 20, 26), outline=(230, 230, 240), width=5)
    d.rounded_rectangle((22, 24, w - 2, h - 2), 18, fill=(245, 245, 248))
    d.ellipse((34, 34, 74, 74), fill=PINK, outline=OUT, width=2)
    paste_scaled(img, sprite(title, 26, (30, 30, 36)), 120, 54, 1, 1)
    d = ImageDraw.Draw(img)
    d.line([(30, 86), (w - 10, 86)], fill=(210, 210, 216), width=2)
    y = 120
    for text, who in lines:
        if who == "seen":
            paste_scaled(img, sprite(text, 20, (140, 140, 150), F_BOLD), w - 50, y - 10, 1, 1)
            y += 30
            continue
        spr = fit_sprite(text, 26, (255, 255, 255) if who == "me" else (30, 30, 36), w - 90, F_BOLD)
        bw = spr.width - 20
        d = ImageDraw.Draw(img)
        if who == "me":
            x1 = w - 10
            d.rounded_rectangle((x1 - bw, y - 24, x1, y + 24), 20, fill=(60, 130, 250))
            paste_scaled(img, spr, x1 - bw / 2, y, 1, 1)
        else:
            x0 = 40
            d.rounded_rectangle((x0, y - 24, x0 + bw, y + 24), 20, fill=(222, 222, 228))
            paste_scaled(img, spr, x0 + bw / 2, y, 1, 1)
        y += 64
    return img


def notif_card(text, a):
    img = Image.new("RGBA", (360, 120), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((6, 6, 354, 114), 22, fill=(250, 250, 252), outline=OUT, width=4)
    d.ellipse((22, 30, 72, 80), fill=PINK, outline=OUT, width=2)
    paste_scaled(img, sprite("HER", 24, (120, 120, 130)), 130, 38, 1, 1)
    paste_scaled(img, fit_sprite(text, 32, (30, 30, 36), 250), 200, 78, 1, 1)
    return img


def tears(d, x, y, t, s=1.0):
    for k in range(2):
        for sg in (-1, 1):
            ph = ((t * 1.4) + k / 2 + (0.25 if sg > 0 else 0)) % 1
            tx, ty = x + sg * 12 * s, y + ph * 36 * s
            d.ellipse((tx - 4 * s, ty - 5 * s, tx + 4 * s, ty + 6 * s), fill=(120, 190, 255))


class Stage(StageBase):
    door = False

    def setup(self):
        c = self.cfg
        self.intro = c.get("intro", False)
        self.label, self.header = str(c["label"]), c["header"]
        self.k0, self.k1 = c["_prev_checks"], c["checks"]
        self.g0, self.g1 = c["_prev_glow"], c["glow"]
        self.fat_r = c["fat_r"]
        self.fat_l = 0.4 + 0.03 * self.i
        self.workout = ["dumbbell", "jacks", "dumbbell", "jacks", "dumbbell", "jacks", "dumbbell"][self.i % 7]
        self.t_msg = 4.2

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else None
        if self.intro:
            s(0.4, "notif", 0.55)
            s(0.6, "fail", 0.4)
            s(1.5, "heartbeat", 0.3)
            s(4.3, "pop_big", 0.4)
            for k in range(5):
                s(5.2 + k * 0.6, "clank", 0.3)
            return
        for k in range(4):
            s(0.8 + k * 0.7, "tick", 0.25)
        if self.i >= 2 and not self.final:
            s(5.4, "whoosh", 0.3)
            s(5.6, "beep", 0.3)
        if self.workout == "dumbbell":
            for k in range(5):
                s(0.8 + k * 0.5, "clank", 0.3)
        else:
            for k in range(8):
                s(0.8 + k * 0.32, "swish", 0.22)
        s(3.6, "page", 0.3)
        s(6.0, "sparkle", 0.35)
        if self.final:
            s(self.t_msg, "notif", 0.55)
            s(self.t_msg + 0.6, "gasp", 0.3)
            s(6.4, "ding", 0.45)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def checks_now(self, t):
        return lerp(self.k0, self.k1, smooth(seg(t, 0.6, 7.0)))

    def glow_now(self, t):
        return lerp(self.g0, self.g1, smooth(seg(t, 0.6, 6.2)))

    # ---- links: hängt fest
    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        for k in range(min(self.i * 2, 12)):
            draw_tub(d, x0 + 300 + (k % 5) * 34, F0 - (k // 5) * 30)
        draw_nightstand(d, x0)
        draw_tub(d, x0 + CLOCK_X - 30, NS_TOP - 2)
        sway = math.sin(t * 2) * 3
        ph = (x0 + 140 + sway, BED_TOP - 112)
        info = draw_bed(d, x0, self.fat_l, arm_to=(ph[0] + 6, ph[1] + 30))
        d = ImageDraw.Draw(c)
        d = draw_clock(c, d, x0 + CLOCK_X + 14, NS_TOP, "3:00" if not self.intro else "11:47", RED, 0, t)
        hx, hy, r = info
        circle(d, hx, hy, r, SKIN)
        for sg in (-1, 1):
            ex, ey = hx + sg * 13 - 6, hy - 6
            d.ellipse((ex - 4.5, ey - 5, ex + 4.5, ey + 5), fill=OUT)
            d.line([(ex - 7, ey - 12 - sg * 2), (ex + 7, ey - 12 + sg * 2)], fill=OUT, width=3)
        d.arc((hx - 16, hy + 10, hx + 6, hy + 24), 200, 340, fill=OUT, width=3)
        if self.intro or self.i <= 2 or (self.final and t > 6.5):
            tears(d, hx - 6, hy, t, 1.0)
        paste_scaled(c, BLUE_GLOW, ph[0], ph[1] + 60, 1.0, 0.7)
        d = ImageDraw.Draw(c)
        capsule(d, (x0 + 158, BED_TOP + 2), (ph[0] + 6, ph[1] + 30), 20, SHIRTS[0])
        circle(d, ph[0] + 6, ph[1] + 30, 11, SKIN, 3)
        draw_mini_phone(d, ph[0], ph[1])
        if self.intro:
            a = ease_out_back(seg(t, 0.4, 0.75))
            paste_scaled(c, notif_card("It's over.", a), x0 + RW / 2, CEIL + 160, 0.6 + 0.4 * a, clamp(a * 2))
            return
        for k in range(4):
            self.float_text(c, "CHECKED", PINK, ph[0] + 60, ph[1] - 10, t - 0.8 - k * 0.7, 26, 0.5, 40)
        if self.i >= 2 and not self.final:
            a = ease_out_back(seg(t, 5.4, 5.75)) * (1 - smooth(seg(t, 8.3, 8.7)))
            if a > 0.02:
                lines = [("u up?", "me"), ("Seen 3:02", "seen")] if t > 6.2 else [("u up?", "me")]
                paste_scaled(c, chat_panel(lines), x0 + 300, CEIL + 230, 0.6 + 0.4 * a, clamp(a * 2))
        if self.final and t > 6.5:
            self.float_text(c, "still checking...", (210, 210, 225), x0 + 300, CEIL + 160, t - 6.5, 32, 2.0, 5)

    def after_left(self, c, t):
        c.alpha_composite(room_overlay("L", (0, 0, 20), 30 + self.i * 8), (ROOMS["L"], CEIL))

    # ---- rechts: Glow-up
    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        draw_books(d, x0 + 375, SHELF[2], 1 + self.i)
        d.rectangle((x0 + 30, 840, x0 + 130, 1010), fill=(200, 220, 235), outline=(230, 230, 240), width=6)
        d.line([(x0 + 50, 860), (x0 + 80, 890)], fill=(250, 250, 255), width=4)
        draw_dumbbell(d, x0 + 300, F0 - 15)
        fx = x0 + 250
        sh = SHIRTS[min(self.i, len(SHIRTS) - 1)]
        hair = HAIR if self.i >= 2 else None
        hands, mood, look, stance, bob, head_drop = [None, None], 0.5, 0.2, 0.0, 0.0, 0.0
        dumb = book = phone = False
        if self.intro:
            mood, head_drop = -0.8, 0.5
            hands = [None, (fx + 30 * S, F0 - 200 * S)] if t < 3.8 else [None, None]
            phone = t < 3.8
            if t > 4.3:
                mood, head_drop = 0.2, 0.0
            if t > 5.0:
                up = 0.5 - 0.5 * math.cos((t - 5.0) * 2 * math.pi / 0.6)
                hands = [(fx - 46 * S, F0 - lerp(110, 200, up) * S), (fx + 46 * S, F0 - lerp(110, 200, up) * S)]
                dumb = True
        else:
            if 0.6 < t < 3.4:
                tt = t - 0.6
                if self.workout == "dumbbell":
                    up = 0.5 - 0.5 * math.cos(tt * 2 * math.pi / 0.5)
                    hands = [(fx - 46 * S, F0 - lerp(110, 200, up) * S), (fx + 46 * S, F0 - lerp(110, 200, up) * S)]
                    dumb = True
                else:
                    up = 0.5 - 0.5 * math.cos(tt * 2 * math.pi / 0.64)
                    hands = [(fx - (40 + 55 * up) * S, F0 - (130 + 140 * up) * S), (fx + (40 + 55 * up) * S, F0 - (130 + 140 * up) * S)]
                    stance, bob = 28 * up, 14 * math.sin(math.pi * up)
                mood = 0.6
            elif 3.6 < t < 5.6 and not (self.final and t > self.t_msg):
                hands = [(fx - 28 * S, F0 - 150 * S), (fx + 28 * S, F0 - 150 * S)]
                book, head_drop, mood = True, 0.35, 0.6
            elif t >= 5.6 and not self.final:
                look, mood = -1.0, 0.9
            if self.final and t > self.t_msg:
                if t < 6.4:
                    hands = [None, (fx + 30 * S, F0 - 205 * S)]
                    phone, look, mood = True, 0.3, 0.3
                else:
                    look, mood = 0.0, 1.0
        info = person_fat(d, fx, F0, self.fat_r, tuple(hands), mood=mood, look=look, stance=stance, bob=bob, head_drop=head_drop,
                          s=S, shirt=sh, hair=hair)
        d = ImageDraw.Draw(c)
        if self.intro and t < 4.3:
            tears(d, info["head"][0], info["head"][1], t, S)
        if dumb:
            for h in info["hands"]:
                draw_dumbbell(d, h[0], h[1])
        if book:
            draw_book_open(d, fx, F0 - 160 * S)
        if phone:
            h = info["hands"][1]
            draw_mini_phone(d, h[0] + 6, h[1] - 26)
        if self.intro:
            a = ease_out_back(seg(t, 0.4, 0.75)) * (1 - smooth(seg(t, 4.0, 4.3)))
            if a > 0.02:
                paste_scaled(c, notif_card("It's over.", a), x0 + RW / 2, CEIL + 160, 0.6 + 0.4 * a, clamp(a * 2))
            if t > 4.3:
                a = ease_out_back(seg(t, 4.3, 4.6))
                paste_scaled(c, sprite('"Enough."', 52, (245, 245, 250)), x0 + RW / 2, CEIL + 160, a, clamp(a * 2))
            return
        if t >= 5.6 and not self.final:
            self.float_text(c, "GLOW UP", GOLD, x0 + 80, 820, t - 5.9, 36, 1.4, 10)
            d = ImageDraw.Draw(c)
            for k in range(3):
                ph = (t * 1.5 + k / 3) % 1
                sx, sy = x0 + 50 + k * 30, 880 + math.sin(ph * 6) * 20
                rr = 9 * math.sin(math.pi * ph)
                d.polygon([(sx, sy - rr), (sx + rr * 0.3, sy), (sx, sy + rr), (sx - rr * 0.3, sy)], fill=(255, 250, 220))
                d.polygon([(sx - rr, sy), (sx, sy + rr * 0.3), (sx + rr, sy), (sx, sy - rr * 0.3)], fill=(255, 250, 220))
        if self.final and t > self.t_msg:
            a = ease_out_back(seg(t, self.t_msg, self.t_msg + 0.35)) * (1 - smooth(seg(t, 7.6, 7.9)))
            if a > 0.02:
                paste_scaled(c, chat_panel([("Hey...", "her"), ("you look different", "her")]), x0 + 250, CEIL + 230,
                             0.6 + 0.4 * a, clamp(a * 2))
            if t > 6.4:
                e = ease_out_cubic(seg(t, 6.4, 7.2))
                paste_scaled(c, GOLD_GLOW, fx, info["head"][1], 0.5 + e, (1 - e) * 0.8)
                self.float_text(c, "*puts phone down*", (230, 230, 240), fx, info["head"][1] - 100, t - 6.4, 30, 1.2, 10)

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, self.header, self.label, self.cfg.get("_prev_label"), self.data.get("subtitle", "SAME HEARTBREAK"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=64, s2=70)
        k = self.checks_now(t)
        g = self.glow_now(t)
        self.draw_counter(c, "L", "PROFILE CHECKS", f"{k:,.0f}", PINK)
        self.draw_counter(c, "R", "GLOW UP", f"{g:.0f}%", GREEN if g > 0 else (235, 235, 240))


def build_lib(rng):
    from skins_video import build_lib as skins_lib
    return skins_lib(rng)


def build(data):
    stages, t = [], 0.0
    pk = pg = 0
    prev = None
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_checks"], sc["_prev_glow"], sc["_prev_label"] = pk, pg, prev
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        pk, pg, prev = sc["checks"], sc["glow"], str(sc["label"])
    return stages, t


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p, build, build_lib)
