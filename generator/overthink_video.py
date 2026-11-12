#!/usr/bin/env python3
"""
"Overthinking vs. Doing" – gleiche Idee. Links vermehren sich die Gedankenblasen, bis das Zimmer voll ist.
Rechts: anfangen, scheitern, reparieren, launchen.

    python3 generator/overthink_video.py skripte/zimmer/25_overthinking.json
"""
import math
import os
import random
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import F_BOLD, clamp, ease_out_back, ease_out_cubic  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, paste_scaled, radial, room_overlay, seg, sprite  # noqa: E402
from wecker_video import person_fat  # noqa: E402
from job_video import SIT_DY, draw_chair_back, draw_desk, draw_laptop  # noqa: E402
from friends_video import draw_bulb  # noqa: E402
from zz_base import StageBase, fit_sprite, run  # noqa: E402

S = 1.15
F0 = FL - 10
THOUGHTS = ["What if I fail?", "What will people think?", "Not the right time.", "I need more research.",
            "Someone already did it.", "I'm not ready.", "What if nobody buys?", "Maybe next year.",
            "I'm not good enough.", "Too risky.", "I need a better plan.", "What if I look stupid?",
            "Wait for the perfect moment.", "Let me watch one more video.", "What if it's a waste?",
            "Others are smarter.", "Just one more month.", "I'll start Monday.", "What if they laugh?",
            "Is it even worth it?", "I need more money first.", "What if I regret it?", "Too late now.",
            "Maybe it's a dumb idea.", "I'll think about it.", "Need more experience.", "What if...",
            "Not yet.", "One day.", "I'm scared."]
MILESTONES = ["STARTED", "FIRST DRAFT", "FAILED", "FIXED IT", "LAUNCHED", "FIRST SALE", "100 CUSTOMERS"]
GOLD_GLOW = radial(320, GOLD, 120)


def thought_sprite(text, gray=0.0):
    spr = fit_sprite(text, 24, (40, 40, 48), 230, F_BOLD)
    w, h = spr.width - 10, 56
    img = Image.new("RGBA", (int(w + 16), int(h + 16)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fill = tuple(int(lerp(250, 175, gray)) for _ in range(3))
    d.ellipse((4, 4, img.width - 4, img.height - 4), fill=fill, outline=OUT, width=3)
    paste_scaled(img, spr, img.width / 2, img.height / 2, 1, 1)
    return img


class Stage(StageBase):
    door = False

    def setup(self):
        c = self.cfg
        self.label, self.header = str(c["label"]), c["header"]
        self.n0, self.n1 = c["_prev_n"], c["n"]
        self.h0, self.h1 = c["_prev_hours"], c["hours"]
        self.p0, self.p1 = c["_prev_prog"], c["prog"]
        self.milestone = MILESTONES[min(self.i, len(MILESTONES) - 1)]
        self.failed = self.milestone == "FAILED"
        k = self.n1 - self.n0
        self.t_new = [0.9 + j * (4.6 / max(1, k)) for j in range(k)]
        rnd = random.Random(42)
        x0 = ROOMS["L"]
        self.pos = []
        for j in range(len(THOUGHTS) * 2):
            if j < 8:
                x = x0 + 70 + (j % 3) * 150 + rnd.uniform(-20, 20)
                y = CEIL + 70 + (j // 3) * 90 + rnd.uniform(-15, 15)
            else:
                x = x0 + rnd.uniform(70, RW - 70)
                y = rnd.uniform(CEIL + 50, F0 - 60)
            self.pos.append((x, y))
        self.t_ms = 6.0
        self.thought_r = c.get("right_thought", "Just start.")

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else None
        if self.i == 0:
            s(0.3, "sparkle", 0.4)
            s(0.35, "pop_big", 0.35)
        for tt in self.t_new:
            s(tt, "pop", 0.3)
        s(1.2, "typing", 0.3)
        s(self.t_ms, "fail" if self.failed else "ding", 0.45)
        if not self.failed:
            s(self.t_ms + 0.1, "sparkle", 0.3)
        if self.i >= 4:
            s(self.t_ms + 0.4, "cash", 0.35)
        if self.final:
            s(5.0, "heartbeat", 0.3)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def n_now(self, t):
        return self.n0 + sum(1 for tt in self.t_new if t > tt)

    def hours_now(self, t):
        return lerp(self.h0, self.h1, smooth(seg(t, 0.8, 6.0)))

    def prog_now(self, t):
        return lerp(self.p0, self.p1, smooth(seg(t, self.t_ms, self.t_ms + 0.6)))

    # ---- links: Gedanken
    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        n = self.n_now(t)
        fill = n / len(THOUGHTS)
        fx = x0 + 240
        hand = (fx + 10 * S, F0 - 205 * S)
        shake = math.sin(t * 30) * 2 * fill if self.i >= 4 else 0
        info = person_fat(d, fx, F0, 0.1, (None, hand), mood=-0.2 - 0.6 * fill, look=0.3, head_drop=0.2 + 0.4 * fill,
                          shake=shake, s=S * (1 - 0.12 * fill))
        if self.i == 0:
            draw_bulb(c, info["head"][0], info["head"][1] - 110, 1 - smooth(seg(t, 4.0, 5.0)) * 0.6, 1.0)
        for j in range(n):
            text = THOUGHTS[j % len(THOUGHTS)]
            x, y = self.pos[j]
            age = (self.i - (j // max(1, self.n1 // max(1, self.i + 1)))) if False else 0
            new_t = None
            if j >= self.n0:
                new_t = self.t_new[j - self.n0]
            a = ease_out_back(seg(t, new_t, new_t + 0.3)) if new_t is not None else 1.0
            gray = 0.0 if new_t is not None else min(0.6, 0.15 + 0.05 * self.i)
            spr = thought_sprite(text, gray)
            x = clamp(x, x0 + spr.width / 2 + 4, x0 + RW - spr.width / 2 - 4)
            y = clamp(y, CEIL + spr.height / 2 + 4, F0 - spr.height / 2)
            paste_scaled(c, spr, x, y, 0.4 + 0.6 * a, clamp(a * 2))
            if j < 3:
                d = ImageDraw.Draw(c)
                hx, hy = info["head"]
                for k2, rr in enumerate((6, 9, 12)):
                    px = lerp(hx + 30, x, (k2 + 1) / 4)
                    py = lerp(hy - 40, y + 26, (k2 + 1) / 4)
                    d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=(240, 240, 245), outline=OUT, width=2)
        if self.final and t > 5.0:
            a = ease_out_back(seg(t, 5.0, 5.4))
            box = Image.new("RGBA", (300, 120), (0, 0, 0, 0))
            ImageDraw.Draw(box).rounded_rectangle((6, 6, 294, 114), 24, fill=(20, 20, 26), outline=RED, width=6)
            paste_scaled(box, sprite("STUCK", 70, RED), 150, 60, 1, 1)
            paste_scaled(c, box, x0 + RW / 2, F0 - 300, a, clamp(a * 2))

    def after_left(self, c, t):
        c.alpha_composite(room_overlay("L", (0, 0, 0), 6 + self.i * 7), (ROOMS["L"], CEIL))

    # ---- rechts: machen
    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        # Fortschrittsleiste mit Meilensteinen
        bx0, bx1, by = x0 + 30, x0 + 446, CEIL + 120
        d.rounded_rectangle((bx0, by - 14, bx1, by + 14), 12, fill=(40, 42, 52), outline=OUT, width=3)
        p = self.prog_now(t) / 100
        if p > 0.01:
            d.rounded_rectangle((bx0 + 4, by - 10, bx0 + 4 + (bx1 - bx0 - 8) * p, by + 10), 9, fill=GREEN)
        done = self.i + (1 if t > self.t_ms else 0)
        for k in range(len(MILESTONES)):
            mx = bx0 + 20 + k * (bx1 - bx0 - 40) / (len(MILESTONES) - 1)
            col = (RED if MILESTONES[k] == "FAILED" else GOLD) if k < done else (90, 92, 104)
            d.ellipse((mx - 12, by - 12, mx + 12, by + 12), fill=col, outline=OUT, width=3)
        cur = MILESTONES[min(done - 1, len(MILESTONES) - 1)] if done > 0 else ""
        if cur:
            spr = fit_sprite(cur, 30, RED if cur == "FAILED" else GOLD, 300)
            d.rounded_rectangle((x0 + RW / 2 - spr.width / 2 + 14, by + 22, x0 + RW / 2 + spr.width / 2 - 14, by + 66), 14,
                                fill=(20, 20, 26), outline=OUT, width=2)
            paste_scaled(c, spr, x0 + RW / 2, by + 44, 1, 1)
            d = ImageDraw.Draw(c)
        draw_chair_back(d, x0)
        hands = [(x0 + 380 + math.sin(t * 18) * 4, F0 - 118), (x0 + 410 + math.cos(t * 23) * 4, F0 - 118)]
        mood = 0.6
        if self.failed and t > self.t_ms:
            mood = -0.5
            hands = [(x0 + 330 - 30 * S, F0 + SIT_DY - 230 * S), (x0 + 330 + 30 * S, F0 + SIT_DY - 230 * S)]
            if t > self.t_ms + 1.2:
                mood = 0.3
                hands = [(x0 + 380 + math.sin(t * 18) * 4, F0 - 118), (x0 + 410 + math.cos(t * 23) * 4, F0 - 118)]
        elif t > self.t_ms and (self.i >= 4 or self.final):
            hands = [(x0 + 330 - 62 * S, F0 + SIT_DY - 280 * S), (x0 + 330 + 62 * S, F0 + SIT_DY - 280 * S)]
            mood = 1.0
        elif t > self.t_ms:
            mood = 0.9
        lay = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        info = person_fat(ld, x0 + 330, F0 + SIT_DY, 0.1, tuple(hands), mood=mood, look=1.0 if t < self.t_ms else 0.2, s=S)
        c.alpha_composite(lay, (x0, CEIL), (x0, CEIL, x0 + RW, F0 - 2))
        d = ImageDraw.Draw(c)
        draw_desk(d, x0)
        draw_laptop(c, d, x0, True, t, (self.i + seg(t, 1, 6)) / 7, self.i)
        d = ImageDraw.Draw(c)
        if self.i == 0:
            draw_bulb(c, info["head"][0], info["head"][1] - 110, 1.0, ease_out_back(seg(t, 0.3, 0.6)))
        a = ease_out_back(seg(t, 0.4, 0.7)) * (1 - smooth(seg(t, 1.8, 2.1)))
        if a > 0.02:
            paste_scaled(c, thought_sprite(self.thought_r), x0 + 260, CEIL + 260, 0.5 + 0.5 * a, clamp(a * 2))
        if t > self.t_ms and not self.failed:
            e = ease_out_cubic(seg(t, self.t_ms, self.t_ms + 0.8))
            paste_scaled(c, GOLD_GLOW, info["head"][0], info["head"][1], 0.5 + e, (1 - e) * 0.8)
        if self.failed and t > self.t_ms + 1.2:
            self.float_text(c, '"Try again."', (230, 230, 240), x0 + 300, CEIL + 260, t - self.t_ms - 1.2, 40, 1.4, 10)

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, self.header, self.label, self.cfg.get("_prev_label"), self.data.get("subtitle", "SAME IDEA · SAME DAY"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=62, s2=70)
        self.draw_counter(c, "L", "HOURS THINKING", f"{self.hours_now(t):,.0f} h", (170, 180, 230))
        pr = self.prog_now(t)
        self.draw_counter(c, "R", "PROGRESS", f"{pr:.0f}%", GREEN if pr > 0 else (235, 235, 240))


def build_lib(rng):
    from skins_video import build_lib as skins_lib
    return skins_lib(rng)


def build(data):
    stages, t = [], 0.0
    pn = ph = pp = 0
    prev = None
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_n"], sc["_prev_hours"], sc["_prev_prog"], sc["_prev_label"] = pn, ph, pp, prev
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        pn, ph, pp, prev = sc["n"], sc["hours"], sc["prog"], str(sc["label"])
    return stages, t


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p, build, build_lib)
