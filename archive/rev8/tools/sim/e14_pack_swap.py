#!/usr/bin/env python3
"""E14 / pack OVP hot-swap simulation (battery board 8xx + core LM66200 input), 2026-09-15.

Run: python3 tools/sim/e14_pack_swap.py [case-substring ...]   (ngspice-47; decks go to build/sim/)
Results are recorded in plans/keyboard.md §4 "Hot swap".

Netlist mirrors tools/sch_battery.py. Models are built from datasheet numbers:
  AO3415A  (AOS rev 3.1): VGS(th) -0.3/-0.57/-0.9 V @ 250 uA, RDS(on) 52/65 mOhm @ -1.8 V,
           Ciss 751 pF, Crss 80 pF, Rg 13 Ohm, VSD 0.64 V @ 1 A.  Subthreshold slope n
           and Vth tempco are NOT published: n = 1.5, -2.5 mV/K assumed (flagged).
  BAT54    (Diodes DS11005 Fig. 1): VF ~0.25 V @ 100 uA 25 C, ~0.35 V @ -40 C.
  TPS3840PL35 (SNVSB03E): VIT- 3.5 V, VHYS 175-225 mV, tD 50 us max (CT open),
           tP_HL 30 us max, VOH >= 0.8 VDD @ 5 mA, IDD 300/700 nA.
  LM66200  (SLVSG04): CIN 1 uF (p. 12), RON 41-61 mOhm, reverse leak out of VINx nA (Fig. 6-8).
"""
import subprocess, sys, os, re, itertools

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "build", "sim")
os.makedirs(HERE, exist_ok=True)

def fet(name, d, g, s, vth, n=1.5):
    # p-channel EKV-style smooth model, source-referenced (body = source)
    # vth = |VGS(th)| at 250 uA.  Fit Is and true threshold so that
    # I(vsg = vth) = 250 uA and RDS(on) = 52 mOhm at vsg = 1.8 V (typ datasheet).
    import math
    vt = 0.02585
    k2 = 2 * n * vt
    # solve Vtt, Is
    f = lambda x: math.log1p(math.exp(x)) ** 2
    sig = lambda x: 1 / (1 + math.exp(-x))
    def is_for(vtt):
        x = (1.8 - vtt) / k2
        g_per_is = 2 * math.log1p(math.exp(x)) * sig(x) * n / k2   # dI/dVsd at Vsd=0
        return (1 / 0.052) / g_per_is
    lo, hi = vth, 1.5
    for _ in range(100):   # I(vsg=vth, saturated) = 250 uA
        vtt = (lo + hi) / 2
        Is = is_for(vtt)
        if Is * f((vth - vtt) / k2) > 250e-6:
            lo = vtt
        else:
            hi = vtt
    return f"""
* {name}: PMOS d={d} g={g} s={s}  |Vth250|={vth} Vtrue={vtt:.3f} Is={Is:.4g}
R{name}g {g} {name}gi 13
C{name}gs {name}gi {s} 670p
C{name}gd {name}gi {d} 80p
B{name} {s} {d} I = {Is:.6g}*( pow(ln(1+exp((V({s},{name}gi)-{vtt:.4f}*(1-0.0025/{vtt:.4f}*(temper-25)))/{k2:.5f})),2)
+ - pow(ln(1+exp((V({s},{name}gi)-{vtt:.4f}*(1-0.0025/{vtt:.4f}*(temper-25))-{n}*V({s},{d}))/{k2:.5f})),2) )
D{name}b {d} {s} DBODY
"""

def deck(vth, cin, removal, temp, idd=700e-9, insert_v=8.4, cold=False, tvs_leak=0.0):
    # tvs_leak: conductance from CELL+ to GND; 1/330e3 models the R806 bleeder
    t_rm = 0.4
    t_in = t_rm + removal
    t_end = t_in + 0.25
    lines = [f"* E14 vth={vth} cin={cin} removal={removal} temp={temp} cold={cold}",
             ".options temp={} reltol=1e-4 abstol=1e-12 vntol=1e-7 method=gear".format(temp),
             ".model DBODY D(Is=1.7e-10 N=1.1 Rs=0.01)",
             # BAT54: 0.25 V @ 100 uA at 25 C; Schottky EG/XTI give ~0.35 V at -40 C
             ".model DBAT54 D(Is=1.0e-8 N=1.05 Rs=1.5 EG=0.69 XTI=2 Cjo=10p)",
             ".model DZ62 D(Is=1e-14 N=1 BV=6.2 IBV=1m Rs=5)",
             ".model SW SW(Vt=0.5 Vh=0.01 Ron=1m Roff=1e12)",
             ".model SWI SW(Vt=0.05 Vh=0.02 Ron=0.051 Roff=1e9)",
             # AA pack 2.8 V (fresh NiMH), 14500 pair 8.4 V
             "Vaa aa 0 2.8", "Raa aa aa1 0.05",
             f"Vli li 0 {insert_v}", "Rli li li1 0.2",
             ]
    if cold:
        lines += ["Vcaa caa 0 0", f"Vcli cli 0 PWL(0 0 1m 0 1.001m 1)"]
        t_in = 1e-3; t_end = 0.25
    else:
        lines += [f"Vcaa caa 0 PWL(0 1 {t_rm} 1 {t_rm+1e-6} 0)",
                  f"Vcli cli 0 PWL(0 0 {t_in} 0 {t_in+1e-6} 1)"]
    lines += [
        "Saa aa1 cellp caa 0 SW", "Sli li1 cellp cli 0 SW",
        "Ccellp cellp 0 300p",
        f"Rtvs cellp 0 {1/tvs_leak if tvs_leak else 1e12}",
        fet("Q801", "cellp", "rbg", "cellrb", vth),
        "R801 rbg 0 100k",
        "D802 rbg cellrb DZ62",
        fet("Q802", "cellovp", "ovpg", "cellrb", vth),
        "R802 cellrb ovpg 10Meg",
        "C801 cellrb ovpg 68n",
        "D803 ovpg cellrb DZ62",
        "R803 ovpg ovprst 470k",
        "D804 ovprst ovpg DBAT54",
        "R804 cellrb supvdd 1k",
        "C802 supvdd 0 100n",
        f"Iidd supvdd 0 {idd}",
        # TPS3840PL35 behavioural: state node with hysteresis, ~tD delay
        "Bcmp stin 0 V = V(supvdd) > (V(st) > 0.5 ? 3.5 : 3.7) ? 1 : 0",
        "Rst stin st 1k", "Cst st 0 36n",   # 0 -> 0.5 crossing ~25 us, done ~50 us
        "Bout ovprst_i 0 V = V(st) > 0.5 ? V(supvdd) : 0",
        "Rout ovprst_i ovprst 300",
        # PTC R max 45 mOhm, J_BAT cable
        "Rptc cellovp packp 0.06",
        "Bvgs vgs 0 V = V(cellrb)-V(ovpg)",
        f"Cin packp 0 {cin}",
        "Iuvlo packp 0 150n",
        # LM66200 channel into VBAT (ideal diode), reverse leak ~nA
        "S1 packp vbat packp vbat SWI",
        "Rrev vbat packp 100Meg",
        # other pack holding VBAT at 2.6 V through channel 2
        "Vob ob 0 2.6", "S2 ob vbat ob vbat SWI",
        "Cvbat vbat 0 22u",
        "Rload vbat 0 56k",
        f".ic V(cellrb)=0 V(ovpg)=0 V(packp)=0 V(vbat)=2.55 V(supvdd)=0 V(st)=0",
        f".tran 5u {t_end} 0 20u uic",
        ".control",
        "set noaskquit",
        "run",
        f"meas tran vpack_max MAX V(packp) FROM={t_in} TO={t_end}",
        f"meas tran vbat_max MAX V(vbat) FROM={t_in} TO={t_end}",
        f"meas tran vpack_pre FIND V(packp) AT={t_in}",
        f"meas tran vgs_pre FIND V(vgs) AT={t_in}",
        f"meas tran vpack_end FIND V(packp) AT={t_end}",
        f"meas tran vbat_end FIND V(vbat) AT={t_end}",
        f"meas tran vgs_min_after MIN V(vgs) FROM={t_in+2e-3} TO={t_end}",
        f"meas tran t6 WHEN V(vbat)=6.0 RISE=1 FROM={t_in}",
        f"meas tran t6f WHEN V(vbat)=6.0 FALL=1 FROM={t_in}",
        f"meas tran tp6 WHEN V(packp)=6.0 RISE=1 FROM={t_in}",
        "echo done",
        ".endc",
        ".end",
    ]
    return "\n".join(lines)

def run(tag, **kw):
    path = os.path.join(HERE, f"{tag}.cir")
    with open(path, "w") as f:
        f.write(deck(**kw))
    out = subprocess.run(["ngspice", "-b", path], capture_output=True, text=True, timeout=600).stdout
    res = {}
    for m in re.finditer(r"^(\w+)\s+=\s+([-+0-9.eE]+)", out, re.M):
        res[m.group(1)] = float(m.group(2))
    if "done" not in out:
        print(out[-3000:])
    return res

if __name__ == "__main__":
    rows = []
    cases = []
    for vth in (0.3, 0.57):
        cases.append((f"cold_v{vth}", dict(vth=vth, cin=1e-6, removal=0, temp=25, cold=True)))
    for vth, rem in itertools.product((0.3, 0.57), (0.01, 0.1, 1.0, 3.0, 10.0)):
        cases.append((f"swap_v{vth}_r{rem}", dict(vth=vth, cin=1e-6, removal=rem, temp=25)))
    for temp in (-40, 85):
        cases.append((f"swap_v0.3_r0.01_T{temp}", dict(vth=0.3, cin=1e-6, removal=0.01, temp=temp)))
    # R806 330k bleeder: 8.4 V pair and one-cell 5.6 V swap after 1 s
    for v in (8.4, 5.6):
        cases.append((f"bleed330k_{v}V_r1.0", dict(vth=0.57, cin=1e-6, removal=1.0, temp=25, idd=300e-9,
                                                   insert_v=v, tvs_leak=1 / 330e3)))
    only = sys.argv[1:]
    for tag, kw in cases:
        if only and not any(o in tag for o in only):
            continue
        r = run(tag, **kw)
        print(tag, {k: (round(v, 4) if abs(v) > 1e-3 else v) for k, v in r.items()}, flush=True)
