#!/usr/bin/env python3
"""Generate layout/keys.json for the 3-module MX keyboard (left, right, numpad).

Run: python3 tools/gen_layout.py   (stdlib only, deterministic)
"""
import json
import math
import os
import sys

PARAMS = {
    "pitch": 19.05,
    "R1": 790.0,
    "frow_gap_u": 0.25,
    "nav_gap_u": 0.5,
    "numpad_gap_u": 0.5,
    "key_field_width_mm": 456.0,
}

CONVENTION = (
    "mm; x to the right, y towards the user (down the page, like KiCad); rot in degrees, "
    "positive = clockwise seen from above; x,y = key (switch) centre; w,h in key units u "
    "(1u = 19.05 mm); keycap = (w*19.05-1.05) x (h*19.05-1.05) mm rotated about the centre."
)

P = PARAMS["pitch"]
R1 = PARAMS["R1"]
CAP_TRIM = 1.05

LEFT_ROWS = [
    "Esc F1 F2 F3 F4 F5 F6",
    "` 1 2 3 4 5 6",
    "Tab:1.5 Q W E R T",
    "Caps:1.75 A S D F G",
    "LShift:2.25 Z X C V B",
    "LCtrl:1.5 LWin:1.5 LAlt:1.5 LSpace:2.75",
]
RIGHT_ROWS = [
    "F7 F8 F9 F10 F11 F12 Del Prt",
    "7 8 9 0 - = Bksp:2",
    "Y U I O P [ ] \\:1.5",
    "H J K L ; ' Enter:2.25",
    "N M , . / RShift:2.75",
    "RSpace:2.75 RAlt:1.75 Fn:1.75 RCtrl:1.5",
]
CHARNAMES = {"`": "GRAVE", "-": "MINUS", "=": "EQUAL", "[": "LBRACKET", "]": "RBRACKET",
             "\\": "BSLASH", ";": "SEMI", "'": "QUOTE", ",": "COMMA", ".": "DOT",
             "/": "SLASH", "*": "STAR", "+": "PLUS"}

NAV_MATRIX = {"K1": (0, 8), "Home": (1, 7), "Ins": (1, 8), "NavDel": (2, 8), "End": (3, 7),
              "PgDn": (3, 8), "Up": (4, 6), "K2": (4, 7), "Dial": (4, 8), "PgUp": (5, 4),
              "Left": (5, 5), "Down": (5, 6), "Right": (5, 7)}


def slug(label):
    return "".join(CHARNAMES.get(c, c.upper()) for c in label)


def parse_row(s):
    out = []
    for tok in s.split():
        if ":" in tok and not tok.startswith(":") and tok.rsplit(":", 1)[1].replace(".", "").isdigit():
            lab, w = tok.rsplit(":", 1)
            out.append((lab, float(w)))
        else:
            out.append((tok, 1.0))
    return out


def radius(p):
    if p == 4:
        return R1
    if p == 3:
        return R1 + P
    if p == 2:
        return R1 + 2 * P
    if p == 1:
        return R1 + 3 * P
    if p == 0:
        return R1 + 4 * P + PARAMS["frow_gap_u"] * P
    raise ValueError(p)


def mk(prefix, label, x, y, rot, w, h, row, col, prow, kind="switch"):
    return {"id": prefix + slug(label), "label": label, "x": x, "y": y, "rot": rot,
            "w": w, "h": h, "row": row, "col": col, "led": None, "prow": prow,
            "kind": kind, "stab": bool(w >= 2 or h >= 2)}


def alpha_half(side, x0, yc):
    rows = LEFT_ROWS if side == "left" else RIGHT_ROWS
    prefix = "L_" if side == "left" else "R_"
    sgn = 1 if side == "left" else -1
    keys = []
    parsed = [parse_row(r) for r in rows]
    shift_w = sum(w for _, w in parsed[4])
    phiW = shift_w * P / R1
    alpha = phiW / 2
    for p, row in enumerate(parsed):
        n = len(row)
        order = range(n) if side == "left" else range(n - 1, -1, -1)
        acc = 0.0
        for idx in order:
            lab, w = row[idx]
            d = (acc + w / 2) * P
            acc += w
            if p <= 4:
                R = radius(p)
                phi = d / R
                x = x0 + sgn * R * math.sin(phi)
                y = yc - R * math.cos(phi)
                rot = sgn * math.degrees(phi)
            else:
                px, py = x0, yc - R1 + P
                x = px + sgn * d * math.cos(alpha)
                y = py + d * math.sin(alpha)
                rot = sgn * math.degrees(alpha)
            keys.append(mk(prefix, lab, x, y, rot, w, 1, p, idx, p))
    return keys


def nav_keys(x0, yc):
    yF, yNum, yQ, yShift = yc - radius(0), yc - radius(1), yc - radius(2), yc - radius(4)
    yArrow = yShift + P
    cx = lambda k: x0 + (PARAMS["nav_gap_u"] + 0.5 + k) * P
    spec = [("K1", 0, yF, 0), ("K2", 1, yF, 0), ("Dial", 2, yF, 0),
            ("Ins", 0, yNum, 1), ("Home", 1, yNum, 1), ("PgUp", 2, yNum, 1),
            ("NavDel", 0, yQ, 2), ("End", 1, yQ, 2), ("PgDn", 2, yQ, 2),
            ("Up", 1, yShift, 4),
            ("Left", 0, yArrow, 5), ("Down", 1, yArrow, 5), ("Right", 2, yArrow, 5)]
    out = []
    for lab, k, y, prow in spec:
        r, c = NAV_MATRIX[lab]
        out.append(mk("R_", lab, cx(k), y, 0.0, 1, 1, r, c, prow,
                      "encoder" if lab == "Dial" else "switch"))
    return out


def numpad_keys(col0x, yc):
    ys = [yc - radius(0), yc - radius(1), yc - radius(2), yc - radius(3), yc - radius(4)]
    yF, yNum, yQ, yHome, yShift = ys
    yArrow = yShift + P
    cx = lambda c: col0x + c * P
    out = []

    def add(lab, x, y, w, h, r, c, prow):
        out.append(mk("N_", lab, x, y, 0.0, w, h, r, c, prow))
    for c, lab in enumerate(["M1", "M2", "M3", "M4"]):
        add(lab, cx(c), yF, 1, 1, 0, c, 0)
    for c, lab in enumerate(["Clr", "/", "*", "-"]):
        add(lab, cx(c), yNum, 1, 1, 1, c, 1)
    for c, lab in enumerate(["7", "8", "9"]):
        add(lab, cx(c), yQ, 1, 1, 2, c, 2)
    add("KP+", cx(3), (yQ + yHome) / 2, 1, 2, 2, 3, 2)
    for c, lab in enumerate(["4", "5", "6"]):
        add(lab, cx(c), yHome, 1, 1, 3, c, 3)
    for c, lab in enumerate(["1", "2", "3", "KPEnter"]):
        add(lab, cx(c), yShift, 1, 1, 4, c, 4)
    add("KP0", cx(0.5), yArrow, 2, 1, 5, 0, 5)
    add("KP.", cx(2), yArrow, 1, 1, 5, 2, 5)
    add("KP=", cx(3), yArrow, 1, 1, 5, 3, 5)
    return out


def assign_leds(keys):
    idx = 0
    for p in range(6):
        row = sorted([k for k in keys if k["prow"] == p and k["kind"] != "encoder"],
                     key=lambda k: k["x"])
        if p % 2 == 1:
            row.reverse()
        for k in row:
            k["led"] = idx
            idx += 1


def corners(k, ox=0.0, oy=0.0):
    hw = (k["w"] * P - CAP_TRIM) / 2
    hh = (k["h"] * P - CAP_TRIM) / 2
    a = math.radians(k["rot"])
    c, s = math.cos(a), math.sin(a)
    pts = []
    for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
        pts.append((k["x"] + ox + dx * c - dy * s, k["y"] + oy + dx * s + dy * c))
    return pts


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def sat_separated(A, B):
    for poly in (A, B):
        for i in range(4):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % 4]
            nx, ny = y2 - y1, x1 - x2
            pa = [nx * x + ny * y for x, y in A]
            pb = [nx * x + ny * y for x, y in B]
            if max(pa) < min(pb) - 1e-9 or max(pb) < min(pa) - 1e-9:
                return True
    return False


def poly_gap(A, B):
    d = 1e9
    for X, Y in ((A, B), (B, A)):
        for pt in X:
            for i in range(4):
                d = min(d, seg_dist(pt, Y[i], Y[(i + 1) % 4]))
    return d


def r3(v):
    v = round(v, 3)
    return 0.0 if v == 0 else v


def build():
    pitch = P
    yc = 0.0
    # right x0 from the field width: right edge of numpad col 3 = x0 + 8 u-ish
    nav_gap, np_gap = PARAMS["nav_gap_u"], PARAMS["numpad_gap_u"]
    right_edge_off = ((nav_gap + 0.5 + 2) + (0.5 + np_gap + 0.5) + 3 + 0.5) * pitch
    x0r = PARAMS["key_field_width_mm"] - right_edge_off
    col0x = x0r + (nav_gap + 0.5 + 2) * pitch + (0.5 + np_gap + 0.5) * pitch
    mods = {
        "left": alpha_half("left", 0.0, yc),
        "right": alpha_half("right", x0r, yc) + nav_keys(x0r, yc),
        "numpad": numpad_keys(col0x, yc),
    }
    for ks in mods.values():
        assign_leds(ks)
    # frames
    allpts = [pt for ks in mods.values() for k in ks for pt in corners(k)]
    gx, gy, _, _ = bbox(allpts)
    out = {}
    for name, ks in mods.items():
        mx, my, _, _ = bbox([pt for k in ks for pt in corners(k)])
        for k in ks:
            k["x"] = r3(k["x"] - mx)
            k["y"] = r3(k["y"] - my)
            k["rot"] = r3(k["rot"])
        out[name] = {"keys": ks, "assembly": {"x": r3(mx - gx), "y": r3(my - gy), "rot": 0}}
    out["left"]["matrix"] = {"rows": 6, "cols": 7}
    out["right"]["matrix"] = {"rows": 6, "cols": 9}
    out["numpad"]["matrix"] = {"rows": 6, "cols": 4}
    return out


def check(mods):
    errs = []
    expect = {"left": 36, "right": 53, "numpad": 22}
    ids = set()
    for name, m in mods.items():
        ks = m["keys"]
        if len(ks) != expect[name]:
            errs.append(f"{name}: {len(ks)} keys, expected {expect[name]}")
        sw = sum(1 for k in ks if k["kind"] == "switch")
        if name == "right" and sw != 52:
            errs.append(f"right: {sw} switches, expected 52")
        for k in ks:
            if k["id"] in ids:
                errs.append("duplicate id " + k["id"])
            ids.add(k["id"])
        rc = [(k["row"], k["col"]) for k in ks]
        if len(set(rc)) != len(rc):
            errs.append(f"{name}: duplicate (row,col)")
        R, C = m["matrix"]["rows"], m["matrix"]["cols"]
        if any(not (0 <= r < R and 0 <= c < C) for r, c in rc):
            errs.append(f"{name}: (row,col) out of bounds")
        leds = sorted(k["led"] for k in ks if k["led"] is not None)
        if leds != list(range(len(leds))):
            errs.append(f"{name}: LED indices not contiguous")
    polys = []
    for name, m in mods.items():
        a = m["assembly"]
        for k in m["keys"]:
            polys.append((name, k["id"], corners(k, a["x"], a["y"])))
    best = (1e9, None)
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            A, B = polys[i], polys[j]
            if not sat_separated(A[2], B[2]):
                errs.append(f"OVERLAP {A[1]} / {B[1]}")
                continue
            g = poly_gap(A[2], B[2])
            if g < best[0]:
                best = (g, (A[1], B[1]))
    return errs, best, polys


def main():
    mods = build()
    errs, (gap, pair), polys = check(mods)
    print("counts:", {n: len(m["keys"]) for n, m in mods.items()},
          "| switches in right:", sum(1 for k in mods["right"]["keys"] if k["kind"] == "switch"))
    print("LEDs:", {n: sum(1 for k in m["keys"] if k["led"] is not None) for n, m in mods.items()})
    print(f"min keycap gap: {gap:.3f} mm between {pair[0]} and {pair[1]}")
    for n in mods:
        b = bbox([pt for nm, _, poly in polys if nm == n for pt in poly])
        a = mods[n]["assembly"]
        print(f"bbox {n}: {b[2]-b[0]:.1f} x {b[3]-b[1]:.1f} mm, assembly origin ({a['x']}, {a['y']})")
    b = bbox([pt for _, _, poly in polys for pt in poly])
    print(f"bbox assembly: {b[2]-b[0]:.1f} x {b[3]-b[1]:.1f} mm")
    if errs:
        for e in errs:
            print("FAIL:", e, file=sys.stderr)
        sys.exit(1)

    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "layout", "keys.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    js = lambda o: json.dumps(o, separators=(",", ":"), ensure_ascii=False)
    lines = ["{", '"version":1,', '"units":"mm",', '"pitch":%s,' % js(P),
             '"convention":%s,' % js(CONVENTION), '"params":%s,' % js(PARAMS), '"modules":{']
    names = list(mods)
    for i, n in enumerate(names):
        m = mods[n]
        lines.append('"%s":{"matrix":%s,"assembly":%s,"keys":[' % (n, js(m["matrix"]), js(m["assembly"])))
        lines.append(",\n".join(js(k) for k in m["keys"]))
        lines.append("]}" + ("," if i < len(names) - 1 else ""))
    lines += ["}", "}"]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    json.load(open(path))
    print("wrote", os.path.normpath(path))


if __name__ == "__main__":
    main()
