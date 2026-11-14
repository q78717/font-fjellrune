**Fjellrune 2.000** is ready for Google Fonts.

**New**
- Full Google Fonts Latin Core character set: the Latin languages of Northern, Western, Central, and Eastern Europe, with curly quotes, dashes, currency signs, and combining accents
- Faceted lowercase on a 480-unit x-height with six-sided bowls and 730-unit ascenders
- Native Elder Futhark & Nordic Runic block (`U+16A0`–`U+16F0`)
- Rune-shield medallions: typing 1–3 letters between `<` and `>` (e.g. `<RV>`, `<TH>`, `<ODN>`) sets them inside an octagonal Nordic shield via contextual alternates
- Clean boolean-merged outlines with mitred/bevelled vertices, optical diagonal thinning, and signature axe-nick staves
- Class kerning (7,822 pairs) measured from glyph profiles across all base and accented letters

**Under the hood**
- Built with Google's toolchain: `sources/build_fjellrune.py` writes the UFO source, `gftools builder` compiles and hints it
- FontBakery's Google Fonts profile passes with 0 FAILs

**What's in the zip**
- `ttf/`: `Fjellrune-Regular.ttf` for desktop apps
- `webfonts/`: `Fjellrune-Regular.woff2` for websites
- `Fjellrune-Specimen.html`: interactive self-contained specimen page, works offline
- `OFL.txt`: SIL Open Font License 1.1

Fjellrune is a display face. It reads best at 28 px and up, and medallions at 48 px and up.
