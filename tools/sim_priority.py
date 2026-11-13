#!/usr/bin/env python3
"""Pack-priority hand-over simulation (hub-conn power path, spec section 3a), ngspice.

Run: python3 tools/sim_priority.py [re-arm resistor in ohms ...]     (decks and raw data go to build/sim/)

Three pack inputs are modelled (the chain logic is the same for five): 1 = nearest the hub, 3 = lowest
module (no priority FET, like hub input 5). Netlist mirrors tools/sch_hub.py build_pack_input():
  pack -> ideal diode -> VMi -> P-FET (source VBAT, drain VMi, body diode VMi -> VBAT) -> VBAT
  BLKi = OK(i+1) or BLK(i+1) through BAT54C, 4.7M to GND; BLKi high -> PENi low -> gate at VBAT (FET off)
  supervisor i: 100k from the pack to VDD, 1u, RFB from VDD to the push-pull output.
Models from datasheet numbers: TPS3840PL43 VIT- 4.3 V, VHYS 200 mV, IDD 300 nA; CSD25402Q3A as a
12 mOhm channel with Vth 0.9 V, 2 nF gate, body diode about 0.65 V at 1 A; LM74610 + CSD17313Q2 as a
16 mV / 30 mOhm diode with 100k reverse leakage (its periodic body-diode refresh is not modelled); BAT54 about 0.2 V at 1 uA.
Pack: voltage source + 0.45 Ohm (4 cells, PTC, two pogo seams). Load: constant power on VBAT (the
buck-boost), 200 uF bulk.
"""
import os
import subprocess
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "sim")
N = 3
RPACK = 0.45
RBLEED = 22e3  # bleeder per pack input (on while the hub runs); 1e12 = none


def deck(rfb, ocv, present, power, tend, name):
    """ocv[i], present[i]: PWL point lists [(t, v), ...] per pack (present: 1 = in the stack); power: PWL in W."""
    pwl = lambda pts: " ".join(f"{t} {v}" for t, v in pts)
    L = [f"* {name} rfb={rfb}", ".options reltol=1e-4 abstol=1e-11 vntol=1e-6 method=gear",
         ".model DID D(Is=1e-9 N=0.03 Rs=0.03)", ".model DBODY D(Is=1e-11 N=1 Rs=0.02)",
         ".model DSCH D(Is=2e-7 N=1.05 Rs=5)", ".model PRES SW(vt=0.5 vh=0.1 ron=0.001 roff=1e9)",
         ".model SUP SW(vt=4.4 vh=0.1 ron=1 roff=1e9)", "VONE one 0 1",
         "CSYS vbat 0 200u", "RLEAK vbat 0 10Meg", f"VPW pw 0 PWL({pwl(power)})",
         "BLOAD vbat 0 I = V(vbat) > 2 ? min(V(pw)/V(vbat), 3) : V(vbat)*V(pw)/4"]
    for i in range(1, N + 1):
        vm = f"vm{i}" if i < N else "vbat"
        L += [f"VOCV{i} ocv{i} 0 PWL({pwl(ocv[i])})", f"VPR{i} pr{i} 0 PWL({pwl(present[i])})",
              f"RP{i} ocv{i} cell{i} {RPACK}", f"SP{i} cell{i} pack{i} pr{i} 0 PRES",
              f"RBLEED{i} pack{i} 0 {RBLEED}", f"CIN{i} pack{i} 0 10n",
              # ideal diode: 16 mV + 30 mOhm forward; reverse: the LM74610 leakage (60 uA typ at 13.5 V) as 100k
              f"DID{i} pack{i} {vm} DID", f"RLK{i} pack{i} {vm} 100k"]
        if i < N:
            L += [f"DB{i} vm{i} vbat DBODY", f"CVM{i} vm{i} 0 10n",
                  f"BQ{i} vm{i} vbat I = V(vm{i},vbat)/0.012/(1+exp(-(V(vbat,pg{i})-0.9)/0.04))",
                  f"CG{i} vbat pg{i} 2n", f"RG{i} vbat pg{i} 1Meg", f"RPEN{i} vbat pen{i} 2.2Meg",
                  f"CPEN{i} pen{i} 0 60p", f"CBLK{i} blk{i} 0 60p", f"RBLK{i} blk{i} 0 4.7Meg",
                  f"BNA{i} pen{i} 0 I = V(pen{i})/5/(1+exp(-(V(blk{i})-1.0)/0.04))",
                  f"BNB{i} pg{i} 0 I = V(pg{i})/5/(1+exp(-(V(pen{i})-1.0)/0.04))",
                  f"DOK{i} ok{i + 1} blk{i} DSCH"]
            if i < N - 1:
                L.append(f"DBL{i} blk{i + 1} blk{i} DSCH")
        if i > 1:
            L += [f"RS{i} pack{i} pvdd{i} 100k", f"CS{i} pvdd{i} 0 1u", f"RFB{i} pvdd{i} ok{i} {rfb}",
                  f"BIDD{i} pvdd{i} 0 I = 300n*tanh(V(pvdd{i}))", f"SS{i} one st{i} pvdd{i} 0 SUP",
                  f"RST{i} st{i} 0 1k", f"BOK{i} oki{i} 0 V = V(st{i})*V(pvdd{i})", f"ROK{i} oki{i} ok{i} 50"]
    sig = ["vbat"] + [f"pack{i}" for i in range(1, N + 1)] + [f"ok{i}" for i in range(2, N + 1)] + \
          [f"pg{i}" for i in range(1, N)] + [f"i(VOCV{i})" for i in range(1, N + 1)]
    L += [".control", f"tran 200u {tend} uic", "set wr_singlescale", "set wr_vecnames",
          f"wrdata {OUT}/{name}.dat " + " ".join(sig), ".endc", ".end"]
    return "\n".join(L) + "\n", sig


def run(rfb, name, ocv, present, power, tend):
    os.makedirs(OUT, exist_ok=True)
    text, sig = deck(rfb, ocv, present, power, tend, name)
    path = os.path.join(OUT, f"{name}.cir")
    open(path, "w").write(text)
    r = subprocess.run(["ngspice", "-b", path], capture_output=True, text=True, timeout=300)
    dat = os.path.join(OUT, f"{name}.dat")
    if r.returncode or not os.path.exists(dat):
        sys.exit(f"{name}: ngspice failed\n{r.stdout[-800:]}{r.stderr[-800:]}")
    rows = [[float(x) for x in ln.split()] for ln in open(dat).read().splitlines()[1:] if ln.strip()]
    os.remove(dat)
    return ["t"] + sig, rows


def col(hdr, rows, name):
    k = hdr.index(name)
    return [r[k] for r in rows]


def edges(t, v, level=2.0):
    return [(round(t[k], 3), "up" if v[k] > level else "down") for k in range(1, len(v))
            if (v[k] > level) != (v[k - 1] > level)]


def at(hdr, rows, tq, names):
    r = min(rows, key=lambda r: abs(r[0] - tq))
    return " ".join(f"{n}={r[hdr.index(n)]:.3f}" for n in names)


def share(hdr, rows, tq):
    r = min(rows, key=lambda r: abs(r[0] - tq))
    return " ".join(f"I{i}={-r[hdr.index(f'i(VOCV{i})')] * 1000:.0f}mA" for i in range(1, N + 1))


def const(v):
    return [(0, 0), (0.001, v), (100, v)]


IN, OUTP = [(0, 1), (100, 1)], [(0, 0), (100, 0)]


def cases(rfb):
    class Out(list):
        def append(self, x):
            print('  ' + x, flush=True)
    out = Out()
    P = [(0, 0.5), (100, 0.5)]
    # thresholds: lowest pack ramps up and down slowly with no load on it
    h, r = run(rfb, "thresholds", {1: const(0), 2: const(0), 3: [(0, 4.0), (14, 5.4), (28, 4.0)]},
               {1: OUTP, 2: OUTP, 3: IN}, [(0, 0), (100, 0)], 28)
    e = edges(col(h, r, "t"), col(h, r, "ok3"))
    lv = [f"{d} at pack={min(r, key=lambda x: abs(x[0] - t))[h.index('pack3')]:.2f} V" for t, d in e]
    out.append(f"thresholds (slow ramp, no load): {', '.join(lv)}")
    # start-up from one pack, in each position
    for k in range(1, N + 1):
        for v in (5.2, 4.6):
            h, r = run(rfb, f"start{k}", {i: const(v if i == k else 0) for i in range(1, N + 1)},
                       {i: (IN if i == k else OUTP) for i in range(1, N + 1)}, P, 6)
            out.append(f"start-up, only pack {k} ({v} V, 0.5 W): t=5.9s {at(h, r, 5.9, ['vbat'])}"
                       + (f" {at(h, r, 5.9, [f'pg{k}'])}" if k < N else "") + f"; min VBAT after 50 ms "
                       f"{min(x[1] for x in r if x[0] > 0.05):.2f}")
    # all three full, the active (lowest) pack is pulled at 1 s; then pack 2 at 4 s
    for pw in (0.5, 5.0):
        h, r = run(rfb, f"pull_{pw}", {i: const(5.2) for i in range(1, N + 1)},
                   {1: IN, 2: [(0, 1), (4, 1), (4.0005, 0), (100, 0)], 3: [(0, 1), (1, 1), (1.0005, 0), (100, 0)]},
                   [(0, 0.3), (0.8, 0.3), (0.801, pw), (100, pw)], 8)
        t = col(h, r, "t")
        out.append(f"pull active pack (3 at 1 s, 2 at 4 s), {pw} W: before {share(h, r, 0.9)}; ok3 {edges(t, col(h, r, 'ok3'))}; "
                   f"pg2 {edges(t, col(h, r, 'pg2'))}; pg1 {edges(t, col(h, r, 'pg1'))}; "
                   f"min VBAT {min(x[1] for x in r if x[0] > 0.5):.2f} V; end {share(h, r, 7.9)} {at(h, r, 7.9, ['vbat'])}")
    # lowest pack empties (5.0 -> 4.0 V open-circuit in 6 s), packs above at 5.2 V
    for pw in (0.3, 2.5):
        h, r = run(rfb, f"empty_{pw}", {1: const(5.2), 2: const(5.2), 3: [(0, 0), (0.001, 5.3), (1, 5.3), (7, 4.0), (100, 4.0)]},
                   {1: IN, 2: IN, 3: IN}, [(0, 0.3), (0.8, 0.3), (0.801, pw), (100, pw)], 9)
        t = col(h, r, "t")
        out.append(f"pack 3 empties, {pw} W: ok3 {edges(t, col(h, r, 'ok3'))}; pg2 {edges(t, col(h, r, 'pg2'))}; "
                   f"min VBAT {min(x[1] for x in r if x[0] > 0.5):.2f} V; "
                   f"just before {share(h, r, max(0.5, (edges(t, col(h, r, 'ok3')) or [(8, 0)])[-1][0] - 0.05))}; end {share(h, r, 8.9)}")
    # heavy load on a pack whose rest voltage is above / below the re-arm level: does it bounce?
    for v, pw in ((5.3, 10.0), (5.3, 4.0), (5.2, 6.0)):
        h, r = run(rfb, f"bounce_{v}_{pw}", {1: const(5.2), 2: const(5.2), 3: const(v)},
                   {1: IN, 2: IN, 3: IN}, [(0, 0.3), (1, 0.3), (1.001, pw), (100, pw)], 6)
        t = col(h, r, "t")
        e = edges(t, col(h, r, "ok3"))
        out.append(f"load step to {pw} W, pack 3 rests at {v} V: ok3 toggles {len(e) - 1} times after start-up "
                   f"{e[1:6]}; min VBAT {min(x[1] for x in r if x[0] > 0.5):.2f} V; end {share(h, r, 5.9)}")
    # a pack is put in at the bottom while pack 2 runs: half-used (4.9 V) and charged (5.3 V)
    for v in (4.9, 5.3):
        h, r = run(rfb, f"insert_{v}", {1: const(5.2), 2: const(5.2), 3: const(v)},
                   {1: IN, 2: IN, 3: [(0, 0), (1, 0), (1.0005, 1), (100, 1)]}, P, 4)
        t = col(h, r, "t")
        out.append(f"insert a {v} V pack below at 1 s: ok3 {edges(t, col(h, r, 'ok3'))}; pg2 {edges(t, col(h, r, 'pg2'))}; "
                   f"end {share(h, r, 3.9)} {at(h, r, 3.9, ['vbat'])}")
    return out


if __name__ == "__main__":
    args = [float(a) for a in sys.argv[1:] if not a.startswith('--')]
    if "--no-bleed" in sys.argv:
        RBLEED = 1e12
    for rfb in args or [910e3]:
        print(f"== re-arm resistor {rfb / 1e3:.0f}k, bleeder {RBLEED:g}")
        cases(rfb)
