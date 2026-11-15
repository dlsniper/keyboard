# Prompt: M3b session 6, fast crowbar on the pod's 3.3 V

Saved 2026-11-15 at the end of the M2 robustness review session. Run it in a clean session. The fit-print session
(`plans/prompt-m3-session-7.md`) is independent of it and can come before or after.

```
Keyboard project, rev 9.1, branch rev9-go. Read next.md ("M2 robustness review session" block and finding 8 of the
"Independent robustness review" block), plans/keyboard.md §2b (pod-power), nothing else to start.
M3b session 6: overvoltage protection of the pod's +3V3 (robustness review 8; I chose "fast crowbar, own session").
The fault: TPS629210 high side shorted, or R6 (MODE/S-CONF) open, puts the pack (up to 10 V) on the nRF52840
(3.9 V absolute); +3V3 passes 3.9 V about 3 us after the short and reaches pack voltage after 11-22 us, so a
supervisor (about 20-30 us) is too slow.
First design it and show me, before any board change: a comparator of about 1 us with its own reference and a
supply that survives the fault, an SCR (or other latching switch) directly on +3V3 that also swallows the 57 uF of
input capacitors through the 2.2 uH, what F1 (MF-MSMF150/16X, trips at 3.0 A) then does, the idle current it adds,
false trips (load steps, plugging the pack in, the radio's bursts), and what a failure of the new parts themselves
does. Simulate the rise and the clamp (ngspice, as tools/sim_*.py). Datasheets into build/ds; delegate only lookups.
Critique it honestly, including "not worth it" and a TPS2553-side variant for +5V_RAW, then ask me through the
options UI with pros and cons whether to build it. Only on a yes: tools/sch_pod.py, pod-power placed and routed
again (say so first), ERC / DRC / parity 0, fab outputs, wireless shells checked if the outline, holes, J1, J2 or SW1
move. No other board changes.
Budget: tokens are tight. PCB and CAD work stays with you. No leftover background processes.
End by updating next.md, committing, and giving me the prompt for the next session.
```
