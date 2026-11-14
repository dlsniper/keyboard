"""Hub tower geometry, rev 9: the one source for the FreeCAD section (mech/hub/build_hub.py) and the board
placement (tools/pcb_hub.py). Plain data, no FreeCAD or KiCad imports.

Axes as rev 8: X to the right seen from the keyboard, Y towards the rear (front wall at -Y faces the keyboard),
Z up. Origin: on the axis of the 94 mm boards (hub-core, battery), which is where rev 8's 100 mm tower had its
axis. Since M2 session 7 the tower is 114 mm square and has grown to the rear and the sides only (the front wall and
the three module ports stay put), so the tower's own axis is at y = AXIS_Y. Units mm. [rev8] = carried over from archive/rev8/mech/hub/build_hub.py (decided
there), [user] = decided 2026-11-13 at M2 session 4, [check] = to confirm on a drawing or a real part.
"""
# --- tower ---------------------------------------------------------------------------------------------------------
OUTSIDE = 114.0             # [user 2026-11-14] outside footprint, square (was 100: no free rear wall for the host port)
WALL = 2.0                  # [rev8]
FRONT_Y = -50.0             # outer face of the front wall: where rev 8 had it
AXIS_Y = FRONT_Y + OUTSIDE / 2      # 7.0: the tower's axis; x is centred
REAR_Y = FRONT_Y + OUTSIDE          # 64.0: outer face of the rear wall
BOARD = 94.0                # [rev8] hub-core and battery board outline, square, centred on the origin
# connector layer board: fills the tower (1 mm to the walls at the sides and the rear, 3 mm at the front as before)
CONN_X = OUTSIDE / 2 - WALL - 1.0   # 54.0: half width
CONN_FRONT = -BOARD / 2             # -47.0: unchanged, the module-port receptacles sit on this edge
CONN_REAR = REAR_Y - WALL - 1.0     # 61.0
T_PCB = 1.6
GAP = 17.5                  # [user] board to board everywhere: ESQ stack (core/connector) and battery seams
PITCH = GAP + T_PCB         # 19.1
HOLE_X = 43.5               # [rev8] M2 holes 3.5 mm from the side edges
MOUNT_XY = [(sx * HOLE_X, sy * 20.0) for sx in (-1, 1) for sy in (-1, 1)]      # [rev8] connector layer, battery
CORE_FRONT_Y = -30.0        # [rev8][user] core board front edge: room for the NKK UB bodies (board 94 x 77)
CORE_XY = MOUNT_XY          # [user 2026-11-14] core screws above the screws of the boards below (were at y -26.5 / 26)

# --- stack connector, core <-> connector layer (frozen 2x25) ---------------------------------------------------------
# [user] Samtec ESQ-125 stack-through as rev 8: the same part on both boards, body on the TOP side, the core's tails
# pass down through the core into the connector layer's socket. Same footprint, same place, same turn on both boards.
STACK_XY = (6.0, 41.0)      # centre, long axis along X (rear edge; clear of the holder below and the Pico above)
ESQ_BODY_H = 13.59          # [rev8] socket body height
ESQ_TAIL = 9.65             # [rev8] tail length (8.05 below the board)
ESQ_W = 4.95

# --- battery chain seam (2x8) ----------------------------------------------------------------------------------------
# [rev8] parts, in 2x8: Samtec DW-08-17-T-D-254 riser on the battery board (pins up), a small cap board on it that
# carries a Mill-Max 827-22-016-10-004101 spring-pin strip; Mill-Max 1578-0-57-15-00-00-03-0 target discs under the
# board above. [check] the 827 2x8 strip and its drawing (the lookup did not find the -004101 drawing again).
CHAIN_RISER_XY = (22.0, 20.0)   # riser on the battery board, long axis along X (behind the holder)
CHAIN_PADS_XY = (22.0, 29.0)    # spring pins on the cap board = target pads under the board above
CAP_BOARD = (26.0, 18.0)        # cap board, spans riser and pin strip; centre between the two
POGO_FREE = 9.957               # [rev8] tip above the cap board, free
POGO_STROKE = 2.286             # [rev8]
RISER_SPACE = 6.452             # [rev8] battery board top to cap board bottom
TARGET_H = 0.635                # [rev8]
TARGET_D = 1.98

# --- battery module --------------------------------------------------------------------------------------------------
HOLDER = (61.3, 57.2, 15.5)     # [rev8] MPD BC4AAPC body: along the cells (X), across, height
HOLDER_XY = (-5.0, -15.0)       # [rev8]

# --- connector layer -------------------------------------------------------------------------------------------------
PORT_X = (-28.0, 0.0, 28.0)     # [rev8] module ports A, B, C on the front wall
USBC = (8.94, 7.3, 3.2)         # receptacle shell w x depth x height [check] JAE DX07S024WJ1R350 drawing (403 so far)
USBC_NOSE = 1.0                 # shell front beyond the board edge [check]
CAN = (8.3, 10.2)               # 220 uF can: diameter, height (8 x 10 case)
JUSB_XY = (-39.0, 31.0)         # host port cable header (JST GH 11), turned 90 deg, rear left

# --- host port board (hardware/usb-port), M2 session 7 [user 2026-11-14] ---------------------------------------------
# In the rear strip of the connector layer, behind the stack connector: lies flat on two M2 x 3 mm threaded standoffs
# that stand on hub-conn, receptacle (GCT USB4085, horizontal, through-hole) through the rear wall, its 11-pin cable
# header at the front edge facing forward. The cable goes to hub-conn's header at JUSB_XY; both plugs are in the open.
UP_X = (-47.0, -9.0)            # board outline, x (38 mm)
UP_Y = (46.49, 61.49)           # board outline, y (15 mm); rear edge 2.51 mm inside the wall face, 0.51 mm from the wall
UP_STANDOFF = 3.0               # hub-conn top to the port board's underside (the receptacle's pin ends are below)
UP_REC_X = -20.0                # receptacle centre line
UP_MOUNT_XY = [(UP_REC_X - 8.0, 57.5), (UP_REC_X + 8.0, 57.5)]     # standoffs left and right of the receptacle
UP_GH_XY = (-37.5, 49.6)        # cable header (JST GH 11) origin, mating face to the front
USB4085 = (8.94, 9.17, 3.46)    # shell width, depth, height; pin A1 is 8.61 mm behind the mouth (KiCad footprint) [check] GCT drawing
USB4085_OVER = 2.51             # shell beyond the board edge: the mouth is flush with the wall's outer face

# --- core layer ------------------------------------------------------------------------------------------------------
PICO_XY = (-10.0, 6.0)          # Pico 2 W centre, long axis along X, USB end towards +X (antenna end towards -X wall)
PICO = (51.0, 21.0, 1.0)
PICO_UNDER = 11.04              # Pico underside above the core board: 8.5 mm socket + 2.54 mm header spacer [check] on the real parts
# [user] long discrete spring pins, Pico on standard sockets: Mill-Max 0929-7-15-20-75-14-11-0 (catalogue p. 25,
# build/ds/pogo/): 12.19 mm free above the board, stroke 1.40, hole 0.74 min, tail 0.64, body 1.83 dia.
SPRING_FREE = 12.19
SPRING_STROKE = 1.40
EXP_XY = (-36.0, 41.0)          # 2x5 expansion header, long axis along X, rear left
BUTTONS = (("power", -30.0), ("reset", 8.0), ("boot", 28.0))    # [rev8] NKK UB16 (latching) / UB15, x on the front wall
BUTTON_PLUG_Y = -25.5           # their JST XH plugs on the core board, behind each button
UB_CUT = 16.2                   # [rev8] panel cut-out
UB_BODY = (15.8, 10.0, 15.8)    # [rev8] width, depth behind the panel face, height

# --- section heights (board top faces), from the base up ---------------------------------------------------------------
BASE_H = 6.0                    # [rev8]


def levels(n_batt=1):
    """Z of each board's bottom face: battery modules (lowest first), connector layer, core."""
    z = BASE_H + 5.0            # [rev8] pogo skirt: a module's board sits 5 mm above its seam
    out = {}
    for i in range(n_batt, 0, -1):          # module n is the lowest
        out[f"battery{i}"] = z
        z += PITCH
    out["conn"] = z
    out["core"] = z + PITCH
    return out
