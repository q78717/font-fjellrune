#!/usr/bin/env python3
"""Build the self-contained specimen page (font and glyph construction data inlined).

Usage: python3 sources/build_specimen.py [--fonts fonts/webfonts] [--ttf fonts/ttf] [--out documentation/specimen/index.html]
"""
import argparse
import base64
import json
import os
import plistlib
import sys

from fontTools.pens.svgPathPen import SVGPathPen

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_fjellrune as B  # noqa: E402


def f(v):
    return round(v, 1)


def svg_outline(path):
    sp = SVGPathPen(None, ntos=lambda v: ("%.1f" % v).rstrip("0").rstrip("."))
    path.draw(sp)
    return sp.getCommands()


def svg_skel(skel):
    parts = []
    for item in skel:
        kind = item[0]
        if kind == "p":
            parts.append("M" + " L".join(f"{f(x)} {f(y)}" for x, y in item[1]))
        elif kind == "loop":
            pts = item[1]
            parts.append("M" + " L".join(f"{f(x)} {f(y)}" for x, y in pts) + " Z")
        elif kind == "d":
            _, cx, cy, rx, ry = item
            parts.append(
                f"M{f(cx)} {f(cy + ry)} L{f(cx + rx)} {f(cy)} "
                f"L{f(cx)} {f(cy - ry)} L{f(cx - rx)} {f(cy)} Z"
            )
    return " ".join(parts)


def glyph_data():
    out = []
    for name, (uni, fn) in B.GLYPHS.items():
        if uni is None or name in ("space", "uni2028", "uni2029"):
            continue
        g = B.G()
        fn(g)
        path = g.outline()
        b = B.path_bounds(path)
        if b is None:
            continue
        skel = svg_skel(g.skel)
        strokes = sum(1 for x in g.skel if x[0] in ("p", "loop"))
        dots = sum(1 for x in g.skel if x[0] == "d")
        out.append(
            {
                "n": name,
                "c": chr(uni),
                "u": uni,
                "p": svg_outline(path),
                "s": skel,
                "cx": round((b[0] + b[2]) / 2.0),
                "strokes": strokes,
                "dots": dots,
            }
        )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", default="fonts/webfonts")
    ap.add_argument("--ttf", default="fonts/ttf")
    ap.add_argument("--template", default=os.path.join(HERE, "specimen_template.html"))
    ap.add_argument("--out", default="documentation/specimen/index.html")
    a = ap.parse_args()

    kplist = os.path.join(HERE, "ufo", "Fjellrune-Regular.ufo", "kerning.plist")
    with open(kplist, "rb") as fh:
        pairs = sum(len(v) for v in plistlib.load(fh).values())

    glist = glyph_data()
    meta = {
        "UPM": B.UPM,
        "CAP": B.CAP,
        "XH": B.XH,
        "W": B.W,
        "glyphs": len(glist),
        "kern": pairs,
        "mono": {k: [round(v[0], 3), round(v[1]), round(v[2])] for k, v in B.MONO_SLOTS.items()},
    }
    data = {"meta": meta, "glyphs": glist}

    t = open(a.template, encoding="utf-8").read()
    woff_b64 = base64.b64encode(open(os.path.join(a.fonts, "Fjellrune-Regular.woff2"), "rb").read()).decode()
    t = (
        t.replace("__FONT_REGULAR__", woff_b64)
        .replace("__GLYPH_DATA__", json.dumps(data, separators=(",", ":")))
        .replace("__VERSION__", B.VERSION)
        .replace("__REPO__", B.REPO_URL)
        .replace("__KERN__", f"{pairs:,}")
        .replace("__CHARS__", str(meta["glyphs"]))
    )
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(t)
    print(f"specimen -> {a.out} ({len(t):,} bytes, {len(glist)} glyphs, {pairs:,} kern pairs)")


if __name__ == "__main__":
    main()
