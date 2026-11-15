#!/usr/bin/env python3
"""Pod 3.3 V overvoltage fault and its clamps (pod-power, spec section 2b; robustness review 8), ngspice.

Run: python3 tools/sim_crowbar.py [name=value ...]   (decks and data go to build/sim/; names as in P below)

Fault: the TPS629210's high-side switch shorts at t = 10 us (rsh ohm, a failed FET; 0.25 = its healthy RDSon).
Netlist mirrors tools/sch_pod.py build_power():
  pack (vp, rp per pack, 200 nH of wire) -> F1 (rf1) -> Q1 (50 mohm) -> VPACK: C20 47 uF can (esr) + ceramics (cin)
  VPACK -> short -> SW -> L1 2.2 uH (20 mohm; l1 = 1.0e-6 stands for the saturated coil, Isat 5.4 A) -> +3V3
  +3V3: 22 uF 1206 (cout, DC bias taken off) ; lead (30 nH, 50 mohm) -> pod capacitors (cpod) and load (rload)
Variants:
  none  no protection
  scr   A: comparator (trip vtrip, delay td = comparator + SCR turn-on) fires an SCR from +3V3 to GND
        (latched; on-state vt0 + rd * I)
  ser   B: series element rs between +3V3 and the lead (+3V3_P, own capacitor cp); the comparator watches
        +3V3_P and closes a FET (rfet) from +3V3_P to GND, latched
The comparator is a threshold, a delay and a latch; the SCR / FET closes within 100 ns after the delay.
Left out: the converter's control loop (it is dead or overridden in this fault), coil saturation as a curve,
the PTCs' heating (F1 and rs are plain resistors here: the first 300 us only; trip times come from the datasheet).
"""
import os
import subprocess
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "sim")
P = dict(vp=10.0, rp=0.3, rf1=0.08, esr=0.05, cin=12e-6, rsh=0.1, l1=2.2e-6, cout=16e-6, cpod=10e-6, rload=330.0,
         vtrip=3.6, td=1.5e-6, vt0=0.85, rd=0.03, rs=4.7, cp=10e-6, rfet=0.03, tend=300e-6)
T0 = 10e-6


def deck(name, variant, p):
    L = [f"* {name}", ".options reltol=1e-4 abstol=1e-9 vntol=1e-6 method=gear",
         ".model SW1 SW(vt=0.5 vh=0.05 ron=1 roff=1e9)", ".model DI D(Is=1e-12 N=1 Rs=0.001)",
         f".model SSH SW(vt=0.5 vh=0.05 ron={p['rsh']} roff=1e8)",
         f".model SCL SW(vt=0.5 vh=0.05 ron={p['rd'] if variant == 'scr' else p['rfet']} roff=1e8)",
         f"VP vp0 0 {p['vp']}", f"RP vp0 vp1 {p['rp']}", "LW vp1 vp2 200n ic=0", f"RF vp2 vp3 {p['rf1']}",
         "RQ vp3 vpack 0.05", f"C20 vpack c20 47u ic={p['vp']}", f"RC20 c20 0 {p['esr']}",
         f"CIN vpack cin {p['cin']} ic={p['vp']}", "RCIN cin 0 0.005",
         f"VF flt 0 PWL(0 0 {T0} 0 {T0 + 20e-9} 1)", "SF vpack sw flt 0 SSH",
         f"L1 sw l1 {p['l1']} ic=0", "RL1 l1 v33 0.02",
         f"CO v33 co {p['cout']} ic=3.3", "RCO co 0 0.005"]
    prot = "v33p" if variant == "ser" else "v33"
    if variant == "ser":
        L += [f"RS v33 v33p {p['rs']}", f"CP v33p cpx {p['cp']} ic=3.3", "RCP cpx 0 0.005"]
    L += [f"LL {prot} ll 30n ic=0", "RLL ll pod 0.05", f"CPOD pod cpd {p['cpod']} ic=3.3", "RCPD cpd 0 0.01",
          f"RLOAD pod 0 {p['rload']}"]
    if variant != "none":
        L += [f"BC cmp 0 V = V({prot}) > {p['vtrip']} ? 1 : 0", f"RD cmp dl {p['td'] / 0.693 / 1e-9}", "CD dl 0 1n ic=0",
              "BT trg 0 V = V(dl) > 0.5 ? 1 : 0", "DL trg lat DI", "CL lat 0 1n ic=0", "RLT lat 0 1e12",
              "BG g 0 V = V(lat) > 0.3 ? 1 : 0", "RG g gg 100", "CG gg 0 1n ic=0"]
        if variant == "scr":
            L += ["SC v33 ka gg 0 SCL", "DK ka kb DI", f"VK kb kc {p['vt0'] - 0.6}", "VCL kc 0 0"]
        else:
            L += ["SC v33p kc gg 0 SCL", "VCL kc 0 0"]
    else:
        L += ["VCL kc 0 0", "RKC kc 0 1"]
    L += [".control", f"tran 20n {p['tend']} uic", "set wr_singlescale", "set wr_vecnames",
          f"wrdata {OUT}/{name}.dat v33 pod vpack i(L1) i(VCL) i(LW)" + (" v33p" if variant == "ser" else ""), ".endc", ".end"]
    return "\n".join(L) + "\n"


def run(name, variant, **over):
    p = dict(P, **over)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".cir")
    with open(path, "w") as f:
        f.write(deck(name, variant, p))
    r = subprocess.run(["ngspice", "-b", path], capture_output=True, text=True, timeout=300)
    dat = os.path.join(OUT, name + ".dat")
    if r.returncode or not os.path.exists(dat):
        sys.exit(f"{name}: ngspice failed\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    rows = [l.split() for l in open(dat)]
    cols = [c.lower() for c in rows[0][1:]]
    d = [[float(x) for x in r_] for r_ in rows[1:] if r_]
    t = [r_[0] for r_ in d]
    v = {c: [r_[i + 1] for r_ in d] for i, c in enumerate(cols)}
    return t, v


def stats(t, v, rail):
    x = v[rail]
    over = sum((t[i + 1] - t[i]) for i in range(len(t) - 1) if x[i] > 3.9)
    first = next((t[i] - T0 for i in range(len(t)) if x[i] > 3.9), None)
    ic = v["i(vcl)"]
    i2t = sum(ic[i] ** 2 * (t[i + 1] - t[i]) for i in range(len(t) - 1))
    return dict(peak=max(x), first=first, over=over, icl=max(ic), i2t=i2t, il=max(v["i(l1)"]), ipk=v["i(lw)"][-1],
                vend=x[-1], vpack=v["vpack"][-1])


def line(tag, s):
    f = "never" if s["first"] is None else f"{s['first'] * 1e6:5.1f} us"
    return (f"{tag:46s} peak {s['peak']:5.2f} V  >3.9 V after {f}, for {s['over'] * 1e6:6.1f} us  clamp {s['icl']:5.1f} A"
            f" (I2t {s['i2t'] * 1e3:6.2f} mA2s)  coil {s['il']:5.1f} A  end: rail {s['vend']:4.2f} V, pack {s['ipk']:4.1f} A")


def main():
    over = {k: float(x) for k, x in (a.split("=") for a in sys.argv[1:])}
    print("rail at the pod (protected side); fault at t = 0; first 300 us")
    for tag, kw in (("6 cells 10 V, short 0.1 ohm", {}), ("short 0.25 ohm (RDSon)", dict(rsh=0.25)),
                    ("coil saturated (1.0 uH), short 0.03", dict(l1=1.0e-6, rsh=0.03)),
                    ("4 cells 6.4 V", dict(vp=6.4)), ("alkaline pack 0.9 ohm, wet can 0.5 ohm", dict(rp=0.9, esr=0.5))):
        kw = dict(kw, **over)
        print(f"-- {tag}")
        t, v = run("cb_none", "none", **kw)
        print(line("   no protection", stats(t, v, "pod")))
        for td in (0.5e-6, 1.5e-6, 3e-6):
            t, v = run("cb_scr", "scr", **dict(kw, td=td))
            print(line(f"   A SCR on +3V3, delay {td * 1e6:.1f} us", stats(t, v, "pod")))
        for rs, td in ((1.0, 1.5e-6), (4.7, 1.5e-6), (4.7, 6e-6), (10.0, 6e-6), (10.0, 20e-6)):
            t, v = run("cb_ser", "ser", **dict(kw, rs=rs, td=td))
            print(line(f"   B series {rs:g} ohm + FET, delay {td * 1e6:.1f} us", stats(t, v, "pod")))


if __name__ == "__main__":
    main()
