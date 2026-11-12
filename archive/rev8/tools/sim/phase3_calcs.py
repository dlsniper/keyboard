#!/usr/bin/env python3
"""Phase 3 calculations, 2026-09-15. Every constant cites the datasheet it came from.

Run: python3 tools/sim/phase3_calcs.py. Results are recorded in plans/keyboard.md §2a, §4, §5.
"""
import itertools, math

print("=== TPS61099DRV feedback divider (SLVSD88M 6.5, 8.2.2.2) ===")
# VREF PWM 0.98/1.00/1.02 V; PFM 1.03 V typ (no min/max); IFB_LKG 10 typ / 50 max nA (into FB)
# nRF52840 VDD recommended max 3.6 V, abs-max 3.9 V (PS v1.9 Table 100/101)
for r1, r2, tol in ((2.32e6, 1.0e6, 0.001), (2.32e6, 1.0e6, 0.01), (1.15e6, 0.499e6, 0.01),
                    (576e3, 249e3, 0.01), (1.00e6, 432e3, 0.01)):
    def vout(vref, r1f, r2f, ilk):
        return vref * (1 + r1f / r2f) + ilk * r1f
    nom = vout(1.00, r1, r2, 10e-9)
    lo = vout(0.98, r1 * (1 - tol), r2 * (1 + tol), 0)
    hi_pwm = vout(1.02, r1 * (1 + tol), r2 * (1 - tol), 50e-9)
    hi_pfm = hi_pwm * 1.03  # PFM offset 1.03/1.00, typical only
    i_div = 1.0 / r2
    print(f"R1 {r1/1e3:.0f}k R2 {r2/1e3:.0f}k {tol*100:.1f}%: nom {nom:.3f} V, PWM {lo:.3f}-{hi_pwm:.3f} V, "
          f"PFM max ~{hi_pfm:.3f} V, leak err max +{50e-9*r1*1e3:.0f} mV, divider {i_div*1e6:.1f} uA")

print("\n=== MAX17222 load check (MAX17220-5 datasheet p. 3-4, 14) ===")
# IPEAK 0.4/0.5/0.575 A; tON max 270/300/330 ns at VOUT 3 V; efficiency 0.85 (ds example)
for L in (2.2e-6, 3.3e-6):
    for vin in (1.85, 2.4):
        ilim = 0.40
        dI = vin * 330e-9 / L            # worst ripple (ds method: dI = VIN*tON(MAX)/L)
        iin = ilim - dI / 2
        iout = 0.85 * vin * iin / 3.3
        print(f"L {L*1e6:.1f} uH VIN {vin} V: ripple {dI*1e3:.0f} mA, IIN {iin*1e3:.0f} mA, IOUT max ~{iout*1e3:.0f} mA")
# VSYS peak load on battery (nRF52840 PS v1.9 5.2.1): TX +8 dBm DCDC 16.4 mA, CPU flash DCDC 3.3 mA
vsys_peak = 16.4 + 3.3 + 1.5 + 2 * 0.71 + 6 * 0.30 + 2 * 0.25 + 1.0
print(f"VSYS peak on battery ~{vsys_peak:.1f} mA (radio 16.4 + CPU 3.3 + SAADC 1.24 + I2C pull-ups + held keys + dial + misc)")

print("\n=== F6 module-ID bands (spec 2a; nRF52840 PS v1.9) ===")
# 100k 1% top from GPIO; ID R 1% to GND; tempco 100 ppm/K assumed over 0-50 C (+-25 K) non-tracking
# GPIO VOH >= VDD-0.4 V at 0.5 mA standard drive -> Rout <= 800 Ohm (6.9.3.1)
# SAADC: same gain/ref for AIN and VDD channel -> gain error cancels; offset +-2 LSB10 (calibrated),
# INL 4.7 LSB12 typ; gain 1/6 range 3.6 V
vdd = 3.3
off_v = 2 * 3.6 / 1024 + 4.7 * 3.6 / 4096
bands = {"left": (10e3, 0.09), "right": (47e3, 0.32), "numpad": (220e3, 0.69)}
for name, (rid, centre) in bands.items():
    ratios = []
    for tr, tb, rout in itertools.product((-1, 1), (-1, 1), (0, 800)):
        rt = 100e3 * (1 + tr * (0.01 + 25 * 100e-6)) + rout
        rb = rid * (1 + tb * (0.01 + 25 * 100e-6))
        v = vdd * rb / (rt + rb)
        for e in (-1, 1):
            ratios.append((v + e * off_v) / (vdd - e * off_v))
    nomr = rid / (100e3 + rid)
    # SAADC acquisition: Thevenin R of node vs Table 41
    rth = 100e3 * rid / (100e3 + rid)
    print(f"{name}: nominal {nomr:.3f}, worst {min(ratios):.3f}-{max(ratios):.3f} vs band "
          f"{centre-0.06:.2f}-{centre+0.06:.2f}; source {rth/1e3:.1f} kOhm -> TACQ >= "
          f"{[t for t, r in ((3,10e3),(5,40e3),(10,100e3),(15,200e3)) if rth <= r][0]} us; "
          f"GPIO load {vdd/(100e3+rid)*1e6:.0f} uA")

print("\n=== E11 I2C series resistors (IS31FL3733 Rev. G; nRF52840 PS v1.9) ===")
# nRF VIL 0.3 VDD, IOL,SD >= 1 mA at 0.4 V; IS31 VIL 0.2 VIO VIH 0.75 VIO; tR <= 300 ns receiving
# driver SDA VOL not published: assume 0.4 V (its SYNC VOL at 8 mA)
vsys_min, vsys_max = 3.23, 3.47   # TPS61099 PWM low / PFM high (divider rows above), LDO TLV75733P +-1% (unverified)
for rp in (2.2e3, 4.7e3):
    for rs in (220, 470, 1000):
        i = (vsys_max - 0.4) / (rp * 0.99 + rs)
        v_ack = 0.4 + i * rs
        vil = 0.3 * vsys_min
        cb = 50e-12
        tr = 0.8473 * rp * 1.01 * cb
        clamp = (vsys_max - 0.6) / (rp * 0.99 + rs)
        print(f"Rp {rp/1e3:.1f}k Rs {rs}: ACK at nRF {v_ack:.2f} V (VIL {vil:.2f}, margin {vil-v_ack:.2f}); "
              f"tr(30-70%) {tr*1e9:.0f} ns @50 pF; SDA/SCL clamp <= {clamp*1e3:.2f} mA")
for rs in (470, 1000, 2200):
    print(f"VIO/SDB series {rs}: clamp <= {(vsys_max-0.6)/rs*1e3:.1f} mA")

print("\n=== left link chain load vs TPS22950L IHCD (SLVSFJ2B Table 7.5, 624 Ohm: 1.2/1.6/1.9 A) ===")
# IS31FL3733 IOUT at REXT 20k: 38/42/46 mA -> scale to 42.2k; ILED = IOUT/12.75; ICC max 3 mA
iout_max = 46e-3 * 20 / 42.2 * 1.01
iled = iout_max / 12.75
keys = {"left": 40, "right": 52, "numpad": 17}
logic = 30e-3   # VSYS via LDO: radio+CPU+pull-ups, from list above, rounded up
mod = {}
for k, n in keys.items():
    rail = n * 3 * iled + 3e-3
    mod[k] = rail + logic + 1e-3   # + KTS1693 180 uA, OVLO 40 uA, TVS leak
    print(f"{k}: rail {rail*1e3:.0f} mA, module {mod[k]*1e3:.0f} mA (no expansion)")
chain = mod["right"] + mod["numpad"]
print(f"left chain (right+numpad) {chain*1e3:.0f} mA; headroom to IHCD min 1.2 A: {1200-chain*1e3:.0f} mA "
      f"= {(1200-chain*1e3)/2:.0f} mA per satellite expansion 3V3")
print(f"right's numpad switch: {mod['numpad']*1e3:.0f} mA")
print(f"whole keyboard on left's host port: {sum(mod.values())*1e3:.0f} mA + expansions")
# peak per scan slot (one SW sink on): 16 dice max
print(f"per-slot LED peak {16*iout_max*1e3:.0f} mA (one SW sink, 16 dice)")

print("\n=== E3 PR1 divider (TPS2116 VREF 0.92/1.00/1.08 V, no hysteresis; ST open-drain low when VIN1 unused) ===")
for rt, rb in ((330e3, 100e3), (301e3, 100e3), (274e3, 100e3)):
    for tol in (0.01,):
        lo = 0.92 * (1 + rt * (1 - tol) / (rb * (1 + tol)))
        hi = 1.08 * (1 + rt * (1 + tol) / (rb * (1 - tol)))
        print(f"{rt/1e3:.0f}k/{rb/1e3:.0f}k: nominal {1+rt/rb:.2f} V, range {lo:.2f}-{hi:.2f} V, {5/(rt+rb)*1e6:.0f} uA at 5 V")
# ST hysteresis: Rh from PR1 to ST; when ST low, bottom = rb || rh
rt, rb = 301e3, 100e3
for rh in (1e6, 2e6):
    rbh = rb * rh / (rb + rh)
    print(f"  301k/100k + {rh/1e6:.0f}M to ST: falls to VIN2 below {1+rt/rb:.2f} V, returns above {1+rt/rbh:.2f} V (nominal)")
