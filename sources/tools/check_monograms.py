#!/usr/bin/env python3
"""Smoke test: bind-rune medallion substitution works in Fjellrune, and leaves other text alone."""
import os
import sys

import uharfbuzz as hb

CASES = {
    "<RV>": ["monogram.ring", "R.mono2l", "V.mono2r", "monogram.end"],
    "<TH>": ["monogram.ring", "T.mono2l", "H.mono2r", "monogram.end"],
    "<odin>": ["less", "o", "d", "i", "n", "greater"],
    "<odn>": ["monogram.ring", "O.mono3l", "D.mono3c", "N.mono3r", "monogram.end"],
    "<Q>": ["monogram.ring", "Q.mono1", "monogram.end"],
    "a < b > c": ["a", "space", "less", "space", "b", "space", "greater", "space", "c"],
}


def shape(path, text):
    font = hb.Font(hb.Face(hb.Blob.from_file_path(path)))
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    return [font.glyph_to_string(i.codepoint) for i in buf.glyph_infos]


def main(folder):
    bad = 0
    for fn in ("Fjellrune-Regular.ttf",):
        for text, want in CASES.items():
            got = shape(os.path.join(folder, fn), text)
            if got != want:
                bad += 1
                print(f"FAIL {fn} {text!r}: {got}")
    print("medallions ok" if not bad else f"{bad} medallion check(s) failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "fonts/ttf"))
