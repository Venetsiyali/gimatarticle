"""Figure 2: one step of P-stream v1.0.

Writes an SVG next to this script. Convert to PDF with any SVG renderer,
for example: python -c "import cairosvg; cairosvg.svg2pdf(url='x.svg', write_to='x.pdf')"
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 643, 334
TXT, GREY, BLUE, RED, LIGHT = "#2E2E2E", "#7A7A7A", "#1C7DB8", "#C72C2C", "#F2F2F2"
FONT = "Helvetica, Arial, sans-serif"
S = []
def add(x): S.append(x)
def txt(x, y, s, size=8, anchor="middle", fill=TXT, weight="normal", style="normal"):
    add(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'text-anchor="{anchor}" fill="{fill}" font-weight="{weight}" '
        f'font-style="{style}">{s}</text>')
def line(x1, y1, x2, y2, stroke=TXT, sw=0.6, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
        f'stroke-width="{sw}"{d}/>')
def poly(pts, stroke=TXT, sw=0.6, dash=None, marker=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    m = f' marker-end="url(#{marker})"' if marker else ''
    p = " ".join(f"{x},{y}" for x, y in pts)
    add(f'<polyline points="{p}" fill="none" stroke="{stroke}" '
        f'stroke-width="{sw}"{d}{m}/>')

add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
    f'viewBox="0 0 {W} {H}">')
add('<defs>')
for mid, col in (("a", TXT), ("ar", RED), ("ab", BLUE)):
    add(f'<marker id="{mid}" viewBox="0 0 8 8" refX="7" refY="4" '
        f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        f'<path d="M0,1 L7,4 L0,7 z" fill="{col}"/></marker>')
add('</defs>')
add(f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>')

# ---- future region ------------------------------------------------------
FUT = 512
add(f'<rect x="{FUT}" y="26" width="{W-FUT-8}" height="150" '
    f'fill="{RED}" fill-opacity="0.055" stroke="none"/>')
txt(W - 14, 40, "not yet available", 7, "end", RED)
txt(W - 14, 50, "(dated after t)", 7, "end", RED)

# ---- time axis ----------------------------------------------------------
AY = 26
line(30, AY, 622, AY)
add(f'<polyline points="616,22 623,26 616,30" fill="none" stroke="{TXT}" '
    f'stroke-width="0.6"/>')
txt(626, AY - 7, "time", 7, "end", GREY)
for x, lab, w in ((120, "t \u2212 1", "normal"), (300, "t", "bold"),
                  (FUT, "t + 1", "normal")):
    line(x, AY - 4, x, AY + 4)
    txt(x, AY + 15, lab, 8, "middle", TXT, w)

# ---- seven stages -------------------------------------------------------
BY, BH = 92, 26
names = ["INGEST", "SCREEN", "ADMIT", "UPDATE", "FORECAST", "LOG", "SCORE"]
subs = ["stamp a(s)", "score against I(t\u22121)", "I(t\u22121) \u2192 I(t)",
        "refit if the policy says so", "emit \u0177 for t+1 \u2026 t+3",
        "store with weights", "only matured targets"]
widths = [56, 62, 54, 70, 76, 48, 56]
gap = 8
total = sum(widths) + gap * 6
x0 = 30
X = {}
x = x0
for n, w in zip(names, widths):
    X[n] = (x, w)
    x += w + gap
for n, sub in zip(names, subs):
    bx, bw = X[n]
    fill = LIGHT if n == "SCORE" else "#FFFFFF"
    add(f'<rect x="{bx}" y="{BY}" width="{bw}" height="{BH}" rx="3" '
        f'fill="{fill}" stroke="{TXT}" stroke-width="0.6"/>')
    txt(bx + bw / 2, BY + 17, n, 7.5, weight="bold")
    txt(bx + bw / 2, BY - 6, sub, 6.5, "middle", GREY)
for a, b in zip(names, names[1:]):
    ax, aw = X[a]; bx, _ = X[b]
    poly([(ax + aw, BY + BH / 2), (bx - 1, BY + BH / 2)], marker="a")

# step t belongs to the whole row
line(300, AY + 20, 300, BY - 18, GREY, 0.6, "3 3")

# ---- leakage channels ---------------------------------------------------
chan = [("L6", "INGEST",   "gap interpolation",       198),
        ("L3", "SCREEN",   "two-sided decomposition", 214),
        ("L5", "SCREEN",   "full-series threshold",   230),
        ("L7", "ADMIT",    "revision at nominal date",246),
        ("L4", "UPDATE",   "tuning on the window",    262),
        ("L2", "UPDATE",   "unseen normalisation",    278),
        ("L1", "FORECAST", "full-record climatology", 294)]
SRC = FUT + 22
for code, target, label, ly in chan:
    bx, bw = X[target]
    tx = bx + bw / 2
    poly([(SRC, 178), (SRC, ly), (tx + 16, ly), (tx, BY + BH + 2)],
         RED, 0.6, "3 3", "ar")
    # every channel is cut at the information boundary
    line(FUT - 4, ly - 4, FUT + 4, ly + 4, RED, 1.1)
    line(FUT - 4, ly + 4, FUT + 4, ly - 4, RED, 1.1)
    txt(SRC + 8, ly + 3, f"{code}  {label}", 6.5, "start", RED)

line(FUT, 182, FUT, 302, RED, 0.6, "2 3")
txt(FUT - 8, 312, "blocked at the boundary I(t)", 6.5, "end", RED)

# ---- conformance tests --------------------------------------------------
SRC_T = FUT + 22
tests = [("T1", "replace the future with 1e6", 574, 108, SRC - 6, 170),
         ("T2", "truncate the archive at t",        424, 52, FUT - 3, 68),
         ("T3", "rerun with the same seed",         152, 52, 300, 78),
         ("T4", "reorder arrivals",                  46, 62, X["INGEST"][0] + 18, BY - 2)]
for code, label, lx, ly, px, py in tests:
    txt(lx, ly, code, 7.5, "middle", BLUE, "bold")
    txt(lx, ly + 10, label, 6.5, "middle", BLUE)
    poly([(lx, ly + 14), (px, py)], BLUE, 0.6, None, "ab")

# ---- footnote -----------------------------------------------------------
txt(30, H - 14, "Red, dashed: information dated after t. All seven channels "
    "are closed by construction.", 7, "start", "#5A5A5A")
txt(30, H - 5, "Blue, solid: what each conformance test perturbs.",
    7, "start", "#5A5A5A")

add('</svg>')
open(os.path.join(HERE, "fig2_protocol.svg"), "w").write("\n".join(S))
print("written: fig2_protocol.svg")
