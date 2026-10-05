# Design — Fjellrune

## 1. Introduction
Fjellrune is an original runic display typeface inspired by Elder Futhark geometry and jagged Nordic aesthetic. Its technical philosophy is "Pure Algorithmic Type Design": the entire typeface—outlines, kerning tables, and optical corrections—is defined algorithmically in Python and compiled directly into TrueType format.

## 2. Tech Stack
- **Language**: Python 3.10+
- **Font Generation**: `fontTools` (`FontBuilder`, `TTGlyphPen`, `addOpenTypeFeaturesFromString`)
- **License**: SIL Open Font License 1.1 (`OFL-LICENSE.txt`)
- **Specimen**: HTML5, CSS3

## 3. Technical Architecture
- **Geometric Vector Synthesis**: Glyphs are generated using mathematical coordinate calculations in `build_fjellrune.py`. Rather than importing external static SVGs, each stroke is drawn via `TTGlyphPen` commands.
- **Optical Corrections**: Diagonal strokes are algorithmically thinned by 8% relative to vertical stems to equalize perceived optical weight.
- **OpenType Layout Engine (GPOS)**: Generates feature code via `fontTools.feaLib` to compile kerning pairs directly for diagonal-heavy combinations (AV, TA, LY, etc.).
- **Signature Feature ("Axe Nick")**: An algorithmic triangular notch inserted into long strokes to introduce characteristic mid-stroke jaggedness.

## 4. File Structure
```text
font-fjellrune/
├── build_fjellrune.py       # Algorithmic font generation and GPOS feature compiler
├── Fjellrune-Regular.ttf    # Compiled TrueType font file
├── Fjellrune-Specimen.html  # Interactive typography specimen and glyph table
└── OFL-LICENSE.txt          # Open Font License terms
```

## 5. Implementation Details
- **Metrics Grid**: Standard 1000 UPM grid with 700 Cap Height and base stroke width of 118 units.
- **Character Support**: Full Latin uppercase, Norwegian extensions (Æ, Ø, Å), punctuation (`. , - ' ! ? : /`), and mapped lowercase characters.
- **OpenType Kerning**: Uses Adobe Feature File syntax compiled into standard OpenType GPOS tables.

## 6. Build & Run
- **Install Dependencies**: `pip install fonttools`
- **Build Font**: `python3 build_fjellrune.py`
- **Specimen Inspection**: Open `Fjellrune-Specimen.html` in a web browser.

## 7. Tooling & Dependencies
- `fontTools`: Provides `FontBuilder`, `TTGlyphPen`, and `feaLib` for binary font generation and OpenType feature compiling.

## 8. Security & Standards
- Conforms to OpenType TTF specifications (OpenType 1.9).
- Free and open-source under the SIL Open Font License 1.1.
