# Rev 5 review findings

**Disposition (2026-09-14): all items folded into rev 6** of the spec, see §17
there. For A1 the chosen option was a dedicated logic boost (option 3 below), not
the LED-rail-fed LDO. Kept as the record of what was found and why.

**Rev 7 follow-up (2026-09-14):** what rev 6 left open is closed in the spec's §17.
B2 took the keyed downstream variant (10-pin header), B5 lays out the core for
both Raytac patterns, and C1 went to a large-plate service. A2's RC is τ ≥ 25 ms
after the TPS3840/AO3415A check. A6's switchover is 8 µs, so bulk only and no
blanking ISR. B3 was added to E9, the logic boost is the TPS61099DRV, and the P7
leaded candidate is the TPS25947. C4 is P12.

Review of [`../plans/keyboard.md`](../plans/keyboard.md) rev 5, 2026-09-14. Ordered
by what it costs if it reaches the fab. Each item names the section it touches and
what would close it. Items marked **damage** would destroy or degrade hardware;
**dead** would make a feature not work; **fab** is a manufacturing constraint;
**verify** is a datasheet or bench check the spec assumes but does not yet own.

## A. Fix before schematic capture

### A1. Cross-module UART logic levels are undefined (§4, §6) — dead, then damage

Every module's `VSYS` is unregulated, 1.85–3.3 V, and independent of the others.
The nRF52840 has `VIH = 0.7·VDD` and an absolute maximum of `VDD + 0.3 V` on any
pin. The link UARTs, the detect pull-ups and the wake break all cross between two
modules whose `VDD` can differ by up to 1.4 V:

- `left` on USB (`VDD` 3.3 V, `VIH` 2.31 V) with `right` on NiMH at 2.2 V: `right`'s
  TX high is ~2.2 V through 470 Ω into a 100 kΩ pull-down → **never detected, data
  never valid**. The same happens with fresh alkaline on one side and mid-discharge
  NiMH on the other. The split silently falls to BLE.
- The reverse: `right` at 3.3 V driving into `left` at 1.9 V puts 3.3 V on a pin
  whose abs-max is 2.2 V. Idle-high means it sits there continuously; the 940 Ω of
  series R limits the clamp current to ~1 mA, which is below damage but is a
  permanent abs-max violation and back-powers the lower module's `VSYS`.

Nothing in rev 5 addresses this, and §16 has no test with mismatched cell states.

**Options, in order of preference:**

1. **Regulate the logic rail.** The boost is already always on for the LED rail.
   Feed the logic LDO from the LED rail (VBUS on USB, boost on battery) instead of
   from VBUS alone, so `VSYS` is a fixed 3.3 V (or 3.0 V) always. Cost is the LDO's
   25 µA plus boost efficiency on ~mA of logic current, roughly 60 µA idle total,
   still years on 4000 mAh. It removes the VSYS TPS2116, and also closes A3, A4,
   B6 and the `VIO`-before-`VCC` ordering, since `VIO` is then derived from `VCC`.
   The 1.9 V hardware UVLO still works: it cuts the boost's input.
2. Keep unregulated `VSYS` and make the link level-tolerant: open-drain both ways
   with pull-ups on each side, plus a clamp-current budget. Ugly, and the detect
   logic must be redone.

Whichever is chosen, add a §16 test: link with `left` on USB and satellites on
cells at 2.0 V, and the reverse.

### A2. 14500 insertion reaches VBAT before the OVP FET opens (§4) — damage

The pack OVP is a supervisor that *detects* over-voltage and then turns the series
FET off. Its default state below threshold is "FET on". On insertion of a 14500
pair the sequence is:

1. Pack goes to 8.4 V instantly; the reverse-block FET conducts at once (body
   diode, then channel with gate at GND).
2. The TPS3840PL35's `VDD` rises through the 1 kΩ / 100 nF filter (τ = 100 µs),
   the supervisor completes its own start-up, its output is low (reset asserted)
   the whole time, which holds the OVP FET **on**.
3. Only after `VDD` crosses 3.7 V and the release delay `tD` elapses does the
   output go high and the FET turn off.

For that whole window, 8.4 V is on the PTC, the LM66200 (6.0 V abs-max), `VBAT`,
and via the LM66200 on `VSYS` and the MCU `VDD` (3.9 V abs-max). Hundreds of µs
to a millisecond of 8.4 V on the MCU is enough. The §16 test "insert two 14500s,
nothing is damaged" would fail on the first try and cost a core.

**Fix:** make the FET off by default and slow to turn on. Pull the OVP FET gate up
to its source (the pack side) with a resistor; let the supervisor pull it down
through a series R with an RC that takes ~10 ms to reach threshold; put a diode
from the supervisor output to the gate so turn-off is immediate. Then on a 14500
insertion the supervisor goes high within ~1 ms and the gate never falls. On AA
insertion the pack connects 10 ms late, which nobody notices. Check `tD` and the
supervisor start-up time in the TPS3840 datasheet and size the RC above their sum.

Also state on the schematic where the OVP supervisor senses: **after the
reverse-block FET**, so a reversed pack (−3 V) never reaches the supervisor's `VDD`
(abs-max −0.3 V). The 1 kΩ limits the current, but a reversed pack sitting on it
for minutes is not a spec'd condition.

### A3. Module ID pull-up from the battery-divider node breaks on USB (§2a) — dead

The ID is read as a ratio against the SAADC `VDD` channel, but the pull-up's top is
the *switched battery-divider node*, which is `VBAT`, not `VDD`. On battery they
are equal and the ratio works. On USB `VDD` is 3.3 V and `VBAT` is whatever the
cells are:

- No cells fitted, USB only: pull-up top is 0 V, ID reads ~0, which the spec
  defines as "short = fault" → **safe mode, keyboard dead on USB with no cells**.
- Flat NiMH on USB: `right` reads 0.32 × 1.9 / 3.3 ≈ 0.18; `numpad` on battery
  reads 0.69. Bands still separate, but not by design.

**Fix:** drive the pull-up from `VSYS` (through the same enable switch), or better,
from a GPIO set high only during the read, which is exactly ratiometric to `VDD`
and costs zero leakage. Goes away entirely under A1 option 1.

### A4. Enable pins must default to "on" in hardware (§4, §5) — dead

The pin budget lists "Boost EN, 3V3 LDO EN" as GPIOs. Two problems:

- **Which LDO?** The logic LDO must never be gated: on USB with no cells the MCU
  has no supply until it enables the LDO, which it cannot. The gated one must be
  the expansion LDO only. Say so explicitly in §4 and §5.
- **Boost EN on a GPIO with no pull-up** means the LED rail is 0 V from
  battery power-on until firmware sets the pin, while `VIO`, SDA and SCL are
  already at `VSYS`. That is the same `VCC + 0.3 V` violation §4 spends three
  paragraphs avoiding. Add a pull-up to `VSYS` on boost `EN` so it is on from the
  first microsecond, and use the GPIO only to disable. The series resistors on
  `VIO`/SDA/SCL from E11 also bound this case; note it in E11's scope.

### A5. USBLC6-2SC6 `VBUS` pin must sit on the protected side (§6) — damage

The USBLC6-2SC6 has a `VBUS` pin (pin 1) that references its clamps. Its abs-max is
5.5 V. On the USB port board the array sits at the connector; if pin 1 is wired to
connector VBUS it sees 20 V on a PD hot-plug and dies, taking D+/D− protection
with it. Wire pin 1 to the KTS1693's `OUT` (protected VBUS) or leave it NC per
ST's application note, and put that on the schematic sheet as a rule.

> Correction 2026-09-14: the `VBUS` pin is **pin 5**, not pin 1 (ST USBLC6-2 datasheet,
> Figure 1: 1/6 I/O1, 2 GND, 3/4 I/O2, 5 VBUS). The finding stands with that pin number.

### A6. LED-rail bulk capacitance is unsized and, as described, is enormous (§4, E4) — dead or fab

§4 says the TPS2116's ~1.3 ms switchover "is carried by the rail's bulk
capacitance" so the rail never drops below `VIO`. At 250 mA of lighting, dropping
from 4.3 V to 3.6 V:

| Allowed droop | Current | Time | Bulk needed |
| --- | --- | --- | --- |
| 0.7 V | 250 mA | 1.3 ms | ~460 µF |
| 0.7 V | 250 mA | 50 µs | ~18 µF |

460 µF on a rail that hangs off VBUS is outside the USB inrush allowance
(10 µF, or 50 µC with soft start) and adds ~2.5 mC through the KTS1693's soft
start. Two things to do:

1. **Verify the 1.3 ms figure.** TPS2116 has a controlled output slew at power-up;
   its break-before-make switchover between inputs is much shorter. Which number
   applies here decides whether this is a problem at all.
2. **Blank the LEDs on VBUS transitions in firmware.** The nRF `POWER`
   `USBDETECTED`/`USBREMOVED` events fire within microseconds; drive `SDB` low in
   the ISR, then size the bulk for that latency (tens of µF), and re-enable after
   the rail settles. Also blank on `VBUS_IN` loss when the link is the source.

Also size `VSYS` bulk for the same event: the MCU at ~10 mA must ride through the
VSYS mux's switchover without dropping below 1.7 V, or a USB unplug resets the
keyboard mid-typing.

## B. Fix before ordering

### B1. `left`'s pair-1 TX is always driven (§6) — leak, back-power

"`left`'s pair-1 TX is always driven" means that with `right` seam-joined but
switched off, `left` pushes idle-high through 470 Ω into `right`'s unpowered
MCU pin. The clamp conducts, ~5 mA flows into `right`'s `VSYS` net, and `left`'s
cells pay for it continuously. Hold pair-1 TX as an input (pull-up only) until RX
detect, exactly as pair 2 already does. It also removes the last case where a link
line has a driver before a handshake.

### B2. Downstream KTS1693 in reverse, sustained (§4) — verify

On `left`'s link port and `right`'s numpad port the KTS1693 conducts OUT → IN. The
spec accepts the ~3 ms body-diode start-up. Two longer cases are not covered:

- The far end is a short. The TPS22950L limits, `IN` sits near 0 V, `OUT` is at
  whatever the switch delivers; `OUT` > `IN` + 0.3 V for as long as the fault
  lasts (until the TPS22950L latches, which is quick, then indefinitely if the
  latch does not fully discharge `OUT`).
- The KTS1693 trips on a transient at the connector and turns off while the
  TPS22950L still feeds `OUT`. `OUT` = 5 V, `IN` = 0 V, forever.

Get Kinetic to confirm in writing that the OTG section permits sustained
`OUT` > `IN` with the switch off. If not, the downstream positions need a
different part, which breaks the single-link-board rule; the alternative is to
drop the KTS1693 on downstream ports (the TPS22950L already blocks reverse
current, and a 20 V source cannot appear on a port with no CC unless it is
non-compliant) and accept a link board population variant, with a footprint key
so it cannot be fitted upstream.

### B3. Local port `ISET` = 3.0 A exceeds the LM66200's 2.5 A abs-max (§4) — damage on a fault

A short behind the core's VBUS_IN OR passes up to 3.27 A through an LM66200
channel rated 2.5 A (4 A for 1 ms) before the KTS1693 latches. The whole keyboard
never needs more than ~1.6 A. Set `ISET` for ~2.0 A on local ports. E9 covers the
pack side of the same part; add this to it.

### B4. KTS1693 WLCSP escape routing sets the fab class for 7 boards (§12) — fab

A 4 × 5 array at 0.4 mm pitch has six inner balls that cannot escape on JLCPCB's
economy rules (0.127 mm trace/space, 0.2 mm via with 0.1 mm annular ring gives a
0.4 mm via land, which is the pitch). The USB port and link boards need 0.15 mm
vias, via-in-pad or both. Quote them as such now, and make the P7 second-source
survey include a QFN or DFN part with ≥20 V abs-max and an adjustable OV
threshold, so a swap does not re-spin the fab class. Candidates to screen: TI
TPS2660x eFuse family (adjustable OV, high abs-max, leaded), NXP NX20P3483
(WLCSP, same problem).

### B5. The MCU "second sources" are not drop-in (§3) — fab

Fanstel BT840 has a different pad layout from the MDBT50Q; it is not a footprint
second source. MDBT50Q-U1MV2 is the chip-antenna variant with a different antenna
keepout. Either lay out the core to accept both Raytac variants and check the
keepout for each, or record the MDBT50Q-1MV2 as single-source like the TPS61023.

### B6. Battery-referenced analogue inputs near a low `VDD` (§13) — verify

CC sense reads up to 2.04 V (3 A source). If a source is attached but VBUS is not
delivering (KTS1693 latched, or OVP tripped), the MCU runs from cells at down to
1.85 V, so `VDD` + 0.3 V = 2.15 V. 110 mV of margin. Add a 100 kΩ series resistor
on each CC line into the `AIN` pad. Under A1 option 1 this is moot.

### B7. UVLO hysteresis is smaller than the load-induced IR drop (§4) — chatter

TPS3840PH18 hysteresis is +100 mV; a 730 mA lighting load through a ~276 mΩ path
drops ~200 mV. With the supervisor sensing on the loaded net, the cut-off can
oscillate near 1.9–2.0 V. Firmware at 2.05 V (also loaded) is meant to fire
first, so specify that firmware measures `VBAT` under a known lighting state and
scales lighting off well above 2.05 V (the spec says "scales lighting with
VBAT" but gives no threshold). Put the cutoff and lighting thresholds in a table.

### B8. NFC pins as GPIO (§5)

`P0.09` and `P0.10` are in the LF-only budget. They are NFC antenna pins by
default; set `CONFIG_NFCT_PINS_AS_GPIOS=y` (writes `UICR.NFCPINS`) or they are
open-circuit as GPIO.

## C. Mechanical and sourcing

### C1. SLA build volume vs a 233 mm deep module (§11) — fab

Desktop SLA printers top out around 200–220 mm on the long axis (Form 4: 200 ×
125 mm; Saturn-class: ~220 × 125 mm). `left` and `right` at 233 mm deep and
~170–270 mm wide do not fit in one piece. Decide now whether the case is printed
in sections with joints designed in, or ordered from a service with a large
build plate. Section joints affect wall thickness, insert positions and the seam
budget (M1).

### C2. Reverse-mount LED position with a Kailh hotswap socket (§12, M3)

The MX "north" LED position (0, −5.08 mm) collides with the Kailh socket body and
its second pad at (2.54, −5.08). Every hotswap-plus-RGB board puts the LED
**south** (0, +5.08 mm) for this reason. Start the M3 test cell from the south
position, and check the chosen switches have a light-transmissive bottom housing
on that side.

### C3. JST GH mating cycles

JST rates GH at roughly 30 mating cycles. Fine for board replacement, not for a
connector that gets unplugged routinely. Note it in the build guide so nobody
"reseats" cables as a diagnostic step. Add the cycle rating to P9.

### C4. Keycaps: two 2.75U spacebars are the hard part (§3)

Standard sets include one 2.75U key (right shift) and no 2.75U spacebar. Two
blank or convex 2.75U keys come from ortho/ergo spacebar kits. The Phase 1 cap
count should pin a specific kit. Good news: 2U, 2.25U and 2.75U all use the same
23.8 mm stabiliser wire spacing, so one plate-mount stabiliser part covers all.

### C5. Antenna position vs the user's hand (§11, M6)

"`left`'s outer edge" includes the outer palm-rest corner, which is under the
user's left palm. A hand within a few cm of a 2.4 GHz antenna costs 10–20 dB.
Put the core at the **rear** outer corner, behind the key field, and make that
explicit in M6.

## D. Firmware items the spec assumes but does not list

### D1. "Nothing transmits" when both satellites are wired (§1)

A ZMK peripheral keeps advertising for its central whenever it has no BLE
connection, regardless of which split transport is active. To make the §1 radio
claim true, the module must stop the peripheral's advertising while the wired
transport is active and restart it on link loss. Add to the module contents in
§9 and to §16 (spectrum analyser or a phone's BLE scanner).

### D2. USB-C cable SBU wiring crosses (§6)

A compliant full-featured cable connects plug-1 `SBU1` (A8) to plug-2 `SBU2` (B8).
So with both plugs "unflipped", `left` A8 meets `right` B8. Orientation detection
handles it, but the §16 test "straight works, flipped is ambiguous" has its
labels the other way round for the seam-plus-cable case. Document it so the
tester does not chase a non-bug.

### D3. State the thresholds

The spec has firmware thresholds scattered as "~": system-off 2.05 V, lighting
scaling "with VBAT", flag timeouts, link-loss 300 ms, relink 2 s / 1 s. Collect
them in one table in §9 with the measurement conditions (loaded or not, which
divider) so 7a can be tested against numbers.

## E. Things I checked and found sound

For completeness, since they were the obvious suspects: the OR-does-not-share
correction; 5 V never on `VSYS`; the TPS2116 priority argument for the LED rail;
bidirectional pack TVS ahead of the reverse-block FET; PTC behind the OVP so 6 V
is enough; series R at MCU pins only; A6=B6/A7=B7 tie with mirrored key-board
routing; SBU cannot be tied; the all-or-nothing transport conclusion from
`central.c`; `BT_MAX_PAIRED` arithmetic; 1 CS + 3 SW common-anode giving 64;
`RSET` 42.2 kΩ at ~20 mA; the 45/47 pin count and the four `AINx` pads all being
available in the LF class; the WLCSP-only-on-small-boards rule.
