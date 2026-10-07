"""Figure 1: architecture of GIMAT v1.0.

Writes an SVG next to this script. Convert to PDF with any SVG renderer,
for example: python -c "import cairosvg; cairosvg.svg2pdf(url='x.svg', write_to='x.pdf')"
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 643, 330                      # 17.0 x 8.6 cm at 96 dpi
TXT, GREY, BLUE, LIGHT = "#2E2E2E", "#7A7A7A", "#1C7DB8", "#F2F2F2"
FONT = "Helvetica, Arial, sans-serif"
S = []
def add(x): S.append(x)

def box(x, y, w, h, fill="#FFFFFF", rx=3, sw=0.6, stroke=TXT, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

def txt(x, y, s, size=8, anchor="middle", fill=TXT, weight="normal",
        style="normal"):
    add(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'text-anchor="{anchor}" fill="{fill}" font-weight="{weight}" '
        f'font-style="{style}">{s}</text>')

def arrow(pts, stroke=TXT, sw=0.6, dash=None, marker="a"):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    p = " ".join(f"{x},{y}" for x, y in pts)
    add(f'<polyline points="{p}" fill="none" stroke="{stroke}" '
        f'stroke-width="{sw}"{d} marker-end="url(#{marker})"/>')

add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
    f'viewBox="0 0 {W} {H}">')
add('<defs>')
for mid, col in (("a", TXT), ("ab", BLUE), ("ag", GREY)):
    add(f'<marker id="{mid}" viewBox="0 0 8 8" refX="7" refY="4" '
        f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        f'<path d="M0,1 L7,4 L0,7 z" fill="{col}"/></marker>')
add('</defs>')
add(f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>')

# ---- zone headers -------------------------------------------------------
HY = 22
for cx, name in ((68, "SENSING"), (196, "STORE"),
                 (392, "PROCESSING CORE"), (574, "INTERFACE")):
    txt(cx, HY, name, 9, fill="#5A5A5A", weight="bold")

# ---- zone 1: sensing ----------------------------------------------------
S1X, S1Y, S1W, S1H = 12, 56, 112, 50
box(S1X, S1Y, S1W, S1H)
for i, line in enumerate(("ultrasonic station",
                          "JSN-SR04T + temperature",
                          "solar, LoRaWAN / GSM")):
    txt(S1X + S1W / 2, S1Y + 18 + i * 12, line, 7.5)
txt(S1X, S1Y + S1H + 14, "±7 mm laboratory", 7, "start", GREY)
txt(S1X, S1Y + S1H + 24, "9.9 mm RMSE in the field", 7, "start", GREY)

# ---- zone 2: store (cylinder) ------------------------------------------
CX, CY, CW, CH, ER = 158, 54, 76, 44, 8
add(f'<path d="M{CX},{CY+ER} a{CW/2},{ER} 0 0,1 {CW},0 '
    f'v{CH-2*ER} a{CW/2},{ER} 0 0,1 -{CW},0 z" '
    f'fill="#FFFFFF" stroke="{TXT}" stroke-width="0.6"/>')
add(f'<path d="M{CX},{CY+ER} a{CW/2},{ER} 0 0,0 {CW},0" '
    f'fill="none" stroke="{TXT}" stroke-width="0.6"/>')
txt(CX + CW / 2, CY + 26, "archive", 7.5)
txt(CX + CW / 2, CY + 37, "(s, v, a(s))", 7.5)
txt(CX + CW / 2, CY - 9, "arrival time stamped on entry", 7, "middle", GREY)

# ---- zone 3: processing core -------------------------------------------
PX, PY, PW, PH = 266, 34, 250, 260          # dashed boundary
box(PX, PY, PW, PH, fill="none", rx=0, sw=1.0, dash="4 4")
txt(PX + 10, PY + 16, "I(t) = {(s,v) : s \u2264 t and a(s) \u2264 t}",
    7.5, "start", TXT, "normal", "italic")

BX, BW = PX + 24, 202
rows = [("SCREEN",   ["seasonal z-score, k = 4"],                       34),
        ("ADMIT",    ["quarantine or accept"],                          34),
        ("UPDATE",   ["C0 \u2026 C4 refit policy"],                     34),
        ("FORECAST", ["climatology\u00b7AR(1) + boosted member",
                      "causal inverse-RMSE weights",
                      "emits \u0177(t+1) \u2026 \u0177(t+3)"],         54)]
y = PY + 30
geom = {}
for name, subs, bh in rows:
    box(BX, y, BW, bh)
    txt(BX + BW / 2, y + 14, name, 8, weight="bold")
    for i, sline in enumerate(subs):
        txt(BX + BW / 2, y + 26 + i * 11, sline, 7)
    geom[name] = (BX, y, BW, bh)
    y += bh + 16
for a, b in (("SCREEN", "ADMIT"), ("ADMIT", "UPDATE"), ("UPDATE", "FORECAST")):
    xa, ya, wa, ha = geom[a]
    arrow([(xa + wa / 2, ya + ha), (xa + wa / 2, geom[b][1] - 1)])

# feedback loop: FORECAST right edge -> around -> UPDATE right edge
fx, fy, fw, fh = geom["FORECAST"]
ux, uy, uw, uh = geom["UPDATE"]
LOOP = fx - 13
arrow([(fx, fy + fh / 2), (LOOP, fy + fh / 2),
       (LOOP, uy + uh / 2), (ux - 1, uy + uh / 2)], BLUE, 0.9, marker="ab")
txt(fx + fw / 2, fy + fh + 13, "verified outcomes \u2192 weights",
    7, "middle", BLUE)

# ---- zone 4: interface --------------------------------------------------
IX, IW = 556, 76
box(IX, 96, IW, 34); txt(IX + IW / 2, 110, "dashboard", 8, weight="bold")
txt(IX + IW / 2, 122, "gimat.uz", 7)
box(IX, 144, IW, 26); txt(IX + IW / 2, 161, "CSV / API", 8, weight="bold")

# ---- inter-zone arrows --------------------------------------------------
arrow([(S1X + S1W, 81), (CX - 1, 81)])
arrow([(CX + CW, 81), (BX - 1, geom["SCREEN"][1] + 17)])
arrow([(fx + fw, fy + 14), (IX - 1, 113)])

RY = PY + PH + 14
arrow([(fx + 40, fy + fh), (fx + 40, RY), (CX + CW / 2, RY),
       (CX + CW / 2, CY + CH + 2)], GREY, 0.6, "3 3", "ag")
txt((CX + CW / 2 + fx + 40) / 2, RY - 5,
    "logged; scored when the observation arrives", 7, "middle", GREY)

# ---- footnote -----------------------------------------------------------
txt(W / 2, H - 8,
    "Nothing inside the dashed boundary reads a value whose arrival time "
    "exceeds t.", 7, "middle", "#5A5A5A")

add('</svg>')
open(os.path.join(HERE, "fig1_architecture.svg"), "w").write("\n".join(S))
print("written: fig1_architecture.svg")
