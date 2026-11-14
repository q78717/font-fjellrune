# Design — Fjellrune

## 1. Introduction
Fjellrune is an original angular Nordic display typeface inspired by Elder Futhark geometry and carved runestone lettering. Its technical philosophy is **Pure Algorithmic Type Design**: every outline, boolean stroke union, mark attachment anchor, bind-rune medallion ligature, and profile-based kerning table is generated in Python (`sources/build_fjellrune.py`), written to a standard UFO source, and compiled with Google Fonts' `gftools builder` pipeline.

## 2. Tech Stack
- **Language**: Python 3.10+
- **Outline Synthesis & Boolean Geometry**: `skia-pathops`, `fontTools`, `ufoLib2`, `numpy`
- **Font Compilation & Hinting**: `gftools builder`, `fontmake`, `ufo2ft`, `ttfautohint-py`
- **Quality Assurance**: `FontBakery` (`googlefonts` profile) / `fontspector`
- **License**: SIL Open Font License 1.1 (`OFL.txt`)

## 3. Technical Architecture
- **Blade-Cut Polygonal Synthesis**: Every glyph is constructed in `sources/build_fjellrune.py` from straight polygonal strokes with mitred/bevelled vertices (`MITRE_LIMIT = 2.05`), chamfered ("axe-cut") terminals, and boolean contour union via `skia-pathops`.
- **Optical Corrections**: Diagonal strokes (`18° < θ < 72°`) are thinned by 9% relative to vertical staves (`W = 92` for capitals/figures, `W_LC = 82` for lowercase) so acute vertices remain crisp.
- **Signature Feature ("Axe Nick")**: Long strokes (`≥ 330` units) receive an algorithmic triangular notch (`28%` stroke depth) along their leading edge.
- **Rune-Shield Medallions (`calt` / `liga`)**: Typing 1 to 3 letters between `<` and `>` (e.g. `<RV>`, `<TH>`, `<ODN>`) substitutes `<` with an octagonal Nordic rune-shield (`monogram.ring`) and overlays scaled, centered initial glyphs (`*.mono1`, `*.mono2l/r`, `*.mono3l/c/r`).
- **Profile-Based Class Kerning**: `auto_kern()` rasterizes horizontal scanline profiles across all base and composite glyph groups to compute 7,822 kerning pairs.

## 4. Repository Layout (Google Fonts Template)
```text
font-fjellrune/
├── .github/workflows/            # CI build/test, GitHub Pages specimen, Release packaging
├── AUTHORS.txt                   # Copyright holders
├── CONTRIBUTORS.txt              # Project contributors
├── DESIGN.md                     # Architectural specification
├── Makefile                      # Standard build, test, proof, images, and update targets
├── OFL.txt                       # SIL Open Font License 1.1
├── README.md                     # User & developer documentation
├── requirements.in               # Top-level build dependencies
├── requirements.txt              # Locked build dependencies
├── requirements-qa.txt           # FontBakery & shaping QA dependencies
├── documentation/
│   ├── article/                  # Google Fonts article & banner image
│   ├── images/                   # Rendered PNG specimens for README
│   └── specimen/index.html       # Self-contained interactive HTML specimen
├── fonts/
│   ├── ttf/Fjellrune-Regular.ttf
│   └── webfonts/Fjellrune-Regular.woff2
└── sources/
    ├── build.sh                  # Single-command build pipeline
    ├── build_fjellrune.py        # Algorithmic UFO generator
    ├── build_specimen.py         # Specimen compiler
    ├── config.yaml               # gftools builder configuration
    ├── specimen_template.html    # Interactive specimen template
    ├── tools/                    # STAT builder, image renderer, medallion smoke test
    └── ufo/Fjellrune-Regular.ufo # Generated UFO source
```

## 5. Character Set & OpenType Features
- **Google Fonts Latin Core**: Full coverage of Northern, Western, Central, and Eastern European Latin (`A–Z`, `a–z`, `Æ`, `Ø`, `Å`, `Þ`, `Ð`, `Œ`, `ß`, `ẞ`, accented composites, and combining marks with `mark`/`mkmk` anchor propagation and `ccmp` dotless `i`/`j`).
- **Elder Futhark & Nordic Runes**: Native support for the Unicode Runic block (`U+16A0`–`U+16F0`).
- **OpenType Features**: `ccmp`, `locl`, `mark`, `mkmk`, `calt`, `liga`, `kern`, plus `STAT` and `meta` (`Latn`, `Runr`) tables.

## 6. Build & QA Verification
- **Build All Artifacts**: `make build` (or `./sources/build.sh`)
- **Regenerate Documentation Images**: `make images`
- **Run Google Fonts QA**: `fontbakery check-googlefonts fonts/ttf/Fjellrune-Regular.ttf` (0 FAILs)
