#!/usr/bin/env python3
"""E21 / rev 8.1 hub power path: USB unplug and plug-in switchover, pack swap (2026-10-01).

Run: python3 tools/sim/e21_switchover.py [case-substring ...]   (ngspice-47, 8 cases in parallel; decks and data go to
build/sim/e21/; `fix3` = the decided value set)
Results are recorded in plans/keyboard.md §4 (rev 8.1 block, E21).

Circuit (spec §4 rev 8.1): pack -> R (cells, holder, PTC, pogo/ESQ) -> LM74610-Q1 + CSD17313Q2 -> VBAT
-> CSD25402Q3A "Qb" (source VBAT, drain SYS) -> SYS.  Qb gate: pull-up RGB to VBAT, pull-down through N2 (gate:
pull-up R2 to VBAT, grounded by N3 on USB) in series with N1 (gate: TPS3840PL40 output via the slide switch, 1 MOhm
pull-down).  USB: host VBUS -> LM66200 (ideal diode) -> VBUS_IN -> CSD25402Q3A "Qu" (source SYS, drain VBUS_IN; gate
pull-up RGU to SYS, pulled down by N4).  TPS3840PL43 on VBUS_IN drives N3 and N4.  N1-N4 = DMN63D8LDW.
Loads on SYS: TPS630701 as constant power (LED rail x 5 V / 0.9, off below its 1.85 V UVLO), TPS70933 26 mA.

Models, from datasheets in build/ds/ (numbers in build/sim/e21/notes.md):
  TPS3840 (SNVSB03E): VIT-, VHYS 200 mV, tP_HL 30 us max, release tD 50 us (CT open), tSTRT 350 us max from VDD
           below 1.5 V, push-pull output ~500 ohm.
  LM74610-Q1 (SNOSCZ1B): pump runs while off and Vac >= 0.48 V, Icharge = Fig. 8 typical x KCH (KCH=40/46 -> the
           0.55 V minimum), Vcap on 6.3 / off 5.15 V, 0.95 uA drain, gate slews ~2 ms on and off, reverse
           (Vac < -20 mV) pull-down in ~2 us.
  CSD17313Q2: Vth 1.3 V, 32 mOhm at 4.5 V, body diode fitted to Fig. 9 (0.60 V at 1 mA, 0.77 V at 0.45 A, 25 C).
  CSD25402Q3A: Vth -0.9 V, 8.9 mOhm at -4.5 V, Cgs 1.34 nF, Cgd 0.1 nF (Qgd 1.1 nC), body diode ~0.7 V at 1 A.
  DMN63D8LDW: Vth 1.5 V (max), 4.2 ohm at 4.5 V, Ciss 22 pF, Crss 2 pF.
  LM66200: ideal diode, 60 mOhm, no reverse current.  TPS70933: dropout 13 ohm (650 mV at 50 mA max).
Not modelled: layout inductance, cell chemistry dynamics (packs are V + R), the KTS1693, AUX_5V.
"""
import os, re, subprocess, sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "build", "sim", "e21")
os.makedirs(OUT, exist_ok=True)

T_EV = 0.02          # event time (s)

def tps3840(n, vdd, sense, out, vitm, hys=0.2, t_hl=30e-6, t_rel=50e-6, t_strt=350e-6):
    # comparator with hysteresis (state c), then an integrator st that crosses 0.5 after t_rel (rising, or
    # t_strt if VDD came up from below 1.5 V) or t_hl (falling).  Output = VDD when st > 0.5.
    return f"""
* TPS3840 {n}: VIT- {vitm} V, VIT+ {vitm + hys:.3f} V
B{n}c {n}ci 0 V = (V({sense}) > (V({n}c) > 0.5 ? {vitm} : {vitm + hys})) && (V({vdd}) > 1.5) ? 1 : 0
R{n}c {n}ci {n}c 1k
C{n}c {n}c 0 1n
B{n}p {n}pi 0 V = V({vdd}) > 1.5 ? 1 : 0
R{n}p {n}pi {n}p 1k
C{n}p {n}p 0 {t_strt / 0.7 / 1e3}
B{n}s 0 {n}st I = V({n}c) > 0.5 ? (V({n}st) < 1 ? 1e-9 * 0.5 / {t_rel} * (V({n}p) > 0.5 ? 1 : 0) : 0) : (V({n}st) > 0 ? -1e-9 * 0.5 / {t_hl} : 0)
C{n}st {n}st 0 1n
B{n}o {n}oi 0 V = V({n}st) > 0.5 ? V({vdd}) : 0
R{n}o {n}oi {out} 500
B{n}io {vdd} 0 I = max(V({n}oi) - V({out}), 0) / 500
"""

def lm74610(k, a, c, kch):
    ich = ("pwl(V({a},{c}), 0.47,0, 0.5,25e-6, 0.55,40e-6, 0.6,55e-6, 0.65,70e-6, 0.7,90e-6, 0.75,110e-6,"
           " 0.8,130e-6, 0.85,170e-6, 0.9,130e-6, 1.0,95e-6, 2,95e-6)").format(a=a, c=c)
    return f"""
* LM74610-Q1 + CSD17313Q2, input {k}
B{k}on {k}oni 0 V = V({k}vc) > (V({k}on) > 0.5 ? 5.15 : 6.3) ? 1 : 0
R{k}on {k}oni {k}on 1k
C{k}on {k}on 0 1n
B{k}ch 0 {k}vc I = (V({k}on) < 0.5 && V({a},{c}) > 0.48) ? {kch} * {ich} : 0
B{k}dis {k}vc 0 I = 0.95e-6 * 0.5 * (1 + tanh(V({k}vc) / 0.01))
C{k}vc {k}vc 0 {{ccap}}
B{k}gs 0 {k}gs I = V({a},{c}) < -0.02 ? -V({k}gs) * 0.5 : 2.75e-3 * tanh(((V({k}on) > 0.5 ? 5.5 : 0) - V({k}gs)) / 0.05)
C{k}gs {k}gs 0 1u
E{k}g {k}g {a} {k}gs 0 1
M{k} {c} {k}g {a} {a} N17 W=1 L=1
D{k}b {a} {c} DB17
"""

def deck(tag, ev="unplug", packs=(4.9,), pack_r=0.35, rail=0.35, r2=10e6, rgu=1e6, rgb=1e6, csys=47e-6,
         cvbat=10e-6, cvbus=10e-6, cin=10e-6, kch=40 / 46, vcap0=0.0, rf=0, cf=0, t_after=0.6, vbus=5.0,
         temp=25, swap_v=None, sense="vbat", n4d=None, tmax=20e-6, r1=1e6, rbleed=1e6, ccap=2.2e-6,
         vtn4=1.5, vtqb=-0.9, cqb=1.34e-9, rs40=0, cf40=100e-9, fw_ms=None):
    # sense: "vbat" = PL40 VDD on VBAT (spec); "anode" = PL40 VDD from the pack inputs through a BAT54 each.
    # n4d: (R, C) = N4 gate fed from det through R, C to GND, a BAT54 from the gate back to det (fast off).
    # r1: N1 gate pull-down; rbleed: VBUS_IN bleeder; ccap: LM74610 charge-pump cap; vtn4 / vtqb: N4 and Qb Vth
    # corners (DMN63D8LDW 0.8-1.5 V, CSD25402Q3A -0.65..-1.15 V); cqb: Qb Cgs (Ciss 1380 typ / 1790 max pF).
    # rs40 / cf40: series R from the Schottky common cathode to the PL40 VDD node, and the VDD cap (sense="anode").
    # fw_ms: firmware drops the LED rail to the 0.35 A battery cap this long after the event (None = never).
    t_end = T_EV + t_after
    p_sys = 5.0 * rail / 0.9
    L = [f"* E21 {tag}", f".options temp={temp} reltol=1e-4 abstol=1e-10 vntol=1e-6 method=gear itl4=100",
         f".param ccap={ccap}",
         ".model N17 NMOS(LEVEL=1 VTO=1.3 KP=9.8 IS=1e-20)",
         ".model DB17 D(IS=8.2e-14 N=1.01 RS=0.02)",
         ".model PQ PMOS(LEVEL=1 VTO=-0.9 KP=33.5 IS=1e-20)",
         f".model PQB PMOS(LEVEL=1 VTO={vtqb} KP=33.5 IS=1e-20)",
         f".model NDMN4 NMOS(LEVEL=1 VTO={vtn4} KP=0.079 IS=1e-20)",
         ".model DPQ D(IS=1e-9 N=1.2 RS=0.005)",
         ".model NDMN NMOS(LEVEL=1 VTO=1.5 KP=0.079 IS=1e-20)",
         ".model SW SW(Vt=0.5 Vh=0.01 Ron=1m Roff=1e12)",
         ".model DBAT54 D(Is=1.0e-8 N=1.05 Rs=1.5 EG=0.69 XTI=2 Cjo=10p)"]
    # packs
    for i, v in enumerate(packs):
        k = "ABC"[i]
        L += [f"Vp{k} p{k} 0 {v}", f"Rp{k} p{k} p{k}r {pack_r}"]
        if ev == "swap" and i == 0:
            L += [f"Vsw{k} sw{k} 0 PWL(0 1 {T_EV} 1 {T_EV + 1e-6} 0)", f"S{k} p{k}r a{k} sw{k} 0 SW"]
        elif ev == "insert" and i == len(packs) - 1:
            L += [f"Vsw{k} sw{k} 0 PWL(0 0 {T_EV} 0 {T_EV + 1e-6} 1)", f"S{k} p{k}r a{k} sw{k} 0 SW"]
        else:
            L += [f"R{k}w p{k}r a{k} 1m"]
        L += [f"C{k}in a{k} 0 {cin}"]
        L.append(lm74610(k, f"a{k}", "vbat", kch))
    L += [f"Cvbat vbat 0 {cvbat}",
          # battery switch Qb and its gate network
          "Mqb sys gb vbat vbat PQB W=1 L=1", "Dqb sys vbat DPQ", f"Cqbgs gb vbat {cqb}", "Cqbgd gb sys 0.1n",
          f"Rgb vbat gb {rgb}",
          "Mn2 gb g2 x 0 NDMN W=1 L=1", "Cn2gs g2 x 20p", "Cn2gd g2 gb 2p",
          "Mn1 x g1 0 0 NDMN W=1 L=1", "Cn1gs g1 0 20p", "Cn1gd g1 x 2p",
          f"R1 g1 0 {r1}",
          f"R2 vbat g2 {r2}",
          "Mn3 g2 det 0 0 NDMN W=1 L=1", "Cn3gs det 0 20p", "Cn3gd det g2 2p",
          "Mn4 gu g4 0 0 NDMN4 W=1 L=1", "Cn4gs g4 0 20p", "Cn4gd g4 gu 2p",
          (f"R4d det g4 {n4d[0]}\nC4d g4 0 {n4d[1]}\nD4d g4 det DBAT54" if n4d else "R4d det g4 1"),
          # USB switch Qu
          "Mqu vbusin gu sys sys PQ W=1 L=1", "Dqu vbusin sys DPQ", "Cqugs gu sys 1.34n", "Cqugd gu vbusin 0.1n",
          f"Rgu sys gu {rgu}",
          f"Cvbus vbusin 0 {cvbus}", f"Rbleed vbusin 0 {rbleed}",
          f"Csys sys 0 {csys}"]
    # UVLO sense filter
    if sense == "anode":
        L += [f"Ds{'ABC'[i]} a{'ABC'[i]} vdd40 DBAT54" for i in range(len(packs))]
        if rs40:
            L[-len(packs):] = [x.replace(" vdd40 ", " sk40 ") for x in L[-len(packs):]]
            L += [f"Rs40 sk40 vdd40 {rs40}"]
        L += [f"Cf vdd40 0 {cf40}", "Iq40 vdd40 0 0.7u"]
    elif rf:
        L += [f"Rf vbat vdd40 {rf}", f"Cf vdd40 0 {cf}", "Iq40 vdd40 0 0.7u"]
    else:
        L += ["Rf vbat vdd40 1", "Cf vdd40 0 100n", "Iq40 vdd40 0 0.7u"]
    L.append(tps3840("u40", "vdd40", "vdd40", "u40out", 4.0))
    # slide switch between the PL40 output and N1's gate
    L.append(f"Vslide slide 0 PWL(0 0 {T_EV} 0 {T_EV + 1e-4} 1)" if ev == "switch_on" else "Vslide slide 0 1")
    L.append("Sslide u40out g1 slide 0 SW")
    L.append(tps3840("u43", "vbusin", "vbusin", "det", 4.3))
    # host USB through the LM66200 (ideal diode)
    if ev == "unplug":
        L.append(f"Vusb usb 0 PWL(0 {vbus} {T_EV} {vbus} {T_EV + 1e-6} 0)")
    elif ev == "plug":
        L.append(f"Vusb usb 0 PWL(0 0 {T_EV} 0 {T_EV + 1e-3} {vbus})")
    else:
        L.append("Vusb usb 0 0")
    L += ["Bdio usb vbusin I = V(usb,vbusin) > 0 ? V(usb,vbusin) / 0.06 : 0",
          # loads
          (f"Vprail prail 0 PWL(0 {p_sys} {T_EV + fw_ms * 1e-3} {p_sys} {T_EV + fw_ms * 1e-3 + 1e-4} "
           f"{5.0 * 0.35 / 0.9})" if fw_ms is not None else f"Vprail prail 0 {p_sys}"),
          "Bled sys 0 I = V(prail) / max(V(sys), 2.0) * 0.5 * (1 + tanh((V(sys) - 1.85) / 0.02))",
          "Bldo sys 0 I = 0.026 * 0.5 * (1 + tanh((V(sys) - 2.0) / 0.05))",
          "Bvsys vsys 0 V = min(3.3, V(sys) - 0.026 * 13)"]
    # initial state
    vp = max(packs)
    on_usb = ev == "unplug"
    if on_usb:
        vb = max(vp - 0.45, vbus - 0.55)
        ic = dict(sys=vbus - 0.02, vbusin=vbus - 0.01, usb=vbus, vbat=vb, g1=vb, g2=0, gb=vb, gu=0, det=vbus, g4=vbus,
                  u43st=1, u43c=1, u43p=1, u40st=1 if vb > 4.2 else 0, u40c=1 if vb > 4.2 else 0, u40p=1,
                  vdd40=vb)
        if sense == "anode":
            ic.update(vdd40=vp - 0.12, u40st=1 if vp - 0.12 > 4.2 else 0, u40c=1 if vp - 0.12 > 4.2 else 0)
        for i in range(len(packs)):
            k = "ABC"[i]
            ic.update({f"{k}vc": vcap0, f"{k}on": 0, f"{k}gs": 0})
    elif ev == "switch_on":
        vb = vp - 0.42
        ic = dict(sys=0, vbat=vb, vbusin=0, usb=0, g1=0, g2=vb, gb=vb, gu=0, det=0, g4=0, u43st=0, u43c=0, u43p=0,
                  x=0)
        vs = vb if sense != "anode" else vp - 0.12
        ic.update(vdd40=vs, u40st=1 if vs > 4.2 else 0, u40c=1 if vs > 4.2 else 0, u40p=1)
        for i in range(len(packs)):
            k = "ABC"[i]
            ic.update({f"{k}vc": vcap0, f"{k}on": 0, f"{k}gs": 0})
    else:
        i_sys = (p_sys / vp + 0.026)
        vb = vp - i_sys * (pack_r + 0.032)
        ic = dict(sys=vb, vbat=vb, vbusin=0, usb=0, g1=vb, g2=vb, gb=0, gu=vb, det=0, g4=0, u43st=0, u43c=0, u43p=0,
                  u40st=1, u40c=1, u40p=1, vdd40=vb if sense != "anode" else vp - 0.12, x=0)
        for i, v in enumerate(packs):
            k = "ABC"[i]
            run_k = (v == vp) and not (ev == "insert" and i == len(packs) - 1)
            ic.update({f"{k}vc": (5.2 if ev == "battery" else 6.0) if run_k else vcap0, f"{k}on": 1 if run_k else 0,
                       f"{k}gs": 5.5 if run_k else 0})
        if swap_v is not None:
            pass
    L.append(".ic " + " ".join(f"V({n})={v:.4g}" for n, v in ic.items()))
    vecs = ["v(sys)", "v(vbat)", "v(vbusin)", "v(gb)", "v(gu)", "v(g1)", "v(g2)", "v(det)", "v(vsys)",
            "v(vdd40)"] + [f"v({'ABC'[i]}vc)" for i in range(len(packs))] + \
           [f"v({'ABC'[i]}gs)" for i in range(len(packs))] + [f"i(Vp{'ABC'[i]})" for i in range(len(packs))]
    dat = os.path.join(OUT, f"{tag}.dat")
    L += [f".tran 2u {t_end} 0 {tmax} uic",
          ".control", "set noaskquit", "set wr_singlescale", "set wr_vecnames", "option numdgt=7", "run",
          f"wrdata {dat} " + " ".join(vecs), "echo done", ".endc", ".end"]
    return "\n".join(L), dat

def load(dat):
    with open(dat) as f:
        hdr = f.readline().split()
        cols = [[] for _ in hdr]
        for line in f:
            for j, x in enumerate(line.split()):
                cols[j].append(float(x))
    return {h.lower(): c for h, c in zip(hdr, cols)}

def edges(t, y, thr, t0):
    n, prev = 0, None
    for ti, yi in zip(t, y):
        if ti < t0:
            continue
        s = yi > thr
        if prev is not None and s != prev:
            n += 1
        prev = s
    return n

def analyse(d, kw):
    t = d["time"]
    after = [i for i, ti in enumerate(t) if ti >= T_EV]
    sl = lambda v: [d[v][i] for i in after]
    ta = [t[i] for i in after]
    sys_ = sl("v(sys)")
    imin = min(range(len(sys_)), key=lambda i: sys_[i])
    below = 0.0
    for i in range(1, len(ta)):
        if sys_[i] < 3.64:
            below += ta[i] - ta[i - 1]
    qb_on = [vb - g > 0.9 for vb, g in zip(sl("v(vbat)"), sl("v(gb)"))]
    qu_on = [s - g > 0.9 for s, g in zip(sys_, sl("v(gu)"))]
    overlap = sum(ta[i] - ta[i - 1] for i in range(1, len(ta)) if qb_on[i] and qu_on[i])
    t_qb = next((ta[i] - T_EV for i in range(len(ta)) if qb_on[i]), None) if kw.get("ev") == "unplug" else None
    r = dict(sys_min=round(sys_[imin], 3), t_sysmin_ms=round((ta[imin] - T_EV) * 1e3, 3),
             sys_lt_3v64_ms=round(below * 1e3, 2), vsys_min=round(min(sl("v(vsys)")), 3),
             vbat_min=round(min(sl("v(vbat)")), 3), vbusin_max=round(max(sl("v(vbusin)")), 3),
             det_edges=edges(t, d["v(det)"], 2.0, T_EV), uvlo_edges=edges(t, d["v(g1)"], 2.0, T_EV),
             overlap_ms=round(overlap * 1e3, 3), sys_end=round(sys_[-1], 3),
             qb_end=qb_on[-1], qu_end=qu_on[-1])
    ue = [ta[i] for i in range(1, len(ta)) if (d["v(g1)"][after[i]] > 2.0) != (d["v(g1)"][after[i - 1]] > 2.0)]
    r["last_uvlo_edge_ms"] = round((ue[-1] - T_EV) * 1e3, 1) if ue else None
    if t_qb is not None:
        r["qb_on_us"] = round(t_qb * 1e6, 1)
    for k in "ABC":
        if f"v({k.lower()}gs)" in d:
            gs = sl(f"v({k.lower()}gs)")
            r[f"fet{k}_on_ms"] = next((round((ta[i] - T_EV) * 1e3, 1) for i in range(len(ta)) if gs[i] > 2.5), None)
    return r

def run(tag, **kw):
    text, dat = deck(tag, **kw)
    path = os.path.join(OUT, f"{tag}.cir")
    with open(path, "w") as f:
        f.write(text)
    try:
        p = subprocess.run(["ngspice", "-b", path], capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        print(tag, "TIMEOUT")
        return None
    if "done" not in p.stdout or "aborted" in p.stdout:
        print(tag, "FAILED\n", p.stdout[-2000:], p.stderr[-2000:])
        return None
    return analyse(load(dat), kw)

CASES = {}
def case(tag, **kw):
    CASES[tag] = kw

# --- as specified (rev 8.1): R2 10 MOhm, Qu pull-up 1 MOhm, no UVLO filter, SYS 47 uF ---
for v in (4.4, 4.9, 5.6, 6.4):
    case(f"unplug_spec_{v}V_0.35A", ev="unplug", packs=(v,), pack_r=0.6 if v == 6.4 else 0.35)
case("unplug_spec_4.9V_0.8A", ev="unplug", packs=(4.9,), rail=0.8)
for v in (4.4, 4.9, 5.6, 6.4):
    case(f"plug_spec_{v}V_0.35A", ev="plug", packs=(v,), pack_r=0.6 if v == 6.4 else 0.35)
case("swap_spec_4.9to4.7V_0.35A", ev="swap", packs=(4.9, 4.7))

# --- fixes: F1 sense (anode BAT54-OR | 1 s RC), F2 Qu pull-up 10 k, F3 N4 delay 2.2 M / 10 nF ---
FIX = dict(sense="anode", rgu=10e3, n4d=(2.2e6, 10e-9))
FIX2 = dict(FIX, r2=1e6, csys=100e-6)
# --- FIX3 (2026-10-01, E21 1a): Qb pull-up 1 MOhm with the N4 cap raised to 22 nF (10 nF overlapped at the worst
# corner), N1 pull-down 4.7 MOhm, VBUS_IN bleeder 100 kOhm, LM74610 cap 1 uF; E21 1b: 10 kOhm from the Schottky
# common cathode to the PL40 VDD, 1 uF on VDD (TVS-clamp filter; ~166 ms firmware window).  The decided set. ---
FIX3 = dict(FIX2, rgb=1e6, n4d=(2.2e6, 22e-9), r1=4.7e6, rbleed=100e3, ccap=1e-6, rs40=10e3, cf40=1e-6)
WORST = dict(vtn4=0.8, vtqb=-0.65, cqb=1.79e-9)     # fastest N4, slowest Qb turn-off
for v in (4.4, 4.9, 5.6, 6.4):
    pr = 0.6 if v == 6.4 else 0.35
    case(f"unplug_fix3_{v}V_0.8A", ev="unplug", packs=(v,), pack_r=pr, rail=0.8, **FIX3)
    case(f"unplug_fix3_{v}V_0.35A", ev="unplug", packs=(v,), pack_r=pr, **FIX3)
    case(f"plug_fix3_{v}V_0.35A", ev="plug", packs=(v,), pack_r=pr, **FIX3)
case("plug_fix3_6.4V_0.35A_worst", ev="plug", packs=(6.4,), pack_r=0.6, **dict(FIX3, n4d=(2.2e6 * 0.99, 19.8e-9), **WORST))
case("plug_fix3_6.4V_0.35A_slow", ev="plug", packs=(6.4,), pack_r=0.6, **dict(FIX3, n4d=(2.2e6 * 1.01, 24.2e-9)))
case("swap_fix3_4.9to4.4V_0.35A", ev="swap", packs=(4.9, 4.4), **FIX3)
case("insert_fix3_4.4then5.6V_0.35A", ev="insert", packs=(4.4, 5.6), **FIX3)
case("battery_fix3_4.5V_0.35A", ev="battery", packs=(4.5,), t_after=3.0, **FIX3)
for v in (4.4, 4.7):
    case(f"switchon_fix3_{v}V_0.35A", ev="switch_on", packs=(v,), **FIX3)
for T in (-20, 60):
    case(f"unplug_fix3_4.4V_0.35A_T{T}", ev="unplug", packs=(4.4,), temp=T, **FIX3)
case("unplug_fix3_4.2V_0.35A", ev="unplug", packs=(4.2,), **FIX3)
for v in (4.4, 4.6):     # firmware drops the lighting to the battery cap 100 ms after unplug
    case(f"unplug_fix3_{v}V_0.8A_fw100ms", ev="unplug", packs=(v,), rail=0.8, fw_ms=100, **FIX3)
for v in (4.4, 4.9, 5.6, 6.4):
    case(f"unplug_fix2_{v}V_0.8A", ev="unplug", packs=(v,), pack_r=0.6 if v == 6.4 else 0.35, rail=0.8, **FIX2)
    case(f"unplug_fix2_{v}V_0.35A", ev="unplug", packs=(v,), pack_r=0.6 if v == 6.4 else 0.35,
         **FIX2)
    case(f"plug_fix2_{v}V_0.35A", ev="plug", packs=(v,), pack_r=0.6 if v == 6.4 else 0.35, **FIX2)
case("swap_fix2_4.9to4.4V_0.35A", ev="swap", packs=(4.9, 4.4), **FIX2)
case("battery_fix2_4.5V_0.35A", ev="battery", packs=(4.5,), t_after=3.0, **FIX2)
for T in (-20, 60):
    case(f"unplug_fix2_4.6V_0.35A_T{T}", ev="unplug", packs=(4.6,), temp=T, **FIX2)
for v in (4.4, 4.9, 5.6, 6.4):
    for rail in (0.35, 0.8):
        case(f"unplug_fix_{v}V_{rail}A", ev="unplug", packs=(v,), pack_r=0.6 if v == 6.4 else 0.35, rail=rail, **FIX)
    case(f"plug_fix_{v}V_0.35A", ev="plug", packs=(v,), pack_r=0.6 if v == 6.4 else 0.35, **FIX)
    case(f"unplug_rc_{v}V_0.35A", ev="unplug", packs=(v,), pack_r=0.6 if v == 6.4 else 0.35,
         rgu=10e3, n4d=(2.2e6, 10e-9), rf=47e3, cf=22e-6, t_after=1.5)
case("unplug_fix_4.2V_0.35A", ev="unplug", packs=(4.2,), **FIX)
case("swap_fix_4.9to4.4V_0.35A", ev="swap", packs=(4.9, 4.4), **FIX)
case("swap_fix_4.9to4.4V_0.8A", ev="swap", packs=(4.9, 4.4), rail=0.8, **FIX)
case("insert_fix_4.4then5.6V_0.35A", ev="insert", packs=(4.4, 5.6), **FIX)
for c in (47e-6, 100e-6, 220e-6):
    for r2 in (10e6, 1e6):
        case(f"unplug_fix_4.9V_0.8A_C{int(c*1e6)}u_R2{r2/1e6:g}M", ev="unplug", packs=(4.9,), rail=0.8, csys=c, r2=r2,
             **FIX)
for v in (4.4, 4.7, 5.0):
    case(f"switchon_fix_{v}V_0.35A", ev="switch_on", packs=(v,), **FIX)
    case(f"switchon_rc_{v}V_0.35A", ev="switch_on", packs=(v,), rgu=10e3, n4d=(2.2e6, 10e-9), rf=47e3, cf=22e-6,
         t_after=3.0)
for v in (4.3, 4.6):
    case(f"battery_fix_{v}V_0.35A", ev="battery", packs=(v,), t_after=3.0, **FIX)
for T in (-20, 60):
    case(f"unplug_fix_4.4V_0.35A_T{T}", ev="unplug", packs=(4.4,), temp=T, **FIX)

def tvs_check():
    """PL40 VDD peak when a pack input sits at the SMF4L9.0CA clamp (VC 15.4 V at 26.4 A) for w (E21 1b)."""
    path = os.path.join(OUT, "tvs.cir")
    for r, c in ((0, 100e-9), (10e3, 100e-9), (10e3, 1e-6)):
        res = []
        for w in (100e-9, 1e-6, 20e-6, 1e-3):
            t1 = 10e-6
            with open(path, "w") as f:
                f.write(f"""* PL40 VDD vs a TVS clamp plateau
.model DBAT54 D(Is=1.0e-8 N=1.05 Rs=1.5 EG=0.69 XTI=2 Cjo=10p)
Va a 0 PWL(0 6.4 {t1} 6.4 {t1 + 5e-9} 15.4 {t1 + 5e-9 + w} 15.4 {t1 + 1e-8 + w} 6.4)
D1 a k DBAT54
R1 k v {r or 1e-3}
C1 v 0 {c} IC=6.28
I1 v 0 1.6u
.tran {w / 200} {t1 + w + 50e-6} 0 {w / 20} uic
.control
set noaskquit
run
meas tran vmax MAX v(v)
quit
.endc
.end
""")
            o = subprocess.run(["ngspice", "-b", path], capture_output=True, text=True).stdout
            res.append(f"{w * 1e6:g} us: {float(re.search(r'vmax\s*=\s*([-\d.e+]+)', o).group(1)):.2f} V")
        print(f"tvs R {r:g} C {c * 1e9:g} nF:", ", ".join(res))

def _run(tag):
    return tag, run(tag, **CASES[tag])

if __name__ == "__main__":
    from multiprocessing import Pool
    only = sys.argv[1:]
    if "tvs" in only:
        tvs_check()
    tags = [t for t in CASES if not only or any(o in t for o in only)]
    with Pool(min(8, os.cpu_count() or 1)) as pool:     # results print in case order
        for tag, r in pool.imap(_run, tags):
            print(tag, r, flush=True)
