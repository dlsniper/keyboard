#!/usr/bin/env python3
"""Fab outputs for every board (roadmap M2 step 5): Gerbers, drill files, placement file, BOM and fab notes.

    python3 tools/fab.py [board ...]        # default: all; output in build/fab/<board>/ (generated, not committed)

Per board: <board>-gerbers.zip (Gerber X2 + Excellon, plated and non-plated holes apart), <board>-cpl.csv
(placement, JLCPCB column names; none for a board without parts), <board>-bom.csv (from the schematic, grouped;
MPN where the schematic has one, no distributor numbers: sourcing is done at the order), fab-notes.txt.
build/fab/README.md sums them up. The table below is the source of what the board files do not say: copper
weights, thickness, how many per keyboard, what to ask the board house. A board with DRC errors, open
connections or a schematic-parity error is not exported.
"""
import csv
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
OUT = ROOT / "build" / "fab"

OZ = {1.0: "1 oz (35 um)", 0.5: "0.5 oz (17.5 um)"}
RULES = "least track / gap 0.15 mm, least via 0.6 / 0.3 mm, copper to board edge 0.3 mm (tools/pcb_keys.py RULES)"
KEY_ASM = ("All SMD parts are on the BOTTOM side (hot-swap sockets, diodes, reverse-mount LEDs through their board "
           "windows, expander, rail switch). The two pin headers go on the TOP side, by hand.")
# name: layers, inner copper oz (None for 2 layers), boards per keyboard, assembly, extra notes
BOARDS = {
    "left": (2, None, "1", KEY_ASM, []),
    "right": (2, None, "1", KEY_ASM + " J3 (dial connector) is on the bottom.", []),
    "numpad": (2, None, "1", KEY_ASM, []),
    "port-module": (4, 1.0, "3 (one per key module)",
                    "SMD parts and the USB-C receptacle (SMD + through-hole pins) on the TOP side; the 2x6 socket J2 on the BOTTOM side, by hand.",
                    ["Inner copper 1 oz (user, 2026-11-14): +5V runs on inner 2.",
                     "Receptacle Amphenol 12401548E4-2A: 0.4 mm plated holes in 0.65 mm pads (0.125 mm annular ring): ask the board house.",
                     "One via pair with holes 0.49 mm apart: check against the board house's hole-to-hole limit."]),
    "hub-core": (2, None, "1", "Mostly through-hole (Pico sockets, stack connector, spring pins, JST XH), by hand; SMD parts on the TOP side.", []),
    "hub-conn": (4, 1.0, "1",
                 "All SMD parts on the TOP side. On the BOTTOM side only the 2x8 chain target pads (Mill-Max 1578 discs): two-sided assembly or by hand, to settle at the order.",
                 ["Inner copper 1 oz (user, 2026-11-14): pack trunks 1.2 mm and the +5V trunk 3 mm on inner 2; inner 1 is an unbroken GND plane.",
                  "Receptacles Amphenol 12401548E4-2A: 0.4 mm plated holes in 0.65 mm pads (0.125 mm annular ring): ask the board house.",
                  "CSD25483F4 (PicoStar): 0.15 mm lands. TPS552892 (VQFN-HR): 0.25 mm strips at 0.5 mm pitch.",
                  "Via pairs with holes 0.49 mm apart may be left: check against the board house's hole-to-hole limit."]),
    "battery": (2, None, "1 per AA module (up to 5)", "Through-hole holder and riser by hand; fuse SMD on the TOP side.",
                ["Pack lines 1.5 mm, their vias 1.5 / 0.9 mm."]),
    "chain-cap": (2, None, "1 per AA module (up to 5)", "No SMD parts: riser pins and the spring-pin strip, by hand.", []),
    "usb-port": (4, 1.0, "1", "All parts on the TOP side.",
                 ["Inner copper 1 oz (user, 2026-11-14): both VBUS paths run on inner 2.",
                  "KTS1693 (WLCSP-20, 0.4 mm pitch): 0.22 mm lands with 0.18 mm between them; ask for the finer process if the standard one does not hold it.",
                  "USB4085 receptacle: 0.45 mm hole to hole between its pin rows (rule exception in the board file)."]),
    "dial": (2, None, "1", "As drawn (rev 8 board, reused).", []),
    "plate-left": (0, None, "1", "No parts.", []),
    "plate-right": (0, None, "1", "No parts.", []),
    "plate-numpad": (0, None, "1", "No parts.", []),
}
PLATE_NOTE = ["Switch plate: FR4, 1.6 mm (user, 2026-11-14), NO COPPER on either side; order as a plain 2-layer board. "
              "Thickness tolerance matters: MX switches clip into 1.5 +/- 0.1 mm.",
              "Cut-outs: 14.0 mm square with 0.5 mm corner radius (routed, not drilled); all holes non-plated."]


def run(*args):
    r = subprocess.run([CLI, *map(str, args)], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"kicad-cli {' '.join(map(str, args[:3]))} failed:\n{r.stdout}{r.stderr}")
    return r.stdout


def check(name, pcb, work):
    rep = work / "drc.json"
    has_sch = pcb.with_suffix(".kicad_sch").exists()
    subprocess.run([CLI, "pcb", "drc", "--severity-all", "--format", "json", "-o", str(rep)]
                   + (["--schematic-parity"] if has_sch else []) + [str(pcb)], capture_output=True)
    d = json.loads(rep.read_text())
    err = [v for v in d["violations"] if v["severity"] == "error"]
    bad = len(err), len(d.get("unconnected_items", [])), len(d.get("schematic_parity", []))
    rep.unlink()
    return bad, len(d["violations"]) - len(err)


def export(name):
    layers, inner, count, assembly, notes = BOARDS[name]
    pcb = ROOT / "hardware" / name / f"{name}.kicad_pcb"
    out = OUT / name
    shutil.rmtree(out, ignore_errors=True)
    g = out / "gerbers"
    g.mkdir(parents=True)
    (errors, opens, parity), warnings = check(name, pcb, out)
    if errors or opens or parity:
        shutil.rmtree(out)
        return f"{name}: NOT exported: {errors} DRC errors, {opens} unconnected, {parity} parity"
    cu = {0: [], 2: ["F.Cu", "B.Cu"], 4: ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]}[layers]
    plot = cu + (["F.Paste", "B.Paste"] if layers else []) + ["F.SilkS", "B.SilkS", "F.Mask", "B.Mask", "Edge.Cuts"]
    run("pcb", "export", "gerbers", "--output", str(g) + "/", "--layers", ",".join(plot), "--subtract-soldermask", pcb)
    run("pcb", "export", "drill", "--output", str(g) + "/", "--format", "excellon", "--excellon-units", "mm",
        "--excellon-separate-th", "--drill-origin", "absolute", "--generate-map", "--map-format", "gerberx2", pcb)
    job = json.loads(next(g.glob("*.gbrjob")).read_text())
    size = job["GeneralSpecs"]["Size"]
    files = sorted(p for p in g.iterdir() if p.suffix != ".gbrjob")
    if len([p for p in files if p.suffix.lower() in (".gtl", ".gbl", ".g1", ".g2", ".g3")]) != len(cu):
        sys.exit(f"{name}: expected {len(cu)} copper Gerbers, got {[p.name for p in files]}")
    with zipfile.ZipFile(out / f"{name}-gerbers.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.name)
    shutil.rmtree(g)
    # placement, JLCPCB column names
    sides = {}
    if layers:
        pos = out / "pos.csv"
        run("pcb", "export", "pos", "--output", pos, "--format", "csv", "--units", "mm", "--side", "both", "--exclude-dnp", pcb)
        rows = list(csv.DictReader(pos.open()))
        pos.unlink()
        with (out / f"{name}-cpl.csv").open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Designator", "Val", "Package", "Mid X", "Mid Y", "Rotation", "Layer"])
            for r in rows:
                w.writerow([r["Ref"], r["Val"], r["Package"], r["PosX"], r["PosY"], r["Rot"], r["Side"]])
                sides[r["Side"]] = sides.get(r["Side"], 0) + 1
        sch = pcb.with_suffix(".kicad_sch")
        run("sch", "export", "bom", "--output", out / f"{name}-bom.csv", "--fields", "Reference,Value,Footprint,MPN,${QUANTITY}",
            "--labels", "Designator,Comment,Footprint,MPN,Qty", "--group-by", "Value,Footprint,MPN", "--exclude-dnp", sch)
    kinds = sum(1 for _ in (out / f"{name}-bom.csv").open()) - 1 if layers else 0
    text = [f"{name}  (keyboard rev 9.1, generated by tools/fab.py)", "",
            f"Boards per keyboard: {count}",
            f"Size: {size['X']:.1f} x {size['Y']:.1f} mm (bounding box)",
            "Material: FR4, 1.6 mm finished thickness",
            f"Copper layers: {layers}" if layers else "Copper layers: none"]
    if layers:
        text += [f"Outer copper: {OZ[1.0]}"] + ([f"INNER COPPER: {OZ[inner]}  (not the board house's default)"] if inner else [])
        text += [f"Design rules: {RULES}",
                 f"Parts: {sum(sides.values())} placed ({', '.join(f'{n} {s}' for s, n in sorted(sides.items())) or 'none'}), {kinds} BOM lines",
                 f"Assembly: {assembly}",
                 "Placement file: KiCad origin and rotations; check every polarised part in the board house's viewer before paying."]
    text += ["Surface finish, solder mask colour, quantity: chosen at the order (D7)."]
    text += ["", "Notes:"] + [f"- {n}" for n in (PLATE_NOTE if not layers else notes or ["none"])]
    text += ["", f"Checks at export: DRC 0 errors, 0 unconnected" + (", schematic parity 0" if layers else "") + f"; {warnings} warnings."]
    (out / "fab-notes.txt").write_text("\n".join(text) + "\n")
    inner_txt = OZ[inner].split(" (")[0] if inner else "-"
    return (f"| {name} | {count} | {size['X']:.1f} x {size['Y']:.1f} | {layers or 'none'} | {inner_txt if layers else '-'} | "
            f"{sum(sides.values()) or '-'} | {kinds or '-'} | {warnings} |")


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("-")] or list(BOARDS)
    unknown = [n for n in names if n not in BOARDS]
    if unknown:
        sys.exit(f"unknown board: {unknown}")
    OUT.mkdir(parents=True, exist_ok=True)
    rows, failed = [], []
    for n in names:
        row = export(n)
        (rows if row.startswith("|") else failed).append(row)
        print(row)
    if names == list(BOARDS):
        (OUT / "README.md").write_text("\n".join(
            ["# Fab outputs, keyboard rev 9.1", "",
             "Generated by `python3 tools/fab.py`; one folder per board with `<board>-gerbers.zip`, `<board>-cpl.csv`,",
             "`<board>-bom.csv` and `fab-notes.txt`. All boards: FR4, 1.6 mm, outer copper 1 oz.", "",
             "| Board | Per keyboard | Size (mm) | Copper layers | Inner copper | Parts | BOM lines | DRC warnings |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"] + rows +
            ["", "**Not the board house's defaults:** inner copper 1 oz on `hub-conn`, `port-module` and `usb-port`;",
             "the three plates carry no copper and their 1.6 mm thickness is what the switches clip into.",
             "The per-board notes list what to ask the board house before the order (D7)."]
            + ["", "Not exported:"] * bool(failed) + failed) + "\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
