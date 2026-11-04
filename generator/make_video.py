#!/usr/bin/env python3
"""
TikTok-Video-Generator (Geld & Mindset)
=======================================
Erzeugt 1080x1920 Hochkant-Videos (30 fps, > 61 s) aus einem JSON-Skript:
animierte Typo, farbige Highlights, Zähler-Animationen, Vergleichs-Karten,
selbst synthetisierte Hintergrundmusik + Soundeffekte (lizenzfrei, da generiert).

Nutzung:
    python3 generator/make_video.py skripte/01_geld_regeln.json
    python3 generator/make_video.py skripte/*.json            # alle

Ausgabe: videos/<name>.mp4  +  videos/<name>_cover.png  +  videos/<name>_caption.txt

Markup im Text:  *wort = Themenfarbe   +wort = Grün   !wort = Rot
"""
import json
import math
import re
import os
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(ROOT, "fonts")
OUT_DIR = os.path.join(ROOT, "videos")

W, H, FPS, SR = 1080, 1920, 30, 44100
MIN_DURATION = 61.5  # sicher über 1 Minute für das Creator-Rewards-Programm

F_BLACK = os.path.join(FONT_DIR, "InterDisplay-Black.otf")
F_BOLD = os.path.join(FONT_DIR, "InterDisplay-Bold.otf")
F_SEMI = os.path.join(FONT_DIR, "Inter-SemiBold.otf")

GREEN = (61, 235, 130)
RED = (255, 77, 109)
WHITE = (255, 255, 255)
SOFT = (215, 218, 235)

THEMES = {
    "gold": dict(top=(9, 10, 28), bottom=(40, 16, 58), accent=(255, 200, 61), blob2=(255, 120, 60)),
    "green": dict(top=(4, 18, 22), bottom=(8, 44, 54), accent=(61, 255, 160), blob2=(40, 160, 255)),
    "purple": dict(top=(16, 6, 36), bottom=(58, 12, 72), accent=(196, 128, 255), blob2=(255, 90, 190)),
}

_font_cache = {}


def font(path, size):
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]


# ----------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out_cubic(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_out_back(x, s=1.9):
    x = clamp(x)
    x -= 1
    return x * x * ((s + 1) * x + s) + 1


def ease_out_expo(x):
    x = clamp(x)
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


# ----------------------------------------------------------------- text helpers
def split_words(text):
    """Trennt an Leerzeichen, hält aber '1 %' / '200 €' zusammen (geschütztes Leerzeichen)."""
    text = re.sub(r"(\d) ([%€x])", "\\1\u00a0\\2", text)
    return [w for w in text.split(" ") if w]


def parse_words(text, theme):
    """'Bezahl dich *zuerst' -> [(wort, farbe, highlight?)]"""
    out = []
    for w in split_words(text):
        col, hl = WHITE, False
        if w[0] == "*" and len(w) > 1:
            col, hl, w = theme["accent"], True, w[1:]
        elif w[0] == "+" and len(w) > 1:
            col, hl, w = GREEN, True, w[1:]
        elif w[0] == "!" and len(w) > 1:
            col, hl, w = RED, True, w[1:]
        out.append((w, col, hl))
    return out


def wrap(words, fnt, max_w):
    lines, cur, cur_w = [], [], 0
    space = fnt.getlength(" ")
    for item in words:
        ww = fnt.getlength(item[0])
        add = ww if not cur else cur_w + space + ww
        if cur and add > max_w:
            lines.append(cur)
            cur, cur_w = [item], ww
        else:
            cur.append(item)
            cur_w = add
    if cur:
        lines.append(cur)
    return lines


def text_sprite(text, fnt, fill, glow=False, shadow=True, pad=40):
    """Rendert Text mit Schatten (und optional Glow) als RGBA-Sprite."""
    l, t, r, b = fnt.getbbox(text)
    w, h = int(r - l) + pad * 2, int(b - t) + pad * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    org = (pad - l, pad - t)
    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((org[0], org[1] + 7), text, font=fnt, fill=(0, 0, 0, 190))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(9)))
    if glow:
        gl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(gl).text(org, text, font=fnt, fill=fill + (150,))
        img = Image.alpha_composite(img, gl.filter(ImageFilter.GaussianBlur(16)))
    ImageDraw.Draw(img).text(org, text, font=fnt, fill=fill + (255,))
    # Offset, um vom Sprite zurück auf die Text-Baseline-Box zu kommen
    return img, (pad, pad)


def with_alpha(img, f):
    if f >= 0.999:
        return img
    img = img.copy()
    a = img.getchannel("A").point(lambda v: int(v * f))
    img.putalpha(a)
    return img


def paste_scaled(layer, sprite, cx, cy, scale=1.0, alpha=1.0):
    """Sprite zentriert bei (cx, cy) mit Skalierung und Alpha einfügen."""
    if alpha <= 0.01 or scale <= 0.01:
        return
    spr = sprite
    if abs(scale - 1) > 0.005:
        nw, nh = max(1, int(spr.width * scale)), max(1, int(spr.height * scale))
        spr = spr.resize((nw, nh), Image.BILINEAR)
    spr = with_alpha(spr, alpha)
    x, y = int(cx - spr.width / 2), int(cy - spr.height / 2)
    layer.alpha_composite(spr, (max(0, x), max(0, y)),
                          (max(0, -x), max(0, -y), spr.width, spr.height))


def fmt_number(v, decimals=0):
    s = f"{v:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ----------------------------------------------------------------- building blocks
class WordBlock:
    """Mehrzeiliger Text, dessen Wörter einzeln 'aufpoppen'."""

    def __init__(self, text, theme, size, max_w=880, interval=0.09, start=0.2):
        self.fnt = font(F_BLACK, size)
        self.lines = wrap(parse_words(text, theme), self.fnt, max_w)
        self.line_h = int(size * 1.14)
        self.height = self.line_h * len(self.lines)
        self.start, self.interval = start, interval
        self.items = []  # (sprite, cx, cy_rel, t_appear, highlight)
        space = self.fnt.getlength(" ")
        asc = self.fnt.getbbox("Hg")[1]
        idx = 0
        for li, line in enumerate(self.lines):
            widths = [self.fnt.getlength(w) for w, _, _ in line]
            total = sum(widths) + space * (len(line) - 1)
            x = W / 2 - total / 2
            for (w, col, hl), ww in zip(line, widths):
                spr, _ = text_sprite(w, self.fnt, col, glow=hl)
                bb = self.fnt.getbbox(w)
                cy = li * self.line_h + asc + (bb[3] - bb[1]) / 2 + (bb[1] - asc)
                self.items.append([spr, x + bb[0] + (bb[2] - bb[0]) / 2, cy, start + idx * interval, hl])
                x += ww + space
                idx += 1
        self.end = start + idx * interval + 0.2

    def times(self):
        return [(it[3], it[4]) for it in self.items]

    def draw(self, layer, t, top):
        for spr, cx, cy, ta, hl in self.items:
            p = (t - ta) / 0.24
            if p <= 0:
                continue
            sc = (0.45 + 0.55 * ease_out_back(p)) if hl else (0.7 + 0.3 * ease_out_back(p, 1.4))
            paste_scaled(layer, spr, cx, top + cy, sc, clamp(p * 2.5))


class Paragraph:
    """Ruhiger Untertitel-Absatz (fadet rein)."""

    def __init__(self, text, size=50, color=SOFT, max_w=860, fnt_path=F_SEMI):
        fnt = font(fnt_path, size)
        lines = wrap([(w, color, False) for w in split_words(text)], fnt, max_w)
        self.line_h = int(size * 1.32)
        self.height = self.line_h * len(lines)
        self.sprites = [text_sprite(" ".join(w for w, _, _ in ln), fnt, color)[0] for ln in lines]

    def draw(self, layer, top, alpha=1.0, dy=0):
        for i, spr in enumerate(self.sprites):
            paste_scaled(layer, spr, W / 2, top + i * self.line_h + self.line_h / 2 + dy, 1.0, alpha)


def pill(text, color, filled=True, size=40, text_color=None):
    fnt = font(F_BLACK, size)
    l, t, r, b = fnt.getbbox(text)
    tw, th = r - l, b - t
    pw, ph = int(tw + size * 1.4), int(th + size * 0.95)
    pad = 30
    img = Image.new("RGBA", (pw + pad * 2, ph + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    box = (pad, pad, pad + pw, pad + ph)
    if filled:
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).rounded_rectangle(box, ph // 2, fill=color + (140,))
        img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(14)))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(box, ph // 2, fill=color + (255,))
        tc = text_color or (12, 12, 24)
    else:
        d.rounded_rectangle(box, ph // 2, fill=(255, 255, 255, 18), outline=color + (230,), width=3)
        tc = text_color or WHITE
    d.text((pad + (pw - tw) / 2 - l, pad + (ph - th) / 2 - t), text, font=fnt, fill=tc + (255,))
    return img


def card(width, height, color, header, fill_alpha=34):
    pad = 40
    img = Image.new("RGBA", (width + pad * 2, height + pad * 2), (0, 0, 0, 0))
    box = (pad, pad, pad + width, pad + height)
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle(box, 38, outline=color + (160,), width=10)
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, 38, fill=(8, 8, 16, 170), outline=color + (255,), width=4)
    d.rounded_rectangle(box, 38, fill=color + (fill_alpha,))
    fnt = font(F_BLACK, 34)
    d.text((pad + 46, pad + 34), header, font=fnt, fill=color + (255,))
    return img


# ----------------------------------------------------------------- scenes
class Scene:
    def __init__(self, data, theme, start):
        self.d, self.theme, self.start, self.dur = data, theme, start, float(data["dur"])
        self.label = pill(data["label"], theme["accent"]) if data.get("label") else None
        self.events = []  # (zeit_lokal, sfx, gain)

    def sfx(self, t, name, gain=1.0):
        self.events.append((t, name, gain))

    def draw_label(self, layer, t, y):
        if self.label is not None:
            p = (t - 0.02) / 0.3
            if p > 0:
                paste_scaled(layer, self.label, W / 2, y, 0.6 + 0.4 * ease_out_back(p), clamp(p * 3))


class TextScene(Scene):
    def __init__(self, data, theme, start, size=104, hook=False, cta=False):
        super().__init__(data, theme, start)
        self.hook, self.cta = hook, cta
        st = 0.35 if self.label else 0.18
        self.words = WordBlock(data["text"], theme, size, interval=0.11 if hook else 0.09, start=st)
        self.sub = Paragraph(data["sub"], size=54 if hook else 50) if data.get("sub") else None
        self.sub_t = self.words.end + 0.25
        lab_h = 120 if self.label else 0
        sub_h = (self.sub.height + 50) if self.sub else 0
        btn_h = 190 if cta else 0
        total = lab_h + self.words.height + sub_h + btn_h
        top = 860 - total / 2
        self.label_y = top + 40
        self.words_top = top + lab_h
        self.sub_top = self.words_top + self.words.height + 50
        self.btn_y = self.sub_top + (self.sub.height if self.sub else 0) + 140
        if cta:
            self.btn = pill("+  FOLGEN", RED, size=56, text_color=WHITE)
            self.btn_t = self.sub_t + 0.5

        # Sounds
        self.sfx(0.0, "impact" if hook else "whoosh", 1.0 if hook else 0.55)
        if self.label:
            self.sfx(0.02, "pop_big", 0.6)
        for ta, hl in self.words.times():
            self.sfx(ta, "pop_big" if hl else "pop", 0.75 if hl else 0.32)
        if any(hl for _, hl in self.words.times()):
            last_hl = max(ta for ta, hl in self.words.times() if hl)
            self.sfx(last_hl + 0.05, "ding" if not hook else "riser_hit", 0.45)
        if self.sub:
            self.sfx(self.sub_t, "swish", 0.3)
        if cta:
            self.sfx(self.btn_t, "cash", 0.6)

    def draw(self, layer, t):
        self.draw_label(layer, t, self.label_y)
        self.words.draw(layer, t, self.words_top)
        if self.sub:
            p = ease_out_cubic((t - self.sub_t) / 0.4)
            if p > 0:
                self.sub.draw(layer, self.sub_top, p, dy=(1 - p) * 30)
        if self.cta:
            p = (t - self.btn_t) / 0.35
            if p > 0:
                pulse = 1 + 0.045 * math.sin((t - self.btn_t) * 2 * math.pi * 1.2)
                paste_scaled(layer, self.btn, W / 2, self.btn_y, (0.5 + 0.5 * ease_out_back(p)) * pulse, clamp(p * 3))

    def shake(self, t):
        if self.hook and t < 0.4:
            k = (0.4 - t) / 0.4 * 18
            return random.uniform(-k, k), random.uniform(-k, k)
        return 0, 0

    def flash(self, t):
        return clamp(1 - t / 0.18) * 0.55 if self.hook else 0


class CounterScene(Scene):
    def __init__(self, data, theme, start):
        super().__init__(data, theme, start)
        self.neg = data.get("negative", False)
        self.col = RED if self.neg else theme["accent"]
        self.pre = Paragraph(data["pre"], size=54, color=WHITE, fnt_path=F_BOLD)
        self.sub = Paragraph(data["sub"], size=50) if data.get("sub") else None
        self.dec = int(data.get("decimals", 0))
        self.v0, self.v1 = float(data["from"]), float(data["to"])
        self.suffix = data.get("suffix", "")
        self.t0, self.t1 = 0.7, 3.3
        final = fmt_number(self.v1, self.dec) + self.suffix
        size = 170
        while font(F_BLACK, size).getlength(final) > 900:
            size -= 6
        self.num_font = font(F_BLACK, size)
        self.num_cache = {}
        self.label_y = 380
        self.pre_top = 480
        self.num_y = self.pre_top + self.pre.height + 150
        self.chart_top, self.chart_bot = self.num_y + 150, self.num_y + 430
        self.sub_top = self.chart_bot + 70
        self.sub_t = self.t1 + 0.35

        self.sfx(0.0, "whoosh", 0.55)
        if self.label:
            self.sfx(0.02, "pop_big", 0.6)
        self.sfx(0.25, "swish", 0.3)
        n = 22
        for i in range(n):
            tt = self.t0 + (self.t1 - self.t0) * (1 - (1 - i / n) ** 2.2)
            self.sfx(tt, "tick", 0.32)
        self.sfx(self.t1, "fail" if self.neg else "cash", 0.85)
        if self.sub:
            self.sfx(self.sub_t, "swish", 0.3)

    def value(self, t):
        p = ease_out_expo((t - self.t0) / (self.t1 - self.t0)) if t > self.t0 else 0
        return self.v0 + (self.v1 - self.v0) * p, p

    def draw(self, layer, t):
        self.draw_label(layer, t, self.label_y)
        p = ease_out_cubic((t - 0.25) / 0.4)
        if p > 0:
            self.pre.draw(layer, self.pre_top, p, dy=(1 - p) * 30)
        v, prog = self.value(t)
        if t > self.t0 - 0.3:
            txt = fmt_number(v, self.dec) + self.suffix
            spr = self.num_cache.get(txt)
            if spr is None:
                spr = text_sprite(txt, self.num_font, self.col, glow=True)[0]
                if len(self.num_cache) < 400:
                    self.num_cache[txt] = spr
            bump = 1 + 0.12 * clamp(1 - (t - self.t1) / 0.3) if t >= self.t1 else 1
            appear = ease_out_back((t - (self.t0 - 0.3)) / 0.3)
            paste_scaled(layer, spr, W / 2, self.num_y, appear * bump, clamp(appear * 2))
            self.draw_chart(layer, prog)
        if self.sub:
            p = ease_out_cubic((t - self.sub_t) / 0.4)
            if p > 0:
                self.sub.draw(layer, self.sub_top, p, dy=(1 - p) * 30)

    def draw_chart(self, layer, prog):
        x0, x1 = 130, W - 130
        y0, y1 = self.chart_bot, self.chart_top
        d = ImageDraw.Draw(layer)
        d.line([(x0, y0), (x1, y0)], fill=(255, 255, 255, 60), width=3)
        if prog <= 0.01:
            return
        k, n = 3.2, 60
        pts = []
        for i in range(int(n * prog) + 1):
            x = i / n
            g = (math.exp(k * x) - 1) / (math.exp(k) - 1)
            yv = (1 - g) if self.neg else g
            if self.neg:
                yv = math.exp(-k * x)
            pts.append((x0 + (x1 - x0) * x, y0 - (y0 - y1) * yv))
        if len(pts) > 1:
            poly = pts + [(pts[-1][0], y0), (pts[0][0], y0)]
            d.polygon(poly, fill=self.col + (40,))
            d.line(pts, fill=self.col + (255,), width=9, joint="curve")
            ex, ey = pts[-1]
            d.ellipse((ex - 14, ey - 14, ex + 14, ey + 14), fill=WHITE + (255,), outline=self.col + (255,), width=5)


class VersusScene(Scene):
    def __init__(self, data, theme, start):
        super().__init__(data, theme, start)
        fnt = font(F_BLACK, 70)
        cw = 900
        self.bad_lines = wrap([(w, WHITE, False) for w in split_words(data["bad"])], fnt, cw - 100)
        self.good_lines = wrap([(w, WHITE, False) for w in split_words(data["good"])], fnt, cw - 100)
        lh = 84
        self.lh = lh
        bh = 120 + lh * len(self.bad_lines) + 30
        gh = 120 + lh * len(self.good_lines) + 30
        self.bad_card = card(cw, bh, RED, "ARM DENKT:")
        self.good_card = card(cw, gh, GREEN, "REICH DENKT:")
        self.bad_txt = [text_sprite(" ".join(w for w, _, _ in ln), fnt, WHITE)[0] for ln in self.bad_lines]
        self.good_txt = [text_sprite(" ".join(w for w, _, _ in ln), fnt, WHITE)[0] for ln in self.good_lines]
        self.bad_w = [fnt.getlength(" ".join(w for w, _, _ in ln)) for ln in self.bad_lines]
        lab_h = 130
        gap = 90
        total = lab_h + bh + gap + gh
        top = 880 - total / 2
        self.label_y = top + 40
        self.bad_top = top + lab_h
        self.good_top = self.bad_top + bh + gap
        self.bh, self.gh = bh, gh
        self.vs = pill("VS", theme["accent"], size=34)
        self.vs_y = self.bad_top + bh + gap / 2
        self.t_bad, self.t_strike, self.t_good = 0.3, 1.9, 2.5

        self.sfx(0.0, "whoosh", 0.55)
        self.sfx(0.02, "pop_big", 0.6)
        self.sfx(self.t_bad, "buzz", 0.5)
        self.sfx(self.t_strike, "swish", 0.55)
        self.sfx(self.t_good - 0.05, "pop_big", 0.7)
        self.sfx(self.t_good + 0.05, "ding", 0.65)

    def _draw_card(self, layer, cardimg, txts, top, h, t_in, alpha_mul=1.0):
        p = (self._t - t_in) / 0.35
        if p <= 0:
            return 0
        sc = 0.85 + 0.15 * ease_out_back(p)
        a = clamp(p * 3) * alpha_mul
        cy = top + h / 2 + (1 - ease_out_cubic(p)) * 50
        paste_scaled(layer, cardimg, W / 2, cy, sc, a)
        for i, spr in enumerate(txts):
            ty = cy - h / 2 + 120 + i * self.lh + self.lh / 2 - 10
            paste_scaled(layer, spr, W / 2, ty, sc, a)
        return cy

    def draw(self, layer, t):
        self._t = t
        self.draw_label(layer, t, self.label_y)
        dim = 1 - 0.45 * ease_out_cubic((t - self.t_strike - 0.3) / 0.4)
        cy = self._draw_card(layer, self.bad_card, self.bad_txt, self.bad_top, self.bh, self.t_bad, dim)
        # Durchstreichen
        sp = ease_out_cubic((t - self.t_strike) / 0.35)
        if sp > 0 and cy:
            d = ImageDraw.Draw(layer)
            for i, lw in enumerate(self.bad_w):
                ty = cy - self.bh / 2 + 120 + i * self.lh + self.lh / 2 - 8
                xs = W / 2 - lw / 2 - 10
                d.line([(xs, ty), (xs + (lw + 20) * sp, ty)], fill=RED + (255,), width=10)
        if t > self.t_good - 0.2:
            pv = (t - (self.t_good - 0.2)) / 0.3
            paste_scaled(layer, self.vs, W / 2, self.vs_y, 0.5 + 0.5 * ease_out_back(pv), clamp(pv * 3))
        self._draw_card(layer, self.good_card, self.good_txt, self.good_top, self.gh, self.t_good)


def make_scene(data, theme, start):
    typ = data["type"]
    if typ == "hook":
        return TextScene(data, theme, start, size=124, hook=True)
    if typ == "cta":
        return TextScene(data, theme, start, size=110, cta=True)
    if typ == "counter":
        return CounterScene(data, theme, start)
    if typ == "versus":
        return VersusScene(data, theme, start)
    return TextScene(data, theme, start)


# ----------------------------------------------------------------- background
class Background:
    def __init__(self, theme, seed):
        top, bot = np.array(theme["top"], float), np.array(theme["bottom"], float)
        yy = np.linspace(0, 1, H)[:, None, None]
        grad = top * (1 - yy) + bot * yy
        grad = np.repeat(grad, W, axis=1)
        # Vignette
        ys, xs = np.mgrid[0:H, 0:W]
        r = np.sqrt(((xs - W / 2) / (W * 0.75)) ** 2 + ((ys - H / 2) / (H * 0.62)) ** 2)
        vig = clamp_np(1 - (r - 0.55) * 0.9, 0.35, 1.0)[..., None]
        self.base = Image.fromarray((grad * vig).clip(0, 255).astype(np.uint8)).convert("RGBA")
        self.blob1 = radial_blob(1100, theme["accent"], 70)
        self.blob2 = radial_blob(1000, theme["blob2"], 55)
        rnd = random.Random(seed)
        self.parts = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(20, 70), rnd.uniform(2, 6),
                       rnd.uniform(0, 6.28), rnd.uniform(0.6, 1.8)) for _ in range(46)]
        self.accent = theme["accent"]

    def frame(self, t):
        img = self.base.copy()
        x1 = W / 2 + 280 * math.sin(t * 0.31) - self.blob1.width / 2
        y1 = 620 + 240 * math.cos(t * 0.23) - self.blob1.height / 2
        x2 = W / 2 + 330 * math.cos(t * 0.19 + 1) - self.blob2.width / 2
        y2 = 1380 + 200 * math.sin(t * 0.27) - self.blob2.height / 2
        for blob, x, y in ((self.blob1, x1, y1), (self.blob2, x2, y2)):
            x, y = int(x), int(y)
            sx, sy = max(0, -x), max(0, -y)
            img.alpha_composite(blob, (max(0, x), max(0, y)), (sx, sy, blob.width, blob.height))
        return img

    def particles(self, layer, t):
        d = ImageDraw.Draw(layer)
        for x, y, sp, sz, ph, tw in self.parts:
            yy = (y - sp * t) % (H + 40) - 20
            xx = x + 18 * math.sin(t * 0.5 + ph)
            a = int(60 + 110 * (0.5 + 0.5 * math.sin(t * tw + ph)))
            d.ellipse((xx - sz, yy - sz, xx + sz, yy + sz), fill=self.accent + (a,))


def clamp_np(a, lo, hi):
    return np.minimum(np.maximum(a, lo), hi)


def radial_blob(size, color, max_a):
    ys, xs = np.mgrid[0:size, 0:size]
    r = np.sqrt((xs - size / 2) ** 2 + (ys - size / 2) ** 2) / (size / 2)
    a = (clamp_np(1 - r, 0, 1) ** 2.2 * max_a).astype(np.uint8)
    arr = np.zeros((size, size, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3] = color[0], color[1], color[2], a
    return Image.fromarray(arr, "RGBA")


# ----------------------------------------------------------------- audio
def env_exp(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def sine_sweep(f0, f1, dur, curve="exp"):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    if curve == "exp":
        f = f0 * (f1 / f0) ** (tt / dur)
    else:
        f = f0 + (f1 - f0) * tt / dur
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def lowpass(x, cutoff):
    """Einpoliger Tiefpass; cutoff kann Array (zeitvariabel) sein."""
    if np.isscalar(cutoff):  # konstant -> schnell per FFT (einpolige Kennlinie)
        spec = np.fft.rfft(x)
        f = np.fft.rfftfreq(len(x), 1 / SR)
        return np.fft.irfft(spec / (1 + 1j * f / cutoff), n=len(x))
    cutoff = np.broadcast_to(np.asarray(cutoff, float), x.shape)
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def build_sfx(rng):
    s = {}
    n = int(0.09 * SR)
    s["pop"] = sine_sweep(1100, 380, 0.09) * env_exp(n, 0.025)
    n = int(0.16 * SR)
    s["pop_big"] = (sine_sweep(700, 180, 0.16) * 0.9 + sine_sweep(1400, 360, 0.16) * 0.3) * env_exp(n, 0.045)
    n = int(0.012 * SR)
    s["tick"] = (np.sin(2 * np.pi * 3200 * np.arange(n) / SR) + rng.normal(0, 0.3, n)) * env_exp(n, 0.003)
    # Whoosh: Rauschen mit Filter-Sweep
    n = int(0.55 * SR)
    tt = np.linspace(0, 1, n)
    cut = 300 + 5000 * np.sin(np.pi * tt) ** 2
    s["whoosh"] = lowpass(rng.normal(0, 1, n), cut) * np.sin(np.pi * tt) ** 1.5 * 1.6
    n = int(0.3 * SR)
    tt = np.linspace(0, 1, n)
    hp = rng.normal(0, 1, n)
    hp = hp - lowpass(hp, 1500)
    s["swish"] = hp * np.sin(np.pi * tt) ** 2 * 0.8
    # Ding
    n = int(1.1 * SR)
    t = np.arange(n) / SR
    s["ding"] = (np.sin(2 * np.pi * 1568 * t) + 0.6 * np.sin(2 * np.pi * 2349 * t)
                 + 0.25 * np.sin(2 * np.pi * 3136 * t)) * env_exp(n, 0.28) * 0.5
    # Kassen-"Ka-Ching"
    n1 = int(0.06 * SR)
    ka = lowpass(rng.normal(0, 1, n1), 3500) * env_exp(n1, 0.015) * 1.4
    n2 = int(1.2 * SR)
    t = np.arange(n2) / SR
    trem = 0.75 + 0.25 * np.sin(2 * np.pi * 22 * t)
    ching = (np.sin(2 * np.pi * 2093 * t) + 0.8 * np.sin(2 * np.pi * 2637 * t)
             + 0.6 * np.sin(2 * np.pi * 3520 * t) + 0.3 * np.sin(2 * np.pi * 4186 * t)) * env_exp(n2, 0.3) * trem * 0.4
    cash = np.zeros(int(0.09 * SR) + n2)
    cash[:n1] += ka
    cash[int(0.09 * SR):] += ching
    s["cash"] = cash
    # Impact / Boom
    n = int(1.0 * SR)
    boom = sine_sweep(140, 38, 1.0) * env_exp(n, 0.32) * 1.3
    nb = lowpass(rng.normal(0, 1, n), 900) * env_exp(n, 0.06) * 1.5
    s["impact"] = np.tanh((boom + nb) * 1.4)
    # Riser-Hit (kurz)
    n = int(0.5 * SR)
    s["riser_hit"] = sine_sweep(220, 880, 0.5) * np.linspace(0, 1, n) ** 2 * 0.5
    s["riser_hit"] = np.concatenate([s["riser_hit"], s["impact"][: int(0.5 * SR)] * 0.6])
    # Fehler-Buzz
    n = int(0.32 * SR)
    t = np.arange(n) / SR
    saw = 2 * ((110 * t) % 1) - 1 + 2 * ((116 * t) % 1) - 1
    s["buzz"] = lowpass(saw, 1800) * env_exp(n, 0.12) * 0.55
    # Abwärts "Wah-wah" für negative Zahlen
    n = int(0.8 * SR)
    s["fail"] = (sine_sweep(520, 160, 0.8) + 0.4 * sine_sweep(780, 240, 0.8)) * env_exp(n, 0.35) * 0.7
    return s


NOTE = {"A2": 110.0, "F2": 87.31, "C3": 130.81, "G2": 98.0}


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


def build_music(dur, rng):
    """Ruhiger, motivierender Lo-Fi/Trap-Beat (selbst generiert)."""
    n = int(dur * SR)
    out = np.zeros(n)
    bpm = 96
    beat = 60 / bpm
    bar = beat * 4
    chords = [[57, 60, 64, 69], [53, 57, 60, 65], [48, 55, 60, 64], [55, 59, 62, 67]]  # Am F C G
    roots = [45, 41, 48, 43]
    t_all = np.arange(n) / SR
    # Pad
    pad = np.zeros(n)
    nb = int(math.ceil(dur / bar))
    for b in range(nb):
        s0, s1 = int(b * bar * SR), min(n, int((b + 1) * bar * SR))
        tt = t_all[s0:s1] - b * bar
        seg = np.zeros(s1 - s0)
        for m in chords[b % 4]:
            f = midi(m)
            for h, amp in ((1, 1.0), (2, 0.35), (3, 0.12)):
                seg += amp * np.sin(2 * np.pi * f * h * tt + rng.uniform(0, 6))
                seg += amp * 0.5 * np.sin(2 * np.pi * f * h * 1.004 * tt)
        e = np.minimum(1, tt / 0.6) * np.minimum(1, (bar - tt) / 0.4)
        pad[s0:s1] += seg * e
    pad = lowpass(pad, 1400) * 0.035
    out += pad
    # Bass + Drums
    kick_n = int(0.35 * SR)
    kick = sine_sweep(160, 45, 0.35) * env_exp(kick_n, 0.12)
    hat_n = int(0.05 * SR)
    hat_src = rng.normal(0, 1, hat_n)
    hat = (hat_src - lowpass(hat_src, 6000)) * env_exp(hat_n, 0.012)
    snare_n = int(0.22 * SR)
    sn_src = rng.normal(0, 1, snare_n)
    snare = (sn_src - lowpass(sn_src, 1200)) * env_exp(snare_n, 0.06) + \
        np.sin(2 * np.pi * 190 * np.arange(snare_n) / SR) * env_exp(snare_n, 0.04)

    def add(sig, t0, g):
        i = int(t0 * SR)
        if i >= n:
            return
        j = min(n, i + len(sig))
        out[i:j] += sig[: j - i] * g

    total_beats = int(dur / beat) + 1
    for k in range(total_beats):
        tb = k * beat
        b = int(tb // bar)
        intro = tb < bar * 2  # erste 2 Takte nur Pad + Hats -> Spannung
        if not intro:
            if k % 4 in (0, 2) or (k % 8 == 7):
                add(kick, tb, 0.42)
            if k % 4 in (1, 3):
                add(snare, tb, 0.16)
            # Bass
            f = midi(roots[b % 4])
            bn = int(beat * 0.9 * SR)
            tt = np.arange(bn) / SR
            bass = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt)) * \
                np.minimum(1, tt / 0.01) * env_exp(bn, 0.25)
            add(bass, tb, 0.16)
        for sub in (0, 0.5):
            add(hat, tb + sub * beat, 0.05 if sub == 0 else 0.08)
    # sanftes Fade-out am Ende
    fo = int(1.5 * SR)
    out[-fo:] *= np.linspace(1, 0, fo)
    fi = int(0.3 * SR)
    out[:fi] *= np.linspace(0, 1, fi)
    return out


def build_audio(scenes, dur, path, seed):
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    music = build_music(dur, rng)
    fx = np.zeros(n)
    lib = build_sfx(rng)
    for sc in scenes:
        for t, name, g in sc.events:
            i = int((sc.start + t) * SR)
            sig = lib[name]
            j = min(n, i + len(sig))
            if 0 <= i < n:
                fx[i:j] += sig[: j - i] * g
    # Ducking: Musik leiser, wenn Effekte laut sind
    envf = np.abs(fx)
    k = int(0.08 * SR)
    envf = np.convolve(envf, np.ones(k) / k, mode="same")
    duck = 1 - 0.45 * np.clip(envf * 4, 0, 1)
    mix = music * duck + fx * 0.6
    mix = np.tanh(mix * 1.6) / np.tanh(1.6)
    mix = mix / max(1e-6, np.max(np.abs(mix))) * 0.92
    pcm = (mix * 32767).astype(np.int16)
    stereo = np.stack([pcm, pcm], axis=1)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(stereo.tobytes())


# ----------------------------------------------------------------- render
def render(script_path):
    with open(script_path, encoding="utf-8") as f:
        data = json.load(f)
    name = os.path.splitext(os.path.basename(script_path))[0]
    theme = THEMES[data.get("theme", "gold")]
    seed = sum(map(ord, name))
    random.seed(seed)

    scenes, t = [], 0.0
    for sd in data["scenes"]:
        sc = make_scene(sd, theme, t)
        scenes.append(sc)
        t += sc.dur
    if t < MIN_DURATION:  # letzte Szene verlängern -> garantiert > 1 Minute
        scenes[-1].dur += MIN_DURATION - t
        t = MIN_DURATION
    dur = t
    nframes = int(round(dur * FPS))

    os.makedirs(OUT_DIR, exist_ok=True)
    wav = os.path.join(OUT_DIR, f".{name}.wav")
    mp4 = os.path.join(OUT_DIR, f"{name}.mp4")
    build_audio(scenes, dur, wav, seed)

    bg = Background(theme, seed)
    tag = pill(data.get("tag", "MINDSET"), theme["accent"], filled=False, size=32)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", wav,
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
           "-movflags", "+faststart", "-t", f"{dur:.3f}", mp4]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    si = 0
    cover_t = scenes[0].dur * 0.85
    for fi in range(nframes):
        gt = fi / FPS
        while si < len(scenes) - 1 and gt >= scenes[si].start + scenes[si].dur:
            si += 1
        sc = scenes[si]
        lt = gt - sc.start
        frame = bg.frame(gt)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bg.particles(layer, gt)
        content = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sc.draw(content, lt)
        # Szenen-Ausgang: weich ausblenden + leicht nach oben
        out_p = clamp((lt - (sc.dur - 0.22)) / 0.22) if si < len(scenes) - 1 else 0
        dx, dy = sc.shake(lt) if hasattr(sc, "shake") else (0, 0)
        if out_p > 0:
            content = with_alpha(content, 1 - out_p)
            dy -= 40 * out_p
        if (int(dx), int(dy)) != (0, 0):
            content = _shift(content, int(dx), int(dy))
        layer.alpha_composite(content)
        # Tag-Pill oben + Fortschrittsbalken
        layer.alpha_composite(tag, (int(W / 2 - tag.width / 2), 175))
        d = ImageDraw.Draw(layer)
        d.rectangle((0, 0, W, 9), fill=(255, 255, 255, 40))
        d.rectangle((0, 0, int(W * gt / dur), 9), fill=theme["accent"] + (255,))
        frame.alpha_composite(layer)
        fl = sc.flash(lt) if hasattr(sc, "flash") else 0
        if fl > 0:
            frame = Image.blend(frame, Image.new("RGBA", (W, H), WHITE + (255,)), fl)
        rgb = frame.convert("RGB")
        if abs(gt - cover_t) < 0.5 / FPS:
            rgb.save(os.path.join(OUT_DIR, f"{name}_cover.png"))
        proc.stdin.write(rgb.tobytes())
        if fi % 300 == 0:
            print(f"[{name}] {fi}/{nframes} Frames", flush=True)
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    with open(os.path.join(OUT_DIR, f"{name}_caption.txt"), "w", encoding="utf-8") as f:
        f.write(data.get("caption", data.get("title", "")) + "\n")
    print(f"[{name}] fertig: {mp4} ({dur:.1f} s)", flush=True)


def _shift(img, dx, dy):
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (dx, dy))
    return out


if __name__ == "__main__":
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        sys.exit(1)
    for p in paths:
        render(p)
