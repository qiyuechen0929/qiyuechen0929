#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主页开场大图生成器 —— 纯 SMIL 动画 SVG，不用 JS，GitHub 直接渲染。

    python hero/make_hero.py        # -> hero/hero-light.svg + hero/hero-dark.svg

剧情（24 秒一环，无 JavaScript、无外部字体、无网络请求）：

   0.0s  一张普通主页，标题和正文逐字打出来
   2.0s  右边睁开一只眼睛
   2.8s  扫描线扫过全文，每行被划上高亮
   4.6s  一行英文从裂缝里掉出来：I can't see images.
   5.4s  扫描线停在它上面，闪了两下
   6.4s  逐字翻译：英文字母往下掉，中文从下面弹起来
  10.0s  一条 Bug 虫从左边爬进来，把「看见」两个字啃走了
  12.0s  光标变成的小人从天上砸下来
  13.2s  蓄力、起跳、竖劈
  14.4s  虫子裂成两半，粒子炸开
  15.4s  「看见」两个字飞回原位
  16.8s  眼睛眨一下，安心闭上
  18.6s  正文退场，金句浮现
  23.0s  淡出，回到开头

每个字都是独立的 <text>，宽度用 textLength 锁死，所以在任何操作系统上排版
完全一致 —— 只有位置固定，才能让角色精确地踩、砍、吃掉某个字。
"""
import math
from xml.sax.saxutils import escape

# ------------------------------------------------------------------ 画布
T = 24.0          # 一圈多长（秒）
EPS = 0.0005
W, H = 1240, 420

PAD = 56
TITLE_Y, TITLE_FS = 78, 34
RULE_Y = 104
L1_Y, L2_Y, L3_Y, FS_LINE = 162, 208, 254, 25
FOURTH_Y, FS_FOURTH, FS_EN = 320, 24, 21
GOLD_Y, GOLD_FS = 234, 35
CRITTER_Y = FOURTH_Y + 30   # 虫子在地面上爬，正文下面那条“地”

EYE_X, EYE_Y, EYE_RX, EYE_RY = 1024, 194, 140, 92

CJK_FONT = ("'PingFang SC','Hiragino Sans GB','Microsoft YaHei',"
            "'Noto Sans CJK SC','Source Han Sans SC',sans-serif")
MONO_FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Courier New',monospace"

PALETTES = {
    "light": dict(
        bg="#ffffff", fg="#1f2328", muted="#6e7781", rule="#d8dee4",
        accent="#7c3aed", accent2="#ec4899", scan="#22d3ee",
        sclera="#ffffff", iris="#7c3aed", pupil="#0b0b12",
        bug="#d94a3d", bug_dark="#a3342b", blade="#4a5361", blade_edge="#1f2328",
        gold="#4c1d95", mark="#f0e9ff", page="#f6f3ff",
    ),
    "dark": dict(
        bg="#0d1117", fg="#e6edf3", muted="#8b949e", rule="#30363d",
        accent="#a78bfa", accent2="#f472b6", scan="#22d3ee",
        sclera="#150f26", iris="#8b5cf6", pupil="#000000",
        bug="#ff7b72", bug_dark="#c0473f", blade="#dfe5ec", blade_edge="#f0f6fc",
        gold="#c4b5fd", mark="#1a1330", page="#150f24",
    ),
}


# ------------------------------------------------------------------ 小工具
def n(v):
    """紧凑数字：1234.0 -> 1234，12.30 -> 12.3"""
    s = f"{v:.1f}"
    if s.endswith(".0"):
        s = s[:-2]
    if s == "-0":
        s = "0"
    return s


def is_cjk(ch):
    o = ord(ch)
    return (0x2E80 <= o <= 0x9FFF) or (0xFF00 <= o <= 0xFFEF) or (0x3000 <= o <= 0x303F)


def char_w(ch, fs, mono):
    if ch == "\u200b":
        return 0.0
    if is_cjk(ch):
        return fs
    if ch == " ":
        return fs * 0.30
    if mono:
        return fs * 0.60
    if ch in "il.,:;'|!":
        return fs * 0.30
    if ch in "mwMW@—":
        return fs * 0.80
    return fs * 0.56


def tokenize(text, mono=False):
    """切词：中文一字一词（方便逐字动），连续的西文合成一个词（保持连字不断）。"""
    out, buf = [], ""
    for ch in text:
        if is_cjk(ch) or ch == " ":
            if buf:
                out.append(buf)
                buf = ""
            out.append(ch)
        else:
            buf += ch
    if buf:
        out.append(buf)
    return out


def text_w(text, fs, mono=False):
    return sum(char_w(c, fs, mono) for c in text)


# ------------------------------------------------------------------ 关键帧轨道
SPLINES = {
    "lin": "0.0 0.0 1.0 1.0",
    "in": "0.55 0.0 1.0 1.0",
    "out": "0.0 0.0 0.45 1.0",
    "inout": "0.45 0.0 0.55 1.0",
    "snap": "0.0 0.0 0.12 1.0",
    "back": "0.12 0.86 0.22 1.0",   # 快出缓入（y 必须留在 0..1，否则 Chromium 丢弃整条动画）
    "fall": "0.5 0.0 0.95 0.55",
}


class Track:
    """一串 (时间, 值, 缓动) 关键帧；值可以是数字，也可以是 (x, y) 元组。"""

    __slots__ = ("keys",)

    def __init__(self, v0):
        self.keys = [[0.0, v0, "lin"]]

    @property
    def t(self):
        return self.keys[-1][0]

    @property
    def v(self):
        return self.keys[-1][1]

    def hold(self, t):
        if t > self.t + 1e-9:
            self.keys.append([round(t, 5), self.v, "lin"])

    def add(self, t, v, ease="inout"):
        t = min(t, T)
        if t <= self.t:
            t = self.t + EPS
        self.keys.append([round(t, 5), v, ease])

    def set(self, t, v, ease="inout"):
        self.hold(t - EPS)
        self.add(t, v, ease)

    def is_const(self):
        v0 = self.keys[0][1]
        return all(k[1] == v0 for k in self.keys)

    def closed(self):
        ks = [list(k) for k in self.keys]
        if ks[-1][0] < T:
            ks.append([T, ks[-1][1], "lin"])
        return ks


def _spline_emit(keys):
    if any(k[2] != "lin" for k in keys[1:]):
        return 'calcMode="spline" keySplines="%s" ' % ";".join(SPLINES[k[2]] for k in keys[1:])
    return ""


def anim(attr, tr, fmt=str, extra=""):
    """普通属性动画（opacity / x / y ...）。值恒定时返回空串。"""
    if tr is None or tr.is_const():
        return ""
    ks = tr.closed()
    vals = ";".join(fmt(k[1]) for k in ks)
    kt = ";".join(f"{k[0] / T:.6f}" for k in ks)
    return (f'<animate attributeName="{attr}" values="{vals}" keyTimes="{kt}" '
            f'{_spline_emit(ks)}{extra}dur="{T}s" repeatCount="indefinite"/>')


def anim_tf(kind, tr, fmt, extra=""):
    """transform 动画。"""
    if tr is None or tr.is_const():
        return ""
    ks = tr.closed()
    vals = ";".join(fmt(k[1]) for k in ks)
    kt = ";".join(f"{k[0] / T:.6f}" for k in ks)
    return (f'<animateTransform attributeName="transform" type="{kind}" values="{vals}" '
            f'keyTimes="{kt}" {_spline_emit(ks)}{extra}dur="{T}s" repeatCount="indefinite"/>')


f_xy = lambda v: f"{n(v[0])} {n(v[1])}"
f_num = lambda v: n(v)


# ------------------------------------------------------------------ 文字块
class Tok:
    """一个可独立动画的排版单元（一个字 / 一个词）。"""

    def __init__(self, text, x, y, fs, fill, mono=False, weight=400, italic=False,
                 spacing=0, natural=False, opacity=1.0):
        self.text = text
        self.x, self.y = x, y
        self.fs = fs
        self.fill = fill
        self.mono = mono
        self.weight = weight
        self.italic = italic
        self.spacing = spacing
        self.w = text_w(text, fs, mono) if not natural else None
        self.natural = natural
        self.pos = Track((0.0, 0.0))
        self.opa = Track(opacity)

    def svg(self):
        attrs = [f'font-family="{MONO_FONT if self.mono else CJK_FONT}"',
                 f'font-size="{n(self.fs)}"']
        if self.weight != 400:
            attrs.append(f'font-weight="{self.weight}"')
        if self.italic:
            attrs.append('font-style="italic"')
        if self.w is not None:
            attrs.append(f'textLength="{n(self.w)}" lengthAdjust="spacingAndGlyphs"')
        if self.spacing:
            attrs.append(f'letter-spacing="{n(self.spacing)}"')
        attrs.append(f'fill="{self.fill}"')
        opa_anim = anim("opacity", self.opa, lambda v: f"{v:.3f}")
        if self.opa.is_const() and self.opa.v == 0:
            return ""
        if not self.opa.is_const():
            attrs.append(f'opacity="{self.opa.keys[0][1]:.3f}"')
        body = (f'<text x="0" y="0" {" ".join(attrs)}>'
                f'{escape(self.text)}{opa_anim}</text>')
        if self.pos.is_const():
            dx, dy = self.pos.v
            return f'<g transform="translate({n(self.x + dx)} {n(self.y + dy)})">{body}</g>'
        tr = anim_tf("translate", self.pos, lambda v: f"{n(self.x + v[0])} {n(self.y + v[1])}")
        return f"<g>{tr}{body}</g>"


def layout(text, x, y, fs, fill, mono=False, weight=400, tracking=0.0, **kw):
    """按固定字宽排一行，返回 token 列表（也返回总宽）。"""
    toks, cx = [], x
    for t in tokenize(text, mono):
        w = text_w(t, fs, mono)
        toks.append(Tok(t, cx, y, fs, fill, mono=mono, weight=weight, **kw))
        cx += w + tracking
    return toks, cx - tracking - x


def underline(x, y, w, h, fill, track, ops=0.55):
    """高亮下划线：宽度从 0 扫到 w。"""
    if track is None:
        return f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="{n(h / 2)}" fill="{fill}" opacity="{ops}"/>'
    tr = anim("width", track, lambda v: n(v))
    return (f'<rect x="{n(x)}" y="{n(y)}" width="0" height="{n(h)}" rx="{n(h / 2)}" '
            f'fill="{fill}" opacity="{ops}">{tr}</rect>')


# ------------------------------------------------------------------ 眼睛
def build_eye(p):
    """一只会睁开、会扫、会眨、最后安心闭上的巨眼。

    眼睑用两片"底色"矩形滑进来模拟（不需要 mask，兼容性最好），所以光晕必须画在
    眼睛外面，否则会被眼睑的底色矩形切出一个方块。
    """
    cx, cy, rx, ry = EYE_X, EYE_Y, EYE_RX, EYE_RY

    # 睁眼程度：0 闭合，1 全开
    openk = Track(0.0)
    openk.set(2.05, 0.0, "lin")
    openk.add(2.85, 1.0, "back")
    for bt in (10.4, 16.85):
        openk.hold(bt - 0.12)
        openk.add(bt, 0.06, "in")
        openk.add(bt + 0.18, 1.0, "out")
    openk.hold(18.7)
    openk.add(19.25, 0.0, "inout")

    lid_top = anim_tf("translate", openk, lambda v: f"0 {n(-(ry + 3) * v)}")
    lid_bot = anim_tf("translate", openk, lambda v: f"0 {n((ry + 3) * v)}")

    # 瞳孔追随：看字、看被啃走的两个字、最后看回来
    look = Track((0.0, 0.0))
    for tt, v in [(2.9, (-40.0, 6.0)), (4.6, (-46.0, 22.0)), (6.4, (-34.0, 14.0)),
                  (10.6, (-62.0, 26.0)), (12.6, (-30.0, 10.0)), (14.4, (-56.0, 26.0)),
                  (17.0, (-12.0, 0.0)), (19.0, (0.0, 0.0))]:
        look.set(tt, v)

    appear = Track(0.0)
    appear.set(1.9, 0.0, "lin")
    appear.add(2.6, 1.0, "out")
    appear.hold(19.35)
    appear.add(19.75, 0.0, "inout")     # 闭眼后退场，只留一道眼线

    scale_in = Track(0.0)
    scale_in.set(1.9, 0.0, "lin")
    scale_in.add(2.75, 1.0, "back")

    g = [f'<g transform="translate({cx} {cy})">']
    # 光晕（在眼睛外面，单独一层）
    g.append(f'<defs><radialGradient id="eyeGlow"><stop offset="0.45" stop-color="{p["accent"]}" '
             f'stop-opacity="0"/><stop offset="0.82" stop-color="{p["accent"]}" stop-opacity="0.15"/>'
             f'<stop offset="1" stop-color="{p["accent"]}" stop-opacity="0"/></radialGradient></defs>')

    # 眼睛本体
    g.append(f'<g opacity="0">{anim("opacity", appear, lambda v: f"{v:.3f}")}<g>')
    g.append(anim_tf("scale", scale_in, lambda v: f"{v:.3f} {v:.3f}"))
    g.append(f'<ellipse cx="0" cy="0" rx="{n(rx)}" ry="{n(ry)}" fill="{p["sclera"]}" '
             f'stroke="{p["accent"]}" stroke-width="2.5"/>')
    g.append(f'<clipPath id="eyeclip"><ellipse cx="0" cy="0" rx="{n(rx - 2)}" ry="{n(ry - 2)}"/></clipPath>')
    g.append(f'<g clip-path="url(#eyeclip)"><g>{anim_tf("translate", look, f_xy)}')
    g.append(f'<circle cx="0" cy="0" r="{n(ry * 0.55)}" fill="{p["iris"]}" opacity="0.92"/>')
    g.append(f'<circle cx="0" cy="0" r="{n(ry * 0.24)}" fill="{p["pupil"]}"/>')
    g.append(f'<circle cx="{n(-ry * 0.20)}" cy="{n(-ry * 0.22)}" r="{n(ry * 0.10)}" '
             f'fill="#ffffff" opacity="0.9"/>')
    g.append(f'<circle cx="{n(ry * 0.22)}" cy="{n(ry * 0.18)}" r="{n(ry * 0.045)}" '
             f'fill="#ffffff" opacity="0.5"/>')
    g.append("</g></g>")
    # 眼睑
    g.append(f'<rect x="{n(-rx - 6)}" y="{n(-ry - 6)}" width="{n(2 * rx + 12)}" height="{n(ry + 6)}" '
             f'fill="{p["bg"]}">{lid_top}</rect>')
    g.append(f'<rect x="{n(-rx - 6)}" y="0" width="{n(2 * rx + 12)}" height="{n(ry + 6)}" '
             f'fill="{p["bg"]}">{lid_bot}</rect>')
    g.append("</g></g>")
    # 光晕最后画（画在眼睑上面，才不会被眼睑的底色矩形切出方块）
    glo = Track(0.0)
    glo.set(2.0, 0.0, "lin")
    glo.add(2.9, 0.85, "out")
    glo.hold(19.35)
    glo.add(19.8, 0.22, "inout")
    g.append(f'<ellipse cx="0" cy="0" rx="{n(rx * 1.42)}" ry="{n(ry * 1.75)}" fill="url(#eyeGlow)">'
             f'{anim("opacity", glo, lambda v: f"{v:.3f}")}</ellipse>')
    # 闭合后留下的那道眼线
    line_opa = Track(0.0)
    line_opa.set(19.15, 0.0, "lin")
    line_opa.add(19.6, 1.0, "out")
    line_opa.hold(22.9)
    line_opa.add(23.4, 0.0, "in")
    g.append(f'<path d="M{n(-rx * 0.84)} 2 Q0 {n(ry * 0.20)} {n(rx * 0.84)} 2" fill="none" '
             f'stroke="{p["accent"]}" stroke-width="3.2" stroke-linecap="round" opacity="0">'
             f'{anim("opacity", line_opa, lambda v: f"{v:.3f}")}</path>')
    # 睫毛
    g.append("</g>")
    return "".join(g)


# ------------------------------------------------------------------ 扫描线
def build_scan(p):
    """一条横着走的扫描带 + 前缘亮线。"""
    top = 128
    bottom = FOURTH_Y - 20
    y = Track(top)
    y.set(2.85, top, "lin")
    y.add(4.75, bottom, "inout")
    y.hold(12.0)

    opa = Track(0.0)
    opa.set(2.8, 0.0, "lin")
    opa.add(3.0, 1.0, "out")
    # 停在英文行上闪两下
    for bt in (5.6, 6.0):
        opa.hold(bt)
        opa.add(bt + 0.08, 0.25, "lin")
        opa.add(bt + 0.16, 1.0, "lin")
    opa.hold(6.5)
    opa.add(6.9, 0.0, "inout")

    g = ['<g opacity="0">', anim("opacity", opa, lambda v: f"{v:.3f}"),
         anim_tf("translate", y, lambda v: f"0 {n(v)}")]
    g.append(f'<defs><linearGradient id="scanGrad" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{p["scan"]}" stop-opacity="0"/>'
             f'<stop offset="0.75" stop-color="{p["scan"]}" stop-opacity="0.20"/>'
             f'<stop offset="1" stop-color="{p["scan"]}" stop-opacity="0.38"/>'
             f'</linearGradient></defs>')
    g.append(f'<rect x="{PAD - 24}" y="-26" width="{n(W - 2 * PAD + 48)}" height="26" fill="url(#scanGrad)"/>')
    g.append(f'<rect x="{PAD - 24}" y="-2.5" width="{n(W - 2 * PAD + 48)}" height="2.5" '
             f'fill="{p["scan"]}" opacity="0.85"/>')
    g.append("</g>")
    return "".join(g)


# ------------------------------------------------------------------ 光标
CURSOR_D = "M0 0 L0 17 L4.6 12.6 L7.8 19 L11 17.4 L7.8 11.2 L12.6 10.8 Z"


def build_cursor(p, pos_track, opa_track):
    g = [f'<g opacity="0">', anim("opacity", opa_track, lambda v: f"{v:.3f}"),
         anim_tf("translate", pos_track, f_xy)]
    g.append(f'<path d="{CURSOR_D}" fill="{p["fg"]}" stroke="{p["bg"]}" stroke-width="1.2" '
             f'stroke-linejoin="round"/>')
    g.append("</g>")
    return "".join(g)


# ------------------------------------------------------------------ Bug 虫
def build_critter(p, x_track, opa_track, split):
    """Bug 虫本体：6 节身体，前 3 节 / 后 3 节分成两组，好让劈开后各飞一边。"""
    radii = [8.5, 10.5, 12, 12.5, 12, 10.5]
    cols = [p["bug_dark"], p["bug_dark"], p["bug"], p["bug"], p["bug"], p["bug_dark"]]
    xs, cx = [], 0.0
    for r in radii:
        xs.append(cx)
        cx += r * 1.62
    xs = [v - cx + 12 for v in xs]   # 让头（最后一节）靠近原点

    def body(idx, fly_dx, fly_dy, rot, bite, t_from):
        parts = ["<g>"]
        spread = Track((0.0, 0.0))
        spread.hold(split)
        spread.add(split + 0.5, (fly_dx, fly_dy), "out")
        spread.add(split + 1.6, (fly_dx * 1.1, fly_dy + 78), "in")
        spread.hold(19.9)
        parts.append(anim_tf("translate", spread, f_xy))
        parts.append("<g>")
        rotk = Track((0.0, 0.0, 0.0))
        rotk.hold(split)
        rotk.add(split + 0.6, (rot, 0.0, 0.0), "out")
        parts.append(anim_tf("rotate", rotk, lambda v: f"{n(v[0])} {n(v[1])} {n(v[2])}"))
        for i in idx:
            r = radii[i]
            parts.append(f'<path d="M{n(xs[i] - r * 0.5)} {n(r * 0.4)} l{n(-r * 0.24)} {n(r * 0.75)}" '
                         f'stroke="{p["bug_dark"]}" stroke-width="1.8" stroke-linecap="round"/>')
            parts.append(f'<path d="M{n(xs[i] + r * 0.5)} {n(r * 0.4)} l{n(r * 0.24)} {n(r * 0.75)}" '
                         f'stroke="{p["bug_dark"]}" stroke-width="1.8" stroke-linecap="round"/>')
            parts.append(f'<circle cx="{n(xs[i])}" cy="0" r="{n(r)}" fill="{cols[i]}"/>')
            parts.append(f'<circle cx="{n(xs[i])}" cy="{n(-r * 0.36)}" r="{n(r * 0.26)}" '
                         f'fill="#ffffff" opacity="0.13"/>')
        parts.append("</g></g>")
        return "".join(parts)

    mouth = Track(1.0)
    mouth.hold(10.35)
    mouth.add(10.5, 1.35, "out")
    mouth.add(10.75, 0.85, "in")
    mouth.add(11.1, 1.35, "out")
    mouth.add(11.4, 1.0, "in")

    g = ['<g opacity="0">', anim("opacity", opa_track, lambda v: f"{v:.3f}"),
         anim_tf("translate", x_track, lambda v: f"{n(v)} {n(CRITTER_Y)}")]
    # 触角
    g.append(f'<g stroke="{p["bug_dark"]}" stroke-width="2" stroke-linecap="round" fill="none" '
             f'opacity="0.9"><path d="M4 -8 q6 -10 14 -11"/><path d="M6 -9 q8 -7 16 -5"/></g>')
    g.append(body([0, 1, 2], -40, -52, -30, 1.0, split))
    g.append(body([3, 4, 5], 40, -44, 22, 1.0, split))
    # 啃咬时张开的嘴
    g.append(f'<g transform="translate(10 2)">'
             f'<path d="M0 0 q9 -7 16 -1" fill="none" stroke="{p["bug_dark"]}" stroke-width="2.4" '
             f'stroke-linecap="round"/></g>')
    # 眼睛（白色高光点，让它显得很有精神）
    g.append(f'<circle cx="1" cy="-3" r="2.6" fill="{p["pupil"]}"/>')
    g.append("</g>")
    return "".join(g)


# ------------------------------------------------------------------ 挥刀的小人
def build_hero(p, land_x, land_y, t_land=12.35):
    """光标变的持刀小人。自己的坐标系里脚在 (0,0)，往上为负。

    层级：落点(translate) > 朝向(scale) > 起跳(translate) > 压缩(scale) > 前倾(rotate) > 手臂(rotate)
    每一层只挂一条动画 —— 同一元素上挂两条 animateTransform 会互相覆盖。
    """
    drop = Track((land_x - 190.0, land_y - 720.0))
    drop.set(t_land - 0.5, (land_x - 190.0, land_y - 720.0), "lin")
    drop.add(t_land, (land_x, land_y), "in")
    drop.hold(20.0)
    drop.add(20.35, (land_x, land_y - 30), "out")
    drop.add(20.7, (land_x, land_y - 900), "in")

    squash = Track((1.0, 1.0))
    squash.hold(t_land)
    squash.add(t_land + 0.12, (1.26, 0.72), "out")
    squash.add(t_land + 0.32, (0.94, 1.07), "inout")
    squash.add(t_land + 0.52, (1.0, 1.0), "inout")
    squash.hold(13.18)
    squash.add(13.46, (1.12, 0.84), "in")
    squash.add(13.86, (1.0, 1.0), "out")

    arm = Track(-64.0)
    arm.set(t_land, -64.0, "lin")
    arm.add(12.95, -104.0, "out")
    arm.hold(13.18)
    arm.add(13.5, -136.0, "in")      # 抬到脑后蓄力
    arm.add(13.84, 92.0, "snap")     # 竖劈
    arm.hold(19.9)
    arm.add(20.2, -64.0, "lin")

    lean = Track(0.0)
    lean.set(t_land, 0.0, "lin")
    lean.add(13.5, -9.0, "out")
    lean.add(13.86, 16.0, "snap")
    lean.add(14.7, 0.0, "inout")

    hop = Track((0.0, 0.0))
    hop.hold(13.18)
    hop.add(13.55, (0.0, -34.0), "out")
    hop.add(13.86, (0.0, 0.0), "in")

    st = p["fg"]
    g = ['<g opacity="1">', anim_tf("translate", drop, f_xy)]
    g.append('<g transform="scale(-1.18 1.18)">')          # 面朝左，整体放大
    g.append(f'<g>{anim_tf("translate", hop, f_xy)}')      # 起跳
    g.append(f'<g>{anim_tf("scale", squash, lambda v: f"{v[0]:.3f} {v[1]:.3f}")}</g>')
    g.append(f'<g>{anim_tf("rotate", lean, lambda v: f"{n(v)} 0 -8")}')

    # 影子
    sh = Track(1.0)
    sh.set(t_land - 0.1, 0.0, "lin")
    sh.add(t_land + 0.25, 1.0, "out")
    g.append(f'<ellipse cx="6" cy="2" rx="26" ry="5" fill="{p["fg"]}" opacity="0.10">'
             f'{anim("opacity", sh, lambda v: f"{v * 0.12:.3f}")}</ellipse>')
    # 腿
    g.append(f'<g stroke="{st}" stroke-width="4.6" stroke-linecap="round" fill="none">'
             f'<path d="M0 -18 L-12 0"/><path d="M0 -18 L11 0"/></g>')
    # 躯干
    g.append(f'<path d="M0 -38 L0 -17" stroke="{st}" stroke-width="5.2" stroke-linecap="round" fill="none"/>')
    # 左手
    g.append(f'<path d="M0 -34 L-12 -22" stroke="{st}" stroke-width="4.4" stroke-linecap="round" fill="none"/>')
    # 右手 + 刀（整组绕肩旋转）
    g.append(f'<g>{anim_tf("rotate", arm, lambda v: f"{n(v)} 0 -34")}')
    g.append(f'<path d="M0 -34 L14 -46" stroke="{st}" stroke-width="4.4" stroke-linecap="round" fill="none"/>')
    g.append(f'<path d="M10 -42 L20 -52" stroke="{p["accent"]}" stroke-width="4" stroke-linecap="round"/>')
    g.append(f'<path d="M12 -44 L20 -52 L58 -90 L50 -98 Z" fill="{p["blade"]}"/>')
    g.append(f'<path d="M20 -52 L58 -90" stroke="{p["blade_edge"]}" stroke-width="2" stroke-linecap="round"/>')
    g.append("</g>")
    # 头
    g.append(f'<circle cx="0" cy="-50" r="12" fill="none" stroke="{st}" stroke-width="4.6"/>')
    g.append(f'<g fill="{p["accent2"]}"><circle cx="-3.8" cy="-52" r="2.1"/>'
             f'<circle cx="2.8" cy="-52" r="2.1"/></g>')
    g.append("</g></g></g></g>")
    return "".join(g)


# ------------------------------------------------------------------ 斩击特效
def build_slash(p, cx, cy, t0, t1, angle=-42):
    opa = Track(0.0)
    opa.set(t0, 0.0, "lin")
    opa.add(t0 + 0.07, 1.0, "out")
    opa.add(t1, 0.0, "in")
    grow = Track(0.3)
    grow.set(t0, 0.3, "lin")
    grow.add(t0 + 0.24, 1.0, "out")
    return (f'<g opacity="0">{anim("opacity", opa, lambda v: f"{v:.3f}")}'
            f'<g transform="translate({n(cx)} {n(cy)}) rotate({n(angle)})"><g>'
            f'{anim_tf("scale", grow, lambda v: f"{v:.3f} {v:.3f}")}'
            f'<path d="M-170 0 Q0 -52 170 0" fill="none" stroke="{p["accent2"]}" '
            f'stroke-width="12" stroke-linecap="round" opacity="0.5"/>'
            f'<path d="M-160 0 Q0 -30 160 0" fill="none" stroke="#ffffff" '
            f'stroke-width="4" stroke-linecap="round" opacity="0.95"/>'
            f'</g></g></g>')


def build_particles(p, cx, cy, t0):
    out = ['<g>']
    for i in range(16):
        a = i / 16 * math.tau + (0.7 if i % 2 else 0.0)
        d = 44 + 58 * ((i * 37) % 11) / 11
        dx, dy = math.cos(a) * d, math.sin(a) * d * 0.7 + 30
        pos = Track((0.0, 0.0))
        pos.hold(t0)
        pos.add(t0 + 0.5, (dx, dy), "out")
        pos.add(t0 + 1.25, (dx * 1.15, dy + 62), "in")
        pos.hold(20.4)
        opa = Track(0.0)
        opa.hold(t0)
        opa.add(t0 + 0.05, 1.0, "lin")
        opa.add(t0 + 1.15, 0.0, "in")
        opa.hold(20.4)
        size = 3 + (i % 3) * 1.6
        col = p["accent2"] if i % 3 else p["scan"]
        rot = Track((0.0, 0.0, 0.0))
        rot.hold(t0)
        rot.add(t0 + 1.0, (i * 47 % 360, 0.0, 0.0), "out")
        out.append(
            f'<g opacity="0">{anim("opacity", opa, lambda v: f"{v:.3f}")}'
            f'{anim_tf("translate", pos, f_xy)}'
            f'<g>{anim_tf("rotate", rot, lambda v: f"{n(v[0])} {n(v[1])} {n(v[2])}")}'
            f'<rect x="{n(-size / 2)}" y="{n(-size / 2)}" width="{n(size)}" height="{n(size)}" '
            f'rx="1" fill="{col}"/></g></g>')
    out.append("</g>")
    return "".join(out)


def build_flash(p, cx, cy, t0):
    opa = Track(0.0)
    opa.set(t0, 0.0, "lin")
    opa.add(t0 + 0.04, 0.42, "out")
    opa.add(t0 + 0.26, 0.0, "in")
    return (f'<defs><radialGradient id="hitFlash"><stop offset="0" stop-color="#ffffff" '
            f'stop-opacity="0.95"/><stop offset="0.45" stop-color="#ffffff" stop-opacity="0.35"/>'
            f'<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></radialGradient></defs>'
            f'<circle cx="{n(cx)}" cy="{n(cy)}" r="78" fill="url(#hitFlash)" opacity="0">'
            f'{anim("opacity", opa, lambda v: f"{v:.3f}")}</circle>')


# ------------------------------------------------------------------ 组装
EN_LINE = "I can't see images."
ZH_LINE = "现在，我能看见你的屏幕了。"


def build(pal, name):
    p = PALETTES[pal]

    # ============ 1. 标题 / 正文（逐字打出来）
    title, tw = layout("hi，我是 陈启粤", PAD, TITLE_Y, TITLE_FS, p["fg"], weight=700, tracking=0.4)
    wave = Tok(" 👋", PAD + tw + 6, TITLE_Y, TITLE_FS + 3, p["fg"], natural=True)
    lines = [
        ("学生开发者 · 一个只会写好玩东西的人", L1_Y, p["fg"], 400),
        ("代表作 vision-bridge：给纯文本 AI 装上一双眼睛", L2_Y, p["muted"], 400),
        ("顺便把 Cursor、Claude Desktop 都汉化了", L3_Y, p["muted"], 400),
    ]
    all_toks = []

    def typewriter(toks, t0, step=0.045, dy=10.0):
        for i, tk in enumerate(toks):
            t = t0 + i * step
            tk.opa.keys = [[0.0, 0.0, "lin"]]
            tk.opa.set(t, 0.0, "lin")
            tk.opa.add(t + 0.16, 1.0, "out")
            tk.pos.keys = [[0.0, (0.0, dy), "lin"]]
            tk.pos.set(t, (0.0, dy), "lin")
            tk.pos.add(t + 0.22, (0.0, 0.0), "out")

    typewriter(title + [wave], 0.25, 0.055)
    all_toks += title + [wave]

    line_toks = []
    for li, (txt, y, col, wt) in enumerate(lines):
        toks, w = layout(txt, PAD, y, FS_LINE, col, weight=wt, tracking=0.3)
        t0 = 1.15 + li * 0.30
        for i, tk in enumerate(toks):
            t = t0 + i * 0.022
            tk.opa.keys = [[0.0, 0.0, "lin"]]
            tk.opa.set(t, 0.0, "lin")
            tk.opa.add(t + 0.30, 1.0, "out")
            tk.pos.keys = [[0.0, (0.0, 6.0), "lin"]]
            tk.pos.set(t, (0.0, 6.0), "lin")
            tk.pos.add(t + 0.40, (0.0, 0.0), "out")
        # 结尾统一淡出（给金句让位）
        for tk in toks:
            tk.opa.hold(18.55)
            tk.opa.add(19.05, 0.0, "inout")
            tk.pos.hold(18.55)
            tk.pos.add(19.05, (0.0, -6.0), "inout")
        line_toks.append((toks, PAD, y, w))
        all_toks += toks

    # 标题也一样退场
    for tk in title + [wave]:
        tk.opa.hold(18.55)
        tk.opa.add(19.05, 0.0, "inout")

    # 高亮下划线：跟着扫描线一层层划过去
    marks = []
    for i, (toks, x, y, w) in enumerate(line_toks):
        wr = Track(0.0)
        t_start = 3.05 + i * 0.34
        wr.set(t_start, 0.0, "lin")
        wr.add(t_start + 0.5, w + 6, "out")
        wr.hold(18.6)
        wr.add(19.1, 0.0, "in")
        marks.append(underline(x - 3, y + 9, w + 6, 4, p["accent"], wr, ops=0.5))

    # ============ 2. 英文行：掉出来 -> 逐字掉落
    toks_en, en_w = layout(EN_LINE, PAD, FOURTH_Y, FS_EN, p["muted"], mono=True)
    for i, tk in enumerate(toks_en):
        t = 4.55 + i * 0.028
        tk.opa.keys = [[0.0, 0.0, "lin"]]
        tk.opa.set(t, 0.0, "lin")
        tk.opa.add(t + 0.18, 1.0, "out")
        tk.pos.keys = [[0.0, (0.0, -16.0), "lin"]]
        tk.pos.set(t, (0.0, -16.0), "lin")
        tk.pos.add(t + 0.30, (0.0, 0.0), "fall")
        # 扫描线扫到 -> 抖两下
        for j, jt in enumerate((5.62, 5.94)):
            tk.pos.hold(jt)
            tk.pos.add(jt + 0.05, (1.6, 0.0), "lin")
            tk.pos.add(jt + 0.12, (-1.4, 0.6), "lin")
        # 翻译：字母往下掉
        f0 = 6.45 + i * 0.045
        tk.pos.hold(f0)
        tk.pos.add(f0 + 0.42, ((i % 5 - 2) * 7.0, 88.0), "in")
        tk.opa.hold(f0)
        tk.opa.add(f0 + 0.38, 0.0, "in")
    all_toks += toks_en

    # ============ 3. 中文行：从下面弹起来替换
    toks_zh, zh_w = layout(ZH_LINE, PAD, FOURTH_Y, FS_FOURTH, p["fg"])
    eaten = []
    for i, tk in enumerate(toks_zh):
        t = 6.60 + i * 0.055
        tk.opa.keys = [[0.0, 0.0, "lin"]]
        tk.opa.set(t, 0.0, "lin")
        tk.opa.add(t + 0.16, 1.0, "out")
        tk.pos.keys = [[0.0, (0.0, 26.0), "lin"]]
        tk.pos.set(t, (0.0, 26.0), "lin")
        tk.pos.add(t + 0.32, (0.0, 0.0), "back")
        eaten.append(tk)
    all_toks += toks_zh

    # 「看见」两个字被 Bug 啃走
    bug_start_x = PAD - 190.0
    for idx, bite_t in ((5, 10.70), (6, 10.92)):
        tk = toks_zh[idx]
        tk.pos.hold(bite_t)
        tk.pos.add(bite_t + 0.10, (0.0, -11.0), "out")
        tk.pos.add(bite_t + 0.45, (0.0, -11.0), "lin")     # 被叼着
        tk.pos.add(bite_t + 1.0, (16.0, 34.0), "in")      # 被拖进嘴里
        tk.pos.hold(15.35)
        tk.pos.add(15.55, (-8.0, -18.0), "out")            # 飞回来
        tk.pos.add(15.95, (0.0, 0.0), "back")
        tk.opa.hold(bite_t + 0.86)
        tk.opa.add(bite_t + 1.16, 0.0, "in")
        tk.opa.hold(15.5)
        tk.opa.add(15.7, 1.0, "out")
        tk.opa.hold(18.55)
        tk.opa.add(19.06, 0.0, "inout")

    for tk in toks_zh:
        if tk in (toks_zh[5], toks_zh[6]):
            continue
        tk.opa.hold(18.55)
        tk.opa.add(19.06, 0.0, "inout")

    # 被啃走后留下的两个小豁口（虚线框，提示"这里缺了点什么"）
    gap = []
    for idx, t_on in ((5, 11.15), (6, 11.15)):
        tk = toks_zh[idx]
        opa = Track(0.0)
        opa.set(t_on, 0.0, "lin")
        opa.add(t_on + 0.2, 1.0, "out")
        opa.hold(15.4)
        opa.add(15.6, 0.0, "in")
        gap.append(
            f'<g opacity="0">{anim("opacity", opa, lambda v: f"{v:.3f}")}'
            f'<rect x="{n(tk.x + 2)}" y="{n(FOURTH_Y - 18)}" width="{n(FS_FOURTH - 4)}" '
            f'height="{n(FS_FOURTH - 2)}" rx="3" fill="none" stroke="{p["bug"]}" '
            f'stroke-width="1.2" stroke-dasharray="3 3" opacity="0.55"/></g>')

    # ============ 4. 金句
    gold_toks = []
    gold_txt = "人和 AI 一起做东西，最好玩。"
    gw = text_w(gold_txt, GOLD_FS)
    gx = (W - gw) / 2 - 6
    gold_toks, _ = layout(gold_txt, gx, GOLD_Y, GOLD_FS, p["gold"], weight=700, tracking=0.6)
    for i, tk in enumerate(gold_toks):
        t = 19.35 + i * 0.05
        tk.opa.keys = [[0.0, 0.0, "lin"]]
        tk.opa.set(t, 0.0, "lin")
        tk.opa.add(t + 0.22, 1.0, "out")
        tk.pos.keys = [[0.0, (0.0, 30.0), "lin"]]
        tk.pos.set(t, (0.0, 30.0), "lin")
        tk.pos.add(t + 0.34, (0.0, 0.0), "back")
        tk.opa.hold(22.75)
        tk.opa.add(23.2, 0.0, "inout")
    all_toks += gold_toks

    # 金句底下那道划线
    gw_tr = Track(0.0)
    gw_tr.set(20.9, 0.0, "lin")
    gw_tr.add(21.6, gw + 14, "out")
    gw_tr.hold(22.7)
    gw_tr.add(23.2, 0.0, "in")
    gold_rule = underline(gx - 7, GOLD_Y + 12, gw + 14, 5, p["accent2"], gw_tr, ops=0.75)

    # 副标题小字
    sub, sub_w = layout("给 AI 装一双眼睛 · 让工具开口说中文", 0, 0, 15, p["muted"])
    sub_x = (W - sub_w) / 2
    for tk in sub:
        tk.x += sub_x
        tk.y = GOLD_Y + 46
        t = 20.55
        tk.opa.keys = [[0.0, 0.0, "lin"]]
        tk.opa.set(t, 0.0, "lin")
        tk.opa.add(t + 0.5, 1.0, "out")
        tk.opa.hold(22.7)
        tk.opa.add(23.15, 0.0, "inout")
    all_toks += sub

    # ============ 5. 光标
    cpos = Track((PAD + tw + 30, TITLE_Y - 22))
    for tt, v in [
        (1.4, (PAD + tw + 34, L1_Y - 20)),
        (2.2, (PAD + 30, L2_Y - 20)),
        (4.5, (PAD + 150, FOURTH_Y - 22)),
        (6.3, (PAD + 176, FOURTH_Y - 14)),
        (9.6, (PAD + 236, FOURTH_Y - 24)),
        (11.7, (PAD + 210, FOURTH_Y - 6)),
        (12.3, (PAD + 250, FOURTH_Y + 30)),
        (19.3, (W / 2 + 40, GOLD_Y - 26)),
        (22.8, (W / 2 + 120, GOLD_Y - 26)),
    ]:
        cpos.set(tt, v)
    copa = Track(0.0)
    copa.set(0.9, 0.0, "lin")
    copa.add(1.3, 1.0, "out")
    copa.hold(11.6)
    copa.add(11.95, 0.0, "lin")       # 光标化成人形，光标本体消失
    copa.hold(20.6)
    copa.add(21.0, 1.0, "out")
    copa.hold(22.6)
    copa.add(23.1, 0.0, "inout")

    # ============ 6. Bug 虫
    bx = Track(bug_start_x)
    bx.set(9.55, bug_start_x, "lin")
    bx.add(10.55, PAD + 122.0, "out")
    bx.hold(11.55)
    bx.add(12.0, PAD + 96.0, "in")       # 往后缩一下
    bx.hold(19.4)
    bx.add(20.4, bug_start_x - 60, "in")
    b_opa = Track(0.0)
    b_opa.set(9.65, 0.0, "lin")
    b_opa.add(9.95, 1.0, "out")
    b_opa.hold(20.2)
    b_opa.add(20.45, 0.0, "in")

    # 虫子的上下起伏（爬行的感觉）
    wig = Track((0.0, 0.0))
    for i in range(30):
        t = 9.7 + i * 0.34
        wig.set(t, (0.0, (-1) ** i * 2.2), "inout")
    wig_opa = anim_tf("translate", wig, f_xy)

    # ============ 7. 收尾：整体轻微晃动
    shake = Track((0.0, 0.0))
    for t, v in [(13.82, (0.0, 0.0)), (13.88, (-5.0, 3.0)), (13.96, (4.0, -3.0)),
                 (14.04, (-3.0, 2.0)), (14.12, (2.0, -1.0)), (14.2, (0.0, 0.0)),
                 (14.42, (-4.0, 2.0)), (14.5, (3.0, -2.0)), (14.58, (0.0, 0.0))]:
        shake.set(t, v, "lin")
    shake_tf = anim_tf("translate", shake, f_xy)

    # ============ 拼装
    parts = []
    parts.append(f'<rect width="{W}" height="{H}" fill="{p["bg"]}"/>')

    # 右上角装饰：极淡的网格，暗示"这是一张页面"
    grid = [f'<g stroke="{p["rule"]}" stroke-width="1" opacity="0.35">']
    for gx_ in range(PAD, W - PAD + 1, 88):
        grid.append(f'<line x1="{gx_}" y1="18" x2="{gx_}" y2="{H - 18}"/>')
    for gy in range(24, H - 18 + 1, 46):
        grid.append(f'<line x1="{PAD}" y1="{gy}" x2="{W - PAD}" y2="{gy}"/>')
    grid.append("</g>")
    parts.append("".join(grid))

    parts.append(f'<g>{shake_tf}')
    # 标题区
    parts.append(f'<line x1="{PAD}" y1="{RULE_Y}" x2="{n(W - PAD)}" y2="{RULE_Y}" '
                 f'stroke="{p["rule"]}" stroke-width="1.5"/>')
    parts.append("".join(t.svg() for t in all_toks))
    parts.append("".join(marks))
    parts.append(gold_rule)
    parts.append("".join(gap))

    # 扫描 / 眼睛 / 角色 / 特效
    parts.append(build_scan(p))
    parts.append(build_eye(p))
    parts.append(f'<g>{wig_opa}{build_critter(p, bx, b_opa, 14.35)}</g>')
    parts.append(build_hero(p, PAD + 236.0, FOURTH_Y + 74.0, 13.85))
    parts.append(build_slash(p, PAD + 172.0, FOURTH_Y + 20.0, 13.82, 14.45))
    parts.append(build_flash(p, PAD + 176.0, FOURTH_Y + 18.0, 14.32))
    parts.append(build_particles(p, PAD + 176.0, FOURTH_Y + 22.0, 14.36))
    parts.append(build_cursor(p, cpos, copa))

    # 结尾整体淡出（回到开头那张白纸）
    end_opa = Track(0.0)
    end_opa.hold(22.9)
    end_opa.add(23.8, 1.0, "inout")
    parts.append(f'<rect width="{W}" height="{H}" fill="{p["bg"]}" opacity="0">'
                 f'{anim("opacity", end_opa, lambda v: f"{v:.3f}")}</rect>')
    parts.append("</g>")

    head = (
        '<!-- 🎉 你又来看源码了。这只蹲在角落里的猫送给你： /\\_/\\  ( =^･ω･^= )\n'
        '     整张图没有一个像素是手画的，也没有一行 JS —— 全部由 hero/make_hero.py\n'
        '     用 keyTimes + keySplines 算出来。改台词就改那个文件里的常量，然后重跑。 -->\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-labelledby="t d">\n'
        '<title id="t">陈启粤 · 给 AI 装一双眼睛</title>\n'
        '<desc id="d">一张会动的主页：文字逐字打出，一只巨大的眼睛睁开扫描全文，'
        '一行英文被逐字翻译成中文，一条 Bug 虫爬进来啃走了「看见」两个字，'
        '光标变成的小人挥刀把虫子劈成两半，被啃走的字飞回原位，最后浮现'
        '「人和 AI 一起做东西，最好玩。」</desc>\n'
        f'<style>text{{white-space:pre}}</style>\n'
    )
    return head + "\n".join(parts) + "\n</svg>\n"


def main():
    import pathlib
    here = pathlib.Path(__file__).resolve().parent
    for pal in ("light", "dark"):
        out = here / f"hero-{pal}.svg"
        out.write_text(build(pal, f"hero-{pal}"), encoding="utf-8")
        kb = out.stat().st_size / 1024
        print(f"{out.name}: {kb:.0f} KB")


if __name__ == "__main__":
    main()
