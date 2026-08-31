"""
FJELLRUNE v2.0 - original runic display font, built entirely in Python.
=======================================================================
Inspired by Elder Futhark geometry and jagged Nordic jersey lettering,
but an original design (not affiliated with Nike, NFF, or FIFA).

v2.0 enhancements over v1.0:
  * Norwegian glyphs: AE (Æ), Oslash (Ø), Aring (Å) + lowercase mapping
  * Punctuation: . , - ' ! ? : /
  * Kerning (GPOS) for diagonal-heavy pairs: AV, TA, LY, etc.
  * Optical corrections: diagonals thinned 8%, per-stroke varied chamfer
  * Signature move: "axe nick" - a small triangular notch bitten into
    every long stroke, giving mid-stroke jaggedness no clone font has.

Build:  pip install fonttools && python build_fjellrune.py
Output: Fjellrune-Regular.ttf
"""
import math
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

UPM = 1000
CAP = 700
W = 118              # base stroke width
NOTCH_MIN_LEN = 430  # strokes longer than this get the axe nick
NOTCH_DEPTH = 0.30   # notch depth as fraction of stroke width
NOTCH_HALF = 34      # half-length of the notch along the stroke


def stroke_poly(p1, p2, w=W, ext1=0.62, ext2=0.62, notch=True):
    """Segment -> polygon: chamfered (axe-cut) caps + optional mid-stroke nick.

    Diagonal strokes are optically thinned by 8% so they don't read heavier
    than horizontals/verticals of the same nominal width.
    """
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L == 0:
        return None
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    # optical: thin diagonals
    ang = abs(math.degrees(math.atan2(dy, dx))) % 90
    if 18 < ang < 72:
        w *= 0.92
    h = w / 2
    e1, e2 = w * ext1, w * ext2

    a = (x1 + nx * h, y1 + ny * h)                       # +n side, start
    b = (x2 + nx * h + ux * e2, y2 + ny * h + uy * e2)   # +n side, end (extended)
    c = (x2 - nx * h, y2 - ny * h)                       # -n side, end
    d = (x1 - nx * h - ux * e1, y1 - ny * h - uy * e1)   # -n side, start (extended)

    pts = [a]
    if notch and L >= NOTCH_MIN_LEN:
        # axe nick on the +n edge at 58% along the stroke
        t = 0.58
        mx, my = x1 + dx * t, y1 + dy * t
        depth = w * NOTCH_DEPTH
        pts.append((mx + nx * h - ux * NOTCH_HALF, my + ny * h - uy * NOTCH_HALF))
        pts.append((mx + nx * (h - depth), my + ny * (h - depth)))   # apex, bites inward
        pts.append((mx + nx * h + ux * NOTCH_HALF, my + ny * h + uy * NOTCH_HALF))
    pts += [b, c, d]
    return pts


def R(x, y):
    return (round(x), round(y))


def seg(*pts, w=None):
    """Polyline -> list of segment dicts."""
    out = []
    for i in range(len(pts) - 1):
        s = {'p1': pts[i], 'p2': pts[i + 1]}
        if w:
            s['w'] = w
        out.append(s)
    return out


# ---------------------------------------------------------------- glyphs ----
# Each entry: (segments, advance_width_before_margin)
G = {}

G['A'] = (seg((30, 0), (280, 700)) + seg((280, 700), (530, 0)) + seg((140, 240), (420, 240)), 560)
G['B'] = (seg((60, 0), (60, 700)) + seg((60, 700), (470, 545), (60, 362)) + seg((60, 362), (490, 175), (60, 0)), 540)
G['C'] = (seg((480, 700), (180, 700), (80, 350), (180, 0), (480, 0)), 520)
G['D'] = (seg((60, 0), (60, 700)) + seg((60, 700), (490, 350), (60, 0)), 540)
G['E'] = (seg((60, 0), (60, 700)) + seg((60, 700), (480, 700)) + seg((60, 362), (390, 362)) + seg((60, 0), (480, 0)), 520)
G['F'] = (seg((60, 0), (60, 700)) + seg((60, 700), (480, 700)) + seg((60, 362), (390, 362)), 500)
G['G'] = (seg((480, 700), (180, 700), (80, 350), (180, 0), (480, 0)) + seg((480, 0), (480, 290), (320, 290)), 550)
G['H'] = (seg((60, 0), (60, 700)) + seg((500, 0), (500, 700)) + seg((60, 420), (500, 300)), 560)
G['I'] = (seg((115, 0), (115, 700)), 230)
G['J'] = (seg((360, 700), (360, 150), (140, 0), (40, 110)), 460)
G['K'] = (seg((60, 0), (60, 700)) + seg((60, 330), (490, 700)) + seg((60, 330), (500, 0)), 540)
G['L'] = (seg((60, 700), (60, 0), (470, 0)), 500)
G['M'] = (seg((60, 0), (60, 700), (300, 290), (540, 700), (540, 0)), 600)
G['N'] = (seg((60, 0), (60, 700)) + seg((60, 700), (500, 0)) + seg((500, 0), (500, 700)), 560)
G['O'] = (seg((280, 700), (510, 350), (280, 0), (50, 350), (280, 700)), 560)
G['P'] = (seg((60, 0), (60, 700)) + seg((60, 700), (480, 520), (60, 340)), 520)
G['Q'] = (seg((280, 700), (510, 350), (280, 0), (50, 350), (280, 700)) + seg((360, 200), (545, -60)), 570)
G['R'] = (seg((60, 0), (60, 700)) + seg((60, 700), (480, 520), (60, 340)) + seg((160, 340), (500, 0)), 540)
G['S'] = (seg((450, 700), (110, 700), (110, 430), (430, 290), (430, 0), (90, 0)), 540)
G['T'] = (seg((40, 610), (280, 700), (520, 610)) + seg((280, 700), (280, 0)), 560)
G['U'] = (seg((60, 700), (60, 220), (280, 0), (500, 220), (500, 700)), 560)
G['V'] = (seg((40, 700), (280, 0), (520, 700)), 560)
G['W'] = (seg((30, 700), (160, 0), (310, 470), (460, 0), (590, 700)), 620)
G['X'] = (seg((50, 700), (510, 0)) + seg((510, 700), (50, 0)), 560)
G['Y'] = (seg((40, 700), (280, 330)) + seg((520, 700), (280, 330)) + seg((280, 330), (280, 0)), 560)
G['Z'] = (seg((80, 700), (480, 700), (80, 0), (490, 0)), 550)

# Norwegian
G['AE'] = (seg((20, 0), (330, 700)) + seg((330, 700), (330, 0)) +
           seg((330, 700), (590, 700)) + seg((330, 375), (540, 375)) +
           seg((330, 0), (590, 0)) + seg((120, 240), (330, 240)), 620)
G['Oslash'] = (seg((280, 700), (510, 350), (280, 0), (50, 350), (280, 700)) +
               seg((120, -55), (445, 755)), 560)
G['Aring'] = (seg((30, 0), (280, 700)) + seg((280, 700), (530, 0)) + seg((140, 240), (420, 240)) +
              seg((280, 880), (345, 800), (280, 720), (215, 800), (280, 880), w=64), 560)

# digits
G['0'] = (seg((270, 700), (490, 350), (270, 0), (50, 350), (270, 700)), 540)
G['1'] = (seg((110, 540), (280, 700), (280, 0)) + seg((110, 0), (450, 0)), 500)
G['2'] = (seg((70, 560), (270, 700), (470, 540), (70, 0), (480, 0)), 540)
G['3'] = (seg((100, 700), (440, 700), (440, 0), (100, 0)) + seg((440, 362), (190, 362)), 540)
G['4'] = (seg((370, 700), (60, 240), (500, 240)) + seg((370, 700), (370, 0)), 550)
G['5'] = (seg((450, 700), (110, 700), (110, 400), (430, 330), (430, 90), (140, 0)), 540)
G['6'] = (seg((430, 700), (110, 470), (110, 90), (300, 0), (450, 140), (430, 330), (140, 330)), 540)
G['7'] = (seg((80, 700), (470, 700), (200, 0)) + seg((160, 340), (420, 340)), 530)
G['8'] = (seg((270, 700), (440, 540), (270, 375), (100, 540), (270, 700)) +
          seg((270, 375), (460, 185), (270, 0), (80, 185), (270, 375)), 540)
G['9'] = (seg((130, 0), (440, 240), (440, 610), (250, 700), (100, 560), (120, 370), (410, 370)), 540)

# punctuation
G['period'] = (seg((85, 40), (185, 135)), 270)
G['comma'] = (seg((100, 135), (180, 55)) + seg((150, 80), (60, -130)), 270)
G['hyphen'] = (seg((60, 320), (330, 320)), 390)
G['quotesingle'] = (seg((110, 700), (75, 520)), 190)
G['exclam'] = (seg((140, 700), (140, 250)) + seg((90, 40), (190, 135)), 280)
G['question'] = (seg((70, 570), (210, 700), (400, 620), (255, 400), (255, 250)) +
                 seg((210, 40), (310, 135)), 470)
G['colon'] = (seg((85, 40), (185, 135)) + seg((85, 420), (185, 515)), 270)
G['slash'] = (seg((60, -40), (400, 740)), 460)

DIGIT_NAMES = {'0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
               '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'}
G = {DIGIT_NAMES.get(k, k): v for k, v in G.items()}

CMAP_NAMES = {'AE': 'Æ', 'Oslash': 'Ø', 'Aring': 'Å',
              'period': '.', 'comma': ',', 'hyphen': '-', 'quotesingle': "'",
              'exclam': '!', 'question': '?', 'colon': ':', 'slash': '/'}
CMAP_NAMES.update({name: ch for ch, name in DIGIT_NAMES.items()})
LOWER_EXTRA = {'AE': 'æ', 'Oslash': 'ø', 'Aring': 'å'}


def build_glyph(segments):
    pen = TTGlyphPen(None)
    for s in segments:
        poly = stroke_poly(s['p1'], s['p2'], w=s.get('w', W),
                           notch=s.get('w') is None)  # no notch on thin diacritics
        if not poly:
            continue
        pen.moveTo(R(*poly[0]))
        for pt in poly[1:]:
            pen.lineTo(R(*pt))
        pen.closePath()
    return pen.glyph()


fb = FontBuilder(UPM, isTTF=True)
names = list(G.keys())
glyph_order = ['.notdef', 'space'] + names
fb.setupGlyphOrder(glyph_order)

cmap = {ord(' '): 'space'}
for name in names:
    ch = CMAP_NAMES.get(name, name)
    cmap[ord(ch)] = name
    if ch.isalpha() and len(ch) == 1:
        cmap[ord(ch.lower())] = name
    if name in LOWER_EXTRA:
        cmap[ord(LOWER_EXTRA[name])] = name
fb.setupCharacterMap(cmap)

glyphs = {'.notdef': TTGlyphPen(None).glyph(), 'space': TTGlyphPen(None).glyph()}
for name, (segments, adv) in G.items():
    glyphs[name] = build_glyph(segments)
fb.setupGlyf(glyphs)

metrics = {'.notdef': (600, 0), 'space': (300, 0)}
glyf = fb.font['glyf']
for name, (segments, adv) in G.items():
    g = glyf[name]
    lsb = g.xMin if g.numberOfContours > 0 else 0
    metrics[name] = (adv + 40, lsb)
fb.setupHorizontalMetrics(metrics)
fb.setupHorizontalHeader(ascent=940, descent=-220)
fb.setupNameTable({
    'familyName': 'Fjellrune',
    'styleName': 'Regular',
    'fullName': 'Fjellrune Regular',
    'psName': 'Fjellrune-Regular',
    'uniqueFontIdentifier': 'Fjellrune-Regular-2.0',
    'version': 'Version 2.0',
    'description': 'Original angular runic display font with blade-cut strokes and axe-nick detailing. Built programmatically with fontTools.',
    'licenseDescription': 'SIL Open Font License 1.1',
})
fb.setupOS2(sTypoAscender=940, sTypoDescender=-220, usWinAscent=980, usWinDescent=260)
fb.setupPost()

# ------------------------------------------------------------- kerning ------
FEA = """
feature kern {
    pos A V -55;   pos V A -55;
    pos A W -40;   pos W A -40;
    pos A Y -60;   pos Y A -60;
    pos A T -60;   pos T A -60;
    pos L T -70;   pos L V -70;
    pos L Y -75;   pos L W -50;
    pos F A -45;   pos P A -50;
    pos T J -60;   pos T O -20;
    pos V O -20;   pos Y O -25;
    pos K O -25;   pos O X -20;
    pos R V -30;   pos R Y -35;
    pos A quotesingle -70;  pos quotesingle A -70;
    pos L quotesingle -80;
    pos seven period -60;   pos period seven -40;
    pos T hyphen -50;       pos V hyphen -40;
} kern;
"""
addOpenTypeFeaturesFromString(fb.font, FEA)

fb.save('Fjellrune-Regular.ttf')
print('Fjellrune v2.0 saved:', len(names) + 2, 'glyphs')
