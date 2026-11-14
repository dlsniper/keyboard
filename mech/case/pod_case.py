"""Wireless variant of a key-module shell (M3b step 3, spec 2b "Shell"); loaded by build_case.py when CASE_VARIANT=pod.

  CASE_VARIANT=pod CASE_MODULE=numpad /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd mech/case/build_case.py
  output: build/case/numpad-pod/ (GUI document "case_numpad_pod")

User decisions 2026-11-14 (options UI, shown in FreeCAD): tray and battery rail are ONE print; two sliding cell lids
with a snap ridge; a Keystone 5201 spring at both ends of the three-cell column; the rear cell on 5223 (button) and
5201 with the power board notched for the spring's wall; service port stays on the pod's rear edge.

Frame as build_case.py (x right, y rear, z up from the desk). Only an unrotated rear edge (numpad) so far: left and
right need the rail turned with their rear strip and their own cell plan.

Rail: side leg 19 mm (pocket 15 mm, the three cells end to end like a torch), rear leg 27 mm (rear cell in the front
lane, wires and the pack plug behind it, the power board east of it on two bosses with inserts and five posts).
Contact plates drop from above into slots; a rib with a window for the spring holds each plate. Wires: the solder
tabs point up and are bent over; column wires lie in the pocket's bottom corner beside the cells (a 15 mm square
round a 14.5 mm cell leaves 2.5 mm there), the strip in front of the power board takes them west, the column's
minus wire passes under the board (2 mm, PB_POSTS keep its path free).
Under the pod the rail walls end at DECK; the cover over the pod closes that part (no separate deck plate: the lead
has to drop from the pod's west edge into the rail there).
Lids slide in grooves of the rail walls (side lid out to the front, rear lid out to the west, where the end wall is
lowered); a ridge under the lid's outer end drops behind that wall. The rear lid ends under the cover's hood; the
hood's west wall is arched over the cell lane so that the cell can be tipped out.
"""
import Part
import FreeCAD as App

V = App.Vector


def box(x0, x1, y0, y1, z0, z1):
    x0, x1 = min(x0, x1), max(x0, x1); y0, y1 = min(y0, y1), max(y0, y1)
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def fuse(shapes):
    s = shapes[0]
    for o in shapes[1:]:
        s = s.fuse(o)
    return s


def build(c, parts, refs, fits):
    g = type("G", (), c)
    assert abs(g.ua.x - 1) < 1e-6 and abs(g.ut.y - 1) < 1e-6, "pod variant: only an unrotated rear edge (numpad) so far"
    ob = g.ob
    X0, X1, Y0, Y1, RX1, RY1 = ob.XMin, ob.XMax, ob.YMin, ob.YMax, g.rx1, g.ry1
    W, RF, TOP = g.RAIL_WALL, g.RAIL_FLOOR, g.RAIL_H
    SLOT, RIB, BACK = g.SLOT, g.RIB, g.BACK
    zc = RF + g.AA_D / 2
    R = g.poly([V(X0, Y0, 0), V(RX1, Y0, 0), V(RX1, RY1, 0), V(X0, RY1, 0)]).makeOffset2D(-5.7, join=2).makeOffset2D(5.7)
    body = g.tray0.fuse(g.prism(R.cut(g.outer_f), 0, TOP))

    # ---- places
    px0, px1 = RX1 - W - g.POCKET_W, RX1 - W                  # side pocket
    xs = (px0 + px1) / 2
    yf = Y0 + W                                               # column: front plate's back face
    yr = yf + 2 * SLOT + 2 * g.SPRING_COL + 3 * g.AA_LMAX     # rear plate's back face
    bx0, by1 = RX1 - W - 0.3 - g.PB[0], RY1 - W - 0.5         # power board: west end, rear edge
    Pb = lambda u, v: V(bx0 + u, by1 - v, 0)
    ly0 = Y1 + 1.49; ly1 = ly0 + g.POCKET_W; yc = (ly0 + ly1) / 2     # rear cell lane
    lx0 = X0 + W
    e = lx0 + SLOT + g.DOME + g.AA_LMAX + g.SPRING_ONE + SLOT + 1.1   # east face of the rear spring's wall
    notch_x, notch_y = bx0 + g.PB_OUT[5][0], by1 - g.PB_OUT[6][1]     # the board's west notch: east edge, rear edge
    assert yr + BACK < by1 - g.PB_OUT[2][1] - 0.25, "column's rear wall reaches the power board"
    assert e < notch_x - 0.3 and yc + g.PLATE[0] / 2 + 0.2 < notch_y - 0.3, "rear spring wall does not fit the board's west notch"
    hx0 = g.b0.x + g.HOOD_X0                                  # cover's west end over the rail
    lid_x1 = hx0 + 1.8                                        # rear lid ends just inside the hood
    low_x0 = e + 0.6                                          # from here east the rail walls end at DECK

    # ---- cavities
    cav = [box(px0, px1, yf, yr + BACK, RF, 99),                                   # side column
           box(bx0 - 0.3, px1, Y1, RY1 - W, RF, 99),                              # power board bay with the wire strip in front
           box(lx0, e, ly0, ly1, RF, 99),                                         # rear cell
           box(lx0, bx0 - 0.3, ly1 + 1.2, RY1 - W, RF, 99),                       # wires, pack plug
           box(lx0, lx0 + 4.0, ly1 - 0.1, ly1 + 1.3, RF, 99),                     # round the divider's west end
           box(bx0 - 12.0, bx0 - 0.3, ly1 - 0.1, ly1 + 1.3, RF, 99)]              # the pack plug's body
    body = body.cut(fuse(cav))

    def holder(axis, s, pf, lo, hi, cc, back, notch=True):
        """Plate holder: plate front face at pf on the axis, cell on side s; lo..hi across, plate centred on cc."""
        a0, a1 = pf - s * (SLOT + back), pf + s * RIB
        bx = (lambda u0, u1, v0, v1, z0, z1: box(u0, u1, v0, v1, z0, z1)) if axis == "x" else (lambda u0, u1, v0, v1, z0, z1: box(v0, v1, u0, u1, z0, z1))
        h = bx(a0, a1, lo, hi, RF - 0.1, zc + 6.5)
        h = h.cut(bx(pf - s * SLOT, pf, cc - g.PLATE[0] / 2 - 0.2, cc + g.PLATE[0] / 2 + 0.2, zc - g.PLATE[1] / 2 - 0.2, 99))
        h = h.cut(bx(pf - s * 0.01, pf + s * (RIB + 0.01), cc - g.WINDOW / 2, cc + g.WINDOW / 2, zc - 3.5, 99))
        if notch:                                             # wire through the bottom corner
            h = h.cut(bx(a0 - 0.01, a1 + 0.01, lo - 0.01, lo + 1.9, RF, RF + 3.0))
        return h
    hold = [holder("y", 1, yf + SLOT, px0, px1, xs, 0.0), holder("y", -1, yr - SLOT, px0, px1, xs, BACK),
            holder("x", 1, lx0 + SLOT, ly0, ly1, yc, 0.0, False),
            holder("x", -1, e - 1.1 - SLOT, Y1, notch_y - 0.3, yc, 1.1)]
    body = body.fuse(fuse(hold))
    bosses = [Pb(*h) for h in g.PB_HOLES]
    posts = [Pb(*p) for p in g.PB_POSTS]
    body = body.fuse(fuse([g.cyl(p, g.BOSS_D, RF - 0.1, g.PB_Z) for p in bosses] + [g.cyl(p, 3.0, RF - 0.1, g.PB_Z) for p in posts]))
    for p in bosses:
        body = body.cut(g.cyl(p, g.INSERT_D, g.PB_Z - g.INSERT_DEPTH, g.PB_Z + 1))

    # ---- lowered walls under the pod, switch slot, lid grooves and entries
    G, LZ = g.GROOVE, g.LID_Z
    gy0, gy1 = ly0 - G, RY1 - W + G
    zs = g.PB_Z + 1.6 + 0.4
    cuts = [box(low_x0, X1, Y1 - 6, RY1 + 1, g.DECK, 99),            # (and the filled corner beside the tray's rounded one)
            box(bx0 + g.SW_U - g.SW_SLOT[0] / 2, bx0 + g.SW_U + g.SW_SLOT[0] / 2, RY1 - W - 1, RY1 + 1, zs, zs + g.SW_SLOT[1]),
            box(px0 - G, px1 + G, Y0 - 1, RY1 - W + G, LZ, LZ + g.LID_EDGE + 0.1),        # side lid: grooves
            box(px0 - G, px1 + G, Y0 - 1, yf, LZ, 99),                                    # its entry at the front
            box(X0 - 1, lid_x1, gy0, gy1, LZ, LZ + g.LID_EDGE + 0.1),                     # rear lid: grooves
            box(X0 - 1, lx0, gy0, gy1, LZ, 99),                                           # its entry at the west end
            box(lx0, low_x0, ly0, RY1 - W, LZ, 99)]                                       # divider and holder tops under the lid
    body = body.cut(fuse(cuts))
    for q in g.feet:
        body = body.cut(g.cyl(q, g.FOOT_D, -1, g.FOOT_DEPTH))
    body = body.removeSplitter()
    inR = g.prism(R, 0, 99)
    lid_side = fuse([box(px0 - G + 0.1, px1 + G - 0.1, Y0, RY1 - W + G - 0.2, LZ, LZ + g.LID_EDGE),
                     box(px0 + 0.15, px1 - 0.15, Y0, RY1 - W - 0.15, LZ, LZ + g.LID_T),
                     box(px0 + 2.0, px1 - 2.0, yf + 0.15, yf + 1.15, LZ - 0.4, LZ)]).common(inR).removeSplitter()
    lid_rear = fuse([box(X0, lid_x1 - 0.2, gy0 + 0.1, gy1 - 0.1, LZ, LZ + g.LID_EDGE),
                     box(X0, lid_x1 - 0.2, ly0 + 0.15, RY1 - W - 0.15, LZ, LZ + g.LID_T),
                     box(lx0 + 0.15, lx0 + 1.15, yc - 5.0, yc + 5.0, LZ - 0.4, LZ)]).common(inR).removeSplitter()

    # ---- cover over the pod: the bay cover carried on to the rail's rear face, a hood west of the pod for the lead's plug
    z_skirt = g.Z_PTOP + g.SKIRT_GAP
    ax1 = g.b0.x + g.SKIRT_A[1]
    cov = g.prism(g.region, z_skirt, g.Z_COVER).fuse(box(hx0, X1, Y1 - 1, RY1, g.DECK + 0.2, g.Z_COVER))
    void = fuse([g.prism(g.void, z_skirt - 1, g.Z_COVER_IN), box(hx0 + 1.6, X1 - 2.4, Y1 + 1.6, RY1 - 1.6, 0, g.Z_COVER_IN),
                 box(ax1, X1 - 2.4, Y1 - 3, RY1 - 1.6, 0, g.Z_COVER_IN)])
    cov = cov.cut(void).cut(g.prism(g.ring, z_skirt - 1, g.Z_WALL)).cut(box(X0 - 1, low_x0, Y1 - 1, RY1 + 1, 0, TOP + 0.2))
    cov = cov.cut(box(hx0 - 1, hx0 + 1.7, ly0, ly1, 0, TOP + 3.5))          # arch over the cell lane: the rear cell tips out under it
    for s in g.bay_screws:
        cov = cov.fuse(Part.makeCone(g.PILLAR_D0 / 2, g.PILLAR_D1 / 2, g.Z_COVER_IN - g.Z_PORT_TOP + 0.1, V(s.x, s.y, g.Z_PORT_TOP)))
    for s in g.bay_screws:
        cov = cov.cut(g.cyl(s, g.SCREW_D, g.Z_PORT_TOP - 1, g.Z_COVER + 1)).cut(g.cyl(s, g.HEAD_D, g.Z_COVER - g.HEAD_H, g.Z_COVER + 1))
    uw, uh, uo = g.USB_SHELL
    ux = g.b0.x + g.POD_USB_A
    cov = cov.cut(box(ux - uw / 2 - 0.3, ux + uw / 2 + 0.3, RY1 - 3, RY1 + 1, g.Z_PORT_TOP - 0.2, g.Z_PORT_TOP + uh + 0.4)).removeSplitter()

    # ---- reference solids: pod, power board, cells
    by = g.b0.y
    pod_rear = by + g.POD_T1
    mx = g.b0.x + g.POD_MOD_A
    pod = [box(g.b0.x - 15, g.b0.x + 15, by + 1.5, pod_rear, g.Z_PORT, g.Z_PORT_TOP), g.hdr,
           box(mx - 5.3, mx + 5.3, pod_rear - 0.3 - 15.6, pod_rear - 0.3, g.Z_PORT_TOP, g.Z_PORT_TOP + 2.05),
           box(ux - uw / 2, ux + uw / 2, pod_rear + uo - 9.8, pod_rear + uo, g.Z_PORT_TOP, g.Z_PORT_TOP + uh),
           box(ux - uw / 2, ux + uw / 2, pod_rear - 8.0, pod_rear - 0.5, g.Z_PORT - 1.6, g.Z_PORT),           # its through-hole tails
           box(g.b0.x - 11.7, g.b0.x - 5.3, by + 27.0, by + 39.0, g.Z_PORT_TOP, g.Z_PORT_TOP + 2.0)]
    zb = g.PB_Z + 1.6
    power = [g.prism(g.poly([Pb(u, v) for u, v in g.PB_OUT]), g.PB_Z, zb)]
    power += [box(bx0 + u0, bx0 + u1, by1 - v0, by1 - v1, zb, zb + h) for _, u0, u1, v0, v1, h in g.PB_TALL]
    power.append(box(bx0 + 22.75, bx0 + 34.25, by1, by1 - 4.9, zb, zb + 3.6))                                  # slide switch body (envelope)
    power.append(box(bx0 + g.SW_U - 3.0, bx0 + g.SW_U + 3.0, by1 + 4.3, by1, zb + 0.6, zb + 3.0))               # its actuator over its travel
    y_c = yf + SLOT + g.SPRING_COL
    cells = [Part.makeCylinder(g.AA_D / 2, g.AA_LMAX, V(xs, y_c + i * g.AA_LMAX, zc), V(0, 1, 0)) for i in range(3)]
    cells.append(Part.makeCylinder(g.AA_D / 2, g.AA_LMAX, V(lx0 + SLOT + g.DOME, yc, zc), V(1, 0, 0)))

    parts.update({"tray": body, "cover": cov, "lid-side": lid_side, "lid-rear": lid_rear})
    refs.update({"port": Part.makeCompound(pod), "power": Part.makeCompound(power), "cells": Part.makeCompound(cells)})
    fits.clear()
    fits.update({"fit-rail-front": body.common(box(px0 - 4.5, RX1 + 1, Y0 - 1, Y0 + 34, -1, 40)),
                 "fit-rail-rear": body.common(box(X0 - 1, X0 + 28, Y1 - 3, RY1 + 1, -1, 40)),
                 "fit-power": body.common(box(bx0 - 9, RX1 + 1, Y1 - 3, RY1 + 1, -1, 40)),
                 "fit-lid-side": lid_side.common(box(px0 - 4.5, RX1 + 1, Y0 - 1, Y0 + 34, -1, 40)),
                 "fit-lid-rear": lid_rear.common(box(X0 - 1, X0 + 28, Y1 - 3, RY1 + 1, -1, 40))})
    P, F = parts, refs
    pairs = [(a, P.get(a, F.get(a)), b, P.get(b, F.get(b))) for a, b in (
        ("tray", "power"), ("tray", "cells"), ("cover", "power"), ("cover", "cells"), ("cover", "lid-rear"), ("cover", "lid-side"),
        ("lid-side", "tray"), ("lid-rear", "tray"), ("lid-side", "cells"), ("lid-rear", "cells"), ("lid-side", "power"),
        ("lid-rear", "power"), ("port", "power"), ("port", "cells"), ("port", "lid-rear"), ("port", "lid-side"), ("power", "cells"))]
    col_min = 2 * g.SPRING_COL + 3 * (g.AA_LMAX - g.AA_LMIN)
    rep = [f"pod variant: module {RX1 - X0:.1f} x {RY1 - Y0:.1f} mm, rail top {TOP:.1f}, walls under the pod {g.DECK:.1f} "
           f"(pod underside {g.Z_PORT:.2f}, its tails to {g.Z_PORT - 1.6:.2f}); power board {g.PB_Z:.1f}-{zb:.1f}, can top {zb + 5.8:.1f}",
           f"column: springs {g.SPRING_COL:.2f} mm each with three {g.AA_LMAX} mm cells, {col_min / 2:.2f} mm each with three {g.AA_LMIN} mm cells "
           f"(5201: 10.5 mm free); rear wall {by1 - g.PB_OUT[2][1] - yr - BACK:.2f} mm from the power board",
           f"rear cell: spring {g.SPRING_ONE:.2f} to {g.SPRING_ONE + g.AA_LMAX - g.AA_LMIN:.2f} mm; its wall {notch_x - e:.2f} mm from the board's notch; "
           f"lane {ly0 - Y1:.2f} mm behind the tray; pack plug room {bx0 - 0.3 - (bx0 - 12.0):.1f} x {RY1 - W - ly1 + 0.1:.1f} mm",
           f"lids: side {lid_side.BoundBox.YLength:.1f} x {lid_side.BoundBox.XLength:.1f} mm, rear {lid_rear.BoundBox.XLength:.1f} x {lid_rear.BoundBox.YLength:.1f} mm, "
           f"{g.LID_T} mm, top {TOP - LZ - g.LID_T:.1f} mm under the rail top; cell top to lid {LZ - RF - g.AA_D:.1f} mm",
           f"cover: {cov.BoundBox.XLength:.1f} x {cov.BoundBox.YLength:.1f} mm, top {g.Z_COVER:.2f}; USB-C opening {uw + 0.6:.1f} x {uh + 0.6:.1f} mm, "
           f"switch slot {g.SW_SLOT[0]} x {g.SW_SLOT[1]} mm at z {zs:.1f}; pod overhangs its screws by {g.POD_T1 - 20.0:.1f} mm (no rear support)"]
    return pairs, rep
