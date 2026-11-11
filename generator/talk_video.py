#!/usr/bin/env python3
"""
"Talk vs. Do" (Move in Silence) – links erzählt er allen von seinem Business, rechts baut er es still.

    python3 generator/talk_video.py skripte/zimmer/21_talk_vs_do.json
"""
import math
import os
import random
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import clamp, ease_out_back, ease_out_cubic  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, draw_box, paste_scaled, radial, room_overlay, seg, sprite  # noqa: E402
from wecker_video import person_fat  # noqa: E402
from scroll_video import draw_heart, draw_phone_screen  # noqa: E402
from job_video import draw_chair_back, draw_desk, draw_laptop, SIT_DY  # noqa: E402
from wedding_video import draw_bubble  # noqa: E402
from zz_base import StageBase, run  # noqa: E402

S = 1.15
F0 = FL - 10
BUBBLES = ["I'm gonna start a business!", "Big things coming soon...", "Still planning. Stay tuned!", "Working on something HUGE!",
           "Next year is MY year!", "The market isn't ready yet.", "I'm about to start something big!"]
GLOW = radial(320, GOLD, 120)


def fmt(v):
    return f"{v:,.0f}"


def draw_whiteboard(d, x0, t, i):
    d.rectangle((x0 + 220, 846, x0 + 450, 990), fill=(240, 240, 236), outline=(150, 150, 160), width=5)
    rnd = random.Random(7)
    for k in range(6 + i * 2):
        x = x0 + 236 + rnd.uniform(0, 190)
        y = 862 + rnd.uniform(0, 110)
        col = [(220, 60, 60), (60, 90, 220), (40, 40, 40)][k % 3]
        if k % 3 == 0:
            d.ellipse((x - 14, y - 9, x + 14, y + 9), outline=col, width=2)
        elif k % 3 == 1:
            d.line([(x - 16, y), (x + 16, y - 6)], fill=col, width=2)
            d.polygon([(x + 16, y - 6), (x + 8, y - 10), (x + 10, y - 2)], fill=col)
        else:
            d.line([(x - 18, y), (x - 6, y + 4), (x + 4, y - 3), (x + 18, y + 2)], fill=col, width=2)
    d.text((x0 + 300, 975), "PLAN v" + str(i + 7), fill=(120, 120, 130))


def draw_first_dollar(d, x0):
    d.rectangle((x0 + 30, 856, x0 + 150, 946), fill=(60, 48, 36), outline=GOLD, width=4)
    d.rectangle((x0 + 40, 866, x0 + 140, 936), fill=(250, 246, 232))
    d.rounded_rectangle((x0 + 54, 886, x0 + 126, 918), 4, fill=(120, 200, 130), outline=OUT, width=2)
    d.ellipse((x0 + 82, 894, x0 + 98, 910), outline=(40, 110, 60), width=2)


class Stage(StageBase):
    door = True

    def setup(self):
        c = self.cfg
        self.label, self.header = str(c["label"]), c["header"]
        self.l0, self.l1 = c["_prev_likes"], c["likes"]
        self.c0, self.c1 = c["_prev_cust"], c["cust"]
        n = c.get("orders", 0)
        self.orders = [1.2 + k * (5.0 / max(1, n)) for k in range(n)]
        self.boxes0 = c["_prev_boxes"]
        self.bubble = BUBBLES[min(self.i, len(BUBBLES) - 1)]

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        s(1.0, "tick", 0.4)
        s(1.05, "whoosh", 0.3)
        for k in range(5):
            s(1.4 + k * 0.3, "pop", 0.2)
        s(1.7, "typing", 0.25)
        for to in self.orders:
            s(to, "notif", 0.4)
            s(to + 0.3, "clink", 0.3)
        if self.i == 2:
            s(6.0, "ding", 0.4)
        if self.final:
            s(6.4, "cash", 0.45)
            s(6.5, "sparkle", 0.45)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def likes_now(self, t):
        return lerp(self.l0, self.l1, smooth(seg(t, 1.2, 3.4)))

    def cust_now(self, t):
        return lerp(self.c0, self.c1, smooth(seg(t, 1.2, 6.4)))

    # ---- links: redet
    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        from job_video import draw_door_anim
        draw_door_anim(d, x0, 0)
        draw_whiteboard(d, x0, t, self.i)
        fx = x0 + 250
        hands, mood, look = [None, None], 0.8, 0.3
        phone = 0.8 < t < 1.5 or t > 6.2
        if phone:
            hands[1] = (fx + 30 * S, F0 - 205 * S)
        if 3.5 < t < 6.0:
            g = math.sin((t - 3.5) * 5)
            hands = [(fx - (60 + 10 * g) * S, F0 - (200 + 10 * g) * S), (fx + (60 + 10 * g) * S, F0 - (200 - 10 * g) * S)]
            mood = 1.0
        if t > 6.2:
            mood = 0.6 - 0.15 * self.i
            look = 0.2
        info = person_fat(d, fx, F0, 0.1, tuple(hands), mood=mood, look=look, mouth_o=(3.5 < t < 6.0 and int(t * 6) % 2 == 0), s=S)
        d = ImageDraw.Draw(c)
        if phone:
            h = info["hands"][1]
            draw_phone_screen(d, h[0] + 4, h[1] - 26, 34, 56, t, scroll=t > 6.2)
        a = smooth(seg(t, 0.6, 0.85)) * (1 - smooth(seg(t, 5.8, 6.1)))
        draw_bubble(c, x0 + RW / 2 + 20, F0 - 360, self.bubble, a)
        self.float_text(c, "POSTED", (200, 205, 220), fx + 110, info["head"][1] + 10, t - 1.05, 32, 0.6, 20)
        d = ImageDraw.Draw(c)
        for k in range(5):
            kk = t - 1.4 - k * 0.3
            if 0 < kk < 1.2:
                draw_heart(d, fx + 70 + (k % 3) * 24, info["head"][1] - 40 - kk * 110, 13 * (1 - kk / 2.4))

    def after_left(self, c, t):
        c.alpha_composite(room_overlay("L", (0, 0, 0), 4 + self.i * 6), (ROOMS["L"], CEIL))

    # ---- rechts: baut still
    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        from job_video import draw_door_anim
        draw_door_anim(d, x0, 0)
        if self.i >= 2:
            draw_first_dollar(d, x0)
        n_box = self.boxes0 + sum(1 for to in self.orders if t > to + 0.3)
        for k in range(min(n_box, 15)):
            draw_box(d, x0 + 150 + (k % 3) * 46 - 46, F0 - (k // 3) * 46, 44, 44)
        draw_chair_back(d, x0)
        hands = [(x0 + 380 + math.sin(t * 18) * 4, F0 - 118), (x0 + 410 + math.cos(t * 23) * 4, F0 - 118)]
        mood, look = 0.6, 1.0
        if self.final and t > 6.4:
            hands = [(x0 + 330 - 62 * S, F0 + SIT_DY - 280 * S), (x0 + 330 + 62 * S, F0 + SIT_DY - 280 * S)]
            mood = 1.0
        lay = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        person_fat(ld, x0 + 330, F0 + SIT_DY, 0.1, tuple(hands), mood=mood, look=look, s=S)
        c.alpha_composite(lay, (x0, CEIL), (x0, CEIL, x0 + RW, F0 - 2))
        d = ImageDraw.Draw(c)
        draw_desk(d, x0)
        draw_laptop(c, d, x0, True, t, (self.i + seg(t, 1, 8)) / 7, self.i)
        d = ImageDraw.Draw(c)
        for to in self.orders:
            self.float_text(c, "NEW ORDER!", GREEN, x0 + 360, F0 - 300, t - to, 34, 0.7, 30)
        if self.final and t > 6.4:
            e = smooth(seg(t, 6.4, 7.0))
            paste_scaled(c, GLOW, x0 + 330, F0 - 250, 1.2, e * (0.7 + 0.3 * math.sin(t * 4)))

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, self.header, self.label, self.cfg.get("_prev_label"),
                           self.data.get("subtitle", "SAME DREAM · SAME START"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=66, s2=78)
        self.draw_counter(c, "L", "LIKES ON PLANS", fmt(self.likes_now(t)), (255, 120, 160))
        cu = self.cust_now(t)
        self.draw_counter(c, "R", "CUSTOMERS", fmt(cu), GREEN if cu > 0 else (235, 235, 240))


def build_lib(rng):
    from skins_video import build_lib as skins_lib
    return skins_lib(rng)


def build(data):
    stages, t = [], 0.0
    pl = pc = pb = 0
    prev = None
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_likes"], sc["_prev_cust"], sc["_prev_boxes"], sc["_prev_label"] = pl, pc, pb, prev
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        pl, pc, prev = sc["likes"], sc["cust"], str(sc["label"])
        pb += sc.get("orders", 0)
    return stages, t


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p, build, build_lib)
