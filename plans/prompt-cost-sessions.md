# Prompts: cost-review rework sessions

Saved 2026-11-15 at the end of the cost review session (spec section 3c holds the decisions). Four independent clean
sessions, any order; A is the largest. The fit-print session (`plans/prompt-m3-session-7.md`) is independent too.

## A. hub-conn: Schottky pack inputs, basic values
```
Keyboard project, rev 9.1, branch rev9-go. Read next.md ("Cost review session" block), plans/keyboard.md section 3c
and the power-path part of 3a, nothing else to start.
Cost session A, hub-conn. I decided: plain Schottky diodes in place of the five LM74610-Q1 + SQ4184EY stages, and odd
resistor values / small parts moved to JLC basic parts where behaviour allows.
First design and show me, before any board change: the diode (current, forward voltage and heat at 2.5 A and 4.5 A,
reverse leakage hot against the 22 k empty-slot bleeders, package and copper for the heat), what happens to the
lowest-first priority and its 0.7 V body-diode handicap, the battery life and one-pack power lost, whether O12 goes
away; run tools/sim_priority.py and tools/sim_switchover.py with the new parts. List every value you want to move to
a basic part with the check that allows it. Critique honestly, then ask me through the options UI.
On a yes: tools/sch_hub.py, hub-conn placed and routed again (tools/pcb_hub.py, route_hub.py), ERC / DRC / parity 0,
tools/esd_stub.py, fab outputs, shell checked if the outline, holes or connectors move.
Budget: tokens are tight. PCB work stays with you; delegate only lookups. No leftover background processes.
End by updating next.md and the spec, committing, and giving me the prompt for the next session.
```

## B. Hub mechanics: chain seam and buttons
```
Keyboard project, rev 9.1, branch rev9-go. Read next.md ("Cost review session" block), plans/keyboard.md section 3c
and the chain-seam and button parts of 3a, nothing else to start.
Cost session B. I decided: a generic 2x8 spring-pin strip in place of the Mill-Max 827 (doubled further only if the
pin rating needs it: 1.25 A per pin today), bare ENIG pads in place of the Mill-Max 1578 target discs on hub-conn
and battery, and generic buttons (16 mm latching, plain momentary) in place of the NKK UB16 / UB15.
First find candidate parts with datasheets (rated current per pin, stroke, height, pad pattern; button body and
panel hole) and show me the options with pros and cons through the options UI; give me the links to buy them.
Then: battery, chain-cap and the hub-conn target footprint, the seam compression check and the tower sections in
FreeCAD (show me through the FreeCAD MCP), button cut-outs in the core shell, DRC / parity 0, fab outputs.
Budget: tokens are tight. PCB and CAD work stays with you. No leftover background processes.
End by updating next.md and the spec, committing, and giving me the prompt for the next session.
```

## C. Key modules: printed plates, matrix diode, socket
```
Keyboard project, rev 9.1, branch rev9-go. Read next.md ("Cost review session" block), plans/keyboard.md sections 2a
and 3c, nothing else to start.
Cost session C. I decided: printed ASA plates first (the FR4 plate designs stay in the repo as the fallback),
BAT43W -> B5819W if its datasheet allows, and a check of the in-stock hot-swap socket clone (JLC C49352235) against
our Kailh footprint because the Kailh part is out of stock and flagged discontinued at JLC.
First: the B5819W datasheet (capacitance, forward voltage at 0.3 mA, reverse leakage hot) against the 10 k column
pull-ups and the 1 kHz scan with three-key ghost paths; the socket drawing against the footprint; tell me the result.
Then the printed plate: thickness and clip geometry from the M0 test cell (14.1 mm cut-out), stiffness and split
for the 241 mm right half on my printers (Bambu H2S, Prusa CORE One, ASA), how it sits in the module shells; show me
through the FreeCAD MCP and ask through the options UI before changing the shells. A diode change is value-only:
no re-routing of the key boards.
Budget: tokens are tight. PCB and CAD work stays with you. No leftover background processes.
End by updating next.md and the spec, committing, and giving me the prompt for the next session.
```

## D. Pods
```
Keyboard project, rev 9.1, branch rev9-go. Read next.md ("Cost review session" block), plans/keyboard.md sections 2b
and 3c, nothing else to start.
Cost session D, pods. I decided: MDBT50Q-1MV2 -> MDBT50Q-P1MV2 (PCB antenna), Coilcraft inductors -> Sunlord,
resistor values moved to JLC basic parts (divider 1 M / 330 k: firmware ADC constant), the genuine JST GH under the
cheaper listing, an SMD USB-C receptacle in place of the USB4085. The debug header is already unfitted (tools/fab.py).
First check and show me: the P1MV2's footprint and antenna keep-out against the board's rule area and the shell;
the inductors' saturation current and DCR against the TPS630701 and TPS629210 peaks at the lowest pack voltage;
the receptacle's footprint and the shell opening. Ask through the options UI where a check fails.
Then tools/sch_pod.py, pod and pod-power placed and routed again where needed (say so first), ERC / DRC / parity 0,
fab outputs, wireless shells checked if anything at the edge moves.
Budget: tokens are tight. PCB and CAD work stays with you. No leftover background processes.
End by updating next.md and the spec, committing, and giving me the prompt for the next session.
```
