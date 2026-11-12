#!/usr/bin/env python3
"""Render layout/keys.json to layout/keys-a4.pdf (1:1 tiled A4) and layout/keys-preview.png.

Run: .venv/bin/python tools/render_layout.py   (needs matplotlib; see tools/requirements.txt)
"""
import datetime
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Circle, Polygon, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "layout", "keys.json")
PDF = os.path.join(HERE, "..", "layout", "keys-a4.pdf")
PNG = os.path.join(HERE, "..", "layout", "keys-preview.png")

PAGE_W, PAGE_H = 297.0, 210.0
MARGIN, OVERLAP = 10.0, 10.0
PW, PH = PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN   # printable area 277 x 190
LABEL_H = 9.0          # room above the field for module names
CUTOUT = 14.0
GREY = "#d9d9d9"
LIGHT = "#9a9a9a"
PT_PER_MM_PDF = 72.0 / 25.4

plt.rcParams["pdf.fonttype"] = 42


def rot_rect(cx, cy, w, h, rot):
    a = math.radians(rot)
    c, s = math.cos(a), math.sin(a)
    return [(cx + dx * c - dy * s, cy + dx * s + dy * c)
            for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]


def load():
    d = json.load(open(SRC))
    keys, labels = [], []
    xs, ys = [], []
    for name, m in d["modules"].items():
        ax_, ay_ = m["assembly"]["x"], m["assembly"]["y"]
        mx0 = my0 = 1e9
        mx1 = my1 = -1e9
        for k in m["keys"]:
            kk = dict(k, x=k["x"] + ax_, y=k["y"] + ay_)
            keys.append(kk)
            for px, py in rot_rect(kk["x"], kk["y"], k["w"] * d["pitch"] - 1.05,
                                   k["h"] * d["pitch"] - 1.05, k["rot"]):
                mx0, mx1, my0, my1 = min(mx0, px), max(mx1, px), min(my0, py), max(my1, py)
        labels.append((name, (mx0 + mx1) / 2, my0))
        xs += [mx0, mx1]
        ys += [my0, my1]
    return d, keys, labels, (min(xs), min(ys), max(xs), max(ys))


def draw(ax, d, keys, labels, ppm):
    """Draw the assembly in mm data units; ppm = points per mm for text/line sizing."""
    pitch = d["pitch"]
    lw = lambda mm: mm * ppm
    for k in keys:
        x, y, r = k["x"], k["y"], k["rot"]
        cw, ch = k["w"] * pitch - 1.05, k["h"] * pitch - 1.05
        ax.add_patch(Polygon(rot_rect(x, y, k["w"] * pitch, k["h"] * pitch, r), closed=True, fill=False,
                             ec=LIGHT, lw=lw(0.12), ls=(0, (3, 3))))
        ax.add_patch(Polygon(rot_rect(x, y, CUTOUT, CUTOUT, r), closed=True, fc=GREY, ec="none", alpha=0.8))
        if k["kind"] == "encoder":
            ax.add_patch(Circle((x, y), cw / 2, fill=False, ec="k", lw=lw(0.25)))
        else:
            ax.add_patch(Polygon(rot_rect(x, y, cw, ch, r), closed=True, fill=False, ec="k", lw=lw(0.25)))
        ax.plot([x - 1.5, x + 1.5], [y, y], color="r", lw=lw(0.12))
        ax.plot([x, x], [y - 1.5, y + 1.5], color="r", lw=lw(0.12))
        ax.text(x, y - 3.2, k["label"], ha="center", va="center", fontsize=2.6 * ppm, color="k")
        ax.text(x, y + 4.2, "%d,%d" % (k["row"], k["col"]), ha="center", va="center",
                fontsize=1.7 * ppm, color="#0044aa")
        if k["led"] is not None:
            ax.text(x, y + 6.4, "L%d" % k["led"], ha="center", va="center", fontsize=1.7 * ppm,
                    color="#aa4400")
    for name, cx, top in labels:
        ax.text(cx, top - 4, name.upper(), ha="center", va="center", fontsize=4.0 * ppm, weight="bold")


def new_ax(fig, xlim, ylim):
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)     # y down
    ax.axis("off")
    return ax


def clip_all(ax, x0, y0, w, h):
    clip = Rectangle((x0, y0), w, h, transform=ax.transData)
    for art in list(ax.patches) + list(ax.lines) + list(ax.texts):
        art.set_clip_path(clip)


def cross(ax, x, y, r, ppm, circle=True):
    ax.plot([x - r, x + r], [y, y], color="m", lw=0.2 * ppm)
    ax.plot([x, x], [y - r, y + r], color="m", lw=0.2 * ppm)
    if circle:
        ax.add_patch(Circle((x, y), r * 0.6, fill=False, ec="m", lw=0.2 * ppm))


def ruler(ax, x, y, horizontal, ppm):
    lw = 0.3 * ppm
    for i in range(11):
        t = i * 10.0
        big = 3.0 if i % 5 == 0 else 1.8
        if horizontal:
            ax.plot([x + t, x + t], [y, y - big], "k", lw=lw)
            ax.text(x + t, y - big - 1.5, str(int(t)), ha="center", va="center", fontsize=2.0 * ppm)
        else:
            ax.plot([x, x + big], [y + t, y + t], "k", lw=lw)
            ax.text(x + big + 2.0, y + t, str(int(t)), ha="left", va="center", fontsize=2.0 * ppm)
    if horizontal:
        ax.plot([x, x + 100], [y, y], "k", lw=lw)
    else:
        ax.plot([x, x], [y, y + 100], "k", lw=lw)


def render_pdf(d, keys, labels, bb):
    ppm = PT_PER_MM_PDF
    W = bb[2] - bb[0]
    H = (bb[3] - bb[1]) + LABEL_H
    nx = max(1, math.ceil((W - OVERLAP) / (PW - OVERLAP)))
    ny = max(1, math.ceil((H - OVERLAP) / (PH - OVERLAP)))
    covW = nx * PW - (nx - 1) * OVERLAP
    covH = ny * PH - (ny - 1) * OVERLAP
    cx = (bb[0] + bb[2]) / 2
    cy = (bb[1] - LABEL_H + bb[3]) / 2
    X0, Y0 = cx - covW / 2, cy - covH / 2
    ntiles = nx * ny
    today = datetime.date.today().isoformat()
    fname = os.path.basename(PDF)
    last = None
    with PdfPages(PDF, metadata={"Title": "keyboard layout 1:1 template"}) as pdf:
        for ty in range(ny):
            for tx in range(nx):
                n = ty * nx + tx + 1
                tX = X0 + tx * (PW - OVERLAP)
                tY = Y0 + ty * (PH - OVERLAP)
                fig = plt.figure(figsize=(PAGE_W / 25.4, PAGE_H / 25.4), dpi=72)
                ax = new_ax(fig, (tX - MARGIN, tX + PAGE_W - MARGIN), (tY + PAGE_H - MARGIN, tY - MARGIN))
                last = (fig, ax)
                draw(ax, d, keys, labels, ppm)
                P = lambda px, py: (tX + px - MARGIN, tY + py - MARGIN)   # page mm -> drawing mm
                # printable frame
                ax.add_patch(Rectangle((tX, tY), PW, PH, fill=False, ec="#bbbbbb", lw=0.1 * ppm))
                joins = []
                # registration crosses + cut lines for neighbours
                if tx + 1 < nx:
                    ox0 = tX + PW - OVERLAP     # start of the overlap strip
                    joins.append("tile %d on the right" % (n + 1))
                    ax.plot([ox0, ox0], [tY, tY + PH], color="m", lw=0.2 * ppm, ls=(0, (6, 3)))
                    ax.text(ox0 + 1, tY + PH * 0.5, "cut here (overlap with tile %d)" % (n + 1),
                            rotation=90, fontsize=2.2 * ppm, color="m", va="center", ha="left")
                    for f in (0.2, 0.8):
                        cross(ax, ox0 + OVERLAP / 2, tY + PH * f, 4.0, ppm)
                if tx > 0:
                    ox0 = tX
                    joins.append("tile %d on the left" % (n - 1))
                    ax.plot([tX + OVERLAP, tX + OVERLAP], [tY, tY + PH], color="m", lw=0.2 * ppm,
                            ls=(0, (6, 3)))
                    for f in (0.2, 0.8):
                        cross(ax, tX + OVERLAP / 2, tY + PH * f, 4.0, ppm)
                if ty + 1 < ny:
                    oy0 = tY + PH - OVERLAP
                    joins.append("tile %d below" % (n + nx))
                    ax.plot([tX, tX + PW], [oy0, oy0], color="m", lw=0.2 * ppm, ls=(0, (6, 3)))
                    for f in (0.2, 0.8):
                        cross(ax, tX + PW * f, oy0 + OVERLAP / 2, 4.0, ppm)
                if ty > 0:
                    joins.append("tile %d above" % (n - nx))
                    ax.plot([tX, tX + PW], [tY + OVERLAP, tY + OVERLAP], color="m", lw=0.2 * ppm,
                            ls=(0, (6, 3)))
                    for f in (0.2, 0.8):
                        cross(ax, tX + PW * f, tY + OVERLAP / 2, 4.0, ppm)
                clip_all(ax, tX, tY, PW, PH)
                # furniture, placed in page coordinates, drawn after clipping
                title = "tile %d/%d" % (n, ntiles)
                if joins:
                    title += ", joins " + " and ".join(joins)
                ax.text(*P(MARGIN + 2, MARGIN + 4), title, fontsize=4 * ppm, weight="bold", va="center")
                rx = P(MARGIN + 8, 0)[0] if tx == 0 else P(PAGE_W - MARGIN - 28, 0)[0]
                ruler(ax, rx, P(0, MARGIN + 40)[1], False, ppm)
                hx = P(MARGIN + 45, 0)[0] if tx == 0 else P(PAGE_W - MARGIN - 150, 0)[0]
                hy = P(0, PAGE_H - MARGIN - 14)[1]
                ruler(ax, hx, hy, True, ppm)
                ax.text(hx + 50, hy - 11, "must measure 100.0 mm - print at 100% / actual size",
                        ha="center", va="center", fontsize=2.6 * ppm)
                ax.text(*P(MARGIN + 2, PAGE_H - MARGIN - 3), "%s    generated %s" % (fname, today),
                        fontsize=2.4 * ppm, va="center", color="#555555")
                # self-check: ruler length in PDF points
                (a, b) = ax.transData.transform([(hx, hy), (hx + 100, hy)])
                length_pt = math.hypot(b[0] - a[0], b[1] - a[1])
                assert abs(length_pt - 100 * PT_PER_MM_PDF) < 0.01, length_pt
                pdf.savefig(fig)
                plt.close(fig)
    return nx, ny, length_pt


def render_png(d, keys, labels, bb):
    pad = 10.0
    x0, x1 = bb[0] - pad, bb[2] + pad
    y0, y1 = bb[1] - LABEL_H, bb[3] + pad
    w_in = 24.0
    fig = plt.figure(figsize=(w_in, w_in * (y1 - y0) / (x1 - x0)), dpi=100)
    ax = new_ax(fig, (x0, x1), (y1, y0))
    ppm = w_in * 72.0 / (x1 - x0)
    draw(ax, d, keys, labels, ppm)
    fig.savefig(PNG, dpi=100, facecolor="white")
    plt.close(fig)


def main():
    d, keys, labels, bb = load()
    nx, ny, length_pt = render_pdf(d, keys, labels, bb)
    render_png(d, keys, labels, bb)
    print("tiles: %d x %d = %d pages" % (nx, ny, nx * ny))
    print("100 mm ruler = %.2f pt (expected 283.46)" % length_pt)
    print("wrote", os.path.normpath(PDF), os.path.normpath(PNG))


if __name__ == "__main__":
    main()
