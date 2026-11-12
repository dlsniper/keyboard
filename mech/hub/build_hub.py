"""Hub tower model (spec §11, M11). This script owns the model; the .FCStd is a build output.

Run inside FreeCAD (GUI or FreeCADCmd), e.g. through the FreeCAD MCP's execute_python:
    p = '<repo>/mech/hub/build_hub.py'; g = {'__file__': p}; exec(open(p).read(), g)

Axes: X to the right as seen from the keyboard, Y towards the rear (front wall faces the
keyboard at -Y), Z up from the desk. Units mm. Every board is BOARD x BOARD, centred on Z.

Decided values (spec §3/§6/§11) are marked [spec]; values that are placeholders until a
part is chosen or a datasheet read are marked [approx].

v1 (2026-09-29): joints. Every section is an open ring of wall; the lower section of each
seam carries a lip (with an asymmetric key) that the upper section's wall sits over.
Magnetic seams (base, battery modules, lid) carry a flat magnet shelf on the left and
right walls on each side of the seam; the core <-> connector seam is screwed instead.
The case is FDM ASA (spec §3): threads are M2 heat-set inserts.
"""
import os

import FreeCAD as App
import Part

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")) if "__file__" in globals() \
    else "/Users/florin/projects/personal/keyboard"
OUT_DIR = os.path.join(REPO, "build", "mech", "hub")
DOC_NAME = "hub"

# --- tower -------------------------------------------------------------------------------
OUTSIDE = 100.0         # [spec] footprint, outside (2026-09-29, was 90)
WALL = 2.0              # [spec] ASA wall (FDM)
BOARD = 94.0            # [spec] board outline
T_PCB = 1.6             # [spec] board thickness
GAP = 17.5              # [spec] ESQ joint gap: lower board top -> upper board bottom
PITCH = GAP + T_PCB     # 19.1 board to board
SPLIT = 9.5             # ESQ seams: section boundary below the upper board's bottom face (>= tail length + margin)
POGO_SKIRT = 5.0        # [spec] pogo seams (battery chain): boundary 5 mm below the upper board (2026-09-29)
LID_ROOF = 2.0
INNER = OUTSIDE / 2 - WALL       # inner wall face, |x| or |y| = 48

# --- Samtec ESQ -24 (F-226) ----------------------------------------------------------------
ESQ_A = 9.65            # [spec] tail length
ESQ_B = 13.59           # [spec] socket body height
ESQ_W = 4.95            # [spec] -D body depth
TAIL_BELOW = ESQ_A - T_PCB  # 8.05 below the board


def esq_len(n_per_row):
    return 2.54 * n_per_row + 0.51


# header centres on the board (x, y), long axis along X: [spec] decided 2026-09-29 (v0 review)
CHAIN = dict(n=6, x=25.0, y=20.0)
SLOT = dict(n=16, x=-5.0, y=5.0)
EXP = dict(n=10, x=0.0, y=-20.0)

# --- battery chain on pogo pins (spec §4, 2026-09-29) -----------------------------------------
# riser on each battery board at the chain position, pins up; a cap board carries the pins to
# POGO_PADS, clear of the connector layer's through-hole ESQ chain socket at CHAIN (its tails
# would sit under the carrier where the pads go). Pads on every upper board's underside.
POGO_PADS = (25.0, 28.0)        # [approx] pin/pad field centre (2x6 on 2.54 mm)
# Mill-Max 827-22-012-10-004101 (decided 2026-09-30, spec §4): through-hole 2x6 strip on the cap
# board. Mill-Max drawing 827-22-0XX-10-004101 (inch values converted).
POGO_FREE = 9.957               # [spec] tip above the cap board, uncompressed (.392")
POGO_STROKE = 2.286             # [spec] full stroke (.090"); mid-stroke = working point
POGO_WORK = POGO_FREE - POGO_STROKE / 2   # 8.81 tip above the cap board at mid-stroke
POGO_BODY = (15.24, 5.08, 2.794)          # [spec] insulator, 2x6 (.600 x .200 x .110")
POGO_BARREL = (1.83, 1.5)                  # [spec] collar dia under the insulator; barrel dia above it
POGO_D = 1.067                  # [spec] plunger diameter (.042")
POGO_TAIL = (2.921, 0.635)      # [spec] tail length below the cap board's top, diameter
# Mill-Max 1578-0-57-15-00-00-03-0 target discs (decided 2026-09-30, spec §4): 12 under every upper board,
# reflowed on ENIG pads. Mill-Max PR663 rev D.
TARGET_D = 1.98                 # [spec] disc diameter (.078")
TARGET_H = 0.635                # [spec] style 0 height (.025")
# Samtec DW-06-17-T-D-254 riser (decided 2026-09-30, spec §4; print XW rev BD): two insulators, posts soldered
# through the battery board and the cap board.
RISER = (15.24, 5.08)           # [spec] insulator footprint, 2x6 on 2.54 mm
RISER_INS = 2.54                # [spec] each insulator's height
RISER_SPACE = 6.452             # [spec] board spacing 0.254" (bottom of the lower insulator to top of the upper)
RISER_TAIL = 2.794              # [spec] tail below the lower insulator (.110")
RISER_OAL = 12.192              # [spec] overall length, lead style -17 (.480")
CAP = (20.0, 16.0)              # [approx] cap board w x depth, spans CHAIN .. POGO_PADS

# --- battery module -------------------------------------------------------------------------
HOLDER = (61.3, 57.2, 15.5)   # [spec] MPD BC4AAPC rev F body (4xAA, decided 2026-09-30): 61.3 along the cells (x), 57.2 across, 15.5 tall
HOLDER_XY = (-5.0, -15.0)     # [spec] cells along x; clears the magnet shelves (|x| >= 37), the cap board (y >= 17.5), the bosses at (+-43.5, +-20)

# --- joints (spec §11) -----------------------------------------------------------------------
LIP_T = 1.2             # [approx] lip thickness (3 FDM lines)
LIP_H = 2.0             # [approx] lip height above the seam
LIP_CLR = 0.2           # [approx] lip to upper wall clearance
KEY_X = -15.0           # [approx] key on the front lip, off centre: no 90/180/270 deg fit
KEY_W = 5.0             # [approx]
KEY_D = 1.0             # [approx] key protrudes this far into the upper wall
KEY_CLR = 0.2           # [approx]

MAGNET = (20.0, 10.0, 2.0)      # [spec] the user's NdFeB blocks (length along the wall, depth, thickness)
POCKET_CLR = 0.3                # [spec] loose side-entry pocket, no glue
POCKET = (MAGNET[0] + 2 * POCKET_CLR, MAGNET[1] + 2 * POCKET_CLR, MAGNET[2] + 0.4)  # 20.6 x 10.6 x 2.4
SKIN = 0.6                      # [spec] skin between pocket and seam
SHELF_FLOOR = 0.6               # [approx] under/over the pocket, away from the seam
SHELF_T = SKIN + POCKET[2] + SHELF_FLOOR   # 3.6
SHELF_D = POCKET[1] + 0.4                  # 11.0 deep from the inner wall face
SHELF_L = POCKET[0] + 2 * 1.2              # 23.0 along the wall
SHELF_Y = 0.0                              # [spec] centred front to back on the left and right walls

M2_CLEAR = 2.4          # [approx] screw clearance through bosses
M2_BOARD_HOLE = 2.2     # [approx] board hole (plated or not: at capture)
INSERT_HOLE = (3.2, 5.0)  # [spec] Ruthex RX-M2x4: hole 3.2, insert 4.0 long (+1 mm for displaced plastic)
BOSS_D = 6.5            # [approx] boss diameter around an insert
BOARD_EDGE_TO_HOLE = 3.5
HOLE_X = BOARD / 2 - BOARD_EDGE_TO_HOLE          # 43.5
CORE_FRONT_Y = -30.0           # [spec] core board front edge (2026-10-01): pulled back behind the panel buttons, no notches (user)
JOINT_XY = [(sx * HOLE_X, y) for sx in (-1, 1) for y in (CORE_FRONT_Y + BOARD_EDGE_TO_HOLE, 26.0)]   # core <-> connector screws
MOUNT_XY = [(sx * HOLE_X, sy * 20.0) for sx in (-1, 1) for sy in (-1, 1)]  # other boards' own screws
MOUNT_BOSS_H = 6.0      # [approx] boss under a board, from its bottom face down (pogo seams: the whole skirt)

BASE_H = 6.0            # [approx] base: 2 mm floor + shelves, top at the lowest seam
BASE_FLOOR = 2.0
FOOT = (12.7 + 0.6, 1.0)  # [spec] 3M Bumpon SJ5012 (black, 12.7 x 3.5 mm +-0.5, 2026-10-01) in a 13.3 x 1.0 recess: ~2.5 mm proud
FOOT_H = 3.5            # [spec]

# --- wall-mounted boards: flat, receptacle at the edge (USB4085 is a horizontal top-mount part) --
USBC_BODY = (8.94, 7.26, 3.46)  # [spec] GCT USB4085 drawing: width, depth, height above the board
USBC_CUT = (8.94 + 0.5, 3.46 + 0.5)  # [approx] opening around the receptacle nose, flush with the outer face
STANDOFF = 1.0                  # [approx] flat board above the board it stands on (keeps >= 1.7 mm of wall over each opening)
SOCKET_BOARD = (18.0, 14.0)     # [approx] w x depth, hub-population comms board
SLOT_X = (-28.0, 0.0, 28.0)     # socket boards on the connector layer's front wall
USB_PORT_X = 35.0               # host port board centre on the rear wall (right end)
SH_X = 13.0                     # expansion board centre on the rear wall
SH_BODY = (14.0, 4.25, 2.9)     # [spec] JST SM12B-SRSS-TB side entry: B x depth x h (JST eSH catalogue p3)
SH_PLUG = (15.0, 2.8)           # [spec] SHR-12V-S-B housing with protrusions: B x thickness (eSH p2; 13.0 wide without)
SH_CUT = (SH_PLUG[0] + 0.6, SH_PLUG[1] + 0.6)   # [approx] 0.3 mm a side around the plug: 15.6 x 3.4
ANTENNA = (39.0, 10.0, 0.55)    # [spec] Yageo ANTX100P011B24003 PCB dipole, L x H x T (datasheet p3)
ANTENNA_TAPE = 0.15             # [approx] its HF-DS adhesive tape (thickness not in the datasheet)
ANTENNA_X = -26.5               # spans -46 .. -7: >= 10 mm to the expansion board (x 4) and its SH shell (datasheet p4)
LID_SEAM_UP = 5.0               # [spec] the core/lid seam sits this far over the core's 19.1 mm band, flat all round,
                                # so the 10 mm antenna fits under it (2026-10-01; replaced a 5 mm rear-wall tab)
WHIP_D = 9.35 + 0.25            # [spec] Yageo ANTX100ETHAB24553 whip base 9.35 +-0.1 (spec p12) + [approx] clearance
KNOCKOUT_SKIN = 0.6             # blanked: a thin skin stays until drilled out
# front controls (2026-10-01): NKK UB snap-in pushbuttons in the core section's front wall, wired to the core board
UB_CUT = 16.2                   # [spec] NKK UB square snap-in panel cut-out (nkk_ub_illum.pdf D80-D83)
UB_BEZEL = (17.8, 1.4)          # [spec] built-in bezel: square size, thickness in front of the panel
UB_CAP = (12.0, 2.5)            # [spec] cap: square size, proud of the bezel when out (1.0 when latched down)
UB_BODY = (15.8, 10.0, 5.0)     # [spec] body width, panel front face to body back, solder lugs beyond it
BUTTONS = [("power", -30.0), ("reset", 8.0), ("boot", 28.0)]   # [approx] x; UB16 latching / UB15 momentary, gold, solder lugs
UB_SEAM = 0.65                  # [spec] bezel top edge under the lid seam: buttons at the top of the core wall (2026-10-02),
                                # 7.6 mm above the slot USB-C receptacles (USB-C sets no overmold maximum)

COLORS = dict(board=(0.1, 0.45, 0.2), esq=(0.2, 0.2, 0.2), tail=(0.85, 0.7, 0.2), holder=(0.05, 0.05, 0.05),
              shell=(0.8, 0.8, 0.85), part=(0.6, 0.6, 0.65), antenna=(0.9, 0.5, 0.1), magnet=(0.7, 0.1, 0.1), green=(0.1, 0.55, 0.2))


def box(sx, sy, sz, cx, cy, z0):
    """Box of size sx, sy, sz centred on (cx, cy), bottom at z0."""
    return Part.makeBox(sx, sy, sz, App.Vector(cx - sx / 2, cy - sy / 2, z0))


def span(x0, x1, y0, y1, z0, z1):
    """Box from corner ranges (any order)."""
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, App.Vector(x0, y0, z0))


def cyl(d, h, x, y, z0):
    return Part.makeCylinder(d / 2, h, App.Vector(x, y, z0))


class Model:
    def __init__(self):
        if App.listDocuments().get(DOC_NAME):
            App.closeDocument(DOC_NAME)
        self.doc = App.newDocument(DOC_NAME)

    def add(self, group, name, shape, color, transparency=0):
        obj = self.doc.addObject("Part::Feature", name)
        obj.Shape = shape
        group.addObject(obj)
        if App.GuiUp:
            obj.ViewObject.ShapeColor = color
            obj.ViewObject.Transparency = transparency
        return obj

    def group(self, name):
        return self.doc.addObject("App::DocumentObjectGroup", name)


def header(m, g, prefix, spec, z_board, tails=TAIL_BELOW):
    """ESQ socket on the board's top, tails below (tails=0.5: cut flush after soldering)."""
    length = esq_len(spec["n"])
    m.add(g, f"{prefix}_socket", box(length, ESQ_W, ESQ_B, spec["x"], spec["y"], z_board + T_PCB), COLORS["esq"])
    m.add(g, f"{prefix}_tails", box(length - 0.8, ESQ_W - 1.6, tails, spec["x"], spec["y"], z_board - tails),
          COLORS["tail"])


def pogo_riser(m, g, prefix, z_board):
    """Riser on a battery board, pogo strip up, shown at mid-stroke against the pads of the board above."""
    z_top = z_board + T_PCB + GAP - TARGET_H      # target disc faces under the board above
    z_cap = z_top - POGO_WORK - T_PCB
    assert abs((z_cap - z_board - T_PCB) - RISER_SPACE) < 0.05, "riser spacing no longer matches the pogo stack"
    zb = z_board + T_PCB
    ins = box(RISER[0], RISER[1], RISER_INS, CHAIN["x"], CHAIN["y"], zb).fuse(
        box(RISER[0], RISER[1], RISER_INS, CHAIN["x"], CHAIN["y"], z_cap - RISER_INS))
    m.add(g, f"{prefix}_riser", ins, COLORS["esq"])
    posts = None
    for r in (-0.5, 0.5):
        for c in range(6):
            p = box(0.64, 0.64, RISER_OAL, CHAIN["x"] + (c - 2.5) * 2.54, CHAIN["y"] + r * 2.54, zb - RISER_TAIL)
            posts = p if posts is None else posts.fuse(p)
    m.add(g, f"{prefix}_riser_posts", posts, COLORS["tail"])
    y0 = CHAIN["y"] - RISER[1] / 2
    m.add(g, f"{prefix}_cap", span(CHAIN["x"] - CAP[0] / 2, CHAIN["x"] + CAP[0] / 2, y0, y0 + CAP[1], z_cap,
                                   z_cap + T_PCB), COLORS["board"])
    z_strip = z_cap + T_PCB
    m.add(g, f"{prefix}_strip", box(POGO_BODY[0], POGO_BODY[1], POGO_BODY[2], POGO_PADS[0], POGO_PADS[1], z_strip),
          COLORS["esq"])
    barrel_top = POGO_FREE - POGO_STROKE          # the plunger shows its stroke above the barrel when free
    metal = None
    for r in (-0.5, 0.5):
        for c in range(6):
            x, y = POGO_PADS[0] + (c - 2.5) * 2.54, POGO_PADS[1] + r * 2.54
            parts = [cyl(POGO_BARREL[1], barrel_top - POGO_BODY[2], x, y, z_strip + POGO_BODY[2]),
                     cyl(POGO_D, POGO_WORK - barrel_top, x, y, z_strip + barrel_top),
                     cyl(POGO_TAIL[1], POGO_TAIL[0], x, y, z_strip - POGO_TAIL[0])]
            for p in parts:
                metal = p if metal is None else metal.fuse(p)
    m.add(g, f"{prefix}_pins", metal, COLORS["tail"])


def pogo_pads(m, g, prefix, z_board):
    """12 target discs on the underside of a board, where the pogo strip below lands."""
    discs = None
    for r in (-0.5, 0.5):
        for c in range(6):
            d = cyl(TARGET_D, TARGET_H, POGO_PADS[0] + (c - 2.5) * 2.54, POGO_PADS[1] + r * 2.54, z_board - TARGET_H)
            discs = d if discs is None else discs.fuse(d)
    m.add(g, f"{prefix}_pads", discs, COLORS["tail"])


def board(z, holes):
    b = box(BOARD, BOARD, T_PCB, 0, 0, z)
    for x, y in holes:
        b = b.cut(cyl(M2_BOARD_HOLE, T_PCB + 2, x, y, z - 1))
    return b


# --- joint features ------------------------------------------------------------------------------

def ring(z0, h, outer, inner):
    return box(2 * outer, 2 * outer, h, 0, 0, z0).cut(box(2 * inner, 2 * inner, h + 2, 0, 0, z0 - 1))


def lip(z_seam, gaps):
    """Lip rising from the lower section's top, inside the upper wall; key on the front."""
    out = INNER - LIP_CLR
    s = ring(z_seam, LIP_H, out, out - LIP_T)
    s = s.fuse(span(KEY_X - KEY_W / 2, KEY_X + KEY_W / 2, -out, -(out + KEY_D), z_seam, z_seam + LIP_H))
    for g in gaps:
        s = s.cut(g)
    return s


def key_notch(z_seam):
    """Notch in the upper section's wall that takes the key."""
    out = INNER - LIP_CLR
    return span(KEY_X - KEY_W / 2 - KEY_CLR, KEY_X + KEY_W / 2 + KEY_CLR, -INNER + 0.1, -(out + KEY_D + KEY_CLR),
                z_seam - 1, z_seam + LIP_H + KEY_CLR)


def shelf_gaps():
    """Cut-outs in a lip where the magnet shelves of the section above come down to the seam."""
    return [span(sx * (INNER + 1), sx * (INNER - LIP_T - LIP_CLR - 1), SHELF_Y - SHELF_L / 2 - 0.3,
                 SHELF_Y + SHELF_L / 2 + 0.3, -1000, 1000) for sx in (-1, 1)]


def boss_gaps():
    """Cut-outs in a lip where the section above brings its wall bosses down to the seam."""
    return [span(x - (BOSS_D / 2 + 0.3) * (1 if x > 0 else -1), (1 if x > 0 else -1) * (INNER + 1),
                 y - BOSS_D / 2 - 0.3, y + BOSS_D / 2 + 0.3, -1000, 1000) for x, y in JOINT_XY]


def mount_gaps():
    """Cut-outs in a lip where the section above brings its board-mount bosses down to the seam."""
    return [span(x - (BOSS_D / 2 + 0.3) * (1 if x > 0 else -1), (1 if x > 0 else -1) * (INNER + 1),
                 y - BOSS_D / 2 - 0.3, y + BOSS_D / 2 + 0.3, -1000, 1000) for x, y in MOUNT_XY]


def magnet_shelves(z_seam, below):
    """Two shelves with loose side-entry pockets. below=True: in the lower section, under the seam."""
    shelves, pockets, magnets = [], [], []
    for sx in (-1, 1):
        if below:
            z0 = z_seam - SHELF_T
            zp = z_seam - SKIN - POCKET[2]
        else:
            z0 = z_seam
            zp = z_seam + SKIN
        shelves.append(span(sx * INNER, sx * (INNER - SHELF_D), SHELF_Y - SHELF_L / 2, SHELF_Y + SHELF_L / 2,
                            z0, z0 + SHELF_T))
        # mouth open towards the section's centre, 0.4 mm back wall towards the outer wall
        pockets.append(span(sx * (INNER - 0.4), sx * (INNER - SHELF_D - 1), SHELF_Y - POCKET[0] / 2,
                            SHELF_Y + POCKET[0] / 2, zp, zp + POCKET[2]))
        mz = zp + (POCKET[2] - MAGNET[2] if below else 0)   # pulled against the seam-side skin by its partner
        magnets.append(span(sx * (INNER - 0.4 - POCKET_CLR), sx * (INNER - 0.4 - POCKET_CLR - MAGNET[1]),
                            SHELF_Y - MAGNET[0] / 2, SHELF_Y + MAGNET[0] / 2, mz, mz + MAGNET[2]))
    return shelves, pockets, magnets


def wall_boss(x, y, z0, z1):
    """Round boss fused to the nearest side wall."""
    sx = 1 if x > 0 else -1
    return cyl(BOSS_D, z1 - z0, x, y, z0).fuse(span(x, sx * (INNER + 0.5), y - BOSS_D / 2, y + BOSS_D / 2, z0, z1))


def insert_boss(x, y, z_top, h):
    """Boss hanging from the wall, top at z_top, heat-set insert hole from the top."""
    b = wall_boss(x, y, z_top - h, z_top)
    return b.cut(cyl(INSERT_HOLE[0], INSERT_HOLE[1] + 0.01, x, y, z_top - INSERT_HOLE[1]))


class Section:
    """One enclosure section: wall ring z0..z1 plus joint features."""

    def __init__(self, name, z0, z1):
        self.name, self.z0, self.z1 = name, z0, z1
        self.solid = ring(z0, z1 - z0, OUTSIDE / 2, INNER)
        self.cuts = []
        self.magnets = []

    def add(self, s):
        self.solid = self.solid.fuse(s)

    def top(self, kind, pogo=False):
        """kind 'mag' or 'screw': the lower side of the seam at z1.
        pogo: a pogo seam, the section above brings its board-mount bosses down to the seam."""
        gaps = shelf_gaps() if kind == "mag" else boss_gaps()
        if pogo:
            gaps += mount_gaps()
        self.add(lip(self.z1, gaps))
        if kind == "mag":
            shelves, pockets, mags = magnet_shelves(self.z1, below=True)
            for s in shelves:
                self.add(s)
            self.cuts += pockets
            self.magnets += mags
        else:
            for x, y in JOINT_XY:
                self.add(insert_boss(x, y, self.z1, 6.0))

    def bottom(self, kind, z_board=None):
        """kind 'mag' or 'screw': the upper side of the seam at z0."""
        self.cuts.append(key_notch(self.z0))
        if kind == "mag":
            shelves, pockets, mags = magnet_shelves(self.z0, below=False)
            for s in shelves:
                self.add(s)
            self.cuts += pockets
            self.magnets += mags
        else:
            for x, y in JOINT_XY:   # bosses from the seam up to the board; the screw passes through
                self.add(wall_boss(x, y, self.z0, z_board))
                self.cuts.append(cyl(M2_CLEAR, z_board - self.z0 + 2, x, y, self.z0 - 1))

    def board_mounts(self, z_board, h=MOUNT_BOSS_H):
        for x, y in MOUNT_XY:
            self.add(insert_boss(x, y, z_board, h))

    def finish(self):
        s = self.solid
        for c in self.cuts:
            s = s.cut(c)
        return s.removeSplitter()


def rear_cut(cx, w, zc, h):
    return box(w, WALL + 2, h, cx, INNER + WALL / 2, zc - h / 2)


def front_cut(cx, w, zc, h):
    return box(w, WALL + 2, h, cx, -INNER - WALL / 2, zc - h / 2)


def flat_board_with_usbc(m, g, name, x, z_under, front):
    """Flat board on standoffs, USB4085 at the wall edge, nose flush with the outer wall face.
    front=True: front wall (-Y). Returns the receptacle centre height."""
    sy = -1 if front else 1
    zb = z_under + STANDOFF
    edge = sy * (INNER - 0.3)
    m.add(g, f"{name}_board", span(x - SOCKET_BOARD[0] / 2, x + SOCKET_BOARD[0] / 2, edge, edge - sy * SOCKET_BOARD[1],
                                   zb, zb + T_PCB), COLORS["board"])
    nose = sy * OUTSIDE / 2
    m.add(g, f"{name}_usbc", span(x - USBC_BODY[0] / 2, x + USBC_BODY[0] / 2, nose, nose - sy * USBC_BODY[1],
                                  zb + T_PCB, zb + T_PCB + USBC_BODY[2]), COLORS["part"])
    return zb + T_PCB + USBC_BODY[2] / 2


def build():
    m = Model()
    layers = ["batt2", "batt1", "connector", "core"]
    zb = {name: POGO_SKIRT + k * PITCH for k, name in enumerate(layers)}   # the lowest seam is z = 0
    sec = {}

    # base: floor + shelves under the lowest seam (z = 0)
    g = m.group("base")
    base = Section("base", -BASE_H, 0.0)
    base.add(box(OUTSIDE, OUTSIDE, BASE_FLOOR, 0, 0, -BASE_H))
    base.top("mag", pogo=True)
    for sx in (-1, 1):
        for sy in (-1, 1):
            base.cuts.append(cyl(FOOT[0], FOOT[1] + 0.01, sx * 40.0, sy * 40.0, -BASE_H - 0.01))
            m.add(g, f"foot_{'rl'[sx > 0]}{'fb'[sy > 0]}", cyl(FOOT[0] - 0.6, FOOT_H, sx * 40.0, sy * 40.0,
                                                             -BASE_H + FOOT[1] - FOOT_H), COLORS["holder"])
    for sx in (-1, 1):   # shelves stand on the floor: fill the space under them
        base.add(span(sx * INNER, sx * (INNER - SHELF_D), SHELF_Y - SHELF_L / 2, SHELF_Y + SHELF_L / 2,
                      -BASE_H + BASE_FLOOR, -SHELF_T))
    sec["base"] = (g, base)

    for name in ("batt2", "batt1"):
        g = m.group(name)
        z = zb[name]
        m.add(g, f"{name}_board", board(z, MOUNT_XY), COLORS["board"])
        m.add(g, f"{name}_holder", box(*HOLDER, *HOLDER_XY, z + T_PCB), COLORS["holder"])
        pogo_riser(m, g, name, z)
        pogo_pads(m, g, name, z)
        s = Section(name, z - POGO_SKIRT, z - POGO_SKIRT + PITCH)
        s.bottom("mag")
        s.top("mag", pogo=True)
        s.board_mounts(z, POGO_SKIRT)
        sec[name] = (g, s)

    # connector layer: carrier + three flat socket boards at the front wall
    g = m.group("connector")
    z = zb["connector"]
    m.add(g, "connector_board", board(z, MOUNT_XY), COLORS["board"])
    header(m, g, "connector_chain", CHAIN, z, tails=0.5)
    header(m, g, "connector_slot", SLOT, z, tails=0.5)
    pogo_pads(m, g, "connector", z)
    s = Section("connector", z - POGO_SKIRT, zb["core"] - SPLIT)
    s.bottom("mag")
    s.top("screw")
    s.board_mounts(z, POGO_SKIRT)
    for i, x in enumerate(SLOT_X):
        zc = flat_board_with_usbc(m, g, f"slot{i}", x, z + T_PCB, front=True)
        s.cuts.append(front_cut(x, USBC_CUT[0], zc, USBC_CUT[1]))
    sec["connector"] = (g, s)

    # core layer: base board, host USB + SH + antenna on the rear, controls on the front
    g = m.group("core")
    z = zb["core"]
    core_b = board(z, JOINT_XY).cut(span(-BOARD, BOARD, -BOARD, CORE_FRONT_Y, z - 1, z + T_PCB + 1))
    m.add(g, "core_board", core_b, COLORS["board"])
    for prefix, spec in (("core_chain", CHAIN), ("core_slot", SLOT), ("core_exp", EXP)):
        header(m, g, prefix, spec, z)
    s = Section("core", z - SPLIT, z - SPLIT + PITCH + LID_SEAM_UP)
    s.bottom("screw", z_board=z)
    s.top("mag")
    zc = flat_board_with_usbc(m, g, "usb_port", USB_PORT_X, z + T_PCB, front=False)
    s.cuts.append(rear_cut(USB_PORT_X, USBC_CUT[0], zc, USBC_CUT[1]))
    zb_sh = z + T_PCB + STANDOFF
    edge = INNER - 0.3
    m.add(g, "expansion_board", span(SH_X - SOCKET_BOARD[0] / 2, SH_X + SOCKET_BOARD[0] / 2, edge,
                                     edge - SOCKET_BOARD[1], zb_sh, zb_sh + T_PCB), COLORS["board"])
    m.add(g, "expansion_sh", span(SH_X - SH_BODY[0] / 2, SH_X + SH_BODY[0] / 2, edge, edge - SH_BODY[1],
                                  zb_sh + T_PCB, zb_sh + T_PCB + SH_BODY[2]), COLORS["part"])
    s.cuts.append(rear_cut(SH_X, SH_CUT[0], zb_sh + T_PCB + SH_BODY[2] / 2, SH_CUT[1]))
    ant_z = z + T_PCB + (s.z1 - z - T_PCB) / 2   # centred between the core board's top and the lid seam
    ant_t = ANTENNA[2] + ANTENNA_TAPE
    m.add(g, "antenna_pcb", box(ANTENNA[0], ant_t, ANTENNA[1], ANTENNA_X, INNER - ant_t / 2, ant_z - ANTENNA[1] / 2),
          COLORS["antenna"])
    btn_z = s.z1 - UB_SEAM - UB_BEZEL[0] / 2
    for name, x in BUTTONS:
        yo = -OUTSIDE / 2
        m.add(g, f"btn_{name}_bezel", span(x - UB_BEZEL[0] / 2, x + UB_BEZEL[0] / 2, yo, yo - UB_BEZEL[1],
                                           btn_z - UB_BEZEL[0] / 2, btn_z + UB_BEZEL[0] / 2), COLORS["holder"])
        m.add(g, f"btn_{name}_cap", span(x - UB_CAP[0] / 2, x + UB_CAP[0] / 2, yo - UB_BEZEL[1], yo - UB_BEZEL[1] - UB_CAP[1],
                                         btn_z - UB_CAP[0] / 2, btn_z + UB_CAP[0] / 2), {"power": COLORS["green"], "reset": COLORS["magnet"]}.get(name, COLORS["holder"]))
        m.add(g, f"btn_{name}_body", span(x - UB_BODY[0] / 2, x + UB_BODY[0] / 2, yo, yo + UB_BODY[1],
                                          btn_z - UB_BODY[0] / 2, btn_z + UB_BODY[0] / 2), COLORS["holder"])
        m.add(g, f"btn_{name}_lugs", span(x - 4.0, x + 4.0, yo + UB_BODY[1], yo + UB_BODY[1] + UB_BODY[2],
                                          btn_z - 4.0, btn_z + 4.0), COLORS["tail"])
        s.cuts.append(front_cut(x, UB_CUT, btn_z, UB_CUT))
    s.cuts.append(Part.makeCylinder(WHIP_D / 2, WALL - KNOCKOUT_SKIN, App.Vector(ANTENNA_X, OUTSIDE / 2, ant_z),
                                    App.Vector(0, -1, 0)))
    sec["core"] = (g, s)

    # lid: from the core section's top to a roof clearing the core's socket bodies
    g = m.group("lid")
    z_roof = z + T_PCB + GAP
    lid = Section("lid", sec["core"][1].z1, z_roof)
    lid.add(box(OUTSIDE, OUTSIDE, LID_ROOF, 0, 0, z_roof))
    lid.bottom("mag")
    sec["lid"] = (g, lid)

    for name, (g, s) in sec.items():
        m.add(g, f"{name}_shell", s.finish(), COLORS["shell"], 60)
        for i, mg in enumerate(s.magnets):
            m.add(g, f"{name}_magnet{i}", mg, COLORS["magnet"])

    m.doc.recompute()
    os.makedirs(OUT_DIR, exist_ok=True)
    m.doc.saveAs(os.path.join(OUT_DIR, DOC_NAME + ".FCStd"))
    return dict(board_z=zb, bottom=-BASE_H, feet_bottom=-BASE_H - (FOOT_H - FOOT[1]), top=z_roof + LID_ROOF, objects=len(m.doc.Objects))


_result_ = build()
