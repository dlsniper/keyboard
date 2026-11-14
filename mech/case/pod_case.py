"""Wireless variant of a key-module shell (M3b step 3, spec 2b "Shell"); loaded by build_case.py when CASE_VARIANT=pod.

  CASE_VARIANT=pod CASE_MODULE=numpad|left|right /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd mech/case/build_case.py
  output: build/case/<name>-pod/ (GUI document "case_<name>_pod")

User decisions 2026-11-14 (options UI, shown in FreeCAD): tray and battery rail are ONE print; two sliding cell lids
with a snap ridge; a Keystone 5201 spring at both ends of a three-cell column; a single rear cell on 5223 (button) and
5201 with the power board notched for the spring's wall; service port stays on the pod's rear edge; `left` has 4 cells
(3 side + 1 rear, as the numpad), `right` 6 (3 side + 3 rear).

Two frames, so that a turned rear strip (left, right) needs nothing special:
  rear frame (a, t): the bay frame of build_case.py (a along the rear edge, t rearwards from the F-row cap line);
  side frame (o, s): o outwards from the tray's outer face on the side that carries the side leg, s from the tray's
  front corner towards the rear.
Three layouts:
  numpad  side leg on the bay's side; power board in the corner under the pod; one rear cell west of it.
  left    side leg at the far (outer, west) end; power board against the split-side wall under the pod; one rear cell
          west of it (spring wall in the board's west notch), the rest of the lane is a wire bay.
  right   side leg at the far (outer, east) end; power board at the split-side wall with 12 mm in front of its pack
          plug; three rear cells east of it.
On left and right the corner belongs to the rear lid (it slides out over the side leg's rear end, the side lid ends
in front of it); on the numpad the corner belongs to the side lid.

Rail: side leg 19 mm (pocket 15 mm, three cells end to end like a torch), rear leg 27 mm (cell lane in front, wires
behind it, the power board on two bosses with inserts and five posts). Contact plates drop from above into slots; a
rib with a window for the spring holds each plate. Wires (not modelled): tabs up and bent over; column wires in the
pocket's bottom corner beside the cells, then along the rear wire strip (numpad: the strip in front of the power
board); a wire to the pack plug may pass under the board (4 mm, PB_POSTS keep its path free).
Under the pod the rail walls end at DECK; the cover over the pod closes that part. Lids slide in grooves of the rail
walls; a ridge under the lid's outer end drops behind the lowered end wall.
"""
import Part
import FreeCAD as App

V = App.Vector
FAR = 400.0


def fuse(shapes):
    s = shapes[0]
    for o in shapes[1:]:
        s = s.fuse(o)
    return s


def build(c, parts, refs, fits):
    g = type("G", (), c)
    ua, ut, b0, Tq, Rq, R = g.ua, g.ut, g.b0, g.Tq, g.Rq, g.R
    near = g.side == 2                                        # numpad
    W, RF, TOP = g.RAIL_WALL, g.RAIL_FLOOR, g.RAIL_H
    SLOT, RIB, BACK, AA = g.SLOT, g.RIB, g.BACK, g.AA_LMAX
    G, LZ = g.GROOVE, g.LID_Z
    zc = RF + g.AA_D / 2
    cross = lambda u, w: u.x * w.y - u.y * w.x

    # ---- frames
    Rf = lambda a, t: b0 + ua * a + ut * t
    A = lambda p: (p - b0).dot(ua)
    T = lambda p: (p - b0).dot(ut)

    def rbox(a0, a1, t0, t1, z0, z1):
        a0, a1 = min(a0, a1), max(a0, a1); t0, t1 = min(t0, t1), max(t0, t1)
        return g.prism(g.poly([Rf(a0, t0), Rf(a1, t0), Rf(a1, t1), Rf(a0, t1)]), z0, z1)
    if g.side == 0:
        O, far_s = Tq[0], Tq[1]
    else:
        O, far_s = Tq[3], Tq[2]
    us = far_s - O; us.normalize()
    no = V(us.y, -us.x, 0)
    if no.dot(O - (Tq[0] + Tq[1] + Tq[2] + Tq[3]) * 0.25) < 0:
        no = no * -1
    S = lambda o, s: O + no * o + us * s

    def sbox(o0, o1, s0, s1, z0, z1):
        o0, o1 = min(o0, o1), max(o0, o1); s0, s1 = min(s0, s1), max(s0, s1)
        return g.prism(g.poly([S(o0, s0), S(o1, s0), S(o1, s1), S(o0, s1)]), z0, z1)
    s_on = lambda o, p, u: cross(p - O - no * o, u) / cross(us, u)        # s where the side frame's line o meets the line (p, u)
    a_on = lambda t, p, u: cross(p - b0 - ut * t, u) / cross(ua, u)       # a where the rear frame's line t meets the line (p, u)
    rb_ = lambda u0, u1, v0, v1, z0, z1: rbox(u0, u1, v0, v1, z0, z1)     # holders: u along the cells, v across
    sb_ = lambda u0, u1, v0, v1, z0, z1: sbox(v0, v1, u0, u1, z0, z1)

    # ---- the rear leg's end walls (outer faces) as lines; which end the bay is at
    lo_l, hi_l = (Rq[1], Rq[0] - Rq[1]), (Rq[2], ut)         # (the bay-side end is square to the rear edge on every module)
    if A(Rq[1]) > A(Rq[2]):
        lo_l, hi_l = hi_l, lo_l
    bay_hi = A(Rq[1]) + A(Rq[2]) < 0                          # the bay (a = 0) lies nearer the +a end: numpad, left
    weff = lambda l: W / abs(cross(l[1], ua) / l[1].Length)   # wall thickness measured along a
    a_lo = lambda t: a_on(t, *lo_l) + weff(lo_l)              # inside faces
    a_hi = lambda t: a_on(t, *hi_l) - weff(hi_l)
    T_TR, T_R = T(Tq[1]), T(Rq[1])                            # tray's rear face, rail's rear face
    ly0 = T_TR + 1.49; ly1 = ly0 + g.POCKET_W; yc = (ly0 + ly1) / 2       # rear cell lane
    by1 = T_R - W - 0.5                                       # power board: rear edge
    bay_t0 = T_TR if near else ly0                            # its bay starts at the tray's wall (numpad: wire strip in front of the board)
    if bay_hi:
        bx0 = min(a_hi(by1), a_hi(by1 - g.PB[1])) - 0.3 - g.PB[0]
    else:
        bx0 = max(a_lo(by1), a_lo(by1 - g.PB[1])) + 0.3 + 12.0            # 12 mm in front of the pack plug's mouth
    Pb = lambda u, v: Rf(bx0 + u, by1 - v)
    notch_a, notch_t = bx0 + g.PB_OUT[5][0], by1 - g.PB_OUT[6][1]         # the board's west notch: east edge, rear edge
    L1 = SLOT + g.DOME + AA + g.SPRING_ONE + SLOT + 1.1       # one rear cell: back of the button's plate to the east face of the spring's wall
    L3 = 2 * SLOT + 2 * g.SPRING_COL + 3 * AA                 # three cells, a spring at each end: between the plates' back faces
    hx = g.HOOD_X0 if bay_hi else -g.SKIRT_A[0]               # the cover's end over the rail (its wall is 1.6 mm, inside of this)

    # ---- side column (all layouts)
    o0, o1 = g.RAIL_SIDE - W - g.POCKET_W, g.RAIL_SIDE - W    # pocket, outwards from the tray's outer face
    oc = (o0 + o1) / 2
    front = (Rq[0], Rq[3] - Rq[0])
    yf = max(s_on(o0 - G, *front), s_on(o1 + G, *front)) + W  # column: front plate's back face (s)
    yr = yf + L3                                              # rear plate's back face
    cells = [Part.makeCylinder(g.AA_D / 2, AA, S(oc, yf + SLOT + g.SPRING_COL + i * AA) + V(0, 0, zc), us) for i in range(3)]

    def holder(bx, s, pf, lo, hi, cc, back, notch=True):
        """Plate holder: plate front face at pf along the cells, cell on side s; lo..hi across, plate centred on cc."""
        p0, p1 = pf - s * (SLOT + back), pf + s * RIB
        h = bx(p0, p1, lo, hi, RF - 0.1, zc + 6.5)
        h = h.cut(bx(pf - s * SLOT, pf, cc - g.PLATE[0] / 2 - 0.2, cc + g.PLATE[0] / 2 + 0.2, zc - g.PLATE[1] / 2 - 0.2, 99))
        h = h.cut(bx(pf - s * 0.01, pf + s * (RIB + 0.01), cc - g.WINDOW / 2, cc + g.WINDOW / 2, zc - 3.5, 99))
        if notch:                                             # wire through the bottom corner
            h = h.cut(bx(p0 - 0.01, p1 + 0.01, lo - 0.01, lo + 1.9, RF, RF + 3.0))
        return h
    hold = [holder(sb_, 1, yf + SLOT, o0, o1, oc, 0.0), holder(sb_, -1, yr - SLOT, o0, o1, oc, BACK)]

    # ---- rear leg per layout: cavities, holders, cells, lid range, lowered zone
    if bay_hi:                                                # one rear cell west of the board
        lx0 = a_lo(yc) if near else notch_a - 0.6 - L1        # back face of the button's plate
        e = lx0 + L1
        assert e < notch_a - 0.3 and yc + g.PLATE[0] / 2 + 0.2 < notch_t - 0.3, "rear spring wall does not fit the board's west notch"
        lid_a = (-FAR, hx + 1.8)                              # rear lid: from the far end to just inside the hood
        low = (max(e + 0.6, lid_a[1]), A(Tq[2]) if near else FAR)         # from here the rail walls end at DECK
        cav = [sbox(o0, o1, yf, yr + BACK if near else FAR, RF, 99),
               rbox(bx0 - 0.3, FAR, bay_t0, T_R - W, RF, 99),                             # power board bay
               rbox(lx0 if near else -FAR, e, ly0, ly1, RF, 99),                          # rear cell (left: and a wire bay west of it)
               rbox(lx0 if near else -FAR, bx0 - 0.3, ly1 + 1.2, T_R - W, RF, 99),        # wires, pack plug
               rbox(bx0 - 12.0, bx0 - 0.3, ly1 - 0.1, ly1 + 1.3, RF, 99)]                 # the pack plug's body
        if near:
            cav.append(rbox(lx0, lx0 + 4.0, ly1 - 0.1, ly1 + 1.3, RF, 99))                # round the divider's west end
        hold += [holder(rb_, 1, lx0 + SLOT, ly0, ly1, yc, 0.0 if near else BACK, False),
                 holder(rb_, -1, e - 1.1 - SLOT, T_TR, notch_t - 0.3, yc, 1.1)]
        cells.append(Part.makeCylinder(g.AA_D / 2, AA, Rf(lx0 + SLOT + g.DOME, yc) + V(0, 0, zc), ua))
        tops = (lx0 if near else -FAR, low[0])                # divider and holder tops under the rear lid
        end_cut = rbox(-FAR, lx0 if near else max(a_lo(ly0 - G), a_lo(T_R)), ly0 - G, T_R - W + G, LZ, 99)
        ridge_a = (lx0 if near else max(a_lo(yc - 5.0), a_lo(yc + 5.0))) + 0.15
        n_rear = 1
    else:                                                     # right: three rear cells east of the board
        bx1 = bx0 + g.PB[0] + 0.3
        r0 = bx1 + BACK; r1 = r0 + L3
        assert r1 + BACK < A(Tq[1]) - 0.5, "the rear cells reach the side leg"
        lid_a = (hx - 1.8, FAR)
        low = (-FAR, lid_a[0])
        e = r0
        cav = [sbox(o0, o1, yf, FAR, RF, 99),
               rbox(-FAR, bx1, bay_t0, T_R - W, RF, 99),                                  # power board bay with the room in front of the pack plug
               rbox(bx1, FAR, ly0, ly1, RF, 99),                                          # rear cells
               rbox(bx1, FAR, ly1 + 1.2, T_R - W, RF, 99)]                                # wires
        hold += [holder(rb_, 1, r0 + SLOT, ly0, ly1, yc, BACK, False), holder(rb_, -1, r1 - SLOT, ly0, ly1, yc, BACK, False)]
        cells += [Part.makeCylinder(g.AA_D / 2, AA, Rf(r0 + SLOT + g.SPRING_COL + i * AA, yc) + V(0, 0, zc), ua) for i in range(3)]
        tops = (low[1], FAR)
        end_cut = rbox(min(a_hi(ly0 - G), a_hi(T_R)), FAR, ly0 - G, T_R - W + G, LZ, 99)
        ridge_a = min(a_hi(yc - 5.0), a_hi(yc + 5.0)) - 1.15
        n_rear = 3
    gy0, gy1 = ly0 - G, T_R - W + G
    sharp = g.poly(g.Rpts)                                        # cavities keep square corners (the board and the lids are square there)
    inside = g.prism(sharp.makeOffset2D(-W, join=2), 0, 99).cut(g.prism(g.outer_f, -1, 100))
    body = g.tray0.fuse(g.prism(R.cut(g.outer_f), 0, TOP))
    body = body.cut(fuse(cav).common(inside)).fuse(fuse(hold))
    bosses = [Pb(*h) for h in g.PB_HOLES]
    posts = [Pb(*p) for p in g.PB_POSTS]
    body = body.fuse(fuse([g.cyl(p, g.BOSS_D, RF - 0.1, g.PB_Z) for p in bosses] + [g.cyl(p, 3.0, RF - 0.1, g.PB_Z) for p in posts]))
    for p in bosses:
        body = body.cut(g.cyl(p, g.INSERT_D, g.PB_Z - g.INSERT_DEPTH, g.PB_Z + 1))

    # ---- lowered walls under the pod, switch slot, lid grooves and entries
    # side lid: on the numpad to the rear wall; elsewhere it ends where the rear lid's strip begins
    s_end = (Rf(0, gy1) - O).dot(us) if near else min(s_on(o0 - G, Rf(0, gy0), ua), s_on(o1 + G, Rf(0, gy0), ua))
    zs = g.PB_Z + 1.6 + 0.4
    sw = bx0 + g.SW_U
    cuts = [rbox(low[0], low[1], T_TR - 6, T_R + 1, g.DECK, 99),         # (and the filled corner beside the tray's rounded one)
            rbox(sw - g.SW_SLOT[0] / 2, sw + g.SW_SLOT[0] / 2, T_R - W - 1, T_R + 1, zs, zs + g.SW_SLOT[1]),
            sbox(o0 - G, o1 + G, -9, s_end, LZ, LZ + g.LID_EDGE + 0.1),                  # side lid: grooves
            sbox(o0 - G, o1 + G, -9, yf, LZ, 99),                                        # its entry at the front
            rbox(lid_a[0], lid_a[1], gy0, gy1, LZ, LZ + g.LID_EDGE + 0.1),               # rear lid: grooves
            end_cut,                                                                     # its entry: the end wall lowered
            rbox(tops[0], tops[1], ly0, T_R - W, LZ, 99)]                                # divider and holder tops under the lid
    body = body.cut(fuse(cuts))
    # ---- tooth under the pod's rear edge (M3 session 5; the pod overhangs its screws by 32 mm): on the rear wall's inner
    # face, 45 degrees underneath, standing free inside the cover above DECK. Along a: as near the service port as the
    # port's through-hole tails, the pack plug and the lead connector on the power board allow.
    tw, td = g.POD_TOOTH
    taken = [(g.POD_USB_A - 5.0, g.POD_USB_A + 5.0), (bx0 - 0.5, bx0 + 12.1), (bx0 + 35.8, bx0 + 47.8)]
    free = [k / 2 for k in range(-24, 25) if all(k / 2 + tw / 2 + 0.5 <= lo or k / 2 - tw / 2 - 0.5 >= hi for lo, hi in taken)]
    ta = min(free, key=lambda a: abs(a - g.POD_USB_A))
    zt, tf = g.Z_PORT - 0.1, T_R - W
    pr = [(tf, zt), (tf - td, zt), (tf - td, zt - 2.9), (tf, zt - 2.9 - td)]
    pts = [Rf(ta - tw / 2, t) + V(0, 0, z) for t, z in pr]
    tooth = Part.Face(Part.makePolygon(pts + pts[:1])).extrude(ua * tw).fuse(rbox(ta - tw / 2, ta + tw / 2, tf - 0.01, tf + 0.3, zt - 2.9 - td, g.DECK))
    body = body.fuse(tooth)
    for q in g.feet:
        body = body.cut(g.cyl(q, g.FOOT_D, -1, g.FOOT_DEPTH))
    body = body.removeSplitter()
    inR = g.prism(R, 0, 99)
    s_lid = s_end - 0.2
    lid_side = fuse([sbox(o0 - G + 0.1, o1 + G - 0.1, -9, s_lid, LZ, LZ + g.LID_EDGE),
                     sbox(o0 + 0.15, o1 - 0.15, -9, s_lid - (G + 0.15 if near else 0), LZ, LZ + g.LID_T),
                     sbox(o0 + 2.0, o1 - 2.0, yf + 0.15, yf + 1.15, LZ - 0.4, LZ)]).common(inR).removeSplitter()
    la0, la1 = (lid_a[0], lid_a[1] - 0.2) if bay_hi else (lid_a[0] + 0.2, lid_a[1])
    lid_rear = fuse([rbox(la0, la1, gy0 + 0.1, gy1 - 0.1, LZ, LZ + g.LID_EDGE),
                     rbox(la0, la1, ly0 + 0.15, T_R - W - 0.15, LZ, LZ + g.LID_T),
                     rbox(ridge_a, ridge_a + 1.0, yc - 5.0, yc + 5.0, LZ - 0.4, LZ)]).common(inR).removeSplitter()

    # ---- cover over the pod: the bay cover carried on to the rail's rear face; on numpad / left a hood beside the pod for the lead's plug
    z_skirt = g.Z_PTOP + g.SKIRT_GAP
    sk = g.SKIRT_A[1]
    if bay_hi:
        c1 = A(Tq[2]) if near else FAR
        hoodf = rbox(hx, c1, T_TR - 1, T_R, g.DECK + 0.2, g.Z_COVER)
        void = [rbox(hx + 1.6, c1 - 2.4, T_TR + 1.6, T_R - 1.6, 0, g.Z_COVER_IN), rbox(sk, c1 - 2.4, T_TR - 3, T_R - 1.6, 0, g.Z_COVER_IN)]
        over = rbox(-FAR, low[0], T_TR - 1, T_R + 1, 0, TOP + 0.2)
    else:
        hoodf = rbox(-FAR, hx, T_TR - 1, T_R, g.DECK + 0.2, g.Z_COVER)
        void = [rbox(-FAR, hx - 1.6, T_TR + 1.6, T_R - 1.6, 0, g.Z_COVER_IN), rbox(-FAR, -sk, T_TR - 3, T_R - 1.6, 0, g.Z_COVER_IN)]
        over = rbox(low[1], FAR, T_TR - 1, T_R + 1, 0, TOP + 0.2)
    void = fuse(void)
    if not near:                                              # keep the cover inside the outline, 1.6 mm wall
        hoodf = hoodf.common(inR)
        void = void.common(g.prism(sharp.makeOffset2D(-1.6, join=2), -1, 100)).common(g.prism(R.makeOffset2D(-1.4), -1, 100))   # 1.4 mm at the rounded corner
    cov = g.prism(g.region, z_skirt, g.Z_COVER).fuse(hoodf)
    cov = cov.cut(fuse([g.prism(g.void, z_skirt - 1, g.Z_COVER_IN), void])).cut(g.prism(g.ring, z_skirt - 1, g.Z_WALL)).cut(over)
    if bay_hi and e > hx:                                     # arch over the cell lane: the rear cell tips out under the hood
        cov = cov.cut(rbox(hx - 1, hx + 1.7, ly0, ly1, 0, TOP + 3.5))
    for s in g.bay_screws:
        cov = cov.fuse(Part.makeCone(g.PILLAR_D0 / 2, g.PILLAR_D1 / 2, g.Z_COVER_IN - g.Z_PORT_TOP + 0.1, V(s.x, s.y, g.Z_PORT_TOP)))
    for s in g.bay_screws:
        cov = cov.cut(g.cyl(s, g.SCREW_D, g.Z_PORT_TOP - 1, g.Z_COVER + 1)).cut(g.cyl(s, g.HEAD_D, g.Z_COVER - g.HEAD_H, g.Z_COVER + 1))
    uw, uh, uo = g.USB_SHELL
    ux = g.POD_USB_A
    cov = cov.cut(rbox(ux - uw / 2 - 0.3, ux + uw / 2 + 0.3, T_R - 3, T_R + 1, g.Z_PORT_TOP - 0.2, g.Z_PORT_TOP + uh + 0.4)).removeSplitter()

    # ---- reference solids: pod, power board, cells
    pt = g.POD_T1
    mx = g.POD_MOD_A
    pod = [rbox(-15, 15, 1.5, pt, g.Z_PORT, g.Z_PORT_TOP), g.hdr,
           rbox(mx - 5.3, mx + 5.3, pt - 0.3 - 15.6, pt - 0.3, g.Z_PORT_TOP, g.Z_PORT_TOP + 2.05),
           rbox(ux - uw / 2, ux + uw / 2, pt + uo - 9.8, pt + uo, g.Z_PORT_TOP, g.Z_PORT_TOP + uh),
           rbox(ux - uw / 2, ux + uw / 2, pt - 8.0, pt - 0.5, g.Z_PORT - 1.6, g.Z_PORT),                    # its through-hole tails
           rbox(-11.7, -5.3, 27.0, 39.0, g.Z_PORT_TOP, g.Z_PORT_TOP + 2.0)]                                 # the lead's connector, mouth to -a
    zb = g.PB_Z + 1.6
    power = [g.prism(g.poly([Pb(u, v) for u, v in g.PB_OUT]), g.PB_Z, zb)]
    power += [rbox(bx0 + u0, bx0 + u1, by1 - v0, by1 - v1, zb, zb + h) for _, u0, u1, v0, v1, h in g.PB_TALL]
    power.append(rbox(bx0 + 22.75, bx0 + 34.25, by1 - 4.9, by1, zb, zb + 3.6))                              # slide switch body (envelope)
    power.append(rbox(sw - 3.0, sw + 3.0, by1, by1 + 4.3, zb + 0.6, zb + 3.0))                              # its actuator over its travel

    parts.update({"tray": body, "cover": cov, "lid-side": lid_side, "lid-rear": lid_rear})
    refs.update({"port": Part.makeCompound(pod), "power": Part.makeCompound(power), "cells": Part.makeCompound(cells)})
    fits.clear()
    if near:                                                  # fit pieces are cut from the numpad only (same features on left and right)
        X0, Y0, Y1, RX1, RY1 = Tq[0].x, Tq[0].y, Tq[1].y, Rq[2].x, Rq[1].y
        px0, bxa = RX1 - W - g.POCKET_W, b0.x + bx0
        box = lambda x0, x1, y0, y1, z0, z1: Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))
        fits.update({"fit-rail-front": body.common(box(px0 - 4.5, RX1 + 1, Y0 - 1, Y0 + 34, -1, 40)),
                     "fit-rail-rear": body.common(box(X0 - 1, X0 + 28, Y1 - 3, RY1 + 1, -1, 40)),
                     "fit-power": body.common(box(bxa - 9, RX1 + 1, Y1 - 3, RY1 + 1, -1, 40)),
                     "fit-lid-side": lid_side.common(box(px0 - 4.5, RX1 + 1, Y0 - 1, Y0 + 34, -1, 40)),
                     "fit-lid-rear": lid_rear.common(box(X0 - 1, X0 + 28, Y1 - 3, RY1 + 1, -1, 40))})
    P, F = parts, refs
    names = [("tray", "power"), ("tray", "cells"), ("cover", "power"), ("cover", "cells"), ("cover", "lid-rear"), ("cover", "lid-side"),
             ("lid-side", "tray"), ("lid-rear", "tray"), ("lid-side", "cells"), ("lid-rear", "cells"), ("lid-side", "power"),
             ("lid-rear", "power"), ("port", "power"), ("port", "cells"), ("port", "lid-rear"), ("port", "lid-side"), ("power", "cells"),
             ("lid-side", "lid-rear"), ("tray", "port"), ("cover", "tray")]
    if "dial-hood" in P:
        names += [("dial-hood", "lid-rear"), ("dial-hood", "cells"), ("dial-hood", "tray")]
    pairs = [(a, P.get(a, F.get(a)), b, P.get(b, F.get(b))) for a, b in names]
    col_min = 2 * g.SPRING_COL + 3 * (AA - g.AA_LMIN)
    bb = g.prism(R, 0, 1).BoundBox
    plug = (-11.7 - (a_on(33.0, *lo_l) + 1.6)) if not bay_hi else (-11.7 - (hx + 1.6))
    rep = [f"pod variant: module {bb.XLength:.1f} x {bb.YLength:.1f} mm, rail top {TOP:.1f}, walls under the pod {g.DECK:.1f} "
           f"(pod underside {g.Z_PORT:.2f}, its tails to {g.Z_PORT - 1.6:.2f}); power board {g.PB_Z:.1f}-{zb:.1f}, can top {zb + 5.8:.1f}; "
           f"{3 + n_rear} cells (3 side + {n_rear} rear)",
           f"column: springs {g.SPRING_COL:.2f} mm each with three {AA} mm cells, {col_min / 2:.2f} mm each with three {g.AA_LMIN} mm cells "
           f"(5201: 10.5 mm free); front wall at s = {yf - W:.2f}",
           (f"rear cell: spring {g.SPRING_ONE:.2f} to {g.SPRING_ONE + AA - g.AA_LMIN:.2f} mm; its wall {notch_a - e:.2f} mm from the board's notch; "
            f"lane {ly0 - T_TR:.2f} mm behind the tray") if bay_hi else
           (f"rear cells: three in a row east of the board, springs as the column; {A(Tq[1]) - (r1 + BACK):.1f} mm to the side leg; "
            f"room in front of the pack plug 12.0 mm"),
           f"power board: a = {bx0:.2f} .. {bx0 + g.PB[0]:.2f} from the bay's centre line, switch at a = {sw:.1f}; "
           f"lead plug on the pod: {plug:.1f} mm from the connector's mouth to the cover's inside",
           f"lids: side {max(lid_side.BoundBox.XLength, lid_side.BoundBox.YLength):.1f} x {min(lid_side.BoundBox.XLength, lid_side.BoundBox.YLength):.1f} mm, "
           f"rear {max(lid_rear.BoundBox.XLength, lid_rear.BoundBox.YLength):.1f} x {min(lid_rear.BoundBox.XLength, lid_rear.BoundBox.YLength):.1f} mm "
           f"(bounding boxes), {g.LID_T} mm, top {TOP - LZ - g.LID_T:.1f} mm under the rail top; cell top to lid {LZ - RF - g.AA_D:.1f} mm",
           f"cover: {cov.BoundBox.XLength:.1f} x {cov.BoundBox.YLength:.1f} mm (bounding box), top {g.Z_COVER:.2f}; USB-C opening {uw + 0.6:.1f} x {uh + 0.6:.1f} mm, "
           f"switch slot {g.SW_SLOT[0]} x {g.SW_SLOT[1]} mm at z {zs:.1f}; pod overhangs its screws by {g.POD_T1 - 20.0:.1f} mm",
           f"pod rear support: tooth on the rear wall at a = {ta - tw / 2:.1f} .. {ta + tw / 2:.1f}, {g.POD_T1 - (tf - td):.2f} mm under the pod's rear edge, "
           f"top {zt:.2f} (pod underside {g.Z_PORT:.2f}); {abs(ta - g.POD_USB_A):.1f} mm from the service port's centre line"]
    return pairs, rep
