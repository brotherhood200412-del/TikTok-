#!/usr/bin/env python3
"""
"Comfort Zone" – leuchtender Kreis auf dem Boden. Jede Challenge: links "Maybe later" (Kreis schrumpft),
rechts zittert er, geht trotzdem raus, schafft es (Kreis wächst).

    python3 generator/comfort_video.py skripte/zimmer/23_comfort_zone.json
"""
import math
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import clamp, ease_out_back, ease_out_cubic  # noqa: E402
from figuren_video import lerp, smooth  # noqa: E402
from zimmer_video import CEIL, FL, GOLD, GREEN, OUT, RED, ROOMS, RW, paste_scaled, radial, room_overlay, seg, sprite  # noqa: E402
from wecker_video import person_fat  # noqa: E402
from job_video import draw_couch_back, draw_couch_front  # noqa: E402
from scroll_video import draw_phone_screen  # noqa: E402
from wedding_video import draw_bubble  # noqa: E402
from zz_base import StageBase, fit_sprite, run  # noqa: E402

S = 1.15
F0 = FL - 10
CX_R = 200
ZONE_COL = (90, 200, 255)
SEAT_FY = F0 + 106
GOLD_GLOW = radial(320, GOLD, 120)


def draw_zone(c, cx, r, t, room_x0, part="back", col=ZONE_COL):
    """Leuchtende Ellipse auf dem Boden; 'back' = hintere Hälfte + Füllung, 'front' = vordere Hälfte."""
    if r < 8:
        return
    lay = Image.new("RGBA", c.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    ry = max(8, r * 0.24)
    cy = F0 - ry + 6
    box = (cx - r, cy - ry, cx + r, cy + ry)
    pulse = 0.8 + 0.2 * math.sin(t * 3)
    if part == "back":
        d.ellipse(box, fill=col + (40,))
        arc = (180, 360)
    else:
        arc = (0, 180)
    for w, a in ((26, 45), (14, 100), (6, 240)):
        d.arc(box, arc[0], arc[1], fill=col + (int(a * pulse),), width=w)
    c.alpha_composite(lay.crop((room_x0, CEIL, room_x0 + RW, FL)), (room_x0, CEIL))
    if part == "front" and r > 55:
        lx = clamp(cx - r * 0.55, room_x0 + 70, room_x0 + RW - 70)
        paste_scaled(c, sprite("COMFORT ZONE", 22, col), lx, cy + ry * 0.55, 1, 0.95)


def draw_ch_card(c, x, y, text, a):
    if a <= 0.02:
        return
    spr = fit_sprite(text, 34, (30, 30, 36), 360)
    w = spr.width + 10
    img = Image.new("RGBA", (int(w + 20), 140), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((6, 6, img.width - 6, 130), 18, fill=(255, 224, 110), outline=OUT, width=5)
    paste_scaled(img, sprite("CHALLENGE", 22, (160, 60, 40)), img.width / 2, 36, 1, 1)
    paste_scaled(img, spr, img.width / 2, 86, 1, 1)
    paste_scaled(c, img, x, y, 0.6 + 0.4 * a, clamp(a * 2))


# Kleine Szenen-Requisiten für das "Rausgehen"
def draw_prop(d, kind, x, t):
    if kind == "SPEAK":
        d.rectangle((x - 30, F0 - 110, x + 30, F0), fill=(110, 80, 60), outline=OUT, width=4)
        d.line([(x + 14, F0 - 110), (x + 30, F0 - 170)], fill=(60, 60, 70), width=4)
        d.ellipse((x + 22, F0 - 186, x + 40, F0 - 164), fill=(40, 40, 46), outline=OUT, width=2)
    elif kind == "GYM":
        d.line([(x - 50, F0 - 6), (x + 50, F0 - 6)], fill=(60, 60, 70), width=8)
        for sx in (x - 50, x + 50):
            d.rounded_rectangle((sx - 10, F0 - 34, sx + 10, F0 + 20), 3, fill=(40, 40, 50), outline=OUT, width=2)
    elif kind == "RAISE":
        d.rectangle((x - 50, F0 - 90, x + 50, F0 - 76), fill=(92, 66, 50), outline=OUT, width=3)
        d.rectangle((x - 42, F0 - 76, x + 42, F0), fill=(110, 80, 60), outline=OUT, width=3)
        person_fat(d, x + 70, F0, 0.2, mood=0.0, look=-1, s=0.95, shirt=(60, 60, 70), hair=(150, 150, 155))
    elif kind == "LANGUAGE":
        d.rectangle((x - 46, F0 - 230, x + 46, F0 - 150), fill=(240, 240, 236), outline=(150, 150, 160), width=4)
        d.text((x - 30, F0 - 220), "HOLA", fill=(220, 60, 60))
        d.text((x - 30, F0 - 196), "BONJOUR", fill=(60, 90, 220))
        d.text((x - 30, F0 - 172), "CIAO", fill=(40, 140, 60))
    elif kind == "TRAVEL":
        d.rounded_rectangle((x - 26, F0 - 70, x + 26, F0), 6, fill=(220, 90, 70), outline=OUT, width=3)
        d.rectangle((x - 8, F0 - 82, x + 8, F0 - 70), outline=OUT, width=3)
    elif kind == "BUSINESS":
        d.rectangle((x - 50, F0 - 200, x + 50, F0 - 150), fill=(30, 30, 40), outline=GOLD, width=4)
        d.text((x - 32, F0 - 182), "OPEN", fill=GOLD)
        d.rectangle((x - 44, F0 - 70, x + 44, F0), fill=(110, 80, 60), outline=OUT, width=3)


class Stage(StageBase):
    door = False

    def setup(self):
        c = self.cfg
        self.label = str(c["month"])
        self.ch = c["challenge"]
        self.prop = c["prop"]
        self.done0 = c["_prev_done"]
        self.rl0, self.rl1 = c["_prev_rl"], c["rl"]
        self.rr0, self.rr1 = c["_prev_rr"], c["rr"]
        self.t_card, self.t_no, self.t_out, self.t_win, self.t_back = 0.35, 1.4, 1.6, 4.4, 5.6

    def schedule(self):
        s = self.sfx
        s(0.05, "page", 0.5) if self.i > 0 else s(0.1, "pop_big", 0.35)
        s(self.t_card, "notif", 0.45)
        s(self.t_card + 0.05, "pop_big", 0.35)
        s(self.t_no, "pop", 0.3)
        s(self.t_out - 0.2, "heartbeat", 0.45)
        for st in (self.t_out + 0.2, self.t_out + 0.45, self.t_out + 0.7):
            s(st, "step", 0.3)
        s(self.t_win, "ding", 0.5)
        s(self.t_win + 0.1, "cheer", 0.3)
        s(self.t_back + 0.2, "whoosh", 0.35)
        s(self.t_back + 0.5, "sparkle", 0.4)
        s(self.t_back + 0.4, "powerdown", 0.18)
        if self.final:
            s(7.0, "cash", 0.35)
            s(8.3, "pop_big", 0.45)
            s(9.3, "ding", 0.5)

    def rl_now(self, t):
        return lerp(self.rl0, self.rl1, smooth(seg(t, self.t_back, self.t_back + 0.8)))

    def rr_now(self, t):
        return lerp(self.rr0, self.rr1, ease_out_back(seg(t, self.t_back, self.t_back + 0.8)))

    # ---- links: bleibt drin
    def draw_left(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["L"]
        draw_zone(c, x0 + 330, self.rl_now(t), t, x0, "back")
        d = ImageDraw.Draw(c)
        draw_couch_back(d, x0)
        hands = [None, (x0 + 330 + 30 * S, SEAT_FY - 200 * S)]
        mood = 0.2 if self.i < 3 else -0.4
        lay = Image.new("RGBA", c.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        info = person_fat(ld, x0 + 330, SEAT_FY, 0.1 + 0.04 * self.i, tuple(hands), mood=mood, look=-0.2,
                          head_drop=0.2 + 0.08 * self.i, s=S)
        h = info["hands"][1]
        draw_phone_screen(ld, h[0] + 4, h[1] - 26, 34, 56, t)
        c.alpha_composite(lay, (x0, CEIL), (x0, CEIL, x0 + RW, F0 - 2))
        d = ImageDraw.Draw(c)
        draw_couch_front(d, x0)
        draw_zone(c, x0 + 330, self.rl_now(t), t, x0, "front")
        a = ease_out_back(seg(t, self.t_card, self.t_card + 0.35)) * (1 - smooth(seg(t, self.t_no + 0.3, self.t_no + 0.6)))
        draw_ch_card(c, x0 + RW / 2, CEIL + 220, self.ch, a)
        b = smooth(seg(t, self.t_no, self.t_no + 0.25)) * (1 - smooth(seg(t, self.t_no + 2.4, self.t_no + 2.7)))
        draw_bubble(c, x0 + 300, F0 - 340, "Maybe later...", b)
        if t > self.t_back and self.rl1 < self.rl0:
            self.float_text(c, "ZONE SHRINKS", (150, 170, 200), x0 + 300, F0 - 300, t - self.t_back, 26, 1.2, 10)

    def after_left(self, c, t):
        c.alpha_composite(room_overlay("L", (0, 0, 0), 6 + self.i * 7), (ROOMS["L"], CEIL))

    # ---- rechts: geht raus
    def draw_right(self, c, t):
        d = ImageDraw.Draw(c)
        x0 = ROOMS["R"]
        r = self.rr_now(t)
        draw_zone(c, x0 + CX_R, r, t, x0, "back")
        d = ImageDraw.Draw(c)
        out_x = x0 + clamp(CX_R + r + 90, 340, 420)
        draw_prop(d, self.prop, out_x + 10, t)
        home = x0 + CX_R
        fx, shake, mood, hands, walk, mouth_o = home, 0.0, 0.5, [None, None], 0.0, False
        if self.t_no - 0.3 < t < self.t_out:
            shake = math.sin(t * 50) * 4
            mood = -0.5
            mouth_o = True
        if self.t_out < t < self.t_out + 0.9:
            k = smooth(seg(t, self.t_out, self.t_out + 0.9))
            fx = lerp(home, out_x - 70, k)
            walk = (t - self.t_out) * 14
            shake = math.sin(t * 50) * 3 * (1 - k)
            mood = -0.2
        elif self.t_out + 0.9 <= t < self.t_back:
            fx = out_x - 70
            mood = 0.4 if t < self.t_win else 1.0
            if t >= self.t_win:
                hands = [(fx - 62 * S, F0 - 285 * S), (fx + 62 * S, F0 - 285 * S)]
            else:
                g = math.sin((t - self.t_out) * 6)
                hands = [None, (fx + (50 + 10 * g) * S, F0 - (210 + 20 * g) * S)]
        elif t >= self.t_back:
            k = smooth(seg(t, self.t_back, self.t_back + 0.6))
            fx = lerp(out_x - 70, home, k)
            walk = (t - self.t_back) * 14 if k < 1 else 0
            mood = 0.9
            if self.final and t > 6.6:
                hands = [(fx - 62 * S, F0 - 285 * S), (fx + 62 * S, F0 - 285 * S)]
        info = person_fat(d, fx, F0, 0.1, tuple(hands), walk=walk, mood=mood, look=0.6, shake=shake, mouth_o=mouth_o, s=S)
        draw_zone(c, x0 + CX_R, r, t, x0, "front")
        d = ImageDraw.Draw(c)
        if self.t_no - 0.3 < t < self.t_out + 0.5:
            hx, hy = info["head"]
            for k in range(2):
                ph = ((t * 2) + k / 2) % 1
                sx = hx + (info["r"] + 6) * (1 if k else -1)
                d.ellipse((sx - 5, hy - 8 + ph * 30, sx + 5, hy + 6 + ph * 30), fill=(130, 200, 255))
            self.float_text(c, "*nervous*", (220, 220, 230), hx, hy - 90, t - self.t_no + 0.3, 30, 1.2, 10)
        a = ease_out_back(seg(t, self.t_card, self.t_card + 0.35)) * (1 - smooth(seg(t, self.t_no + 0.3, self.t_no + 0.6)))
        draw_ch_card(c, x0 + RW / 2, CEIL + 220, self.ch, a)
        if t > self.t_win:
            e = ease_out_cubic(seg(t, self.t_win, self.t_win + 0.8))
            paste_scaled(c, GOLD_GLOW, fx, info["head"][1], 0.5 + e, (1 - e) * 0.8)
            self.float_text(c, "DONE!", GOLD, fx, info["head"][1] - 100, t - self.t_win, 50, 1.0, 20)
        if t > self.t_back + 0.4 and self.rr1 > self.rr0:
            self.float_text(c, "ZONE GROWS", ZONE_COL, x0 + CX_R, F0 - 330, t - self.t_back - 0.4, 30, 1.2, 10)

    def draw_hud(self, c, t):
        self.draw_calendar(c, t, "MONTH", self.label, str(self.cfg["_prev_month"]) if self.cfg["_prev_month"] else None,
                           self.data.get("subtitle", "SAME FEARS · SAME CHANCES"))
        if self.final:
            self.draw_punch(c, t, self.data["punch1"], self.data["punch2"], s1=66, s2=72)
        dn = self.done0 + (1 if t > self.t_win else 0)
        bump = 1 + 0.18 * (1 - smooth(seg(t, self.t_win, self.t_win + 0.3))) if t > self.t_win else 1
        self.draw_counter(c, "L", "FEARS FACED", "0", (235, 235, 240))
        self.draw_counter(c, "R", "FEARS FACED", str(dn), GREEN if dn > 0 else (235, 235, 240), bump=bump)


def build_lib(rng):
    from skins_video import build_lib as skins_lib
    return skins_lib(rng)


def build(data):
    stages, t = [], 0.0
    pd = 0
    pm = None
    rl, rr = data["r_start"], data["r_start"]
    n = len(data["stages"])
    for i, sc in enumerate(data["stages"]):
        sc = dict(sc)
        sc["_prev_done"], sc["_prev_month"], sc["_prev_rl"], sc["_prev_rr"] = pd, pm, rl, rr
        st = Stage(i, sc, t, n, data)
        stages.append(st)
        t += st.dur
        pd += 1
        pm = sc["month"]
        rl, rr = sc["rl"], sc["rr"]
    return stages, t


if __name__ == "__main__":
    for p in sys.argv[1:]:
        run(p, build, build_lib)
