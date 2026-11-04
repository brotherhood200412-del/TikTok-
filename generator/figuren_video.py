#!/usr/bin/env python3
"""
Figuren-Stil Generator (schwarz, leuchtende Strichfiguren, farbige Akzente)
==========================================================================
Jede Szene ist eine animierte Metapher (Tauziehen, Weggabelung, Mauer, Treppe,
Baum, Waage, Münzstapel, Menge, Rucksack) mit Glow-Effekt, Sounddesign und
dunklem Ambient-Beat. Videos sind 1080x1920, 30 fps, mindestens 61,5 s.

    python3 generator/figuren_video.py skripte/figuren/*.json
"""
import json
import math
import os
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_video import (F_BLACK, F_SEMI, FPS, H, SR, W, WordBlock, build_sfx, clamp,  # noqa: E402
                        ease_out_back, ease_out_cubic, env_exp, font, lowpass, midi, pill,
                        paste_scaled, sine_sweep, text_sprite)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "videos")
MIN_DURATION = 61.5
GROUND = 1150

COLORS = dict(white=(255, 255, 255), gold=(255, 196, 60), green=(70, 232, 140), red=(255, 78, 98),
              blue=(90, 175, 255), purple=(185, 130, 255), gray=(120, 120, 135))
WHITE, GOLD, GREEN, RED, BLUE = (COLORS[k] for k in ("white", "gold", "green", "red", "blue"))
LINE = (200, 200, 212)


def col(c):
    return COLORS[c] if isinstance(c, str) else tuple(c)


def dim(c, f):
    return tuple(int(v * f) for v in c)


def lerp(a, b, t):
    return a + (b - a) * t


def lerpc(a, b, t):
    return tuple(int(lerp(x, y, t)) for x, y in zip(a, b))


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def interp(keys, x):
    if x <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if x <= t1:
            return v0 + (v1 - v0) * smooth((x - t0) / (t1 - t0))
    return keys[-1][1]


def label(text, size=52, color=WHITE, path=F_BLACK, glow=False):
    return text_sprite(text, font(path, size), color, glow=glow)[0]


def fit_label(text, max_w, size, color, glow=False):
    while size > 14 and font(F_BLACK, size).getlength(text) > max_w:
        size -= 2
    return label(text, size, color, glow=glow)


# ----------------------------------------------------------------- figure
def figure(d, x, gy, s=1.0, ang=0.0, color=WHITE, hands=(), bob=0.0, head=(0, 0), body_h=1.0):
    """Leuchtende Figur: Pillen-Körper + runder Kopf. ang>0 = nach rechts geneigt."""
    w, h, r, gap = 92 * s, 122 * s * body_h, 33 * s, 11 * s
    ca, sa = math.cos(ang), math.sin(ang)
    by = gy - bob

    def tr(px, py):
        return (x + px * ca - py * sa, by + px * sa + py * ca)

    cy = -(h - w / 2)
    pts = [tr(-w / 2, 0)]
    for i in range(17):
        a = math.pi + math.pi * i / 16
        pts.append(tr(w / 2 * math.cos(a), cy + w / 2 * math.sin(a)))
    pts.append(tr(w / 2, 0))
    d.polygon(pts, fill=color)
    hx, hy = tr(head[0] * s, -(h + gap + r) + head[1] * s)
    d.ellipse((hx - r, hy - r, hx + r, hy + r), fill=color)
    aw = max(3, int(11 * s))
    for side, (px, py) in hands:
        sx, sy = tr(side * w * 0.22, -h * 0.62)
        d.line([(sx, sy), (px, py)], fill=color, width=aw)
        d.ellipse((px - aw * 0.7, py - aw * 0.7, px + aw * 0.7, py + aw * 0.7), fill=color)
    return dict(head=(hx, hy), top=(hx, hy - r))


def walk_bob(t, moving, s=1.0, rate=10.0):
    return abs(math.sin(t * rate)) * 9 * s if moving else 0.0


def step_times(t0, t1, rate=10.0):
    k0 = math.ceil(t0 * rate / math.pi)
    out = []
    k = k0
    while k * math.pi / rate < t1:
        out.append(k * math.pi / rate)
        k += 1
    return out


def coin(c, x, y, r, scale=1.0):
    r = r * scale
    if r < 2:
        return
    d = ImageDraw.Draw(c)
    d.ellipse((x - r, y - r, x + r, y + r), fill=(205, 140, 30))
    d.ellipse((x - r * 0.86, y - r * 0.86, x + r * 0.86, y + r * 0.86), fill=GOLD)
    d.ellipse((x - r * 0.62, y - r * 0.62, x + r * 0.62, y + r * 0.62), outline=(215, 150, 35), width=max(2, int(r * 0.08)))
    fs = max(10, int(r * 1.0))
    f = font(F_BLACK, fs)
    d.text((x, y), "€", font=f, fill=(150, 95, 10), anchor="mm")


def radial_sprite(size, color, max_a=255, power=2.0):
    ys, xs = np.mgrid[0:size, 0:size]
    rr = np.sqrt((xs - size / 2) ** 2 + (ys - size / 2) ** 2) / (size / 2)
    a = (np.clip(1 - rr, 0, 1) ** power * max_a).astype(np.uint8)
    arr = np.zeros((size, size, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = a
    return Image.fromarray(arr, "RGBA")


# ----------------------------------------------------------------- scenes
class Scene:
    has_ground = True

    def __init__(self, d, start):
        self.d, self.start, self.dur = d, start, float(d["dur"])
        self.ev = []
        self.head = None
        if d.get("headline"):
            self.head = WordBlock(d["headline"], dict(accent=GOLD), d.get("headline_size", 74),
                                  max_w=900, interval=0.075, start=0.12)
            for ta, hl in self.head.times():
                self.sfx(ta, "pop_big" if hl else "pop", 0.5 if hl else 0.16)
        self.cap = label(d["caption"], 68, WHITE, F_SEMI, glow=False) if d.get("caption") else None
        self.cap_t, self.cap_y = 1.0, GROUND + 115
        self.sfx(0.0, "whoosh", 0.35)
        self.setup()

    def setup(self):
        pass

    def sfx(self, t, name, g=1.0):
        if 0 <= t < self.dur:
            self.ev.append((t, name, g))

    def draw(self, c, t):
        d = ImageDraw.Draw(c)
        if self.has_ground:
            d.line([(0, GROUND), (W, GROUND)], fill=LINE, width=3)
        self.scene(c, d, t)
        if self.head:
            self.head.draw(c, t, 400 - self.head.height / 2)
        if self.cap:
            p = ease_out_cubic((t - self.cap_t) / 0.5)
            if p > 0:
                paste_scaled(c, self.cap, W / 2, self.cap_y + (1 - p) * 20, 1, p)

    def scene(self, c, d, t):
        pass


class HookScene(Scene):
    def setup(self):
        self.spot = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        arr = np.zeros((H, W, 4), np.uint8)
        ys, xs = np.mgrid[0:H, 0:W]
        top, bot = 560, GROUND
        frac = np.clip((ys - top) / (bot - top), 0, 1)
        half = 40 + frac * 260
        inside = (np.abs(xs - W / 2) < half) & (ys >= top) & (ys <= bot + 40)
        edge = np.clip(1 - np.abs(xs - W / 2) / np.maximum(half, 1), 0, 1) ** 0.6
        a = np.where(inside, (25 + 45 * frac) * edge, 0)
        arr[..., :3] = (255, 236, 190)
        arr[..., 3] = a.astype(np.uint8)
        self.spot = Image.fromarray(arr, "RGBA")
        self.pool = radial_sprite(700, (255, 220, 150), 70)
        self.sfx(0.05, "impact", 1.0)

    def scene(self, c, d, t):
        on = 1.0 if (0.05 < t < 0.14 or t > 0.22) else 0.0
        if on:
            c.alpha_composite(self.spot)
            paste_scaled(c, self.pool, W / 2, GROUND, 1.0, 0.9)
        d = ImageDraw.Draw(c)
        d.line([(0, GROUND), (W, GROUND)], fill=LINE, width=3)
        b = 4 * (0.5 + 0.5 * math.sin(t * 3))
        figure(d, W / 2, GROUND, 1.05, 0, WHITE if on else (60, 60, 70), bob=b * 0.3)


class CtaScene(Scene):
    def setup(self):
        self.btn = pill("+  FOLGEN", RED, size=56, text_color=WHITE)
        self.bt = 1.4
        self.sfx(self.bt, "cash", 0.55)
        self.sfx(0.5, "swish", 0.3)

    def scene(self, c, d, t):
        x = W / 2
        wave_ = math.sin(t * 9) * 28
        figure(d, x, GROUND, 1.05, 0, WHITE, hands=[(1, (x + 95 + wave_, GROUND - 270))])
        p = (t - self.bt) / 0.35
        if p > 0:
            pulse = 1 + 0.05 * math.sin((t - self.bt) * 7.5)
            paste_scaled(c, self.btn, W / 2, GROUND + 255, (0.5 + 0.5 * ease_out_back(p)) * pulse, clamp(p * 3))


class TugScene(Scene):
    def setup(self):
        dd = self.d
        self.lc, self.rc = col(dd.get("left_color", "gold")), col(dd.get("right_color", "red"))
        self.ls, self.rs = label(dd["left"], 54, self.lc), label(dd["right"], 54, self.rc)
        sg = 1 if dd.get("winner", "right") == "right" else -1
        D = self.dur
        self.sg = sg
        self.tw = 0.85 * D
        self.keys = [(0, 0), (0.3 * D, -sg * 35), (0.5 * D, sg * 25), (0.62 * D, -sg * 12),
                     (self.tw, sg * 180), (D, sg * 188)]
        for k in range(int(D / 0.97) + 1):
            self.sfx(0.24 + k * 0.97, "creak", 0.28)
        self.sfx(0.62 * D + 0.05, "whoosh", 0.45)
        self.sfx(self.tw - 0.05, "thud", 0.8)
        self.sfx(self.tw + 0.05, "ding", 0.5)

    def scene(self, c, d, t):
        D = self.dur
        jit = 9 * math.sin(t * 6.5) * (1 - smooth((t - self.tw + 0.4) / 0.4))
        dx = interp(self.keys, t) + jit
        xL, xR, ry = 330 + dx, 750 + dx, GROUND - 88
        angL = clamp(-0.26 + dx * 0.0016, -0.42, 0.1)
        angR = clamp(0.26 + dx * 0.0016, -0.1, 0.42)
        # Seil
        d.line([(xL + 40, ry + 3), (xR - 40, ry + 3)], fill=WHITE, width=6)
        d.line([(xR - 40, ry + 3), (xR + 75, ry + 14)], fill=WHITE, width=6)
        figure(d, xL, GROUND, 1, angL, WHITE, hands=[(1, (xL + 82, ry + 3)), (1, (xL + 118, ry + 3))])
        figure(d, xR, GROUND, 1, angR, WHITE, hands=[(-1, (xR - 82, ry + 3)), (-1, (xR - 118, ry + 3))])
        # Seil-Markierung (zeigt, wer gewinnt)
        xm = 540 + dx
        side = self.rc if dx > 0 else self.lc
        kc = lerpc(WHITE, side, min(1, abs(dx) / 140))
        d.ellipse((xm - 14, ry + 3 - 14, xm + 14, ry + 3 + 14), fill=kc)
        # feste Mitte: Pfeil + gestrichelte Linie
        d.polygon([(540, ry + 24), (526, ry + 48), (554, ry + 48)], fill=WHITE)
        yy = ry + 52
        while yy < GROUND - 4:
            d.line([(540, yy), (540, min(GROUND - 4, yy + 9))], fill=LINE, width=3)
            yy += 17
        # Labels
        won = smooth((t - self.tw) / 0.3)
        lw = 1 + 0.16 * won * (self.sg < 0)
        rw = 1 + 0.16 * won * (self.sg > 0)
        la = 1 - 0.55 * won * (self.sg > 0)
        ra = 1 - 0.55 * won * (self.sg < 0)
        app = ease_out_back((t - 0.3) / 0.35)
        if app > 0:
            paste_scaled(c, self.ls, clamp(xL, self.ls.width / 2 + 10, W - self.ls.width / 2 - 10), GROUND - 330, app * lw, clamp(app * 2) * la)
            paste_scaled(c, self.rs, clamp(xR, self.rs.width / 2 + 10, W - self.rs.width / 2 - 10), GROUND - 330, app * rw, clamp(app * 2) * ra)


class ForkScene(Scene):
    has_ground = False

    def setup(self):
        self.gs = fit_label(self.d["good"], 380, 50, GOLD)
        self.bs = fit_label(self.d["bad"], 380, 50, RED)
        self.q = label("?", 90, WHITE)
        self.F, self.G, self.B = (440, 1120), (900, 800), (900, 1320)
        D = self.dur
        self.w1 = (0.3, 2.2)
        self.w2 = (3.3, D - 0.7)
        self.burst = radial_sprite(500, GOLD, 100)
        for st in step_times(*self.w1) + step_times(*self.w2):
            self.sfx(st, "step", 0.45)
        self.sfx(2.35, "pop_big", 0.6)
        self.sfx(self.w2[1], "ding", 0.7)

    def scene(self, c, d, t):
        F, G, B = self.F, self.G, self.B
        d.line([(0, F[1]), F], fill=LINE, width=4)
        p2 = clamp((t - self.w2[0]) / (self.w2[1] - self.w2[0]))
        d.line([F, B], fill=dim(RED, 0.7), width=5)
        d.line([F, G], fill=(150, 150, 160), width=5)
        if p2 > 0:
            d.line([F, (lerp(F[0], G[0], p2), lerp(F[1], G[1], p2))], fill=GOLD, width=7)
        a = ease_out_back((t - 0.6) / 0.35)
        if a > 0:
            paste_scaled(c, self.gs, (F[0] + G[0]) / 2 - 60, (F[1] + G[1]) / 2 - 85, a, clamp(a * 2))
            paste_scaled(c, self.bs, (F[0] + B[0]) / 2 - 40, (F[1] + B[1]) / 2 + 75, a, clamp(a * 2) * (1 - 0.4 * p2))
        if t < self.w2[0]:
            x = lerp(110, F[0] - 10, smooth((t - self.w1[0]) / (self.w1[1] - self.w1[0])))
            mv = self.w1[0] < t < self.w1[1]
            info = figure(d, x, F[1], 0.9, 0.04 if mv else 0, WHITE, bob=walk_bob(t, mv, 0.9))
            qa = ease_out_back((t - 2.35) / 0.3) * (1 - smooth((t - 3.1) / 0.2))
            if qa > 0:
                paste_scaled(c, self.q, info["top"][0] + 10, info["top"][1] - 70, qa, clamp(qa * 2))
        else:
            mv = p2 < 1
            gx, gy = lerp(F[0], B[0], p2), lerp(F[1], B[1], p2)
            figure(d, gx, gy, 0.9, 0.1, dim(RED, 0.4), bob=walk_bob(t, mv, 0.9))
            x, y = lerp(F[0], G[0], p2), lerp(F[1], G[1], p2)
            figure(d, x - 40 * (1 - p2) * 0, y, 0.9, -0.04 if mv else 0, WHITE, bob=walk_bob(t, mv, 0.9))
            if p2 >= 1:
                e = ease_out_cubic((t - self.w2[1]) / 0.5)
                paste_scaled(c, self.burst, G[0] - 60, G[1] - 120, 0.4 + 0.8 * e, 1 - 0.3 * e)
                coin(c, G[0] - 60, G[1] - 260, 40, ease_out_back((t - self.w2[1]) / 0.35))


class LoadScene(Scene):
    def setup(self):
        D = self.dur
        self.box = fit_label(self.d["box"], 165, 32, WHITE, glow=False)
        self.t1, self.td = 0.3, D * 0.5
        self.x0, self.vs, self.vf = 220, 70, 270
        self.xd = self.x0 + (self.td - self.t1) * self.vs
        self.by0 = GROUND - 205
        g = 3000
        self.g = g
        self.tl = self.td + math.sqrt(2 * ((GROUND - 70) - self.by0) / g)
        self.tf = self.td + 0.5
        for st in step_times(self.t1, self.td, 6):
            self.sfx(st, "step", 0.6)
        for st in step_times(self.tf, D, 11):
            self.sfx(st, "step", 0.35)
        self.sfx(self.tl, "thud", 0.9)
        self.sfx(self.tf, "whoosh", 0.5)

    def x_at(self, t):
        if t < self.t1:
            return self.x0
        if t < self.td:
            return self.x0 + (t - self.t1) * self.vs
        if t < self.tf:
            return self.xd
        return min(980, self.xd + (t - self.tf) * self.vf)

    def draw_box(self, c, d, bx, by):
        d.rounded_rectangle((bx - 90, by - 70, bx + 90, by + 70), 14, fill=dim(RED, 0.32), outline=RED, width=5)
        paste_scaled(c, self.box, bx, by, 1, 1)

    def scene(self, c, d, t):
        x = self.x_at(t)
        if t < self.td:
            mv = t > self.t1
            b = walk_bob(t, mv, 1, 6) * 0.6
            bx, by = x - 150, self.by0 - b
            self.draw_box(c, d, bx, by)
            d = ImageDraw.Draw(c)
            figure(d, x, GROUND, 1, 0.3, WHITE, hands=[(-1, (bx + 88, by - 45)), (1, (bx + 92, by + 10))], bob=b)
        else:
            bx = self.xd - 150
            if t < self.tl:
                by = self.by0 + 0.5 * self.g * (t - self.td) ** 2
            else:
                k = t - self.tl
                by = GROUND - 70 - abs(math.sin(k * 14)) * 18 * math.exp(-k * 9)
            self.draw_box(c, d, bx, by)
            d = ImageDraw.Draw(c)
            ang = 0.3 * (1 - smooth((t - self.td) / 0.45))
            mv = t > self.tf and x < 980
            if mv:
                for i, yy in enumerate((GROUND - 60, GROUND - 105, GROUND - 150)):
                    l0 = x - 85 - i * 12
                    d.line([(l0 - 70, yy), (l0, yy)], fill=dim(GOLD, 0.8), width=5)
            figure(d, x, GROUND, 1, ang - (0.08 if mv else 0) * -1, WHITE, bob=walk_bob(t, mv, 1, 11))


class WallScene(Scene):
    def setup(self):
        D = self.dur
        rnd = random.Random(7)
        self.wx0, self.wx1, self.wtop = 650, 740, GROUND - 560
        self.wl = fit_label(self.d["wall"], 400, 52, RED)
        self.rw = fit_label(self.d["reward"], 420, 64, GOLD)
        self.light = radial_sprite(700, GOLD, 105, 1.8)
        self.walk = (0.3, 1.7)
        self.cracks = [1.8 + 0.55, 1.8 + 1.1, 1.8 + 1.65]
        self.tb = 1.8 + 2.15
        self.crack_lines = []
        for _ in range(3):
            pts = [(rnd.uniform(665, 725), rnd.uniform(self.wtop + 60, GROUND - 60))]
            for _ in range(5):
                pts.append((clamp(pts[-1][0] + rnd.uniform(-28, 28), 652, 738), pts[-1][1] + rnd.uniform(-70, 70)))
            self.crack_lines.append(pts)
        self.pieces = []
        ph = (GROUND - self.wtop) / 8
        for i in range(2):
            for j in range(8):
                self.pieces.append(dict(x=self.wx0 + i * 45, y=self.wtop + j * ph, w=45, h=ph,
                                        vx=rnd.uniform(150, 650), vy=rnd.uniform(-700, -100)))
        self.tend = (self.tb + 0.4, D - 0.3)
        for st in step_times(*self.walk):
            self.sfx(st, "step", 0.45)
        self.sfx(1.85, "creak", 0.5)
        for tc in self.cracks:
            self.sfx(tc, "crack", 0.7)
        self.sfx(self.tb, "impact", 0.85)
        self.sfx(self.tb + 0.3, "ding", 0.6)
        for st in step_times(*self.tend):
            self.sfx(st, "step", 0.35)

    def scene(self, c, d, t):
        broken = t >= self.tb
        if broken:
            e = ease_out_cubic((t - self.tb) / 0.6)
            paste_scaled(c, self.light, 840, GROUND - 260, 0.3 + 0.8 * e, e)
            ra = ease_out_back((t - self.tb - 0.25) / 0.4)
            if ra > 0:
                paste_scaled(c, self.rw, 820, GROUND - 330, ra, clamp(ra * 2))
            d = ImageDraw.Draw(c)
            d.line([(0, GROUND), (W, GROUND)], fill=LINE, width=3)
            k = t - self.tb
            for p in self.pieces:
                px = p["x"] + p["vx"] * k * 0.5
                py = min(GROUND - p["h"] * 0.4, p["y"] + p["vy"] * k + 1100 * k * k)
                a = 1 - smooth((k - 0.8) / 0.6)
                if a > 0:
                    d.rectangle((px, py, px + p["w"] - 4, py + p["h"] * 0.6), fill=dim(RED, 0.5 * a), outline=dim(RED, a), width=3)
        else:
            sh = math.sin(t * 60) * 3 if t > 1.8 else 0
            d.rectangle((self.wx0 + sh, self.wtop, self.wx1 + sh, GROUND), fill=dim(RED, 0.32), outline=RED, width=5)
            for i, tc in enumerate(self.cracks):
                if t > tc:
                    d.line([(x + sh, y) for x, y in self.crack_lines[i]], fill=(10, 0, 4), width=6)
            a = ease_out_back((t - 0.5) / 0.35)
            if a > 0:
                paste_scaled(c, self.wl, 695, self.wtop - 55, a, clamp(a * 2))
        # Figur
        if t < 1.8:
            mv = self.walk[0] < t < self.walk[1]
            x = lerp(160, 545, smooth((t - self.walk[0]) / (self.walk[1] - self.walk[0])))
            figure(d, x, GROUND, 1, 0.05 if mv else 0, WHITE, bob=walk_bob(t, mv))
        elif not broken:
            x = 545 + math.sin(t * 9) * 3
            figure(d, x, GROUND, 1, 0.36, WHITE, hands=[(1, (self.wx0 - 2, GROUND - 175)), (1, (self.wx0 - 2, GROUND - 120))])
        else:
            mv = self.tend[0] < t < self.tend[1]
            x = lerp(545, 790, smooth((t - self.tend[0]) / (self.tend[1] - self.tend[0])))
            ang = 0.36 * (1 - smooth((t - self.tb) / 0.4))
            figure(d, x, GROUND, 1, ang, WHITE, bob=walk_bob(t, mv))


class StairsScene(Scene):
    has_ground = False

    def setup(self):
        self.labels = self.d["steps"]
        n = self.n = len(self.labels)
        self.x0, self.x1, self.yb, self.yt = 140, 900, 1260, 800
        self.sw, self.sh = (self.x1 - self.x0) / n, (self.yb - self.yt) / n
        self.ls_off = [fit_label(s, self.sw - 16, 30, (120, 120, 135), glow=False) for s in self.labels]
        self.ls_on = [fit_label(s, self.sw - 16, 30, GOLD) for s in self.labels]
        self.hop0, self.hopi, self.hopd = 0.7, 0.62, 0.4
        self.tend = self.hop0 + n * self.hopi + 0.1
        self.burst = radial_sprite(420, GOLD, 95)
        for k in range(n):
            self.sfx(self.hop0 + k * self.hopi + self.hopd, f"note{min(k, 7)}", 0.6)
        self.sfx(self.tend, "cash", 0.6)
        self.cap_y = self.yb + 95

    def pos(self, k):
        if k < 0:
            return (self.x0 - 60, self.yb)
        return (self.x0 + k * self.sw + self.sw / 2, self.yb - (k + 1) * self.sh)

    def scene(self, c, d, t):
        pts = [(0, self.yb), (self.x0, self.yb)]
        for k in range(self.n):
            x = self.x0 + k * self.sw
            y = self.yb - (k + 1) * self.sh
            pts += [(x, y), (x + self.sw, y)]
        pts.append((W, self.yt))
        d.line(pts, fill=LINE, width=4, joint="curve")
        cur = -1
        for k in range(self.n):
            if t >= self.hop0 + k * self.hopi + self.hopd:
                cur = k
        for k in range(self.n):
            x = self.x0 + k * self.sw
            y = self.yb - (k + 1) * self.sh
            on = k <= cur
            if on:
                d.line([(x, y), (x + self.sw, y)], fill=GOLD, width=8)
            spr = self.ls_on[k] if on else self.ls_off[k]
            paste_scaled(c, spr, x + self.sw / 2, y + 36, 1, 1)
        d = ImageDraw.Draw(c)
        # Figur hüpft
        hk = int((t - self.hop0) // self.hopi) if t >= self.hop0 else -1
        fx, fy = self.pos(-1)
        if hk >= 0:
            hk = min(hk, self.n - 1)
            p = clamp((t - self.hop0 - hk * self.hopi) / self.hopd)
            a, b = self.pos(hk - 1), self.pos(hk)
            fx, fy = lerp(a[0], b[0], p), lerp(a[1], b[1], p) - math.sin(math.pi * p) * 70
        if t > self.tend:
            e = ease_out_cubic((t - self.tend) / 0.5)
            tx, ty = self.pos(self.n - 1)
            paste_scaled(c, self.burst, tx, ty - 250, 0.5 + 0.7 * e, 1 - 0.3 * e)
            coin(c, tx, ty - 260, 46, ease_out_back((t - self.tend) / 0.35))
            d = ImageDraw.Draw(c)
            fy -= abs(math.sin((t - self.tend) * 7)) * 22 * math.exp(-(t - self.tend) * 1.2)
        figure(d, fx, fy, 0.72, 0, WHITE)


class TreeScene(Scene):
    def setup(self):
        rnd = random.Random(3)
        self.sx = 620
        self.branches, self.tips = [], []

        def grow(x, y, ang, ln, k):
            x2, y2 = x + math.cos(ang) * ln, y + math.sin(ang) * ln
            self.branches.append((x, y, x2, y2, k))
            if k >= 4:
                self.tips.append((x2, y2, k))
                return
            for sgn in (-1, 1):
                grow(x2, y2, ang + sgn * math.radians(rnd.uniform(20, 34)), ln * 0.74, k + 1)

        grow(self.sx, GROUND, -math.pi / 2, 165, 0)
        self.levels = 5
        self.seed = fit_label(self.d.get("seed", "HEUTE"), 300, 36, WHITE, glow=False)
        self.hand = (410, GROUND - 120)
        self.drops = [0.4 + i * 0.22 for i in range(8)]
        for td in self.drops:
            self.sfx(td + 0.45, "drop", 0.45)
        self.g0, self.g1 = 1.6, 4.2
        self.sfx(self.g0, "grow", 0.5)
        tips = sorted(self.tips, key=lambda p: p[1])
        self.coin_tips = tips[::max(1, len(tips) // 7)][:7]
        self.ct = [4.3 + i * 0.2 for i in range(len(self.coin_tips))]
        for tc in self.ct:
            self.sfx(tc, "clink", 0.5)

    def scene(self, c, d, t):
        figure(d, 300, GROUND, 1, 0.05, WHITE, hands=[(1, self.hand)])
        for td in self.drops:
            p = (t - td) / 0.45
            if 0 < p < 1:
                x = lerp(self.hand[0] + 10, self.sx, p)
                y = lerp(self.hand[1], GROUND - 8, p * p) - math.sin(math.pi * p) * 50
                d.ellipse((x - 9, y - 13, x + 9, y + 9), fill=BLUE)
        g = smooth((t - self.g0) / (self.g1 - self.g0))
        if g <= 0:
            d.ellipse((self.sx - 22, GROUND - 16, self.sx + 22, GROUND + 4), fill=dim(GREEN, 0.9))
        for x, y, x2, y2, k in self.branches:
            f = clamp(g * self.levels - k)
            if f <= 0:
                continue
            wdt = max(3, int(15 * 0.7 ** k))
            d.line([(x, y), (lerp(x, x2, f), lerp(y, y2, f))], fill=WHITE, width=wdt)
        lg = clamp((g - 0.75) / 0.25)
        if lg > 0:
            for x, y, _ in self.tips:
                r = 24 * ease_out_back(lg)
                d.ellipse((x - r, y - r, x + r, y + r), fill=GREEN)
        for (x, y, _), tc in zip(self.coin_tips, self.ct):
            s = ease_out_back((t - tc) / 0.3)
            if s > 0:
                coin(c, x, y + 4, 22, s)
        a = 1 - smooth((t - self.g0) / 0.8) * 0.6
        paste_scaled(c, self.seed, self.sx, GROUND + 45, 1, a)


class CrowdScene(Scene):
    def setup(self):
        D = self.dur
        self.cl = label(self.d.get("crowd", "ALLE"), 44, (150, 150, 165), glow=False)
        self.yl = label(self.d.get("you", "DU"), 54, GOLD)
        self.xs = [215 + i * 130 for i in range(6)]
        self.w = (0.4, D - 0.3)
        for st in step_times(*self.w, 9):
            self.sfx(st, "step", 0.35)

    def scene(self, c, d, t):
        p = smooth((t - self.w[0]) / (self.w[1] - self.w[0])) * 0.6 + 0.4 * clamp((t - self.w[0]) / (self.w[1] - self.w[0]))
        wx = lerp(-70, 1150, p)
        mv = self.w[0] < t < self.w[1]
        d.line([(0, GROUND), (max(0, wx), GROUND)], fill=GOLD, width=5)
        gray = (95, 95, 112)
        for x in self.xs:
            look = smooth(1 - abs(wx - x) / 160)
            figure(d, x, GROUND, 0.66, 0.0, gray, body_h=0.72, head=(14 * (1 - look), 20 * (1 - look)))
            pa = 1 - look
            d.rectangle((x + 30, GROUND - 70, x + 46, GROUND - 46), fill=dim(BLUE, 0.4 + 0.6 * pa))
        figure(d, wx, GROUND, 1.0, 0.06 if mv else 0, WHITE, bob=walk_bob(t, mv, 1, 9))
        a = ease_out_back((t - 0.3) / 0.35)
        if a > 0:
            paste_scaled(c, self.cl, 540, GROUND - 230, a, clamp(a * 2) * 0.9)
        if 0 < wx < W:
            paste_scaled(c, self.yl, clamp(wx, self.yl.width / 2 + 10, W - self.yl.width / 2 - 10), GROUND - 300, 1, clamp((t - 0.4) * 3))


class SeesawScene(Scene):
    def setup(self):
        dd = self.d
        self.mode = dd.get("mode", "bad")
        self.lc, self.rc = col(dd.get("left_color", "green")), col(dd.get("right_color", "red"))
        self.ll = fit_label(dd["left"], 210, 32, WHITE, glow=False)
        self.rl = fit_label(dd["right"], 210, 32, WHITE, glow=False)
        self.P = (540, GROUND - 120)
        if self.mode == "bad":
            self.wl0, self.wr0, self.side = 1.0, 1.0, 1
            self.drops = [1.0 + 0.6 * i for i in range(4)]
        else:
            self.wl0, self.wr0, self.side = 1.0, 2.4, -1
            self.drops = [0.9 + 0.45 * i for i in range(7)]
        self.fall = 0.45
        # Feder-Simulation des Neigungswinkels
        n = int(self.dur * FPS) + 2
        th, v = self.target(0), 0.0
        self.th = []
        for i in range(n):
            tt = i / FPS
            a = 60 * (self.target(tt) - th) - 7 * v
            v += a / FPS
            th += v / FPS
            self.th.append(th)
        self.flip_t = None
        for i in range(1, n):
            if self.th[i - 1] > 0 >= self.th[i] and self.mode != "bad":
                self.flip_t = i / FPS
                break
        for td in self.drops:
            self.sfx(td + self.fall, "thud", 0.45)
            self.sfx(td + self.fall, "clink", 0.4)
            self.sfx(td + self.fall + 0.08, "creak", 0.25)
        if self.flip_t:
            self.sfx(self.flip_t, "ding", 0.6)

    def weights(self, t):
        k = sum(1 for td in self.drops if t >= td + self.fall)
        if self.side > 0:
            return self.wl0, self.wr0 + 0.5 * k
        return self.wl0 + 0.5 * k, self.wr0

    def target(self, t):
        wl, wr = self.weights(t)
        return clamp((wr - wl) * 0.11, -0.27, 0.27)

    def box(self, c, d, th, dist, wgt, color, spr):
        P = self.P
        ca, sa = math.cos(th), math.sin(th)
        h = 60 + 32 * wgt
        w = 220
        cx, cy = P[0] + ca * dist, P[1] + sa * dist
        nx, ny = sa, -ca  # Normale nach oben
        pts = []
        for ox, oy in ((-w / 2, 0), (w / 2, 0), (w / 2, h), (-w / 2, h)):
            pts.append((cx + ca * ox + nx * (oy + 5), cy + sa * ox + ny * (oy + 5)))
        d.polygon(pts, fill=dim(color, 0.33), outline=color, width=5)
        mx, my = cx + nx * (h / 2 + 5), cy + ny * (h / 2 + 5)
        paste_scaled(c, spr, mx, my, 1, 1)
        return (cx + nx * (h + 5), cy + ny * (h + 5))

    def scene(self, c, d, t):
        P = self.P
        th = self.th[min(len(self.th) - 1, int(t * FPS))]
        d.polygon([(P[0], P[1] - 8), (P[0] - 75, GROUND), (P[0] + 75, GROUND)], fill=WHITE)
        ca, sa = math.cos(th), math.sin(th)
        L = 400
        d.line([(P[0] - ca * L, P[1] - sa * L), (P[0] + ca * L, P[1] + sa * L)], fill=WHITE, width=10)
        wl, wr = self.weights(t)
        lt = self.box(c, d, th, -270, wl, self.lc, self.ll)
        d = ImageDraw.Draw(c)
        rt = self.box(c, d, th, 270, wr, self.rc, self.rl)
        for td in self.drops:
            p = (t - td) / self.fall
            if 0 < p < 1:
                tx, ty = rt if self.side > 0 else lt
                coin(c, tx, lerp(560, ty - 24, p * p), 26)
        if self.flip_t and t > self.flip_t:
            e = ease_out_cubic((t - self.flip_t) / 0.6)
            coin(c, lt[0], lt[1] - 120 - 30 * e, 34, ease_out_back((t - self.flip_t) / 0.35))


class CoinsScene(Scene):
    def setup(self):
        self.stacks = self.d["stacks"]
        n = len(self.stacks)
        self.xs = [200 + i * (680 / max(1, n - 1)) for i in range(n)]
        self.ts, self.iv, self.endt = [], [], []
        for i, s in enumerate(self.stacks):
            t0 = 0.5 + i * 1.05
            iv = min(0.12, 0.85 / s["coins"])
            self.ts.append(t0)
            self.iv.append(iv)
            self.endt.append(t0 + s["coins"] * iv + 0.1)
            for k in range(s["coins"]):
                self.sfx(t0 + k * iv, "clink", 0.22 if k % 2 else 0.3)
            self.sfx(self.endt[-1], "cash" if i == n - 1 else "pop_big", 0.6 if i == n - 1 else 0.4)
        self.lab = [fit_label(s["label"], 200, 34, WHITE, glow=False) for s in self.stacks]
        self.val = [fit_label(s["value"], 220, 42, GOLD) for s in self.stacks]
        self.cap_y = GROUND + 140

    def scene(self, c, d, t):
        for i, s in enumerate(self.stacks):
            x = self.xs[i]
            paste_scaled(c, self.lab[i], x, GROUND + 48, 1, 1)
            top = GROUND
            for k in range(s["coins"]):
                ta = self.ts[i] + k * self.iv[i]
                if t < ta:
                    break
                p = ease_out_cubic((t - ta) / 0.15)
                y = GROUND - 26 - k * 22 - (1 - p) * 60
                d.ellipse((x - 72, y - 12, x + 72, y + 26), fill=(190, 125, 25))
                d.ellipse((x - 72, y - 20, x + 72, y + 18), fill=GOLD)
                d.ellipse((x - 50, y - 12, x + 50, y + 10), outline=(215, 150, 35), width=3)
                top = y - 20
            a = ease_out_back((t - self.endt[i]) / 0.35)
            if a > 0:
                paste_scaled(c, self.val[i], x, top - 45, a, clamp(a * 2))


SCENES = dict(hook=HookScene, cta=CtaScene, tug=TugScene, fork=ForkScene, load=LoadScene, wall=WallScene,
              stairs=StairsScene, tree=TreeScene, crowd=CrowdScene, seesaw=SeesawScene, coins=CoinsScene)


# ----------------------------------------------------------------- background + glow
class Background:
    def __init__(self, seed, tint):
        arr = np.zeros((H, W, 3), np.float32)
        ys, xs = np.mgrid[0:H, 0:W]
        for (cx, cy, rad, colr, k) in ((200, 500, 900, tint[0], 0.10), (900, 1500, 1000, tint[1], 0.09)):
            r = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / rad
            arr += (np.clip(1 - r, 0, 1) ** 2)[..., None] * np.array(colr, np.float32) * k
        self.base = Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert("RGBA")
        rnd = random.Random(seed)
        self.stars = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(0.8, 2.3), rnd.uniform(0, 6.3),
                       rnd.uniform(0.5, 2.0), rnd.random() < 0.2) for _ in range(110)]

    def frame(self, t):
        img = self.base.copy()
        d = ImageDraw.Draw(img)
        for x, y, s, ph, sp, cross in self.stars:
            b = int(50 + 90 * (0.5 + 0.5 * math.sin(t * sp + ph)))
            cc = (b, b, b + 10)
            y2 = (y - t * 4 * sp) % H
            if cross:
                d.line([(x - 4, y2), (x + 4, y2)], fill=cc, width=1)
                d.line([(x, y2 - 4), (x, y2 + 4)], fill=cc, width=1)
            else:
                d.ellipse((x - s, y2 - s, x + s, y2 + s), fill=cc)
        return img


def apply_glow(img):
    rgb = img.convert("RGB")
    arr = np.asarray(rgb, np.float32)
    s1 = rgb.resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BILINEAR)
    s2 = rgb.resize((W // 12, H // 12), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4)).resize((W, H), Image.BILINEAR)
    return arr + np.asarray(s1, np.float32) * 0.5 + np.asarray(s2, np.float32) * 0.38


# ----------------------------------------------------------------- audio
def extra_sfx(lib, rng):
    def nz(n):
        return rng.normal(0, 1, n)

    n = int(0.12 * SR)
    lib["step"] = (sine_sweep(95, 50, 0.12) * env_exp(n, 0.035) + lowpass(nz(n), 500) * env_exp(n, 0.02) * 0.8) * 0.9
    n = int(0.45 * SR)
    lib["thud"] = np.tanh((sine_sweep(120, 38, 0.45) * env_exp(n, 0.12) * 1.4 + lowpass(nz(n), 700) * env_exp(n, 0.05) * 2) * 1.2)
    n = int(0.25 * SR)
    src = nz(n)
    hp = src - lowpass(src, 2500)
    cr = hp * env_exp(n, 0.025) * 1.2
    cr[int(0.035 * SR):] += hp[: n - int(0.035 * SR)] * env_exp(n - int(0.035 * SR), 0.02) * 0.8
    lib["crack"] = cr
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    lib["clink"] = (np.sin(2 * np.pi * 2960 * t) + 0.7 * np.sin(2 * np.pi * 4420 * t) + 0.3 * np.sin(2 * np.pi * 6100 * t)) * env_exp(n, 0.07) * 0.45
    n = int(0.14 * SR)
    lib["drop"] = sine_sweep(500, 1500, 0.14) * env_exp(n, 0.05) * 0.8
    n = int(0.55 * SR)
    t = np.arange(n) / SR
    f = 62 + 9 * np.sin(2 * np.pi * 3 * t)
    saw = 2 * ((np.cumsum(f) / SR) % 1) - 1
    lib["creak"] = lowpass(saw, 700) * np.sin(np.pi * t / t[-1]) ** 2 * 0.9
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    lib["grow"] = (sine_sweep(300, 900, 1.6) * 0.5 + sine_sweep(450, 1350, 1.6) * 0.3) * np.sin(np.pi * t / t[-1]) ** 2 * 0.5
    for i, m in enumerate([69, 72, 74, 76, 79, 81, 84, 86]):
        n = int(0.6 * SR)
        t = np.arange(n) / SR
        fr = midi(m)
        lib[f"note{i}"] = (np.sin(2 * np.pi * fr * t) + 0.25 * np.sin(2 * np.pi * 4 * fr * t) * env_exp(n, 0.03)) * env_exp(n, 0.18) * 0.6
    return lib


def build_music_dark(dur, rng):
    n = int(dur * SR)
    out = np.zeros(n)
    bpm = 84
    beat = 60 / bpm
    bar = beat * 4
    chords = [[57, 60, 64], [53, 57, 60, 64], [48, 52, 55, 60], [55, 59, 62]]  # Am Fmaj7 C G
    t_all = np.arange(n) / SR
    pad = np.zeros(n)
    for b in range(int(math.ceil(dur / bar))):
        s0, s1 = int(b * bar * SR), min(n, int((b + 1) * bar * SR))
        tt = t_all[s0:s1] - b * bar
        seg = np.zeros(s1 - s0)
        for m in chords[b % 4]:
            f = midi(m - 12)
            seg += np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * f * 2.003 * tt) + 0.15 * np.sin(2 * np.pi * f * 3 * tt)
        e = np.minimum(1, tt / 0.9) * np.minimum(1, (bar - tt) / 0.6)
        pad[s0:s1] += seg * e
    out += lowpass(pad, 900) * 0.05

    def add(sig, t0, g):
        i = int(t0 * SR)
        if i >= n:
            return
        j = min(n, i + len(sig))
        out[i:j] += sig[: j - i] * g

    # Arpeggio (Pluck) mit Echo
    arp = np.zeros(n)
    pn = int(0.5 * SR)
    pt = np.arange(pn) / SR
    for k in range(int(dur / (beat / 2))):
        tb = k * beat / 2
        b = int(tb // bar)
        ch = chords[b % 4]
        m = ch[[0, 1, 2, 1, len(ch) - 1, 2, 1, 2][k % 8] % len(ch)] + 12
        f = midi(m)
        sig = (np.sin(2 * np.pi * f * pt) + 0.2 * np.sin(2 * np.pi * 2 * f * pt)) * env_exp(pn, 0.12)
        i = int(tb * SR)
        j = min(n, i + pn)
        arp[i:j] += sig[: j - i]
    dl = int(beat * 0.75 * SR)
    echo = np.zeros(n)
    echo[dl:] = arp[:-dl] * 0.35
    out += (arp + echo) * 0.045
    kick_n = int(0.4 * SR)
    kick = sine_sweep(140, 42, 0.4) * env_exp(kick_n, 0.14)
    hn = int(0.04 * SR)
    hs = rng.normal(0, 1, hn)
    hat = (hs - lowpass(hs, 7000)) * env_exp(hn, 0.01)
    sn = int(0.3 * SR)
    ss = rng.normal(0, 1, sn)
    clap = (ss - lowpass(ss, 1500)) * env_exp(sn, 0.07)
    for k in range(int(dur / beat) + 1):
        tb = k * beat
        if tb < bar * 2:
            continue
        if k % 4 in (0,) or k % 8 == 5:
            add(kick, tb, 0.45)
        if k % 4 == 2:
            add(clap, tb, 0.09)
        add(hat, tb + beat / 2, 0.05)
    fi, fo = int(0.3 * SR), int(1.5 * SR)
    out[:fi] *= np.linspace(0, 1, fi)
    out[-fo:] *= np.linspace(1, 0, fo)
    return out


def build_audio(scenes, dur, path, seed):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    music = build_music_dark(dur, rng)
    lib = extra_sfx(build_sfx(rng), rng)
    fx = np.zeros(n)
    for sc in scenes:
        for t, name, g in sc.ev:
            i = int((sc.start + t) * SR)
            sig = lib[name]
            j = min(n, i + len(sig))
            if 0 <= i < n:
                fx[i:j] += sig[: j - i] * g
    k = int(0.08 * SR)
    envf = np.convolve(np.abs(fx), np.ones(k) / k, mode="same")
    duck = 1 - 0.4 * np.clip(envf * 4, 0, 1)
    mix = music * duck + fx * 0.6
    mix = np.tanh(mix * 1.6) / np.tanh(1.6)
    mix = mix / max(1e-6, np.max(np.abs(mix))) * 0.92
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(np.stack([pcm, pcm], axis=1).tobytes())


# ----------------------------------------------------------------- render
def build_scenes(data):
    scenes, t = [], 0.0
    for sd in data["scenes"]:
        sc = SCENES[sd["type"]](sd, t)
        scenes.append(sc)
        t += sc.dur
    if t < MIN_DURATION:
        scenes[-1].dur += MIN_DURATION - t
        t = MIN_DURATION
    return scenes, t


def render_frame(bg, scenes, si, gt, dur):
    sc = scenes[si]
    lt = gt - sc.start
    c = bg.frame(gt)
    sc.draw(c, lt)
    arr = apply_glow(c)
    fade = 1.0
    if si > 0:
        fade *= smooth(lt / 0.25)
    if si < len(scenes) - 1:
        fade *= smooth((sc.dur - lt) / 0.25)
    else:
        fade *= smooth((dur - gt) / 0.8)
    return np.clip(arr * fade, 0, 255).astype(np.uint8)


def render(script_path):
    with open(script_path, encoding="utf-8") as f:
        data = json.load(f)
    name = os.path.splitext(os.path.basename(script_path))[0]
    seed = sum(map(ord, name))
    random.seed(seed)
    scenes, dur = build_scenes(data)
    nframes = int(round(dur * FPS))
    os.makedirs(OUT_DIR, exist_ok=True)
    wav = os.path.join(OUT_DIR, f".{name}.wav")
    mp4 = os.path.join(OUT_DIR, f"{name}.mp4")
    build_audio(scenes, dur, wav, seed)
    tint = [col(c) for c in data.get("tint", ["gold", "purple"])]
    bg = Background(seed, tint)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
           "-movflags", "+faststart", "-t", f"{dur:.3f}", mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    si = 0
    cover_f = int(scenes[0].dur * 0.85 * FPS)
    for fi in range(nframes):
        gt = fi / FPS
        while si < len(scenes) - 1 and gt >= scenes[si].start + scenes[si].dur:
            si += 1
        arr = render_frame(bg, scenes, si, gt, dur)
        if fi == cover_f:
            Image.fromarray(arr).save(os.path.join(OUT_DIR, f"{name}_cover.png"))
        proc.stdin.write(arr.tobytes())
        if fi % 300 == 0:
            print(f"[{name}] {fi}/{nframes}", flush=True)
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    with open(os.path.join(OUT_DIR, f"{name}_caption.txt"), "w", encoding="utf-8") as f:
        f.write(data.get("caption", data.get("title", "")) + "\n")
    print(f"[{name}] fertig: {mp4} ({dur:.1f} s)", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for p in sys.argv[1:]:
        render(p)
