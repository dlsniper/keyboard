"""Hub tower model (spec §11, M11). This script owns the model; the .FCStd is a build output.

Run inside FreeCAD (GUI or FreeCADCmd), e.g. through the FreeCAD MCP's execute_python:
    exec(open('<repo>/mech/hub/build_hub.py').read())

Axes: X to the right as seen from the keyboard, Y towards the rear (front wall faces the
keyboard at -Y), Z up from the desk. Units mm. Every board is BOARD x BOARD, centred on Z.

Decided values (2026-09-29, spec §6/§11) are marked [spec]; values that are placeholders
until a part is chosen or a datasheet read are marked [approx].
"""
import os

import FreeCAD as App
import Part

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")) if "__file__" in globals() \
    else "/Users/florin/projects/personal/keyboard"
OUT_DIR = os.path.join(REPO, "build", "mech", "hub")
DOC_NAME = "hub"

# --- tower -------------------------------------------------------------------------------
OUTSIDE = 90.0          # [spec] footprint, outside
WALL = 2.0              # [spec] resin wall
BOARD = 84.0            # [spec] board outline
T_PCB = 1.6             # [spec] board thickness
GAP = 17.5              # [spec] ESQ joint gap: lower board top -> upper board bottom
PITCH = GAP + T_PCB     # 19.1 board to board
SPLIT = 9.5             # section boundary below each board's bottom face (>= tail length + margin)
LID_ROOF = 2.0

# --- Samtec ESQ -24 (F-226) ----------------------------------------------------------------
ESQ_A = 9.65            # [spec] tail length
ESQ_B = 13.59           # [spec] socket body height
ESQ_W = 4.95            # [spec] -D body depth
TAIL_BELOW = ESQ_A - T_PCB  # 8.05 below the board


def esq_len(n_per_row):
    return 2.54 * n_per_row + 0.51


# header centres on the board (x, y), long axis along X: proposal for review
CHAIN = dict(n=6, x=25.0, y=20.0)
SLOT = dict(n=16, x=-5.0, y=5.0)
EXP = dict(n=10, x=0.0, y=-20.0)

# --- battery module -------------------------------------------------------------------------
HOLDER = (58.0, 30.5, 15.0)   # [spec] MPD BC2AAPC rev P body
HOLDER_XY = (0.0, -22.0)

# --- wall-mounted boards ----------------------------------------------------------------------
USBC_BODY = (8.94, 7.35, 3.26)  # [approx] USB4085-class receptacle w x depth x h
USBC_CUT = (13.0, 7.0)          # [approx] wall opening for a plug overmold, w x h
SLOT_X = (-27.0, 0.0, 27.0)     # socket boards on the connector layer's front wall
SOCKET_BOARD = (20.0, 14.0)     # [approx] w x h
USB_PORT_X = 30.0               # host port board centre on the rear wall (right end)
SH_X = 8.0                      # expansion board centre on the rear wall
SH_BODY = (15.0, 2.9, 4.25)     # [approx] JST SM12B-SRSS-TB body w x depth x h
SH_CUT = (18.0, 7.0)            # [approx]
ANTENNA = (40.0, 10.0)          # [approx] flex antenna, <= ~40 mm long [spec], on the rear wall's left end
ANTENNA_X = -21.0
RPSMA_D = 6.5                   # [approx] 1/4"-36 bulkhead thread clearance
KNOCKOUT_SKIN = 0.6             # blanked: a thin skin stays until drilled out
FRONT_CONTROLS = [              # [approx] core front wall: (name, x, w, h)
    ("slide", -30.0, 7.0, 3.0),
    ("reset", 25.0, 3.5, 3.5),
    ("boot", 33.0, 3.5, 3.5),
]

COLORS = dict(board=(0.1, 0.45, 0.2), esq=(0.2, 0.2, 0.2), tail=(0.85, 0.7, 0.2), holder=(0.05, 0.05, 0.05),
              shell=(0.8, 0.8, 0.85), part=(0.6, 0.6, 0.65), antenna=(0.9, 0.5, 0.1))

INNER = OUTSIDE / 2 - WALL       # inner wall face, |x| or |y|


def box(sx, sy, sz, cx, cy, z0):
    """Box of size sx, sy, sz centred on (cx, cy), bottom at z0."""
    return Part.makeBox(sx, sy, sz, App.Vector(cx - sx / 2, cy - sy / 2, z0))


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


def header(m, g, prefix, spec, z_board):
    length = esq_len(spec["n"])
    m.add(g, f"{prefix}_socket", box(length, ESQ_W, ESQ_B, spec["x"], spec["y"], z_board + T_PCB), COLORS["esq"])
    m.add(g, f"{prefix}_tails", box(length - 0.8, ESQ_W - 1.6, TAIL_BELOW, spec["x"], spec["y"], z_board - TAIL_BELOW),
          COLORS["tail"])


def shell(z0, height, cuts=(), skins=()):
    outer = box(OUTSIDE, OUTSIDE, height, 0, 0, z0)
    inner = box(OUTSIDE - 2 * WALL, OUTSIDE - 2 * WALL, height + 2, 0, 0, z0 - 1)
    s = outer.cut(inner)
    for c in cuts:
        s = s.cut(c)
    for c in skins:
        s = s.cut(c)
    return s


def rear_cut(cx, w, zc, h):
    return box(w, WALL + 2, h, cx, INNER + WALL / 2, zc - h / 2)


def front_cut(cx, w, zc, h):
    return box(w, WALL + 2, h, cx, -INNER - WALL / 2, zc - h / 2)


def build():
    m = Model()
    layers = ["batt2", "batt1", "connector", "core"]
    zb = {name: SPLIT + k * PITCH for k, name in enumerate(layers)}

    for name in ("batt2", "batt1"):
        g = m.group(name)
        z = zb[name]
        m.add(g, f"{name}_board", box(BOARD, BOARD, T_PCB, 0, 0, z), COLORS["board"])
        m.add(g, f"{name}_holder", box(*HOLDER, *HOLDER_XY, z + T_PCB), COLORS["holder"])
        header(m, g, f"{name}_chain", CHAIN, z)
        m.add(g, f"{name}_shell", shell(z - SPLIT, PITCH), COLORS["shell"], 70)

    # connector layer: carrier + three socket boards on the front wall
    g = m.group("connector")
    z = zb["connector"]
    m.add(g, "connector_board", box(BOARD, BOARD, T_PCB, 0, 0, z), COLORS["board"])
    header(m, g, "connector_chain", CHAIN, z)
    header(m, g, "connector_slot", SLOT, z)
    cuts = []
    rc_z = z + T_PCB + 1.0 + SOCKET_BOARD[1] / 2  # receptacle centre height
    for i, x in enumerate(SLOT_X):
        yb = -INNER + USBC_BODY[1] - 1.0          # board face just behind the receptacle
        m.add(g, f"slot{i}_board", box(SOCKET_BOARD[0], T_PCB, SOCKET_BOARD[1], x, yb + T_PCB / 2, z + T_PCB + 1.0),
              COLORS["board"])
        m.add(g, f"slot{i}_usbc", box(USBC_BODY[0], USBC_BODY[1], USBC_BODY[2], x, yb - USBC_BODY[1] / 2,
                                      rc_z - USBC_BODY[2] / 2), COLORS["part"])
        cuts.append(front_cut(x, USBC_CUT[0], rc_z, USBC_CUT[1]))
    m.add(g, "connector_shell", shell(z - SPLIT, PITCH, cuts), COLORS["shell"], 70)

    # core layer: base board, host USB + SH + antenna on the rear, controls on the front
    g = m.group("core")
    z = zb["core"]
    m.add(g, "core_board", box(BOARD, BOARD, T_PCB, 0, 0, z), COLORS["board"])
    for prefix, spec in (("core_chain", CHAIN), ("core_slot", SLOT), ("core_exp", EXP)):
        header(m, g, prefix, spec, z)
    wall_z = z + T_PCB + 1.0 + SOCKET_BOARD[1] / 2
    yb = INNER - USBC_BODY[1] + 1.0
    m.add(g, "usb_port_board", box(SOCKET_BOARD[0], T_PCB, SOCKET_BOARD[1], USB_PORT_X, yb - T_PCB / 2, z + T_PCB + 1.0),
          COLORS["board"])
    m.add(g, "usb_port_usbc", box(USBC_BODY[0], USBC_BODY[1], USBC_BODY[2], USB_PORT_X, yb + USBC_BODY[1] / 2,
                                  wall_z - USBC_BODY[2] / 2), COLORS["part"])
    yb_sh = INNER - SH_BODY[1] - 0.5
    m.add(g, "expansion_board", box(SOCKET_BOARD[0], T_PCB, SOCKET_BOARD[1], SH_X, yb_sh - T_PCB / 2, z + T_PCB + 1.0),
          COLORS["board"])
    m.add(g, "expansion_sh", box(SH_BODY[0], SH_BODY[1], SH_BODY[2], SH_X, yb_sh + SH_BODY[1] / 2,
                                 wall_z - SH_BODY[2] / 2), COLORS["part"])
    ant_z = z + T_PCB + GAP / 2
    m.add(g, "antenna_flex", box(ANTENNA[0], 0.3, ANTENNA[1], ANTENNA_X, INNER - 0.15, ant_z - ANTENNA[1] / 2),
          COLORS["antenna"])
    cuts = [rear_cut(USB_PORT_X, USBC_CUT[0], wall_z, USBC_CUT[1]), rear_cut(SH_X, SH_CUT[0], wall_z, SH_CUT[1])]
    cuts += [front_cut(x, w, wall_z, h) for _, x, w, h in FRONT_CONTROLS]
    knock = Part.makeCylinder(RPSMA_D / 2, WALL - KNOCKOUT_SKIN, App.Vector(ANTENNA_X, OUTSIDE / 2, ant_z),
                              App.Vector(0, -1, 0))
    m.add(g, "core_shell", shell(z - SPLIT, PITCH, cuts, [knock]), COLORS["shell"], 70)

    # lid: from the core section's top to a roof clearing the core's socket bodies
    g = m.group("lid")
    z_lid0 = z - SPLIT + PITCH
    z_roof = z + T_PCB + GAP
    lid = shell(z_lid0, z_roof - z_lid0).fuse(box(OUTSIDE, OUTSIDE, LID_ROOF, 0, 0, z_roof))
    m.add(g, "lid_shell", lid, COLORS["shell"], 70)

    m.doc.recompute()
    os.makedirs(OUT_DIR, exist_ok=True)
    m.doc.saveAs(os.path.join(OUT_DIR, DOC_NAME + ".FCStd"))
    return dict(board_z=zb, top=z_roof + LID_ROOF, objects=len(m.doc.Objects))


_result_ = build()
