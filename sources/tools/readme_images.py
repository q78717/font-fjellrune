#!/usr/bin/env python3
"""Render the README and article images in documentation/ from the built font (`make images`)."""
import os
import sys
import unicodedata

from fontTools.ttLib import TTFont
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grid  # noqa: E402
from shape_proof import line, stack  # noqa: E402

OFF, RED, DENIM = (246, 242, 233), (196, 48, 43), (62, 97, 148)
F = "fonts/ttf/Fjellrune-Regular.ttf"
OUT = "documentation/images"
ART_OUT = "documentation/article"


def pad(img, w):
    out = Image.new("RGB", (w, img.height), OFF)
    out.paste(img, (0, 0))
    return out


def save(rows, path):
    w = max(i.width for i in rows)
    stack([pad(i, w) for i in rows]).save(path)
    print(path)


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(ART_OUT, exist_ok=True)
    save(
        [
            line(F, "FJELLRUNE", 195, pad=36),
            line(F, "Angular Nordic display type with blade-cut strokes & axe-nick staves.", 48, pad=36),
            line(F, "<RV> <TH> <ODN>   ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ", 96, color=RED, pad=36),
        ],
        os.path.join(OUT, "fjellrune-banner.png"),
    )
    save(
        [
            line(F, "<RV> <TH> <TYR> <ODN> <Q>", 126, pad=28),
            line(F, "ᚠ ᚢ ᚦ ᚨ ᚱ ᚲ ᚷ ᚹ ᚺ ᚾ ᛁ ᛃ ᛇ ᛈ ᛉ ᛊ ᛏ ᛒ ᛖ ᛗ ᛚ ᛜ ᛞ ᛟ", 76, color=DENIM, pad=28),
        ],
        os.path.join(OUT, "runes.png"),
    )
    save(
        [
            line(F, "Sølvløve fra Tromsø & Ålesund · Þór & Óðinn", 64, pad=28),
            line(F, "Žluťoučký kůň úpěl ďábelské ódy", 64, pad=28),
            line(F, "Zażółć gęślą jaźń · Árvíztűrő tükörfúrógép", 64, pad=28),
            line(F, "«Quotes» “curly” — £12 €34 ¥56 ₹78 © ® ™", 64, pad=28),
        ],
        os.path.join(OUT, "languages.png"),
    )
    save(
        [
            line(F, "Fjellrune", 160, pad=30),
            line(F, "Nordic runic display · Ærøskøbing · Žluťoučký", 56, pad=30),
            line(F, "<RV> <TH> <ODN>   ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃ", 92, color=RED, pad=30),
        ],
        os.path.join(ART_OUT, "fjellrune-article.png"),
    )
    cmap = TTFont(F).getBestCmap()
    chars = "".join(
        chr(c)
        for c in sorted(cmap)
        if c > 32 and c not in (0xA0, 0x2028, 0x2029, 0x25CC) and unicodedata.category(chr(c)) != "Mn"
    )
    grid.grid(F, chars, os.path.join(OUT, "glyphs.png"), px=88, cols=20)


if __name__ == "__main__":
    main()
