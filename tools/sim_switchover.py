#!/usr/bin/env python3
"""USB / battery switchover simulation (hub-conn power path, spec section 3a), ngspice.

Run: python3 tools/sim_switchover.py [name=value ...]   (decks go to build/sim/; names as in P below,
     e.g. vit=4.3 rqu=10e3 csys=160e-6 for the values before M1 task 5)

Netlist mirrors tools/sch_hub.py build_conn():
  VBAT -> QB (P-FET, source VBAT, body diode SYS -> VBAT) -> SYS; gate: RQB_G to VBAT, pulled low while NVBUS is high
  VBUS_IN -> QU (P-FET, source SYS, body diode VBUS_IN -> SYS) -> SYS; gate: RQU_G to SYS, pulled low by USB_DLY
  USB_OK = supervisor on VBUS_IN (falls at VIT-, rises 0.2 V higher; 15 us detect delay)
  NVBUS = RNV to VBAT, low while USB_OK; USB_DLY = RDLY / CDLY from USB_OK, Schottky back for a fast discharge
  SYS bulk CSYS (4 x 47 uF ceramic with the DC bias taken off + 220 uF polymer); load = the buck-boost: constant power, 9 A input limit,
  off below 2.95 V and back on above 3.5 V (TPS552892 EN/UVLO divider 100k / 54.9k).
Models from datasheet numbers: CSD25402Q3A 12 mOhm, Vth 0.9 V, Ciss 1.8 nF, body diode; DMN63D8LDW Vth 1 V;
TPS3840 tP_HL 15 us typ. Pack: source + 0.5 Ohm; USB: source + cable/port resistance.
After a time on USB the LM74610 of the pack has lost its charge-pump voltage, so for the first 25-140 ms after a
hand-over the pack current runs through the ideal-diode FET's body diode: the "body diode" cases add that drop.
Left out: the KTS1693 current limit and its 200 ms restart, the converter's soft start, cable inductance.
"""
import os
import subprocess
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build", "sim")
# values on the schematic (tools/sch_hub.py); keep in step
P = dict(csys=380e-6, vit=3.6, rqu=1e3, rnv=1e6, rqb=1e6, rdly=2.2e6, cdly=22e-9, cvbus=1.2e-6)


def deck(name, vbat, vusb, rusb, plug, power, tend, p):
    """plug: PWL points (t, 0/1) for the host cable; vbat 0 = no pack."""
    pwl = " ".join(f"{t} {v}" for t, v in plug)
    L = [f"* {name}", ".options reltol=1e-4 abstol=1e-10 vntol=1e-6 method=gear",
         ".model DBODY D(Is=1e-11 N=1 Rs=0.02)", ".model DSCH D(Is=2e-7 N=1.05 Rs=5)",
         ".model PRES SW(vt=0.5 vh=0.1 ron=0.001 roff=1e9)",
         f".model SUP SW(vt={p['vit'] + 0.1} vh=0.1 ron=1 roff=1e9)", ".model HALF SW(vt=0.5 vh=0.05 ron=1 roff=1e9)",
         ".model UV SW(vt=3.22 vh=0.27 ron=1 roff=1e9)", "VONE one 0 1",
         f"VB vb0 0 PWL(0 0 0.001 {vbat} 100 {vbat})", *([f"RB vb0 vbx {0.5 if vbat else 1e9}", "DLM vbx vbat DBODY"] if p.get("bodydiode") else
           [f"RB vb0 vbat {0.5 if vbat else 1e9}"]), "CVBAT vbat 0 100n", "RVBAT vbat 0 10Meg",
         f"VU vu0 0 {vusb}", f"VPL pl 0 PWL({pwl})", "SU vu0 vu1 pl 0 PRES", f"RU vu1 vbus {rusb}",
         f"CVBUS vbus 0 {p['cvbus']}", "RVBUS vbus 0 100k",
         # USB switch QU
         "BQU vbus sys I = V(vbus,sys)/0.012/(1+exp(-(V(sys,qug)-0.9)/0.04))", "DQU vbus sys DBODY",
         "CGU sys qug 1.8n", f"RGU sys qug {p['rqu']}",
         "BNU qug 0 I = V(qug)/5/(1+exp(-(V(dly)-1.0)/0.04))",
         # battery switch QB (power switch closed, UVLO good)
         "BQB vbat sys I = V(vbat,sys)/0.012/(1+exp(-(V(vbat,qbg)-0.9)/0.04))", "DQB sys vbat DBODY",
         "CGB vbat qbg 1.8n", f"RGB vbat qbg {p['rqb']}",
         "BNB qbg 0 I = V(qbg)/10/(1+exp(-(V(nvbus)-1.0)/0.04))",
         f"RNV vbat nvbus {p['rnv']}", "CNV nvbus 0 60p",
         "BNV nvbus 0 I = V(nvbus)/5/(1+exp(-(V(ok)-1.0)/0.04))",
         # supervisor with its detect delay
         "SS one st vbus 0 SUP", "RST st 0 1k", "RD st std 1k", "CD std 0 20n", "SS2 one st2 std 0 HALF", "RST2 st2 0 1k",
         "BOK oki 0 V = V(st2)*V(vbus)", "ROK oki ok 50",
         f"RDL ok dly {p['rdly']}", f"CDL dly 0 {p['cdly']}", "DDL dly ok DSCH",
         f"CSYS sys 0 {p['csys']}", "RSYS sys 0 1Meg",
         "SUV one uv sys 0 UV", "RUV uv 0 1k",
         f"VPW pw 0 PWL({' '.join(f'{t} {v}' for t, v in power)})",
         "BLOAD sys 0 I = V(uv) > 0.5 ? min(V(pw)/max(V(sys),1), 9) : 0",
         ".control", f"tran 2u {tend} uic", "set wr_singlescale", "set wr_vecnames",
         f"wrdata {OUT}/{name}.dat sys vbus vbat ok qug qbg uv i(VB) i(VU)", ".endc", ".end"]
    return "\n".join(L) + "\n"


def run(name, **kw):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{name}.cir")
    open(path, "w").write(deck(name, **kw))
    r = subprocess.run(["ngspice", "-b", path], capture_output=True, text=True, timeout=300)
    dat = os.path.join(OUT, f"{name}.dat")
    if r.returncode or not os.path.exists(dat):
        sys.exit(f"{name}: ngspice failed\n{r.stdout[-800:]}{r.stderr[-800:]}")
    lines = open(dat).read().splitlines()
    hdr = lines[0].split()
    rows = [[float(x) for x in ln.split()] for ln in lines[1:] if ln.strip()]
    os.remove(dat)
    return hdr, rows


def report(label, hdr, rows, t0):
    k = {n: hdr.index(n) for n in hdr}
    after = [r for r in rows if r[0] >= t0]
    sys_min = min(after, key=lambda r: r[k["sys"]])
    ok = [r[k["ok"]] > 2 for r in after]
    toggles = sum(1 for a, b in zip(ok, ok[1:]) if a != b)
    uvlo = any(r[k["uv"]] < 0.5 for r in after)
    # both switches on at once: QU gate more than 0.9 V below SYS and QB gate more than 0.9 V below VBAT
    both = sum(b[0] - a[0] for a, b in zip(after, after[1:])
               if a[k["sys"]] - a[k["qug"]] > 0.9 and a[k["vbat"]] - a[k["qbg"]] > 0.9)
    back = max(r[k["i(VU)"]] for r in after)  # positive = current pushed back into the host
    end = after[-1]
    print(f"  {label}: min SYS {sys_min[k['sys']]:.2f} V at +{(sys_min[0] - t0) * 1e3:.2f} ms; "
          f"converter UVLO {'HIT' if uvlo else 'no'}; USB_OK edges {toggles}; both switches on {both * 1e6:.0f} us; "
          f"end SYS {end[k['sys']]:.2f} V, pack {-end[k['i(VB)']]:.2f} A, USB {-end[k['i(VU)']]:.2f} A"
          + (f"; peak current into the host {back:.2f} A" if back > 0.05 else ""))


def cases(p):
    T = 0.1
    step = lambda pw: [(0, 0.6), (0.05, 0.6), (0.0501, pw), (1, pw)]  # the hub starts with the LEDs off
    # one pack (0.5 Ohm with its path) cannot give more than about 13 W; 16 W is "LEDs at full power when the cable is pulled"
    for vbat in (4.4, 5.2, 6.3):
        for pw in (0.6, 6.0, 10.0, 16.0):
            h, r = run("unplug", vbat=vbat, vusb=5.0, rusb=0.15, plug=[(0, 1), (T, 1), (T + 1e-5, 0), (1, 0)],
                       power=step(pw), tend=T + 0.05, p=p)
            report(f"unplug USB, pack {vbat} V, {pw} W in", h, r, T)
            if pw in (6.0, 10.0):
                h, r = run("unplug_bd", vbat=vbat, vusb=5.0, rusb=0.15, plug=[(0, 1), (T, 1), (T + 1e-5, 0), (1, 0)],
                           power=step(pw), tend=T + 0.05, p={**p, "bodydiode": 1})
                report(f"  same, pack on the body diode", h, r, T)
    for vbat in (4.4, 5.2, 6.3):
        for pw in (0.6, 10.0):
            h, r = run("plug", vbat=vbat, vusb=5.0, rusb=0.15, plug=[(0, 0), (T, 0), (T + 1e-5, 1), (1, 1)],
                       power=step(pw), tend=T + 0.1, p=p)
            report(f"plug USB in, pack {vbat} V, {pw} W in", h, r, T)
    # weak host and cable: 4.75 V source, 0.35 Ohm to the hub; does the detect chatter under load?
    for vbat, pw in ((5.2, 6.0), (5.2, 12.0), (0, 6.0), (0, 12.0)):
        h, r = run("sag", vbat=vbat, vusb=4.75, rusb=0.35, plug=[(0, 1), (1, 1)], power=step(pw), tend=0.3, p=p)
        report(f"weak host 4.75 V / 0.35 Ohm, {'pack ' + str(vbat) + ' V' if vbat else 'no pack'}, {pw} W in", h, r, 0.05)


if __name__ == "__main__":
    p = dict(P)
    for a in sys.argv[1:]:
        k, v = a.split("=")
        p[k] = float(v)
    print("== " + ", ".join(f"{k}={v:g}" for k, v in p.items()))
    cases(p)
