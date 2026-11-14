#!/usr/bin/env python3
"""
Fjellrune — an angular Nordic display typeface built entirely in Python.

Construction rules
  * Every glyph is constructed from straight, blade-cut strokes with mitred/bevelled
    vertices and chamfered ("axe-cut") terminals.
  * Diagonal strokes are optically thinned so they balance vertical staves and bars.
  * Every long stroke carries Fjellrune's signature "axe nick" — a sharp triangular
    bite cut into the edge of the stave.
  * Lowercase sits on a compact 480-unit runic x-height with faceted hex-bowls;
    capitals, figures, and ascenders rise to 700 units.

Bind-runes & Medallions
  Typing 1-3 letters between < and >, e.g. <RV>, <TH>, <OD>, sets them inside an
  octagonal rune-shield medallion (contextual alternates / standard ligatures).

Character set
  Google Fonts Latin Core (Western, Central, and Eastern European Latin, punctuation,
  currency symbols, combining marks) plus the Elder Futhark & Nordic Runic block
  (U+16A0–U+16F0) and bind-rune medallions.

Build
  This script writes the UFO source in sources/ufo/Fjellrune-Regular.ufo;
  gftools builder compiles and hints it into fonts/ttf and fonts/webfonts.
  Run sources/build.sh to do both.
  Usage:  python3 sources/build_fjellrune.py [--ufo sources/ufo]
"""
import math
import os
import shutil
import sys
import unicodedata

import numpy as np
import pathops
from pathops import Path, PathOp
from fontTools.agl import UV2AGL
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.transformPen import TransformPen

# --------------------------------------------------------------------------------------
# Design constants (1000 UPM font-unit coordinate space)
# --------------------------------------------------------------------------------------
UPM = 1000
CAP = 700           # capital & figure height
XH = 480            # lowercase x-height
ASC = 730           # ascender height (b, d, f, h, k, l, thorn)
DESC = -210         # descender depth (g, j, p, q, y, thorn)
W = 92              # base stroke width for capitals/figures
W_LC = 82           # base stroke width for lowercase
W_ACC = 68          # accent & mark stroke width
W_SYM = 76          # symbol stroke width
SB = 44             # standard sidebearing

NOTCH_MIN = 330     # minimum segment length that receives the signature axe nick
NOTCH_DEPTH = 0.28  # nick depth as fraction of stroke width
NOTCH_HALF = 26     # half-width of the nick opening along the stroke
MITRE_LIMIT = 2.05  # bevels sharp outer corners so apexes sit cleanly near cap/base

FAMILY = "Fjellrune"
VERSION = "2.000"
REPO_URL = "https://github.com/q78717/font-fjellrune"
COPYRIGHT = f"Copyright 2026 The Fjellrune Project Authors ({REPO_URL})"


def union(a, b):
    return pathops.op(a, b, PathOp.UNION)


def difference(a, b):
    return pathops.op(a, b, PathOp.DIFFERENCE)


def intersect(a, b):
    return pathops.op(a, b, PathOp.INTERSECTION)


def path_bounds(path):
    bp = BoundsPen(None)
    path.draw(bp)
    return bp.bounds


def signed_area(path):
    ap = AreaPen()
    path.draw(ap)
    return ap.value


def _seg_w(dx, dy, w):
    """Optical thinning: diagonals between 18° and 72° are thinned by 9%."""
    ang = abs(math.degrees(math.atan2(dy, dx))) % 90
    return w * 0.91 if 18 < ang < 72 else w


def _line_intersect(p1, d1, p2, d2):
    cross = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(cross) < 1e-6:
        return ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0), 0.0
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    t = (dx * d2[1] - dy * d2[0]) / cross
    return (p1[0] + t * d1[0], p1[1] + t * d1[1]), t


def stroke_poly(pts, w=W, c0="c", c1="c", closed=False, notch=True):
    """Convert a polyline (or closed polygon) into a blade-cut outline Path."""
    if closed and len(pts) > 1 and pts[0] == pts[-1]:
        pts = list(pts[:-1])
    n = len(pts)
    if n < 2:
        return Path()
    dirs, norms, hs, lens = [], [], [], []
    num_segs = n if closed else n - 1
    for i in range(num_segs):
        p0, p1 = pts[i], pts[(i + 1) % n]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if L < 1e-6:
            L = 1e-6
        ux, uy = dx / L, dy / L
        dirs.append((ux, uy))
        norms.append((-uy, ux))
        hs.append(_seg_w(dx, dy, w) / 2.0)
        lens.append(L)

    def join_side(i, sign):
        s0 = (i - 1) % num_segs
        s1 = i
        P = pts[i]
        d0, d1 = dirs[s0], dirs[s1]
        n0 = (norms[s0][0] * sign, norms[s0][1] * sign)
        n1 = (norms[s1][0] * sign, norms[s1][1] * sign)
        h0, h1 = hs[s0], hs[s1]
        p_a = (P[0] + n0[0] * h0, P[1] + n0[1] * h0)
        p_b = (P[0] + n1[0] * h1, P[1] + n1[1] * h1)
        ip, _ = _line_intersect(p_a, d0, p_b, d1)
        dist = math.hypot(ip[0] - P[0], ip[1] - P[1])
        h_avg = (h0 + h1) / 2.0
        turn = d0[0] * d1[1] - d0[1] * d1[0]
        is_outside = (turn * sign) < 0
        if is_outside and dist > MITRE_LIMIT * h_avg:
            return [p_a, p_b]
        if not is_outside and dist > min(lens[s0], lens[s1]) * 0.72:
            return [p_a, p_b]
        return [ip]

    def cap_end(P, ux, uy, nx, ny, h, kind):
        if kind == "f":
            return (P[0] + nx * h, P[1] + ny * h), (P[0] - nx * h, P[1] - ny * h)
        if kind == "s":
            return (
                (P[0] + nx * h + ux * h, P[1] + ny * h + uy * h),
                (P[0] - nx * h + ux * h, P[1] - ny * h + uy * h),
            )
        # "c": axe-chamfered terminal (~19 deg slant, well clear of semi-vertical/horizontal check)
        if abs(ux) < 0.05 or abs(uy) < 0.05:
            e_l, e_r = h * 0.35, -h * 0.35
        else:
            e_l, e_r = h * 0.30, -h * 0.15
        return (
            (P[0] + nx * h + ux * e_l, P[1] + ny * h + uy * e_l),
            (P[0] - nx * h + ux * e_r, P[1] - ny * h + uy * e_r),
        )

    left_pts, right_pts = [], []
    for i in range(num_segs):
        if i == 0 and not closed:
            l0, r0 = cap_end(pts[0], -dirs[0][0], -dirs[0][1], norms[0][0], norms[0][1], hs[0], c0)
            left_pts.append(l0)
            right_pts.append(r0)
        else:
            left_pts.extend(join_side(i, 1))
            right_pts.extend(join_side(i, -1))

        if notch and lens[i] >= NOTCH_MIN:
            # Skip notch if the next vertex is a sharp inside turn on +n that could clip the nick
            skip_nick = False
            if i + 1 < num_segs or closed:
                nxt = (i + 1) % num_segs
                turn_nxt = dirs[i][0] * dirs[nxt][1] - dirs[i][1] * dirs[nxt][0]
                if turn_nxt > 0.35 and lens[i] < 540:
                    skip_nick = True
            if not skip_nick:
                p0, p1 = pts[i], pts[(i + 1) % n]
                dx, dy = p1[0] - p0[0], p1[1] - p0[1]
                ux, uy = dirs[i]
                nx, ny = norms[i]
                h = hs[i]
                t = 0.56
                mx, my = p0[0] + dx * t, p0[1] + dy * t
                depth = 2.0 * h * NOTCH_DEPTH
                nh = min(NOTCH_HALF, lens[i] * 0.12)
                left_pts.append((mx + nx * h - ux * nh, my + ny * h - uy * nh))
                left_pts.append((mx + nx * (h - depth), my + ny * (h - depth)))
                left_pts.append((mx + nx * h + ux * nh, my + ny * h + uy * nh))

    if not closed:
        l1, r1 = cap_end(pts[-1], dirs[-1][0], dirs[-1][1], norms[-1][0], norms[-1][1], hs[-1], c1)
        left_pts.append(l1)
        right_pts.append(r1)
        path = Path()
        all_pts = left_pts + right_pts[::-1]
        path.moveTo(*all_pts[0])
        for q in all_pts[1:]:
            path.lineTo(*q)
        path.close()
        return pathops.simplify(path)
    else:
        p1, p2 = Path(), Path()
        p1.moveTo(*left_pts[0])
        for q in left_pts[1:]:
            p1.lineTo(*q)
        p1.close()
        p2.moveTo(*right_pts[0])
        for q in right_pts[1:]:
            p2.lineTo(*q)
        p2.close()
        b1, b2 = path_bounds(p1), path_bounds(p2)
        if (b1[2] - b1[0]) > (b2[2] - b2[0]):
            return difference(pathops.simplify(p1), pathops.simplify(p2))
        return difference(pathops.simplify(p2), pathops.simplify(p1))


def diamond_path(cx, cy, rx, ry=None):
    if ry is None:
        ry = rx * 1.15
    p = Path()
    p.moveTo(cx, cy + ry)
    p.lineTo(cx + rx, cy)
    p.lineTo(cx, cy - ry)
    p.lineTo(cx - rx, cy)
    p.close()
    return p


# --------------------------------------------------------------------------------------
# Glyph construction kit
# --------------------------------------------------------------------------------------
class G:
    """Collects angular strokes and diamond dots in 1000-UPM space."""

    def __init__(self, k=1.0, sx=1, sy=1, ox=0.0, oy=0.0, w=W, notch=True, skel=None):
        self.k = k
        self.sx = sx
        self.sy = sy
        self.ox = ox
        self.oy = oy
        self.w = w
        self.notch = notch
        self.paths = []
        self.cuts = []
        self.skel = skel if skel is not None else []
        self.children = []

    def T(self, p):
        return (self.ox + self.sx * self.k * p[0], self.oy + self.sy * self.k * p[1])

    def flipped(self, sx=1, sy=1, cx=260.0, cy=350.0):
        """Return a view that mirrors around (cx, cy)."""
        nx = self.ox + self.sx * self.k * cx * (1 - sx)
        ny = self.oy + self.sy * self.k * cy * (1 - sy)
        child = G(
            k=self.k,
            sx=self.sx * sx,
            sy=self.sy * sy,
            ox=nx,
            oy=ny,
            w=self.w,
            notch=self.notch,
            skel=self.skel,
        )
        self.children.append(child)
        return child

    def part(self, dx=0.0, dy=0.0, k_mul=1.0, sx=1, sy=1, w=None, notch=None):
        child = G(
            k=self.k * k_mul,
            sx=self.sx * sx,
            sy=self.sy * sy,
            ox=self.ox + self.sx * self.k * dx,
            oy=self.oy + self.sy * self.k * dy,
            w=self.w if w is None else w,
            notch=self.notch if notch is None else notch,
            skel=self.skel,
        )
        self.children.append(child)
        return child

    def poly(self, pts, c0="c", c1="c", w=None, notch=None, closed=False):
        P = [self.T(p) for p in pts]
        if self.sx * self.sy < 0:
            P = P[::-1]
            c0, c1 = c1, c0
        w_use = (self.w if w is None else w) * self.k
        n_use = (self.notch and w is None and self.k >= 0.75) if notch is None else notch
        self.skel.append(("p" if not closed else "loop", list(P)))
        self.paths.append(stroke_poly(P, w=w_use, c0=c0, c1=c1, closed=closed, notch=n_use))

    def line(self, p0, p1, c0="c", c1="c", w=None, notch=None):
        self.poly([p0, p1], c0=c0, c1=c1, w=w, notch=notch, closed=False)

    def loop(self, pts, w=None, notch=None):
        self.poly(pts, w=w, notch=notch, closed=True)

    def dot(self, c, rx=52, ry=62):
        cx, cy = self.T(c)
        r_x = rx * self.k
        r_y = ry * self.k
        self.skel.append(("d", cx, cy, r_x, r_y))
        self.paths.append(diamond_path(cx, cy, r_x, r_y))

    def box_cut(self, x0, y0, x1, y1):
        a, b = self.T((x0, y0)), self.T((x1, y1))
        lx, rx = min(a[0], b[0]), max(a[0], b[0])
        by, ty = min(a[1], b[1]), max(a[1], b[1])
        p = Path()
        p.moveTo(lx, by)
        p.lineTo(rx, by)
        p.lineTo(rx, ty)
        p.lineTo(lx, ty)
        p.close()
        self.cuts.append(p)

    def outline(self):
        out = Path()
        for p in self.paths:
            out = union(out, p)
        for cut in self.cuts:
            out = difference(out, cut)
        for ch in self.children:
            co = ch.outline()
            if path_bounds(co) is not None:
                out = union(out, co)
        return pathops.simplify(out)

    def empty(self):
        return not (self.paths or any(not c.empty() for c in self.children))


# --------------------------------------------------------------------------------------
# Glyph registry & shared primitives
# --------------------------------------------------------------------------------------
GLYPHS = {}   # name -> (codepoint, function)


def glyph(name, uni=None):
    def deco(f):
        GLYPHS[name] = (uni, f)
        return f
    return deco


def lc_hex_bowl(g, x0=55, x1=395, y0=0, y1=XH, w=W_LC):
    """Faceted 6-vertex runic bowl for lowercase letters (a, b, d, g, o, p, q)."""
    xm = (x0 + x1) / 2.0
    ym = (y0 + y1) / 2.0
    dy = (y1 - y0) * 0.22
    g.loop(
        [
            (xm, y1),
            (x1, y1 - dy),
            (x1, y0 + dy),
            (xm, y0),
            (x0, y0 + dy),
            (x0, y1 - dy),
        ],
        w=w,
        notch=False,
    )


def cap_hex_loop(g, x0=55, x1=485, y0=0, y1=CAP, w=W, notch=True):
    """Faceted 6-vertex runic shield/loop for O, Q, 0."""
    xm = (x0 + x1) / 2.0
    dy = (y1 - y0) * 0.24
    g.loop(
        [
            (xm, y1),
            (x1, y1 - dy),
            (x1, y0 + dy),
            (xm, y0),
            (x0, y0 + dy),
            (x0, y1 - dy),
        ],
        w=w,
        notch=notch,
    )


# --------------------------------------------------------------------------------------
# Capitals (A–Z)
# --------------------------------------------------------------------------------------
@glyph("A", 0x41)
def cap_A(g):
    g.poly([(40, 0), (270, 690), (500, 0)])
    g.line((125, 235), (415, 235), c0="f", c1="f", notch=False)


@glyph("B", 0x42)
def cap_B(g):
    g.line((60, 0), (60, CAP))
    g.poly([(60, CAP), (455, 545), (60, 360)], c0="f", c1="f")
    g.poly([(60, 360), (475, 175), (60, 0)], c0="f", c1="f")


@glyph("C", 0x43)
def cap_C(g):
    g.poly([(465, 650), (190, 665), (65, 350), (190, 35), (465, 50)])


@glyph("D", 0x44)
def cap_D(g):
    g.line((60, 0), (60, CAP))
    g.poly([(60, CAP), (430, 560), (485, 350), (430, 140), (60, 0)], c0="f", c1="f")


@glyph("E", 0x45)
def cap_E(g):
    g.poly([(465, 660), (60, 660), (60, 40), (470, 40)])
    g.line((60, 360), (390, 360), c0="f", c1="c", notch=False)


@glyph("F", 0x46)
def cap_F(g):
    g.poly([(60, 0), (60, 660), (465, 660)])
    g.line((60, 360), (385, 360), c0="f", c1="c", notch=False)


@glyph("G", 0x47)
def cap_G(g):
    g.poly([(465, 650), (190, 665), (65, 350), (190, 35), (465, 45), (465, 305), (295, 305)])


@glyph("H", 0x48)
def cap_H(g):
    g.line((60, 0), (60, CAP))
    g.line((490, 0), (490, CAP))
    g.line((60, 405), (490, 315), c0="f", c1="f")


@glyph("I", 0x49)
def cap_I(g):
    g.line((130, 0), (130, CAP))


@glyph("J", 0x4A)
def cap_J(g):
    g.poly([(380, CAP), (380, 155), (175, 20), (45, 135)])


@glyph("K", 0x4B)
def cap_K(g):
    g.line((60, 0), (60, CAP))
    g.line((60, 335), (475, CAP), c0="f", c1="c")
    g.line((165, 420), (490, 0), c0="f", c1="c")


@glyph("L", 0x4C)
def cap_L(g):
    g.poly([(60, CAP), (60, 40), (460, 40)])


@glyph("M", 0x4D)
def cap_M(g):
    g.poly([(60, 0), (60, 690), (305, 275), (550, 690), (550, 0)])


@glyph("N", 0x4E)
def cap_N(g):
    g.poly([(60, 0), (60, 690), (490, 10), (490, CAP)])


@glyph("O", 0x4F)
def cap_O(g):
    cap_hex_loop(g, 55, 485, 10, 690)


@glyph("P", 0x50)
def cap_P(g):
    g.line((60, 0), (60, CAP))
    g.poly([(60, CAP), (470, 520), (60, 335)], c0="f", c1="f")


@glyph("Q", 0x51)
def cap_Q(g):
    cap_hex_loop(g, 55, 485, 10, 690)
    g.line((320, 185), (525, -75), c0="c", c1="c", notch=False)


@glyph("R", 0x52)
def cap_R(g):
    g.line((60, 0), (60, CAP))
    g.poly([(60, CAP), (470, 525), (60, 345)], c0="f", c1="f")
    g.line((205, 405), (490, 0), c0="f", c1="c")


@glyph("S", 0x53)
def cap_S(g):
    g.poly([(450, 645), (175, 665), (75, 515), (455, 215), (345, 35), (65, 55)])


@glyph("T", 0x54)
def cap_T(g):
    g.poly([(40, 595), (275, 685), (510, 595)])
    g.line((275, 680), (275, 0), c0="f", c1="c")


@glyph("U", 0x55)
def cap_U(g):
    g.poly([(60, CAP), (60, 195), (275, 15), (490, 195), (490, CAP)])


@glyph("V", 0x56)
def cap_V(g):
    g.poly([(45, CAP), (275, 10), (505, CAP)])


@glyph("W", 0x57)
def cap_W(g):
    g.poly([(35, CAP), (165, 10), (315, 445), (465, 10), (595, CAP)])


@glyph("X", 0x58)
def cap_X(g):
    g.line((50, CAP), (500, 0))
    g.line((500, CAP), (50, 0))


@glyph("Y", 0x59)
def cap_Y(g):
    g.poly([(45, CAP), (275, 330), (505, CAP)])
    g.line((275, 345), (275, 0), c0="f", c1="c")


@glyph("Z", 0x5A)
def cap_Z(g):
    g.poly([(70, 660), (475, 660), (75, 40), (485, 40)])


# --------------------------------------------------------------------------------------
# Figures (0–9, all CAP=700 tall)
# --------------------------------------------------------------------------------------
@glyph("zero", 0x30)
def fig_zero(g):
    cap_hex_loop(g, 55, 465, 10, 690)
    g.line((150, 175), (370, 525), c0="f", c1="f", w=68, notch=False)


@glyph("one", 0x31)
def fig_one(g):
    g.poly([(95, 535), (275, 685), (275, 40)], c1="f")
    g.line((105, 40), (445, 40), notch=False)


@glyph("two", 0x32)
def fig_two(g):
    g.poly([(65, 550), (265, 685), (465, 530), (75, 40), (480, 40)])


@glyph("three", 0x33)
def fig_three(g):
    g.poly([(80, 660), (455, 660), (245, 395), (465, 200), (285, 25), (65, 65)])


@glyph("four", 0x34)
def fig_four(g):
    g.poly([(365, 685), (55, 215), (495, 215)])
    g.line((365, 685), (365, 0), c0="f", c1="c")


@glyph("five", 0x35)
def fig_five(g):
    g.poly([(445, 660), (95, 660), (95, 385), (445, 305), (445, 115), (255, 20), (65, 70)])


@glyph("six", 0x36)
def fig_six(g):
    g.poly([(415, 685), (90, 435), (90, 135), (275, 15), (455, 135), (455, 325), (275, 415), (90, 325)], c1="f")


@glyph("seven", 0x37)
def fig_seven(g):
    g.poly([(70, 660), (465, 660), (195, 0)], notch=False)
    g.line((135, 345), (425, 345), notch=False)


@glyph("eight", 0x38)
def fig_eight(g):
    g.loop([(265, 690), (445, 530), (265, 365), (85, 530)], notch=False)
    g.loop([(265, 365), (465, 185), (265, 10), (65, 185)], notch=False)


@glyph("nine", 0x39)
def fig_nine(g):
    g.poly([(125, 15), (450, 265), (450, 565), (265, 685), (85, 565), (85, 375), (265, 285), (450, 375)], c1="f")


# --------------------------------------------------------------------------------------
# Lowercase (a–z)
# --------------------------------------------------------------------------------------
@glyph("a", 0x61)
def lc_a(g):
    lc_hex_bowl(g, 50, 375, 8, XH - 8)
    g.line((375, XH), (375, 0), w=W_LC)


@glyph("b", 0x62)
def lc_b(g):
    lc_hex_bowl(g, 60, 390, 8, XH - 8)
    g.line((60, 0), (60, ASC), w=W_LC)


@glyph("c", 0x63)
def lc_c(g):
    g.poly([(375, 435), (175, 450), (55, 240), (175, 30), (375, 45)], w=W_LC, notch=False)


@glyph("d", 0x64)
def lc_d(g):
    lc_hex_bowl(g, 50, 380, 8, XH - 8)
    g.line((380, 0), (380, ASC), w=W_LC)


@glyph("e", 0x65)
def lc_e(g):
    g.poly([(65, 245), (385, 245), (385, 380), (225, 460), (60, 360), (60, 120), (225, 20), (380, 55)], w=W_LC, notch=False)


@glyph("f", 0x66)
def lc_f(g):
    g.poly([(335, 695), (195, 715), (125, 610), (125, 0)], w=W_LC)
    g.line((35, 440), (295, 440), w=W_LC, notch=False)


@glyph("g", 0x67)
def lc_g(g):
    lc_hex_bowl(g, 50, 380, 8, XH - 8)
    g.poly([(380, XH), (380, -105), (225, DESC), (75, -155)], w=W_LC)


@glyph("h", 0x68)
def lc_h(g):
    g.line((60, 0), (60, ASC), w=W_LC)
    g.poly([(60, 355), (245, 460), (385, 365), (385, 0)], c0="f", w=W_LC, notch=False)


@glyph("i", 0x69)
def lc_i(g):
    g.line((110, 0), (110, XH), w=W_LC, notch=False)
    g.dot((110, 625), 48, 56)


@glyph("j", 0x6A)
def lc_j(g):
    g.poly([(225, XH), (225, -110), (105, DESC), (20, -145)], w=W_LC)
    g.dot((225, 625), 48, 56)


@glyph("k", 0x6B)
def lc_k(g):
    g.line((60, 0), (60, ASC), w=W_LC)
    g.line((60, 225), (375, XH), c0="f", w=W_LC, notch=False)
    g.line((145, 290), (390, 0), c0="f", w=W_LC, notch=False)


@glyph("l", 0x6C)
def lc_l(g):
    g.poly([(105, ASC), (105, 85), (235, 20)], w=W_LC)


@glyph("m", 0x6D)
def lc_m(g):
    g.line((55, 0), (55, XH), w=W_LC, notch=False)
    g.poly([(55, 360), (195, 460), (315, 365), (315, 0)], c0="f", w=W_LC, notch=False)
    g.poly([(315, 360), (455, 460), (575, 365), (575, 0)], c0="f", w=W_LC, notch=False)


@glyph("n", 0x6E)
def lc_n(g):
    g.line((60, 0), (60, XH), w=W_LC, notch=False)
    g.poly([(60, 355), (245, 460), (385, 365), (385, 0)], c0="f", w=W_LC, notch=False)


@glyph("o", 0x6F)
def lc_o(g):
    lc_hex_bowl(g, 55, 385, 8, XH - 8)


@glyph("p", 0x70)
def lc_p(g):
    lc_hex_bowl(g, 60, 390, 8, XH - 8)
    g.line((60, XH), (60, DESC), w=W_LC)


@glyph("q", 0x71)
def lc_q(g):
    lc_hex_bowl(g, 50, 380, 8, XH - 8)
    g.line((380, XH), (380, DESC), w=W_LC)


@glyph("r", 0x72)
def lc_r(g):
    g.line((60, 0), (60, XH), w=W_LC, notch=False)
    g.poly([(60, 345), (215, 460), (335, 405)], c0="f", w=W_LC, notch=False)


@glyph("s", 0x73)
def lc_s(g):
    g.poly([(355, 435), (155, 455), (65, 350), (360, 145), (265, 25), (55, 45)], w=W_LC, notch=False)


@glyph("t", 0x74)
def lc_t(g):
    g.poly([(135, 645), (135, 85), (285, 20)], w=W_LC)
    g.line((40, 440), (300, 440), w=W_LC, notch=False)


@glyph("u", 0x75)
def lc_u(g):
    g.poly([(60, XH), (60, 115), (200, 20), (380, 125)], c1="f", w=W_LC, notch=False)
    g.line((380, XH), (380, 0), w=W_LC, notch=False)


@glyph("v", 0x76)
def lc_v(g):
    g.poly([(40, XH), (215, 10), (390, XH)], w=W_LC, notch=False)


@glyph("w", 0x77)
def lc_w(g):
    g.poly([(35, XH), (145, 10), (275, 335), (405, 10), (515, XH)], w=W_LC, notch=False)


@glyph("x", 0x78)
def lc_x(g):
    g.line((45, XH), (385, 0), w=W_LC, notch=False)
    g.line((385, XH), (45, 0), w=W_LC, notch=False)


@glyph("y", 0x79)
def lc_y(g):
    g.line((40, XH), (215, 20), c1="f", w=W_LC, notch=False)
    g.poly([(390, XH), (215, 20), (125, DESC)], w=W_LC)


@glyph("z", 0x7A)
def lc_z(g):
    g.poly([(55, 445), (375, 445), (55, 35), (385, 35)], w=W_LC, notch=False)


# --------------------------------------------------------------------------------------
# Punctuation & ASCII Symbols
# --------------------------------------------------------------------------------------
@glyph("space", 0x20)
def gl_space(g):
    pass


@glyph("exclam", 0x21)
def gl_exclam(g):
    g.line((115, CAP), (115, 210), notch=True)
    g.dot((115, 62), 50, 60)


@glyph("quotedbl", 0x22)
def gl_quotedbl(g):
    g.line((85, CAP), (60, 470), w=W_SYM, notch=False)
    g.line((235, CAP), (210, 470), w=W_SYM, notch=False)


@glyph("numbersign", 0x23)
def gl_numbersign(g):
    g.line((155, 60), (215, 640), w=W_SYM, notch=False)
    g.line((335, 60), (395, 640), w=W_SYM, notch=False)
    g.line((55, 245), (485, 245), w=W_SYM, notch=False)
    g.line((65, 445), (495, 445), w=W_SYM, notch=False)


@glyph("dollar", 0x24)
def gl_dollar(g):
    cap_S(g.part(0, 0, 1.0))
    g.line((265, 760), (265, -60), w=72, notch=False)


@glyph("percent", 0x25)
def gl_percent(g):
    g.line((75, 10), (465, 690), w=W_SYM, notch=False)
    g.loop([(145, 680), (235, 565), (145, 450), (55, 565)], w=64, notch=False)
    g.loop([(395, 250), (485, 135), (395, 20), (305, 135)], w=64, notch=False)


@glyph("ampersand", 0x26)
def gl_ampersand(g):
    g.poly([(465, 295), (225, 25), (65, 185), (295, 475), (365, 585), (235, 680), (105, 575), (175, 435), (480, 0)], w=W_LC)


@glyph("quotesingle", 0x27)
def gl_quotesingle(g):
    g.line((110, CAP), (85, 470), w=W_SYM, notch=False)


@glyph("parenleft", 0x28)
def gl_parenleft(g):
    g.poly([(245, 730), (95, 480), (95, 180), (245, -70)], w=W_SYM)


@glyph("parenright", 0x29)
def gl_parenright(g):
    g.poly([(75, 730), (225, 480), (225, 180), (75, -70)], w=W_SYM)


@glyph("asterisk", 0x2A)
def gl_asterisk(g):
    cx, cy, r = 210, 515, 155
    for deg in (90, 30, 150):
        rad = math.radians(deg)
        dx, dy = r * math.cos(rad), r * math.sin(rad)
        g.line((cx - dx, cy - dy), (cx + dx, cy + dy), w=60, notch=False)


@glyph("plus", 0x2B)
def gl_plus(g):
    g.line((55, 290), (425, 290), w=W_SYM, notch=False)
    g.line((240, 105), (240, 475), w=W_SYM, notch=False)


@glyph("comma", 0x2C)
def gl_comma(g):
    g.dot((115, 62), 50, 60)
    g.line((125, 62), (65, -115), w=66, notch=False)


@glyph("hyphen", 0x2D)
def gl_hyphen(g):
    g.line((55, 275), (325, 275), w=W_SYM, notch=False)


@glyph("period", 0x2E)
def gl_period(g):
    g.dot((115, 62), 50, 60)


@glyph("slash", 0x2F)
def gl_slash(g):
    g.line((55, -40), (365, 740), w=W_SYM)


@glyph("colon", 0x3A)
def gl_colon(g):
    g.dot((115, 62), 50, 60)
    g.dot((115, 395), 50, 60)


@glyph("semicolon", 0x3B)
def gl_semicolon(g):
    gl_comma(g)
    g.dot((115, 395), 50, 60)


@glyph("less", 0x3C)
def gl_less(g):
    g.poly([(395, 485), (85, 290), (395, 95)], w=W_SYM, notch=False)


@glyph("equal", 0x3D)
def gl_equal(g):
    g.line((55, 375), (425, 375), w=W_SYM, notch=False)
    g.line((55, 205), (425, 205), w=W_SYM, notch=False)


@glyph("greater", 0x3E)
def gl_greater(g):
    g.poly([(85, 485), (395, 290), (85, 95)], w=W_SYM, notch=False)


@glyph("question", 0x3F)
def gl_question(g):
    g.poly([(65, 555), (225, 680), (415, 560), (225, 335), (225, 210)])
    g.dot((225, 62), 50, 60)


@glyph("at", 0x40)
def gl_at(g):
    lc_hex_bowl(g, 165, 365, 175, 445, w=58)
    g.poly(
        [
            (365, 435),
            (365, 185),
            (465, 185),
            (515, 295),
            (515, 495),
            (355, 665),
            (165, 665),
            (45, 495),
            (45, 195),
            (165, 25),
            (425, 25),
        ],
        w=60,
        notch=False,
    )


@glyph("bracketleft", 0x5B)
def gl_bracketleft(g):
    g.poly([(255, 720), (95, 720), (95, -60), (255, -60)], w=W_SYM)


@glyph("backslash", 0x5C)
def gl_backslash(g):
    g.line((365, -40), (55, 740), w=W_SYM)


@glyph("bracketright", 0x5D)
def gl_bracketright(g):
    g.poly([(75, 720), (235, 720), (235, -60), (75, -60)], w=W_SYM)


@glyph("asciicircum", 0x5E)
def gl_asciicircum(g):
    g.poly([(60, 445), (220, 680), (380, 445)], w=W_SYM, notch=False)


@glyph("underscore", 0x5F)
def gl_underscore(g):
    g.line((20, -90), (460, -90), w=W_SYM, notch=False)


@glyph("grave", 0x60)
def gl_grave(g):
    g.line((95, 695), (225, 545), w=W_ACC, notch=False)


@glyph("braceleft", 0x7B)
def gl_braceleft(g):
    g.poly([(265, 720), (155, 645), (155, 405), (65, 330), (155, 255), (155, 15), (265, -60)], w=W_SYM, notch=False)


@glyph("bar", 0x7C)
def gl_bar(g):
    g.line((130, -80), (130, 760), w=W_SYM)


@glyph("braceright", 0x7D)
def gl_braceright(g):
    g.poly([(65, 720), (175, 645), (175, 405), (265, 330), (175, 255), (175, 15), (65, -60)], w=W_SYM, notch=False)


@glyph("asciitilde", 0x7E)
def gl_asciitilde(g):
    g.poly([(55, 255), (165, 355), (315, 225), (425, 325)], w=W_SYM, notch=False)


@glyph(".notdef")
def gl_notdef(g):
    g.loop([(60, 40), (440, 40), (440, 660), (60, 660)], w=68, notch=False)
    g.line((60, 40), (440, 660), c0="f", c1="f", w=54, notch=False)
    g.line((440, 40), (60, 660), c0="f", c1="f", w=54, notch=False)


# --------------------------------------------------------------------------------------
# Combining Marks & Spacing Accents (Google Fonts Latin Core)
# --------------------------------------------------------------------------------------
LC_TOP = 540
CAP_TOP = 755
LC_BOT = -25
CAP_BOT = -25
TALL = 560
MARK_CENTER = 220

MARKS = {}   # name -> dict(draw, kind, uni, spacing=(name, uni))


def mark(name, kind, uni=None, spacing=None):
    def deco(f):
        MARKS[name] = dict(draw=f, kind=kind, uni=uni, spacing=spacing)
        return f
    return deco


@mark("acutecomb", "top", 0x0301, ("acute", 0x00B4))
def m_acute(g):
    g.line((-45, 0), (65, 135), w=W_ACC, notch=False)


@mark("gravecomb", "top", 0x0300, ("grave_", None))
def m_grave(g):
    g.line((45, 0), (-65, 135), w=W_ACC, notch=False)


@mark("circumflexcomb", "top", 0x0302, ("circumflex", 0x02C6))
def m_circumflex(g):
    g.poly([(-115, 5), (0, 130), (115, 5)], w=W_ACC, notch=False)


@mark("caroncomb", "top", 0x030C, ("caron", 0x02C7))
def m_caron(g):
    g.poly([(-115, 130), (0, 5), (115, 130)], w=W_ACC, notch=False)


@mark("tildecomb", "top", 0x0303, ("tilde", 0x02DC))
def m_tilde(g):
    g.poly([(-125, 35), (-40, 115), (40, 35), (125, 115)], w=62, notch=False)


@mark("macroncomb", "top", 0x0304, ("macron", 0x00AF))
def m_macron(g):
    g.line((-125, 55), (125, 55), w=W_ACC, notch=False)


@mark("brevecomb", "top", 0x0306, ("breve", 0x02D8))
def m_breve(g):
    g.poly([(-115, 125), (-45, 20), (45, 20), (115, 125)], w=64, notch=False)


@mark("dotaccentcomb", "top", 0x0307, ("dotaccent", 0x02D9))
def m_dot(g):
    g.dot((0, 60), 46, 54)


@mark("dieresiscomb", "top", 0x0308, ("dieresis", 0x00A8))
def m_dieresis(g):
    g.dot((-85, 60), 44, 52)
    g.dot((85, 60), 44, 52)


@mark("ringcomb", "top", 0x030A, ("ring", 0x02DA))
def m_ring(g):
    g.loop([(0, 165), (85, 80), (0, -5), (-85, 80)], w=56, notch=False)


@mark("hungarumlautcomb", "top", 0x030B, ("hungarumlaut", 0x02DD))
def m_hungarumlaut(g):
    g.line((-95, 0), (-15, 135), w=60, notch=False)
    g.line((15, 0), (95, 135), w=60, notch=False)


@mark("commaturnedabovecomb", "top", 0x0312)
def m_commaturned(g):
    g.dot((0, 50), 38, 44)
    g.line((-10, 55), (35, 155), w=54, notch=False)


@mark("caroncomb.alt", "caronalt")
def m_caronalt(g):
    g.line((15, 145), (-15, 0), w=60, notch=False)


@mark("cedillacomb", "bottom", 0x0327, ("cedilla", 0x00B8))
def m_cedilla(g):
    g.poly([(0, 25), (0, -45), (55, -105), (-15, -165), (-65, -135)], w=56, notch=False)


@mark("commaaccentcomb", "bottom", 0x0326)
def m_commabelow(g):
    g.dot((0, -45), 38, 44)
    g.line((10, -45), (-35, -155), w=54, notch=False)


@mark("ogonekcomb", "ogonek", 0x0328, ("ogonek", 0x02DB))
def m_ogonek(g):
    g.poly([(0, 25), (-55, -85), (15, -155), (85, -115)], w=56, notch=False)


def mark_attach_y(kind):
    return {"top": LC_TOP, "caronalt": LC_TOP, "bottom": LC_BOT, "ogonek": LC_BOT}[kind]


def draw_mark(g, name, x, y):
    MARKS[name]["draw"](g.part(x, y, w=W_ACC, notch=False))


def _register_marks():
    for name, m in MARKS.items():
        y = mark_attach_y(m["kind"])
        fn = (lambda nm, yy: (lambda g: draw_mark(g, nm, 0.0, yy)))(name, y)
        GLYPHS[name] = (m["uni"], fn)
        if m["spacing"]:
            sname, suni = m["spacing"]
            if suni is not None:
                GLYPHS[sname] = (suni, fn)


# --------------------------------------------------------------------------------------
# Special Latin Letters (Nordic & Pan-European)
# --------------------------------------------------------------------------------------
@glyph("dotlessi", 0x0131)
def gl_dotlessi(g):
    g.line((110, 0), (110, XH), w=W_LC, notch=False)


@glyph("dotlessj", 0x0237)
def gl_dotlessj(g):
    g.poly([(225, XH), (225, -110), (105, DESC), (20, -145)], w=W_LC)


@glyph("AE", 0x00C6)
def gl_AE(g):
    g.poly([(35, 0), (325, 660), (580, 660)])
    g.poly([(325, 660), (325, 40), (585, 40)], c0="f")
    g.line((325, 360), (525, 360), c0="f", notch=False)
    g.line((125, 235), (325, 235), c0="f", c1="f", notch=False)


@glyph("OE", 0x0152)
def gl_OE(g):
    g.poly([(345, 660), (175, 660), (55, 350), (175, 40), (345, 40)])
    g.poly([(345, 660), (345, 40), (595, 40)])
    g.line((345, 660), (590, 660), c0="f", notch=False)
    g.line((345, 360), (535, 360), c0="f", notch=False)


@glyph("ae", 0x00E6)
def gl_ae(g):
    lc_hex_bowl(g, 45, 325, 8, XH - 8)
    g.line((325, 8), (325, XH - 8), w=W_LC, notch=False)
    g.poly([(325, 245), (585, 245), (585, 385), (455, 460), (325, 365)], c0="f", w=W_LC, notch=False)
    g.poly([(325, 115), (455, 20), (585, 55)], c0="f", w=W_LC, notch=False)


@glyph("oe", 0x0153)
def gl_oe(g):
    lc_hex_bowl(g, 45, 335, 8, XH - 8)
    g.poly([(335, 245), (595, 245), (595, 385), (465, 460), (335, 365)], c0="f", w=W_LC, notch=False)
    g.poly([(335, 115), (465, 20), (595, 55)], c0="f", w=W_LC, notch=False)


@glyph("Oslash", 0x00D8)
def gl_Oslash(g):
    cap_O(g)
    g.line((95, -50), (445, 750))


@glyph("oslash", 0x00F8)
def gl_oslash(g):
    lc_o(g)
    g.line((75, -45), (365, 525), w=72, notch=False)


@glyph("Eth", 0x00D0)
def gl_Eth(g):
    cap_D(g)
    g.line((-15, 355), (245, 355), w=76, notch=False)


GLYPHS["Dcroat"] = (0x0110, gl_Eth)


@glyph("dcroat", 0x0111)
def gl_dcroat(g):
    lc_d(g)
    g.line((235, 585), (485, 585), w=68, notch=False)


@glyph("eth", 0x00F0)
def gl_eth(g):
    lc_hex_bowl(g, 55, 385, 8, XH - 8)
    g.poly([(355, 365), (325, 565), (155, 710)], c0="f", w=W_LC, notch=False)
    g.line((135, 525), (385, 655), w=68, notch=False)


@glyph("Hbar", 0x0126)
def gl_Hbar(g):
    cap_H(g)
    g.line((-10, 525), (560, 525), w=72, notch=False)


@glyph("hbar", 0x0127)
def gl_hbar(g):
    lc_h(g)
    g.line((-15, 575), (235, 575), w=68, notch=False)


@glyph("Lslash", 0x0141)
def gl_Lslash(g):
    cap_L(g)
    g.line((5, 265), (235, 425), w=72, notch=False)


@glyph("lslash", 0x0142)
def gl_lslash(g):
    lc_l(g)
    g.line((20, 315), (210, 445), w=68, notch=False)


@glyph("Thorn", 0x00DE)
def gl_Thorn(g):
    g.line((60, 0), (60, CAP))
    g.poly([(60, 565), (465, 385), (60, 205)], c0="f", c1="f")


@glyph("thorn", 0x00FE)
def gl_thorn(g):
    lc_hex_bowl(g, 60, 390, 8, XH - 8)
    g.line((60, DESC), (60, ASC), w=W_LC)


@glyph("germandbls", 0x00DF)
def gl_germandbls(g):
    g.poly([(60, 0), (60, 585), (235, 715), (415, 585), (225, 375), (435, 195), (255, 15), (145, 45)], w=W_LC)


@glyph("Germandbls", 0x1E9E)
def gl_Germandbls(g):
    g.poly([(60, 0), (60, 660), (435, 660), (245, 385), (475, 195), (285, 20), (145, 45)])


@glyph("dottedCircle", 0x25CC)
def gl_dottedCircle(g):
    cx, cy, r = 240, 250, 195
    for i in range(12):
        ang = math.radians(i * 30)
        g.dot((cx + r * math.cos(ang), cy + r * math.sin(ang)), 22, 26)


# --------------------------------------------------------------------------------------
# Extended Punctuation & Currency Symbols (Google Fonts Latin Core)
# --------------------------------------------------------------------------------------
@glyph("exclamdown", 0x00A1)
def gl_exclamdown(g):
    g.dot((115, 425), 50, 60)
    g.line((115, 275), (115, -180))


@glyph("questiondown", 0x00BF)
def gl_questiondown(g):
    g.dot((225, 425), 50, 60)
    g.poly([(385, -65), (225, -190), (35, -70), (225, 155), (225, 280)])


@glyph("cent", 0x00A2)
def gl_cent(g):
    lc_c(g)
    g.line((225, -70), (225, 550), w=64, notch=False)


@glyph("sterling", 0x00A3)
def gl_sterling(g):
    g.poly([(415, 585), (255, 685), (115, 565), (115, 40), (455, 40)], w=W_SYM)
    g.line((35, 335), (345, 335), w=68, notch=False)


@glyph("yen", 0x00A5)
def gl_yen(g):
    cap_Y(g.part(0, 0, 1.0, w=W_SYM))
    g.line((95, 265), (455, 265), w=64, notch=False)
    g.line((95, 145), (455, 145), w=64, notch=False)


@glyph("Euro", 0x20AC)
def gl_Euro(g):
    g.poly([(495, 650), (225, 665), (100, 350), (225, 35), (495, 50)], w=W_SYM, notch=False)
    g.line((15, 425), (395, 425), w=64, notch=False)
    g.line((15, 275), (365, 275), w=64, notch=False)


@glyph("rupeeIndian", 0x20B9)
def gl_rupeeIndian(g):
    g.line((55, 660), (455, 660), w=72, notch=False)
    g.line((55, 485), (455, 485), w=68, notch=False)
    g.poly([(145, 660), (365, 485), (115, 305), (435, 0)], w=W_SYM)


SEPARATORS = {"uni2028": 0x2028, "uni2029": 0x2029}
for _n, _u in SEPARATORS.items():
    GLYPHS[_n] = (_u, lambda g: None)


@glyph("section", 0x00A7)
def gl_section(g):
    g.poly([(365, 665), (185, 710), (75, 585), (385, 355), (255, 195), (95, 295)], w=62, notch=False)
    g.poly([(95, -5), (275, -50), (385, 75), (75, 305), (205, 465), (365, 365)], w=62, notch=False)


@glyph("paragraph", 0x00B6)
def gl_paragraph(g):
    g.poly([(385, 660), (145, 660), (55, 515), (145, 370), (265, 370)], c1="f", w=68, notch=False)
    g.line((265, 660), (265, -60), w=68)
    g.line((385, 660), (385, -60), w=68)


@glyph("copyright", 0x00A9)
def gl_copyright(g):
    cap_hex_loop(g, 45, 515, 20, 680, w=58, notch=False)
    cap_C(g.part(148, 185, 0.48, w=118, notch=False))


@glyph("registered", 0x00AE)
def gl_registered(g):
    cap_hex_loop(g, 45, 515, 20, 680, w=58, notch=False)
    cap_R(g.part(152, 185, 0.48, w=118, notch=False))


@glyph("trademark", 0x2122)
def gl_trademark(g):
    cap_T(g.part(20, 355, 0.46, w=118, notch=False))
    cap_M(g.part(265, 355, 0.46, w=118, notch=False))


@glyph("ordfeminine", 0x00AA)
def gl_ordfeminine(g):
    lc_a(g.part(35, 375, 0.58, w=110, notch=False))
    g.line((45, 285), (305, 285), w=56, notch=False)


@glyph("ordmasculine", 0x00BA)
def gl_ordmasculine(g):
    lc_o(g.part(35, 375, 0.58, w=110, notch=False))
    g.line((45, 285), (305, 285), w=56, notch=False)


@glyph("degree", 0x00B0)
def gl_degree(g):
    g.loop([(165, 695), (265, 595), (165, 495), (65, 595)], w=56, notch=False)


@glyph("periodcentered", 0x00B7)
def gl_periodcentered(g):
    g.dot((115, 275), 50, 60)


@glyph("bullet", 0x2022)
def gl_bullet(g):
    g.dot((145, 285), 82, 96)


@glyph("ellipsis", 0x2026)
def gl_ellipsis(g):
    for x in (95, 265, 435):
        g.dot((x, 62), 46, 54)


@glyph("endash", 0x2013)
def gl_endash(g):
    g.line((45, 275), (445, 275), w=W_SYM, notch=False)


@glyph("emdash", 0x2014)
def gl_emdash(g):
    g.line((35, 275), (685, 275), w=W_SYM, notch=True)


@glyph("minus", 0x2212)
def gl_minus(g):
    g.line((55, 290), (425, 290), w=W_SYM, notch=False)


@glyph("multiply", 0x00D7)
def gl_multiply(g):
    g.line((75, 125), (405, 455), w=W_SYM, notch=False)
    g.line((405, 125), (75, 455), w=W_SYM, notch=False)


@glyph("divide", 0x00F7)
def gl_divide(g):
    g.line((55, 290), (425, 290), w=W_SYM, notch=False)
    g.dot((240, 445), 46, 54)
    g.dot((240, 135), 46, 54)


def _quote_mark(g, x, y, flip=False):
    if not flip:
        g.dot((x, y), 44, 52)
        g.line((x + 10, y), (x - 45, y - 155), w=58, notch=False)
    else:
        g.dot((x, y - 135), 44, 52)
        g.line((x - 10, y - 135), (x + 45, y + 20), w=58, notch=False)


@glyph("quoteright", 0x2019)
def gl_quoteright(g):
    _quote_mark(g, 115, 650, flip=False)


@glyph("quoteleft", 0x2018)
def gl_quoteleft(g):
    _quote_mark(g, 115, 650, flip=True)


@glyph("quotedblright", 0x201D)
def gl_quotedblright(g):
    _quote_mark(g, 95, 650, flip=False)
    _quote_mark(g, 255, 650, flip=False)


@glyph("quotedblleft", 0x201C)
def gl_quotedblleft(g):
    _quote_mark(g, 95, 650, flip=True)
    _quote_mark(g, 255, 650, flip=True)


@glyph("quotesinglbase", 0x201A)
def gl_quotesinglbase(g):
    _quote_mark(g, 115, 62, flip=False)


@glyph("quotedblbase", 0x201E)
def gl_quotedblbase(g):
    _quote_mark(g, 95, 62, flip=False)
    _quote_mark(g, 255, 62, flip=False)


@glyph("guilsinglleft", 0x2039)
def gl_guilsinglleft(g):
    g.poly([(255, 425), (85, 255), (255, 85)], w=66, notch=False)


@glyph("guilsinglright", 0x203A)
def gl_guilsinglright(g):
    g.poly([(85, 425), (255, 255), (85, 85)], w=66, notch=False)


@glyph("guillemetleft", 0x00AB)
def gl_guillemetleft(g):
    g.poly([(235, 425), (65, 255), (235, 85)], w=64, notch=False)
    g.poly([(415, 425), (245, 255), (415, 85)], w=64, notch=False)


@glyph("guillemetright", 0x00BB)
def gl_guillemetright(g):
    g.poly([(65, 425), (235, 255), (65, 85)], w=64, notch=False)
    g.poly([(245, 425), (415, 255), (245, 85)], w=64, notch=False)


# --------------------------------------------------------------------------------------
# Elder Futhark & Nordic Runic Block (U+16A0–U+16F0)
# --------------------------------------------------------------------------------------
@glyph("uni16A0", 0x16A0)  # ᚠ Fehu
def r_fehu(g):
    g.line((80, 0), (80, CAP))
    g.line((80, 445), (385, CAP), c0="f")
    g.line((80, 235), (365, 475), c0="f")


@glyph("uni16A2", 0x16A2)  # ᚢ Uruz
def r_uruz(g):
    g.poly([(75, 0), (75, 685), (385, 445), (385, 0)])


@glyph("uni16A6", 0x16A6)  # ᚦ Thurisaz
def r_thurisaz(g):
    g.line((80, 0), (80, CAP))
    g.poly([(80, 535), (395, 365), (80, 195)], c0="f", c1="f")


@glyph("uni16A8", 0x16A8)  # ᚨ Ansuz
def r_ansuz(g):
    g.line((80, 0), (80, CAP))
    g.line((80, 685), (385, 455), c0="f")
    g.line((80, 445), (365, 215), c0="f")


@glyph("uni16B1", 0x16B1)  # ᚱ Raido
def r_raido(g):
    cap_R(g)


@glyph("uni16B2", 0x16B2)  # ᚲ Kauna
def r_kauna(g):
    g.poly([(365, 635), (85, 350), (365, 65)])


@glyph("uni16B4", 0x16B4)  # ᚴ Kaun (Younger Futhark)
def r_kaun(g):
    g.line((80, 0), (80, CAP))
    g.line((80, 345), (385, 665), c0="f")


@glyph("uni16B7", 0x16B7)  # ᚷ Gebo
def r_gebo(g):
    cap_X(g)


@glyph("uni16B9", 0x16B9)  # ᚹ Wunjo
def r_wunjo(g):
    cap_P(g)


@glyph("uni16BA", 0x16BA)  # ᚺ Haglaz
def r_haglaz(g):
    cap_H(g)


@glyph("uni16BC", 0x16BC)  # ᚼ Long-branch Hagall
def r_hagall(g):
    g.line((265, 0), (265, CAP))
    g.line((65, 165), (465, 535))
    g.line((65, 535), (465, 165))


@glyph("uni16BE", 0x16BE)  # ᚾ Naudiz
def r_naudiz(g):
    g.line((235, 0), (235, CAP))
    g.line((55, 495), (415, 235))


@glyph("uni16C1", 0x16C1)  # ᛁ Isaz
def r_isaz(g):
    cap_I(g)


@glyph("uni16C3", 0x16C3)  # ᛃ Jeran
def r_jeran(g):
    g.poly([(245, 690), (65, 485), (275, 315)], notch=False)
    g.poly([(245, 10), (425, 215), (215, 385)], notch=False)


@glyph("uni16C5", 0x16C5)  # ᛅ Long-branch Ar
def r_ar(g):
    g.line((235, 0), (235, CAP))
    g.line((55, 235), (415, 495))


@glyph("uni16C7", 0x16C7)  # ᛇ Iwaz
def r_iwaz(g):
    g.poly([(75, 475), (265, 685), (265, 15), (455, 225)])


@glyph("uni16C8", 0x16C8)  # ᛈ Pertho
def r_pertho(g):
    g.poly([(395, 685), (235, 535), (75, 685), (75, 15), (235, 165), (395, 15)])


@glyph("uni16C9", 0x16C9)  # ᛉ Algiz
def r_algiz(g):
    g.line((265, 0), (265, CAP))
    g.poly([(55, 665), (265, 385), (475, 665)], notch=False)


@glyph("uni16CA", 0x16CA)  # ᛊ Sowilo
def r_sowilo(g):
    g.poly([(385, 690), (85, 425), (385, 275), (85, 10)])


@glyph("uni16CB", 0x16CB)  # ᛋ Sigel
def r_sigel(g):
    r_sowilo(g)


@glyph("uni16CF", 0x16CF)  # ᛏ Tiwaz
def r_tiwaz(g):
    cap_T(g)


@glyph("uni16D2", 0x16D2)  # ᛒ Berkanan
def r_berkanan(g):
    cap_B(g)


@glyph("uni16D6", 0x16D6)  # ᛖ Ehwaz
def r_ehwaz(g):
    cap_M(g)


@glyph("uni16D7", 0x16D7)  # ᛗ Mannaz
def r_mannaz(g):
    g.line((65, 0), (65, CAP))
    g.line((485, 0), (485, CAP))
    g.line((65, 660), (485, 330), c0="f", c1="f", notch=False)
    g.line((485, 660), (65, 330), c0="f", c1="f", notch=False)


@glyph("uni16D8", 0x16D8)  # ᛘ Long-branch Madr
def r_madr(g):
    r_algiz(g)


@glyph("uni16DA", 0x16DA)  # ᛚ Laukaz
def r_laukaz(g):
    g.poly([(80, 0), (80, 685), (385, 435)])


@glyph("uni16DC", 0x16DC)  # ᛜ Ingwaz
def r_ingwaz(g):
    g.loop([(245, 585), (435, 350), (245, 115), (55, 350)], notch=False)


@glyph("uni16DD", 0x16DD)  # ᛝ Ing
def r_ing(g):
    g.line((75, 0), (455, CAP))
    g.line((455, 0), (75, CAP))
    g.poly([(75, 455), (265, 685), (455, 455)], c0="f", c1="f", notch=False)
    g.poly([(75, 245), (265, 15), (455, 245)], c0="f", c1="f", notch=False)


@glyph("uni16DE", 0x16DE)  # ᛞ Dagaz
def r_dagaz(g):
    g.line((65, 0), (65, CAP))
    g.line((485, 0), (485, CAP))
    g.line((65, 650), (485, 50), c0="f", c1="f", notch=False)
    g.line((485, 650), (65, 50), c0="f", c1="f", notch=False)


@glyph("uni16DF", 0x16DF)  # ᛟ Othalan
def r_othalan(g):
    g.poly([(75, 0), (445, 475), (260, 685), (75, 475), (445, 0)])


@glyph("uni16E6", 0x16E6)  # ᛦ Long-branch Yr
def r_yr(g):
    g.line((265, 0), (265, CAP))
    g.poly([(55, 35), (265, 305), (475, 35)])


@glyph("uni16EB", 0x16EB)  # ᛫ Runic Single Punctuation
def r_punct1(g):
    g.dot((115, 350), 50, 60)


@glyph("uni16EC", 0x16EC)  # ᛬ Runic Multiple Punctuation
def r_punct2(g):
    g.dot((115, 210), 48, 58)
    g.dot((115, 490), 48, 58)


@glyph("uni16ED", 0x16ED)  # ᛭ Runic Cross Punctuation
def r_punct_cross(g):
    gl_plus(g)


@glyph("uni16EE", 0x16EE)  # ᛮ Arlaug
def r_arlaug(g):
    r_tiwaz(g)
    g.line((135, 335), (415, 335), notch=False)


@glyph("uni16EF", 0x16EF)  # ᛯ Tvimadur
def r_tvimadur(g):
    g.line((50, CAP), (500, 0), notch=False)
    g.line((500, CAP), (50, 0), notch=False)
    g.line((275, 0), (275, CAP), notch=False)


@glyph("uni16F0", 0x16F0)  # ᛰ Belgthor
def r_belgthor(g):
    g.loop([(265, 685), (445, 465), (265, 245), (85, 465)], notch=False)
    g.line((265, 265), (265, 0), c0="f")
    g.poly([(95, 20), (265, 195), (435, 20)], notch=False)


# --------------------------------------------------------------------------------------
# Accented Latin Composites (Google Fonts Latin Core)
# --------------------------------------------------------------------------------------
TOP_X = {
    "c": 225, "C": 275, "G": 275, "L": 145, "l": 105, "t": 135, "r": 165,
    "J": 355, "j": 225, "dotlessj": 225, "dotlessi": 110, "I": 130,
}
BOTTOM_X = {"t": 175, "L": 240, "l": 145, "T": 275, "g": 225, "G": 295, "C": 285, "c": 235, "S": 255, "s": 205}
OGONEK_AT = {
    "A": (475, 10), "a": (375, 10), "E": (425, 40), "e": (325, 25),
    "I": (130, 10), "i": (110, 10), "dotlessi": (110, 10),
    "U": (385, 45), "u": (380, 10), "dottedCircle": (295, 70),
}
CARONALT_AT = {"d": (495, 575), "l": (235, 575), "t": (275, 545), "L": (215, 545)}

COMB = {
    0x0300: "gravecomb", 0x0301: "acutecomb", 0x0302: "circumflexcomb", 0x0303: "tildecomb",
    0x0304: "macroncomb", 0x0306: "brevecomb", 0x0307: "dotaccentcomb", 0x0308: "dieresiscomb",
    0x030A: "ringcomb", 0x030B: "hungarumlautcomb", 0x030C: "caroncomb", 0x0326: "commaaccentcomb",
    0x0327: "cedillacomb", 0x0328: "ogonekcomb",
}
COMMA_BELOW_LETTERS = set("GKLNRgklnr")
CARONALT_LETTERS = set("dltL")

COMPOSITES = {}
_ANCHOR_CACHE = {}


def base_bounds(base):
    if base not in _ANCHOR_CACHE:
        g = G()
        GLYPHS[base][1](g)
        _ANCHOR_CACHE[base] = path_bounds(g.outline())
    return _ANCHOR_CACHE[base]


def anchor(base, kind):
    x0, y0, x1, y1 = base_bounds(base)
    if kind == "top":
        return (TOP_X.get(base, (x0 + x1) / 2.0), CAP_TOP if y1 > TALL else LC_TOP)
    if kind == "bottom":
        return (BOTTOM_X.get(base, (x0 + x1) / 2.0), CAP_BOT if y0 < -100 else LC_BOT)
    if kind == "ogonek":
        return OGONEK_AT[base]
    if kind == "caronalt":
        return CARONALT_AT[base]
    raise KeyError(kind)


def glyph_name_for(cp):
    special = {
        0x0110: "Dcroat", 0x0111: "dcroat", 0x0122: "Gcommaaccent", 0x0123: "gcommaaccent",
        0x0136: "Kcommaaccent", 0x0137: "kcommaaccent", 0x013B: "Lcommaaccent",
        0x013C: "lcommaaccent", 0x0145: "Ncommaaccent", 0x0146: "ncommaaccent",
        0x0156: "Rcommaaccent", 0x0157: "rcommaaccent", 0x0218: "Scommaaccent",
        0x0219: "scommaaccent", 0x021A: "Tcommaaccent", 0x021B: "tcommaaccent",
        0x0130: "Idotaccent", 0x1E80: "Wgrave", 0x1E81: "wgrave", 0x1E82: "Wacute",
        0x1E83: "wacute", 0x1E84: "Wdieresis", 0x1E85: "wdieresis", 0x1EF2: "Ygrave",
        0x1EF3: "ygrave", 0x0150: "Ohungarumlaut", 0x0151: "ohungarumlaut",
        0x0170: "Uhungarumlaut", 0x0171: "uhungarumlaut",
    }
    return special.get(cp) or UV2AGL.get(cp) or f"uni{cp:04X}"


LATIN_CORE_COMPOSITES = [
    0x00C0, 0x00C1, 0x00C2, 0x00C3, 0x00C4, 0x00C5, 0x00C7, 0x00C8, 0x00C9, 0x00CA, 0x00CB, 0x00CC,
    0x00CD, 0x00CE, 0x00CF, 0x00D1, 0x00D2, 0x00D3, 0x00D4, 0x00D5, 0x00D6, 0x00D9, 0x00DA, 0x00DB,
    0x00DC, 0x00DD, 0x00E0, 0x00E1, 0x00E2, 0x00E3, 0x00E4, 0x00E5, 0x00E7, 0x00E8, 0x00E9, 0x00EA,
    0x00EB, 0x00EC, 0x00ED, 0x00EE, 0x00EF, 0x00F1, 0x00F2, 0x00F3, 0x00F4, 0x00F5, 0x00F6, 0x00F9,
    0x00FA, 0x00FB, 0x00FC, 0x00FD, 0x00FF, 0x0100, 0x0101, 0x0102, 0x0103, 0x0104, 0x0105, 0x0106,
    0x0107, 0x010A, 0x010B, 0x010C, 0x010D, 0x010E, 0x010F, 0x0112, 0x0113, 0x0116, 0x0117, 0x0118,
    0x0119, 0x011A, 0x011B, 0x011E, 0x011F, 0x0120, 0x0121, 0x0122, 0x0123, 0x012A, 0x012B, 0x012E,
    0x012F, 0x0130, 0x0136, 0x0137, 0x0139, 0x013A, 0x013B, 0x013C, 0x013D, 0x013E, 0x0143, 0x0144,
    0x0145, 0x0146, 0x0147, 0x0148, 0x0150, 0x0151, 0x0154, 0x0155, 0x0158, 0x0159, 0x015A, 0x015B,
    0x015E, 0x015F, 0x0160, 0x0161, 0x0164, 0x0165, 0x016A, 0x016B, 0x016E, 0x016F, 0x0170, 0x0171,
    0x0172, 0x0173, 0x0174, 0x0175, 0x0176, 0x0177, 0x0178, 0x0179, 0x017A, 0x017B, 0x017C, 0x017D,
    0x017E, 0x0218, 0x0219, 0x021A, 0x021B, 0x1E80, 0x1E81, 0x1E82, 0x1E83, 0x1E84, 0x1E85, 0x1EF2,
    0x1EF3,
]


def _add_composites():
    for cp in LATIN_CORE_COMPOSITES:
        dec = unicodedata.decomposition(chr(cp)).split()
        base_ch, marks = chr(int(dec[0], 16)), [int(m, 16) for m in dec[1:]]
        base = glyph_name_for(ord(base_ch))
        out = []
        for m in marks:
            mname = COMB[m]
            kind = MARKS[mname]["kind"]
            if m == 0x0327 and base_ch in COMMA_BELOW_LETTERS:
                if base_ch == "g":
                    mname, kind = "commaturnedabovecomb", "top"
                else:
                    mname, kind = "commaaccentcomb", "bottom"
            if m == 0x030C and base_ch in CARONALT_LETTERS:
                mname, kind = "caroncomb.alt", "caronalt"
            if kind == "top" and base_ch in "ij":
                base = "dotlessi" if base_ch == "i" else "dotlessj"
            out.append((mname, kind))
        COMPOSITES[glyph_name_for(cp)] = (cp, base, out)


def composite_fn(base, marks):
    def fn(g):
        GLYPHS[base][1](g)
        for mname, kind in marks:
            x, y = anchor(base, kind)
            draw_mark(g, mname, x, y)
    return fn


_register_marks()
_add_composites()
COMPOSITES["iogonek.dotless"] = (None, "dotlessi", [("ogonekcomb", "ogonek")])
for _n, (_cp, _b, _m) in COMPOSITES.items():
    GLYPHS[_n] = (_cp, composite_fn(_b, _m))


# --------------------------------------------------------------------------------------
# Bind-Rune Medallions (<RV>, <TH>, <OD>, etc. — 1 to 3 letters between < and >)
# --------------------------------------------------------------------------------------
MONO_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
SHIELD_ADV = 920
SHIELD_CX = 460
SHIELD_CY = 350

MONO_SLOTS = {
    # slot: (scale, target_cx, target_cy) in font units inside the octagonal rune shield
    "mono1": (0.62, SHIELD_CX, SHIELD_CY),
    "mono2l": (0.48, SHIELD_CX - 150, SHIELD_CY),
    "mono2r": (0.48, SHIELD_CX + 150, SHIELD_CY),
    "mono3l": (0.37, SHIELD_CX - 205, SHIELD_CY),
    "mono3c": (0.37, SHIELD_CX, SHIELD_CY),
    "mono3r": (0.37, SHIELD_CX + 205, SHIELD_CY),
}


def mono_ring_path():
    """Octagonal Nordic rune-shield frame."""
    g = G(w=66, notch=True)
    cx, cy = SHIELD_CX, SHIELD_CY
    rx, ry = 395, 395
    c = 155
    g.loop(
        [
            (cx - c, cy + ry),
            (cx + c, cy + ry),
            (cx + rx, cy + c),
            (cx + rx, cy - c),
            (cx + c, cy - ry),
            (cx - c, cy - ry),
            (cx - rx, cy - c),
            (cx - rx, cy + c),
        ],
        w=66,
        notch=True,
    )
    return g.outline()


def mono_letter_path(letter, slot):
    k, tx, ty = MONO_SLOTS[slot]
    bx0, by0, bx1, by1 = base_bounds(letter)
    bcx, bcy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0
    ox = tx - k * bcx
    oy = ty - k * bcy
    g = G(k=k, ox=ox, oy=oy, w=W, notch=False)
    GLYPHS[letter][1](g)
    return g.outline()


def mono_glyphs():
    out = [("monogram.ring", mono_ring_path(), -SHIELD_CX, SHIELD_ADV), ("monogram.end", Path(), 0, 0)]
    for L in MONO_LETTERS:
        for slot in MONO_SLOTS:
            # Placed as zero-width overlay glyph shifted back by SHIELD_ADV
            out.append((f"{L}.{slot}", mono_letter_path(L, slot), -SHIELD_ADV, 0))
    return out


def mono_fea():
    ins = " ".join(list(MONO_LETTERS) + list(MONO_LETTERS.lower()))
    lines = [f"@MONO_IN = [{ins}];"]
    for slot in MONO_SLOTS:
        body = " ".join(f"sub {c} by {c.upper()}.{slot};" for c in MONO_LETTERS + MONO_LETTERS.lower())
        lines.append(f"lookup MONO_{slot.upper()} {{ {body} }} MONO_{slot.upper()};")
    lines.append("lookup MONO_OPEN { sub less by monogram.ring; } MONO_OPEN;")
    lines.append("lookup MONO_CLOSE { sub greater by monogram.end; } MONO_CLOSE;")
    lt = "less' lookup MONO_OPEN"
    gt = "greater' lookup MONO_CLOSE"
    lines.append("lookup MONOGRAM {")
    lines.append(f"  sub {lt} @MONO_IN' lookup MONO_MONO3L @MONO_IN' lookup MONO_MONO3C @MONO_IN' lookup MONO_MONO3R {gt};")
    lines.append(f"  sub {lt} @MONO_IN' lookup MONO_MONO2L @MONO_IN' lookup MONO_MONO2R {gt};")
    lines.append(f"  sub {lt} @MONO_IN' lookup MONO_MONO1 {gt};")
    lines.append("} MONOGRAM;")
    lines.append("feature calt { lookup MONOGRAM; } calt;")
    lines.append("feature liga { lookup MONOGRAM; } liga;")
    return "\n".join(lines) + "\n"


def ccmp_fea():
    tops = " ".join(n for n, m in MARKS.items() if m["uni"] and m["kind"] == "top")
    bottoms = " ".join(n for n, m in MARKS.items() if m["uni"] and m["kind"] in ("bottom", "ogonek"))
    return (
        f"@TOP_MARKS = [{tops}];\n"
        f"@BOTTOM_MARKS = [{bottoms}];\n"
        "lookup DOTLESS { sub i by dotlessi; sub j by dotlessj; sub iogonek by iogonek.dotless; } DOTLESS;\n"
        "feature ccmp {\n"
        "  sub [i j iogonek]' lookup DOTLESS @TOP_MARKS;\n"
        "  sub [i j iogonek]' lookup DOTLESS @BOTTOM_MARKS @TOP_MARKS;\n"
        "  sub [i j iogonek]' lookup DOTLESS @BOTTOM_MARKS @BOTTOM_MARKS @TOP_MARKS;\n"
        "} ccmp;\n"
    )


# --------------------------------------------------------------------------------------
# Spacing & Auto-Kerning
# --------------------------------------------------------------------------------------
PANOSE_PROP = [2, 11, 6, 3, 0, 0, 0, 0, 0, 0]
MATH_SIGNS = ["plus", "minus", "less", "equal", "greater", "asciitilde", "multiply", "divide"]

KERN_EXTRA = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "period", "comma", "colon", "semicolon", "hyphen", "endash", "emdash",
    "quotesingle", "quotedbl", "quoteleft", "quoteright", "quotedblleft", "quotedblright",
    "quotesinglbase", "quotedblbase", "guilsinglleft", "guilsinglright",
    "guillemetleft", "guillemetright", "parenleft", "parenright", "slash", "exclam",
    "question", "ampersand", "ellipsis",
]
KERN_ROWS_STEP = 8
KERN_WINDOW = 28
KERN_FACTOR = 0.78
KERN_MAX = 180
KERN_MIN = 12


def _is_lc_letter(name):
    return len(name) == 1 and name.islower()


def _flat_contours(path, dx):
    class FlatPen(BasePen):
        def __init__(self):
            super().__init__(None)
            self.contours, self.cur = [], []

        def _moveTo(self, p):
            self.cur = [p]

        def _lineTo(self, p):
            self.cur.append(p)

        def _qCurveToOne(self, p1, p2):
            p0 = self.cur[-1]
            for i in range(1, 9):
                t = i / 8.0
                a_, b_, c_ = (1 - t) ** 2, 2 * (1 - t) * t, t * t
                self.cur.append((a_ * p0[0] + b_ * p1[0] + c_ * p2[0], a_ * p0[1] + b_ * p1[1] + c_ * p2[1]))

        def _closePath(self):
            self.contours.append(self.cur)
            self.cur = []

        _endPath = _closePath

    pen = FlatPen()
    path.draw(TransformPen(pen, (1, 0, 0, 1, dx, 0)))
    return pen.contours


def profile(path, dx, rows):
    L = np.full(rows.shape, np.inf)
    Rr = np.full(rows.shape, -np.inf)
    for c in _flat_contours(path, dx):
        if not c:
            continue
        pts = np.array(c + [c[0]], dtype=float)
        for xa, ya, xb, yb in zip(pts[:-1, 0], pts[:-1, 1], pts[1:, 0], pts[1:, 1]):
            lo, hi = min(ya, yb), max(ya, yb)
            m = (rows >= lo) & (rows <= hi)
            if not m.any():
                continue
            xs = xa if ya == yb else xa + (rows[m] - ya) * (xb - xa) / (yb - ya)
            L[m] = np.minimum(L[m], xs)
            Rr[m] = np.maximum(Rr[m], xs)
    k = KERN_WINDOW // KERN_ROWS_STEP
    Lw, Rw = L.copy(), Rr.copy()
    for s_ in range(1, k + 1):
        Lw[s_:] = np.minimum(Lw[s_:], L[:-s_])
        Lw[:-s_] = np.minimum(Lw[:-s_], L[s_:])
        Rw[s_:] = np.maximum(Rw[s_:], Rr[:-s_])
        Rw[:-s_] = np.maximum(Rw[:-s_], Rr[s_:])
    return Lw, Rw


def kern_groups(names):
    groups = {}
    for n in names:
        base = COMPOSITES[n][1] if n in COMPOSITES else n
        base = {"dotlessi": "i", "dotlessj": "j", "Dcroat": "Eth"}.get(base, base)
        groups.setdefault(base, []).append(n)
    return groups


def auto_kern(glyphs, names):
    rows = np.arange(-300, 950, KERN_ROWS_STEP, dtype=float)
    groups = kern_groups(names)
    prof = {}
    for gname, members in groups.items():
        Ls, Rs = [], []
        for n in members:
            gl = glyphs[n]
            p_path = _draw_glyph(gname) if n == gname or _is_lc_letter(gname) else gl["path"]
            Lp, Rp = profile(p_path, gl["dx"], rows)
            Ls.append(Lp)
            Rs.append(Rp)
        prof[gname] = (np.min(Ls, axis=0), np.max(Rs, axis=0), glyphs[groups[gname][0]]["adv"])
    target_cap = 2.0 * SB
    target_lc = 52.0
    kerning = {}
    for ga, (_, Ra, adv) in prof.items():
        for gb, (Lb, _, _) in prof.items():
            m = np.isfinite(Ra) & np.isfinite(Lb)
            if not m.any():
                continue
            dmin = float(np.min(adv - Ra[m] + Lb[m]))
            tgt = target_lc if (_is_lc_letter(ga) or _is_lc_letter(gb)) else target_cap
            kv = -int(round(min(KERN_MAX, KERN_FACTOR * (dmin - tgt)) / 2.0) * 2)
            if abs(kv) >= KERN_MIN:
                left = f"public.kern1.{ga}" if len(groups[ga]) > 1 else ga
                right = f"public.kern2.{gb}" if len(groups[gb]) > 1 else gb
                kerning[(left, right)] = kv
    plist = {}
    for gname, members in groups.items():
        if len(members) > 1:
            plist[f"public.kern1.{gname}"] = list(members)
            plist[f"public.kern2.{gname}"] = list(members)
    return plist, kerning


# --------------------------------------------------------------------------------------
# UFO Assembly & Cleanup
# --------------------------------------------------------------------------------------
def is_mark(name):
    return name in MARKS and MARKS[name]["uni"] is not None


def glyph_order():
    names = [n for n in GLYPHS if n not in (".notdef", "space")]
    return [".notdef", "space"] + names


def _draw_glyph(name):
    g = G()
    GLYPHS[name][1](g)
    return Path() if g.empty() else g.outline()


def build_glyphs():
    out = {}
    for name in glyph_order():
        uni, _ = GLYPHS[name]
        path = Path() if name == "space" else _draw_glyph(name)
        b = path_bounds(path)
        if name in SEPARATORS:
            out[name] = dict(path=Path(), dx=0, adv=0, unicodes=[uni])
            continue
        if is_mark(name):
            dx = -MARK_CENTER
            adv = 0
        else:
            if b is None:
                dx, adv = 0, 260
            else:
                sb = 26 if _is_lc_letter(name) or name in ("dotlessi", "dotlessj", "ae", "oe", "oslash", "eth", "dcroat", "hbar", "lslash", "thorn", "germandbls") else SB
                dx = round(sb - b[0])
                adv = round(b[2] - b[0] + 2 * sb)
        out[name] = dict(path=path, dx=dx, adv=adv, unicodes=[uni] if uni is not None else [])
    out["space"]["unicodes"] = [0x20, 0xA0]
    for name, c in COMPOSITES.items():
        base = out[c[1]]
        g = out[name]
        g["dx"] = base["dx"]
        g["adv"] = base["adv"]
    signs = [n for n in MATH_SIGNS if n in out]
    adv = max(out[n]["adv"] for n in signs)
    for n in signs:
        b = path_bounds(out[n]["path"])
        out[n]["dx"] = round((adv - (b[2] - b[0])) / 2.0 - b[0])
        out[n]["adv"] = adv
    for name, path, dx, m_adv in mono_glyphs():
        # For monogram.ring, center at SHIELD_CX
        if name == "monogram.ring":
            out[name] = dict(path=path, dx=0, adv=m_adv, unicodes=[])
        else:
            out[name] = dict(path=path, dx=dx, adv=m_adv, unicodes=[])
    return out


TINY = 14.0
COLINEAR = 3.5
SNAP = 3


def _clean_contours(path, dx):
    rp = RecordingPen()
    path.draw(TransformPen(rp, (1, 0, 0, 1, dx, 0)))

    def rnd(pt):
        return None if pt is None else (round(pt[0]), round(pt[1]))

    def dist(p0, p1):
        return math.hypot(p0[0] - p1[0], p0[1] - p1[1])

    contours, cur = [], None
    for op, pts in rp.value:
        if op == "moveTo":
            cur = [rnd(pts[0]), []]
        elif op in ("lineTo", "qCurveTo"):
            if cur is None:
                cur = [None, []]
            cur[1].append((op, [rnd(q) for q in pts]))
        elif op in ("closePath", "endPath"):
            contours.append(cur)
            cur = None

    out = []
    for start, segs in contours:
        if start is None:
            out.append((None, segs))
            continue
        cleaned, here = [], start
        for op, pts in segs:
            end = pts[-1]
            if end is not None and all(q is None or dist(q, here) < TINY for q in pts):
                continue
            if op == "lineTo":
                ex, ey = end
                if 0 < abs(ex - here[0]) <= SNAP and abs(ey - here[1]) > 10:
                    pts = [(here[0], ey)]
                elif 0 < abs(ey - here[1]) <= SNAP and abs(ex - here[0]) > 10:
                    pts = [(ex, here[1])]
                end = pts[-1]
            cleaned.append([op, pts, here])
            here = end if end is not None else here
        while cleaned and cleaned[-1][0] == "lineTo" and dist(cleaned[-1][1][-1], start) < TINY:
            cleaned.pop()
        merged = []
        for seg in cleaned:
            if merged and seg[0] == "lineTo" and merged[-1][0] == "lineTo":
                a_, b_, c_ = merged[-1][2], merged[-1][1][-1], seg[1][-1]
                t1 = math.atan2(b_[1] - a_[1], b_[0] - a_[0])
                t2 = math.atan2(c_[1] - b_[1], c_[0] - b_[0])
                turn = abs((math.degrees(t2 - t1) + 180) % 360 - 180)
                if turn < COLINEAR:
                    merged[-1][1] = [c_]
                    continue
            merged.append(seg)
        if len(merged) >= 2:
            out.append((start, [(op, pts) for op, pts, _ in merged]))
    return out


def _draw_ufo_outline(glyph, path, dx):
    if path_bounds(path) is None:
        return
    pen = glyph.getPen()
    if signed_area(path) < 0:
        pen = ReverseContourPen(pen)
    for start, segs in _clean_contours(path, dx):
        if start is not None:
            pen.moveTo(start)
        for op, pts in segs:
            getattr(pen, op)(*pts)
        pen.closePath()


def vertical_metrics(glyphs):
    ys = [path_bounds(g["path"]) for g in glyphs.values() if path_bounds(g["path"]) is not None]
    ymax = max(b[3] for b in ys)
    ymin = min(b[1] for b in ys)
    asc = int(math.ceil(ymax / 10.0) * 10)
    desc = int(math.floor(ymin / 10.0) * 10)
    return asc, desc


def production_name(name, unicodes):
    if not unicodes:
        return name
    cp = unicodes[0]
    if cp in UV2AGL:
        return UV2AGL[cp]
    return f"uni{cp:04X}" if cp <= 0xFFFF else f"u{cp:05X}"


def write_ufo(path_out):
    import ufoLib2
    from ufoLib2.objects import Anchor

    glyphs = build_glyphs()
    ufo = ufoLib2.Font()
    info = ufo.info
    info.familyName = FAMILY
    info.styleName = "Regular"
    info.styleMapFamilyName = FAMILY
    info.styleMapStyleName = "regular"
    major, minor = VERSION.split(".")
    info.versionMajor, info.versionMinor = int(major), int(minor)
    info.copyright = COPYRIGHT
    info.openTypeNameDesigner = "RV"
    info.openTypeNameManufacturer = "The Fjellrune Project Authors"
    info.openTypeNameManufacturerURL = REPO_URL
    info.openTypeNameLicense = (
        "This Font Software is licensed under the SIL Open Font License, "
        "Version 1.1. This license is available with a FAQ at: "
        "https://openfontlicense.org"
    )
    info.openTypeNameLicenseURL = "https://openfontlicense.org"
    info.openTypeNameDescription = (
        "Angular Nordic runic display typeface with blade-cut strokes, axe-nick "
        "staves, Elder Futhark runes, and bind-rune medallions."
    )
    info.unitsPerEm = UPM
    asc, desc = vertical_metrics(glyphs)
    info.ascender, info.descender = asc, desc
    info.xHeight = XH
    info.capHeight = CAP
    info.openTypeHheaAscender, info.openTypeHheaDescender, info.openTypeHheaLineGap = asc, desc, 0
    info.openTypeOS2TypoAscender, info.openTypeOS2TypoDescender, info.openTypeOS2TypoLineGap = asc, desc, 0
    info.openTypeOS2WinAscent, info.openTypeOS2WinDescent = asc, -desc
    info.openTypeOS2Selection = [7, 8]
    info.openTypeOS2Type = []
    info.openTypeOS2VendorID = "FJEL"
    info.openTypeOS2WeightClass = 400
    info.openTypeOS2WidthClass = 5
    info.openTypeOS2Panose = PANOSE_PROP
    info.openTypeOS2StrikeoutSize = 68
    info.openTypeOS2StrikeoutPosition = 260
    info.postscriptUnderlinePosition = -120
    info.postscriptUnderlineThickness = 56
    info.postscriptIsFixedPitch = False
    info.postscriptFontName = f"{FAMILY}-Regular"

    order = list(glyphs)
    categories = {}
    for name in order:
        g = glyphs[name]
        gl = ufo.newGlyph(name)
        gl.width = g["adv"]
        gl.unicodes = g["unicodes"]
        comp = COMPOSITES.get(name)
        if comp:
            _, base, marks = comp
            pen = gl.getPen()
            pen.addComponent(base, (1, 0, 0, 1, 0, 0))
            for mname, kind in marks:
                ax, ay = anchor(base, kind)
                mx = ax + glyphs[base]["dx"] - glyphs[mname]["dx"]
                my = ay - mark_attach_y(kind)
                pen.addComponent(mname, (1, 0, 0, 1, round(mx), round(my)))
        elif name == "Dcroat":
            gl.getPen().addComponent("Eth", (1, 0, 0, 1, 0, 0))
        else:
            _draw_ufo_outline(gl, g["path"], g["dx"])
        if is_mark(name):
            categories[name] = "mark"
            kind = MARKS[name]["kind"]
            aname = {"top": "_top", "bottom": "_bottom", "ogonek": "_ogonek"}.get(kind)
            if aname:
                ay = mark_attach_y(kind)
                gl.anchors.append(Anchor(round(g["dx"]), round(ay), aname))
                b = path_bounds(g["path"])
                if kind == "top":
                    gl.anchors.append(Anchor(round(g["dx"]), round(b[3] + 35), "top"))
                elif kind == "bottom":
                    gl.anchors.append(Anchor(round(g["dx"]), round(b[1] - 25), "bottom"))
        elif g["unicodes"] or name in COMPOSITES:
            categories[name] = "base"

    bases = set(c[1] for c in COMPOSITES.values()) | set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghklmnopqrstuvwxyz")
    bases |= {"dotlessi", "dotlessj", "dottedCircle"}
    bases -= set(COMPOSITES)
    for base in sorted(bases):
        if base not in ufo:
            continue
        gl = ufo[base]
        dx = glyphs[base]["dx"]
        for kind, aname in (("top", "top"), ("bottom", "bottom")):
            ax, ay = anchor(base, kind)
            gl.anchors.append(Anchor(round(ax + dx), round(ay), aname))
        if base in OGONEK_AT:
            ax, ay = OGONEK_AT[base]
            gl.anchors.append(Anchor(round(ax + dx), round(ay), "ogonek"))

    ufo.lib["public.glyphOrder"] = order
    ufo.lib["public.openTypeMeta"] = {"dlng": ["Latn", "Runr"], "slng": ["Latn", "Runr"]}
    ufo.lib["com.github.googlei18n.ufo2ft.filters"] = [{"name": "propagateAnchors", "pre": True}]
    ufo.lib["public.openTypeCategories"] = categories
    ufo.lib["public.postscriptNames"] = {n: production_name(n, glyphs[n]["unicodes"]) for n in order}

    fea = "languagesystem DFLT dflt;\nlanguagesystem latn dflt;\nlanguagesystem runr dflt;\n\n" + ccmp_fea() + "\n" + mono_fea()
    ufo.features.text = fea

    names = [
        n for n in order
        if n in glyphs and (
            (glyphs[n]["unicodes"] and unicodedata.category(chr(glyphs[n]["unicodes"][0])).startswith("L") and glyphs_is_latin(glyphs[n]["unicodes"][0]))
            or n in KERN_EXTRA
        )
    ]
    groups, kerning = auto_kern(glyphs, names)
    ufo.groups.update(groups)
    ufo.kerning.update(kerning)

    if os.path.exists(path_out):
        shutil.rmtree(path_out)
    ufo.save(path_out)
    return path_out, len(order), len(ufo.kerning)


def glyphs_is_latin(cp):
    return cp < 0x16A0 or cp > 0x16FF


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Write the Fjellrune UFO source.")
    ap.add_argument("--ufo", default="sources/ufo", help="folder for the .ufo source")
    args = ap.parse_args()
    os.makedirs(args.ufo, exist_ok=True)
    p, n, nk = write_ufo(os.path.join(args.ufo, f"{FAMILY}-Regular.ufo"))
    print(f"wrote {p}: {n} glyphs, {nk} kerning pairs")
