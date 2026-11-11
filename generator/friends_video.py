#!/usr/bin/env python3
"""
"Your 5 Friends" – gleiche Idee, andere Freunde. Links lachen sie ihn aus, rechts pushen sie ihn.

    python3 generator/friends_video.py skripte/zimmer/22_your_5_friends.json
"""
import math
import os
import sys

from PIL import ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import F_BOLD, clamp, ease_out_back, ease_out_cubic  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, paste_scaled, radial, room_overlay, seg, sprite  # noqa: E402
from wecker_video import person_fat  # noqa: E402
from wedding_video import draw_bubble  # noqa: E402
from betting_video import draw_popcorn  # noqa: E402
from zz_base import StageBase, fit_sprite, run  # noqa: E402

F0 = FL - 10
SF, SM = 0.9, 1.1
MAIN_X = 240
FRIENDS = [(70, (200, 80, 80)), (150, (90, 170, 110)), (330, (230, 160, 60)), (410, (150, 100, 200))]
GLOW = radial(260, (255, 230, 120), 170)
GOLD_GLOW = radial(320, GOLD, 120)


def draw_bulb(c, x, y, on, scale=1.0):
    d = ImageDraw.Draw(c)
    if on > 0.05:
        paste_scaled(c, GLOW, x, y, 0.8 * scale, on)
        d = ImageDraw.Draw(c)
    r = 24 * scale
    col = tuple(int(lerp(a, b, on)) for a, b in zip((110, 110, 120), (255, 230, 110)))
    d.ellipse((x - r, y - r, x + r, y + r), fill=col, outline=OUT, width=3)
    d.rectangle((x - 10 * scale, y + r - 4, x + 10 * scale, y + r + 12 * scale), fill=(170, 170, 180), outline=OUT, width=2)
    return d


def draw_trophy(d, x, y):
    d.polygon([(x - 18, y - 40), (x + 18, y - 40), (x + 12, y - 14), (x - 12, y - 14)], fill=GOLD, outline=OUT)
    d.rectangle((x - 4, y - 14, x + 4, y - 4), fill=GOLD, outline=OUT, width=2)
    d.rectangle((x - 14, y - 4, x + 14, y + 2), fill=(120, 90, 50), outline=OUT, width=2)


class Stage(StageBase):
    door = False

    def setup(self):
        c = self.cfg
        self.label = str(c["year"])
        self.goal = c["goal"]
        self.bad = c["bad"]
        self.good = c["good"]
        self.g0 = c["_prev_goals"]
        self.t_idea, self.t_bad1, self.t_bad2, self.t_out = 0.4, 1.4, 2.6, 4.0
        self.t_win = 6.2

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        s(self.t_idea, "sparkle", 0.35)
        s(self.t_idea + 0.05, "pop_big", 0.35)
        s(self.t_bad1, "laugh", 0.45)
        s(self.t_bad2, "laugh", 0.4)
        s(self.t_out, "powerdown", 0.3)
        s(self.t_bad1 + 0.1, "pop", 0.3)
        s(self.t_bad2 + 0.1, "pop", 0.3)
        s(4.2, "cheer", 0.3)
        s(self.t_win, "ding", 0.5)
        s(self.t_win + 0.1, "cash", 0.35)
        for k in range(4):
            s(1.6 + k * 0.5, "crunch", 0.12)
        if self.final:
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def friends(self, c, d, x0, t, good):
        cheer = good and 4.2 < t < 5.6
        laugh = (not good) and (self.t_bad1 < t < 3.8)
        for k, (fx, col) in enumerate(FRIENDS):
            hands, mood, look, mouth_o, shake, bob = [None, None], 0.4, (1 if fx < MAIN_X else -1) * 0.8, False, 0.0, 0.0
            if cheer:
                ph = t * 8 + k
                hands = [(x0 + fx - 50 * SF, F0 - (250 + 30 * math.sin(ph)) * SF), (x0 + fx + 50 * SF, F0 - (250 - 30 * math.sin(ph)) * SF)]
                mood, bob = 1.0, abs(math.sin(ph)) * 8
            elif laugh:
                mouth_o = int(t * 8 + k) % 2 == 0
                shake = math.sin(t * 40 + k) * 3
                mood = 1.0
                if k % 2 == 0:
                    hands[1 if fx < MAIN_X else 0] = (x0 + fx + (60 if fx < MAIN_X else -60) * SF, F0 - 200 * SF)
            elif not good:
                mood = 0.2
                if k == 1:
                    hands[1] = (x0 + fx + 34 * SF, F0 - 200 * SF)
            person_fat(d, x0 + fx, F0, 0.1 if good else 0.2, tuple(hands), mood=mood, look=look, mouth_o=mouth_o, shake=shake, bob=bob,
                       s=SF, shirt=col, skin=(236, 236, 242))

    def main_person(self, c, d, x0, t, good):
        hands, mood, look, head_drop, bob = [None, None], 0.6, 0.0, 0.0, 0.0
        if self.t_idea < t < 1.4:
            hands[1] = (x0 + MAIN_X + 40 * SM, F0 - 250 * SM)
            mood = 0.9
        if not good and t > self.t_bad1:
            mood = -0.6
            head_drop = smooth(seg(t, self.t_out, self.t_out + 0.6)) * 0.8
        if good and t > 4.2:
            ph = t * 7
            hands = [(x0 + MAIN_X - 62 * SM, F0 - 285 * SM), (x0 + MAIN_X + 62 * SM, F0 - 285 * SM)] if t > self.t_win else hands
            mood = 1.0
            bob = abs(math.sin(ph)) * 6 if t > self.t_win else 0
        return person_fat(d, x0 + MAIN_X, F0, 0.1, tuple(hands), mood=mood, look=look, head_drop=head_drop, bob=bob, s=SM)

    def draw_side(self, c, t, good):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R" if good else "L"]
        n_tr = self.g0 + (1 if (good and t > self.t_win) else 0)
        if good:
            d.line([(x0 + 22, 872), (x0 + 240, 872)], fill=(92, 66, 50), width=6)
            for k in range(min(n_tr, 7)):
                draw_trophy(d, x0 + 44 + k * 30, 868)
        self.friends(c, d, x0, t, good)
        info = self.main_person(c, d, x0, t, good)
        hx, hy = info["head"]
        # Glühbirne
        if t > self.t_idea:
            pop = ease_out_back(seg(t, self.t_idea, self.t_idea + 0.35))
            if good:
                on = 1.0
                sc = 1.0 + (0.4 * smooth(seg(t, 4.2, 5.0)))
            else:
                on = 1 - smooth(seg(t, self.t_out, self.t_out + 0.5))
                sc = 1.0
            if not good and t > self.t_out + 1.6:
                on = 0
            if not (not good and t > 6.0):
                draw_bulb(c, hx, hy - info["r"] - 70 * pop, on, sc * pop)
        idea_a = smooth(seg(t, self.t_idea, self.t_idea + 0.25)) * (1 - smooth(seg(t, 1.3, 1.5)))
        draw_bubble(c, x0 + RW / 2, CEIL + 300, f'"I wanna {self.goal}"', idea_a)
        lines = self.good if good else self.bad
        for k, (tt, x) in enumerate(((self.t_bad1, FRIENDS[0][0] + 30), (self.t_bad2, FRIENDS[3][0] - 30))):
            a = smooth(seg(t, tt, tt + 0.25)) * (1 - smooth(seg(t, tt + 1.25, tt + 1.45)))
            draw_bubble(c, x0 + clamp(x, 150, 330), CEIL + 300 + k * 10, lines[k], a)
        if good and t > self.t_win:
            e = ease_out_cubic(seg(t, self.t_win, self.t_win + 0.8))
            paste_scaled(c, GOLD_GLOW, hx, hy, 0.6 + e, (1 - e) * 0.9)
            a = ease_out_back(seg(t, self.t_win, self.t_win + 0.35))
            paste_scaled(c, fit_sprite("GOAL REACHED", 44, GOLD, 420), x0 + RW / 2, CEIL + 160, a, clamp(a * 2))
        if not good and t > self.t_out + 0.8:
            a = smooth(seg(t, self.t_out + 0.8, self.t_out + 1.1))
            paste_scaled(c, fit_sprite("DREAM CANCELLED", 40, (170, 170, 185), 420), x0 + RW / 2, CEIL + 160, 1, a)

    def draw_left(self, c, t):
        self.draw_side(c, t, False)

    def after_left(self, c, t):
        c.alpha_composite(room_overlay("L", (0, 0, 0), 8 + self.i * 6), (ROOMS["L"], CEIL))

    def draw_right(self, c, t):
        self.draw_side(c, t, True)

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, "YEAR", self.label, str(self.cfg["_prev_year"]) if self.cfg["_prev_year"] else None,
                           self.data.get("subtitle", "SAME IDEAS · DIFFERENT FRIENDS"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=66, s2=74)
        gr = self.g0 + (1 if t > self.t_win else 0)
        bump = 1 + 0.18 * (1 - smooth(seg(t, self.t_win, self.t_win + 0.3))) if t > self.t_win else 1
        self.draw_counter(c, "L", "GOALS REACHED", "0", (235, 235, 240))
        self.draw_counter(c, "R", "GOALS REACHED", str(gr), GREEN if gr > 0 else (235, 235, 240), bump=bump)


def build_lib(rng):
    from skins_video import build_lib as skins_lib
    return skins_lib(rng)


def build(data):
    stages, t = [], 0.0
    pg = 0
    py = None
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_goals"], sc["_prev_year"] = pg, py
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        pg += 1
        py = sc["year"]
    return stages, t


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p, build, build_lib)
