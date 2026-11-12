#!/usr/bin/env python3
"""
"Compare vs. Improve" – links vergleicht er sich mit perfekten Instagram-Leben (Regenwolke, HAPPINESS fällt),
rechts vergleicht er sich nur mit sich selbst von gestern (+1% pro Tag, x37.8 nach einem Jahr).

    python3 generator/compare_video.py skripte/zimmer/26_compare_vs_improve.json
"""
import math
import os
import random
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import F_BOLD, clamp, ease_out_back, ease_out_cubic  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, SHELF, draw_book_open, draw_books, paste_scaled, radial, room_overlay, seg, sprite  # noqa: E402
from wecker_video import draw_dumbbell, person_fat  # noqa: E402
from job_video import draw_couch_back, draw_couch_front  # noqa: E402
from scroll_video import draw_heart, draw_phone_screen  # noqa: E402
from auto_video import draw_chart  # noqa: E402
from zz_base import StageBase, fit_sprite, run  # noqa: E402

S = 1.15
F0 = FL - 10
SEAT_FY = F0 + 106
GOLD_GLOW = radial(320, GOLD, 120)
POSTS = [("@rich_mike", "new Lambo", "car"), ("@fit_jay", "summer body", "abs"), ("@travel_lisa", "Bali again", "palm"),
         ("@ceo_dan", "7 figures", "money"), ("@perfect_couple", "engaged!", "ring"), ("@crypto_kid", "retired at 22", "yacht"),
         ("@influencer", "best life", "palm")]


def post_image(kind, w, h):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bgs = {"car": (255, 200, 120), "abs": (120, 200, 255), "palm": (120, 220, 240), "money": (140, 220, 160),
           "ring": (255, 200, 220), "yacht": (110, 180, 250)}
    d.rectangle((0, 0, w, h), fill=bgs[kind])
    cx, cy = w / 2, h / 2
    if kind == "car":
        d.rounded_rectangle((cx - 70, cy, cx + 70, cy + 34), 12, fill=(255, 210, 40), outline=OUT, width=3)
        d.polygon([(cx - 40, cy), (cx - 20, cy - 26), (cx + 30, cy - 26), (cx + 50, cy)], fill=(255, 210, 40), outline=OUT)
        for wx in (cx - 40, cx + 40):
            d.ellipse((wx - 15, cy + 22, wx + 15, cy + 52), fill=(30, 30, 34), outline=OUT, width=2)
    elif kind == "abs":
        d.rounded_rectangle((cx - 40, cy - 60, cx + 40, cy + 60), 20, fill=(240, 200, 170), outline=OUT, width=3)
        for k in range(3):
            for sg in (-1, 1):
                d.rounded_rectangle((cx + sg * 4 - (30 if sg < 0 else 0), cy - 34 + k * 26, cx + sg * 4 + (30 if sg > 0 else 0), cy - 14 + k * 26), 6,
                                    fill=(225, 180, 150), outline=OUT, width=2)
    elif kind == "palm":
        d.ellipse((cx + 30, cy - 70, cx + 70, cy - 30), fill=(255, 220, 90))
        d.rectangle((0, cy + 40, w, h), fill=(250, 225, 160))
        d.line([(cx - 20, cy + 44), (cx - 6, cy - 40)], fill=(130, 90, 50), width=8)
        for a in (-2.6, -2.0, -1.2, -0.5):
            d.line([(cx - 6, cy - 40), (cx - 6 + math.cos(a) * 50, cy - 40 + math.sin(a) * 30 + 16)], fill=(60, 160, 80), width=8)
    elif kind == "money":
        for k in range(5):
            d.rectangle((cx - 50 + k * 4, cy + 30 - k * 16, cx + 50 + k * 4, cy + 44 - k * 16), fill=(120, 200, 130), outline=OUT, width=2)
    elif kind == "ring":
        d.ellipse((cx - 30, cy - 10, cx + 30, cy + 50), outline=GOLD, width=10)
        d.polygon([(cx - 18, cy - 14), (cx + 18, cy - 14), (cx, cy + 6)], fill=(200, 240, 255), outline=OUT)
        d.polygon([(cx - 18, cy - 14), (cx - 8, cy - 30), (cx + 8, cy - 30), (cx + 18, cy - 14)], fill=(230, 250, 255), outline=OUT)
    elif kind == "yacht":
        d.rectangle((0, cy + 30, w, h), fill=(60, 120, 220))
        d.polygon([(cx - 70, cy + 10), (cx + 70, cy + 10), (cx + 50, cy + 36), (cx - 50, cy + 36)], fill=(250, 250, 250), outline=OUT)
        d.rectangle((cx - 30, cy - 14, cx + 30, cy + 10), fill=(240, 240, 245), outline=OUT, width=2)
    return img


def post_panel(user, caption, kind, likes_k):
    w, h = 300, 360
    img = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((10, 10, 10 + w, 10 + h), 26, fill=(20, 20, 26), outline=(230, 230, 240), width=5)
    d.rounded_rectangle((22, 22, w - 2, h - 2), 16, fill=(250, 250, 252))
    d.ellipse((32, 32, 66, 66), fill=(255, 150, 90), outline=OUT, width=2)
    paste_scaled(img, fit_sprite(user, 22, (30, 30, 36), 200, F_BOLD), 150, 50, 1, 1)
    img.alpha_composite(post_image(kind, w - 40, 190), (30, 76))
    d = ImageDraw.Draw(img)
    draw_heart(d, 48, 292, 13, (240, 60, 90))
    paste_scaled(img, sprite(f"{likes_k}K", 22, (30, 30, 36)), 92, 290, 1, 1)
    paste_scaled(img, fit_sprite(caption, 26, (30, 30, 36), 260, F_BOLD), 160, 330, 1, 1)
    return img


def draw_cloud(d, x, y, size, t, rain=True):
    if size < 0.05:
        return
    s = size
    col = (90, 96, 112)
    for dx, dy, r in ((-40, 0, 26), (-12, -14, 32), (20, -8, 28), (44, 4, 22), (0, 8, 26)):
        d.ellipse((x + dx * s - r * s, y + dy * s - r * s, x + dx * s + r * s, y + dy * s + r * s), fill=col)
    if rain:
        for k in range(int(6 * s) + 2):
            ph = ((t * 1.8) + k * 0.37) % 1
            rx = x - 40 * s + k * 16 * s
            ry = y + 20 * s + ph * 80 * s
            d.line([(rx, ry), (rx - 3, ry + 12)], fill=(130, 170, 230), width=3)


class Stage(StageBase):
    door = False

    def setup(self):
        c = self.cfg
        self.label, self.header = str(c["label"]), c["header"]
        self.h0, self.h1 = c["_prev_happy"], c["happy"]
        self.x0v, self.x1v = c["_prev_x"], c["x"]
        self.post = POSTS[self.i % len(POSTS)]
        self.activity = ["book", "dumbbell", "book", "dumbbell", "book", "dumbbell", "book"][self.i]
        self.plus_t = [5.7, 6.1, 6.5]

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        s(0.7, "flickup", 0.3)
        s(1.0, "pop_big", 0.35)
        s(1.9, "flickup", 0.25)
        s(3.4, "flickup", 0.25)
        s(2.4, "groan", 0.25)
        s(4.6, "fail", 0.18)
        if self.activity == "dumbbell":
            for k in range(6):
                s(0.8 + k * 0.6, "clank", 0.3)
        else:
            s(0.8, "page", 0.3)
            s(2.8, "page", 0.25)
        for tt in self.plus_t:
            s(tt, f"note{min(7, self.i + self.plus_t.index(tt))}", 0.45)
        s(6.9, "ding", 0.4)
        if self.final:
            s(7.0, "cash", 0.35)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def happy_now(self, t):
        return lerp(self.h0, self.h1, smooth(seg(t, 1.0, 5.0)))

    def x_now(self, t):
        return lerp(self.x0v, self.x1v, smooth(seg(t, 5.6, 7.0)))

    # ---- links: vergleicht
    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        draw_couch_back(d, x0)
        hp = self.happy_now(t) / 100
        hands = [None, (x0 + 330 + 30 * S, SEAT_FY - 200 * S)]
        lay = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        info = person_fat(ld, x0 + 330, SEAT_FY, 0.12, tuple(hands), mood=lerp(-0.9, 0.5, hp), look=0.3,
                          head_drop=lerp(0.7, 0.0, hp), s=S)
        h = info["hands"][1]
        draw_phone_screen(ld, h[0] + 4, h[1] - 26, 34, 56, t)
        c.alpha_composite(lay, (x0, CEIL), (x0, CEIL, x0 + RW, F0 - 2))
        d = ImageDraw.Draw(c)
        draw_couch_front(d, x0)
        hx, hy = info["head"]
        draw_cloud(d, hx, hy - 120, 0.4 + 0.9 * (1 - hp), t, rain=hp < 0.75)
        a = ease_out_back(seg(t, 1.0, 1.35)) * (1 - smooth(seg(t, 5.0, 5.3)))
        if a > 0.02:
            user, cap, kind = self.post
            panel = post_panel(user, cap, kind, 120 + self.i * 230)
            paste_scaled(c, panel, x0 + 170, CEIL + 240, 0.6 + 0.4 * a, clamp(a * 2))
        if 2.4 < t < 4.6:
            self.float_text(c, '"Why not me?"', (210, 215, 230), x0 + 360, hy - 40, t - 2.4, 30, 1.6, 10)

    def after_left(self, c, t):
        c.alpha_composite(room_overlay("L", (0, 0, 20), 10 + self.i * 9), (ROOMS["L"], CEIL))

    # ---- rechts: verbessert sich
    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        draw_books(d, x0 + 375, SHELF[2], 1 + self.i)
        # Tafel: YESTERDAY vs TODAY + Chart
        bx0, by0, bx1, by1 = x0 + 24, 840, x0 + 250, 1010
        d.rectangle((bx0, by0, bx1, by1), fill=(30, 46, 40), outline=(160, 120, 80), width=6)
        prog = (self.i + smooth(seg(t, 5.6, 7.0))) / 7
        draw_chart(d, bx0 + 10, by0 + 40, bx1 - 10, by1 - 10, max(0.03, prog))
        paste_scaled(c, sprite("ME vs ME YESTERDAY", 18, (220, 230, 220)), (bx0 + bx1) / 2, by0 + 20, 1, 1)
        d = ImageDraw.Draw(c)
        fx = x0 + 330
        hands, mood, look, head_drop = [None, None], 0.6, 0.2, 0.0
        book = dumb = False
        if 0.6 < t < 5.4:
            if self.activity == "dumbbell":
                up = 0.5 - 0.5 * math.cos((t - 0.6) * 2 * math.pi / 0.6)
                hands = [(fx - 46 * S, F0 - lerp(110, 200, up) * S), (fx + 46 * S, F0 - lerp(110, 200, up) * S)]
                dumb = True
            else:
                hands = [(fx - 28 * S, F0 - 150 * S), (fx + 28 * S, F0 - 150 * S)]
                book, head_drop = True, 0.35
            mood = 0.6
        if t >= 5.6:
            look, mood = -1.0, 0.9
            hands = [(fx - 40 * S, F0 - 170 * S), (fx - 120 * S, F0 - 215 * S)]
            if self.final and t > 7.0:
                hands = [(fx - 62 * S, F0 - 285 * S), (fx + 62 * S, F0 - 285 * S)]
                look = 0.0
        info = person_fat(d, fx, F0, 0.1, tuple(hands), mood=mood, look=look, head_drop=head_drop, s=S)
        d = ImageDraw.Draw(c)
        if dumb:
            for h in info["hands"]:
                draw_dumbbell(d, h[0], h[1])
        if book:
            draw_book_open(d, fx, F0 - 160 * S)
        for tt in self.plus_t:
            k = self.plus_t.index(tt)
            self.float_text(c, "+1%", GREEN, (bx0 + bx1) / 2 + (k - 1) * 85, by0 - 10 - (k % 2) * 30, t - tt, 40, 0.8, 30)
        if t > 6.9:
            e = ease_out_cubic(seg(t, 6.9, 7.6))
            paste_scaled(c, GOLD_GLOW, info["head"][0], info["head"][1], 0.5 + e, (1 - e) * 0.7)

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, self.header, self.label, self.cfg.get("_prev_label"), self.data.get("subtitle", "SAME LIFE · DIFFERENT FOCUS"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=62, s2=64)
        hp = self.happy_now(t)
        self.draw_counter(c, "L", "HAPPINESS", f"{hp:.0f}%", RED if hp < 50 else (235, 235, 240))
        xv = self.x_now(t)
        bump = 1 + 0.15 * (1 - smooth(seg(t, 6.9, 7.2))) if t > 6.9 else 1
        self.draw_counter(c, "R", "BETTER THAN DAY 1", f"x{xv:.2f}", GREEN, bump=bump)


def build_lib(rng):
    from skins_video import build_lib as skins_lib
    return skins_lib(rng)


def build(data):
    stages, t = [], 0.0
    ph, px = 80, 1.0
    prev = None
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_happy"], sc["_prev_x"], sc["_prev_label"] = ph, px, prev
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        ph, px, prev = sc["happy"], sc["x"], str(sc["label"])
    return stages, t


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p, build, build_lib)
