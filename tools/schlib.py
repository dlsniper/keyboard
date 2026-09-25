"""Shared schematic capture for the tools/sch_*.py board scripts.

A board script describes parts as a table and calls run(). Every pin gets a short
stub and a net label (GND gets a power symbol), so connectivity is readable from
the netlist and survives moving parts around in Eeschema. After writing, the
netlist KiCad exports is compared against the board's intended nets.

Symbols stay unrotated: kicad-sch-api 0.5.6 mirrors pin positions of rotated
symbols relative to KiCad, which silently swaps nets, so pin positions are
computed here from the library pins. It also reports hidden no_connect pins as
passive, so tables mark those with "-".

Part tuple: (ref, lib_id, value, footprint, (x, y) in grid units, {pin: net}, {property: value})
  net "GND" -> power symbol, None -> no-connect flag, "-" -> leave alone
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import kicad_sch_api as ksa

ROOT = Path(__file__).resolve().parent.parent
G = 2.54
HIDDEN_PROPS = ("MPN", "Tolerance", "Voltage", "Dielectric", "Power", "DNP_reason", "Shaft")


def _pin_direction(lib_pin):
    """Outward direction on the sheet (y-down) for a library pin.

    A pin's angle points from its connection point toward the body (0 = +x,
    90 = +y in the library's y-up frame), so outward is the opposite vector with
    y flipped for the sheet.
    """
    lx, ly = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[int(lib_pin.rotation) % 360]
    return (-lx, ly)


def _label_rotation(d):
    return {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[d]


def build(name, title, ref_base, parts, flags, notes, paper="A4"):
    ksa.get_symbol_cache().add_library_path(str(ROOT / "hardware" / "lib" / "keyboard.kicad_sym"))
    sch = ksa.create_schematic(name)
    sch.set_paper_size(paper)
    sch.set_title_block(title=title, company="keyboard", rev="A")
    pwr = 0

    def gnd(x, y):
        nonlocal pwr
        pwr += 1
        sch.components.add("power:GND", reference=f"#PWR0{ref_base + pwr}", value="GND", position=(x, y))

    for ref, lib_id, value, fp, (gx, gy), pins, props in parts:
        # stable UUID per board and reference, so a --force rerun keeps the PCB footprints linked
        comp = sch.components.add(lib_id, reference=ref, value=value, position=(gx * G, gy * G), footprint=fp,
                                  component_uuid=str(uuid.uuid5(uuid.NAMESPACE_URL, f"keyboard/{name}/{ref}")))
        for k, v in props.items():
            comp.set_property(k, v)
        centre = comp.position
        lib_pins = ksa.get_symbol_info(lib_id).pins
        missing = {p.number for p in lib_pins} ^ set(pins)
        if missing:
            sys.exit(f"{ref}: pin table and symbol {lib_id} differ on {sorted(missing)}")
        done = set()  # stacked pins share one position; stub it once
        for lib_pin in lib_pins:
            # library pins are y-up, the sheet is y-down
            pos = ksa.core.types.Point(centre.x + lib_pin.position.x, centre.y - lib_pin.position.y)
            net = pins[lib_pin.number]
            key = (round(pos.x, 3), round(pos.y, 3))
            if net == "-" or key in done:
                continue
            done.add(key)
            if net is None:
                sch.no_connects.add(pos)
                continue
            d = _pin_direction(lib_pin)
            end = (pos.x + d[0] * 2 * G, pos.y + d[1] * 2 * G)
            sch.add_wire(start=(pos.x, pos.y), end=end)
            if net == "GND":
                gnd(*end)
            else:
                sch.add_label(net, position=end, rotation=_label_rotation(d))

    for ref, net, (gx, gy) in flags:
        x, y = gx * G, gy * G
        sch.components.add("power:PWR_FLAG", reference=ref, value="PWR_FLAG", position=(x, y))
        sch.add_wire(start=(x, y), end=(x, y + G))
        if net == "GND":
            gnd(x, y + G)
        else:
            sch.add_label(net, position=(x, y + G), rotation=270)

    for (gx, gy), text in notes:
        sch.add_text(text, position=(gx * G, gy * G))
    return sch


def post_process(path, dnp, variants, fields):
    """Edits kicad-sch-api 0.5.6 has no setter for: DNP flags, library in_bom no, design variants, hidden fields, left-justified notes.

    A KiCad 10 variant override sits inside the symbol's instance path
    (eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr.cpp, 10.0 branch) as
    (variant (name ..) (dnp ..) (field (name ..) (value ..))), and is only written
    where it differs from the base symbol, as KiCad itself does.
    """
    text = path.read_text()
    # kicad-sch-api writes (in_bom yes) on every instance; keep the library's "not in BOM" (e.g. Mechanical:MountingHole)
    not_in_bom = set(re.findall(r'\n\t\t\(symbol "([^"]+)"\n(?:\t\t\t[^\n]*\n)*?\t\t\t\(in_bom no\)', text))
    for m in reversed(list(re.finditer(r'\n\t\(symbol\n\t\t\(lib_id "([^"]+)"\)', text))):
        end = text.find("\n\t)", m.end())
        block = text[m.start():end]
        ref = re.search(r'\(property "Reference" "([^"]+)"', block).group(1)
        if m.group(1) in not_in_bom:
            block = block.replace("(in_bom yes)", "(in_bom no)", 1)
        if ref in dnp:
            block = block.replace("(dnp no)", "(dnp yes)", 1)
        overrides = ""
        for name, fit_dnp in variants.items():
            diff = f' (dnp {"yes" if ref in fit_dnp else "no"})' if (ref in fit_dnp) != (ref in dnp) else ""
            diff += "".join(f' (field (name "{k}") (value "{v}"))' for k, v in fields.get(name, {}).get(ref, {}).items())
            if diff:
                overrides += f'\n\t\t\t\t\t(variant (name "{name}"){diff})'

        if overrides:
            block, n = re.subn(r'(\(reference "%s"\)\s*\(unit \d+\))' % re.escape(ref), lambda u: u.group(1) + overrides, block)
            if n != 1:
                sys.exit(f"{ref}: instance path not found for variant overrides")
        for prop in HIDDEN_PROPS:
            block = re.sub(r'(\(property "%s" "[^"]*"\s*\(at [^)]*\)\s*\(effects)' % prop, r"\1 (hide yes)", block)
        text = text[:m.start()] + block + text[end:]
    text = re.sub(r'(\(text "[^"]*"\s*\(exclude_from_sim no\)\s*\(at [^)]*\)\s*\(effects\s*\(font\s*\(size [^)]*\)\s*\))',
                  r"\1 (justify left top)", text)
    path.write_text(text)


def check_netlist(sch_path, nets):
    """Export the netlist with kicad-cli and compare every named net against nets."""
    cli = _cli()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "board.net"
        subprocess.run([cli, "sch", "export", "netlist", "-o", str(out), str(sch_path)], check=True, capture_output=True)
        text = out.read_text()
    got = {}
    for m in re.finditer(r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', text, re.S):
        nodes = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2))
        got[m.group(1).lstrip("/")] = sorted(f"{r}.{p}" for r, p in nodes)
    bad = [f"{name}: got {got.get(name)}, want {sorted(want)}" for name, want in nets.items()
           if got.get(name) != sorted(want)]
    stray = [name for name in got if name not in nets and not name.startswith("unconnected-")]
    if bad or stray:
        sys.exit("netlist check failed:\n  " + "\n  ".join(bad + [f"unexpected net {n}" for n in stray]))
    print(f"netlist matches: {len(nets)} nets")


def register_variants(pro_path, variants):
    """List the variants in the project file, so ones with no overrides survive a reload in Eeschema."""
    pro = json.loads(pro_path.read_text())
    pro.setdefault("schematic", {})["variants"] = [{"name": n} for n in variants]
    pro_path.write_text(json.dumps(pro, indent=2) + "\n")


def check_variant_boms(sch_path, parts, variants, fields):
    """Export each variant's BOM with DNP excluded and compare the fitted references, values and MPNs."""
    cli = _cli()
    # symbols the library marks "not in BOM" (e.g. solder jumpers) never appear in an exported BOM
    text = sch_path.read_text()
    not_in_bom = {re.search(r'\(property "Reference" "([^"]+)"', b).group(1)
                  for b in re.split(r'\n\t\(symbol\n', text)[1:] if "(in_bom no)" in b.split("(property", 1)[0]}
    base = {p[0]: (p[2], p[6].get("MPN", "")) for p in parts if p[0] not in not_in_bom}
    for name, fit_dnp in variants.items():
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bom.csv"
            subprocess.run([cli, "sch", "export", "bom", "--variant", name, "--exclude-dnp", "--fields", "Reference,Value,MPN",
                            "--group-by", "", "--string-delimiter", "", "--field-delimiter", "\t", "-o", str(out), str(sch_path)],
                           check=True, capture_output=True)
            got = {}
            for line in out.read_text().splitlines()[1:]:
                ref, value, mpn = (line.split("\t") + ["", ""])[:3]
                got[ref.strip()] = (value.strip(), mpn.strip())
        want = {}
        for ref, (value, mpn) in base.items():
            if ref in fit_dnp:
                continue
            o = fields.get(name, {}).get(ref, {})
            want[ref] = (o.get("Value", value), o.get("MPN", mpn))
        if got != want:
            diff = sorted(set(got.items()) ^ set(want.items()))
            sys.exit(f"variant {name} BOM differs (got/want symmetric difference): {diff}")
        print(f"variant {name}: {len(got)} fitted, DNP {sorted(fit_dnp)}")


def _cli():
    return shutil.which("kicad-cli") or "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"


def run(sch_path, name, title, ref_base, parts, flags, notes, nets, dnp=(), variants=None, fields=None, paper="A4"):
    """variants: {name: refs not fitted in that variant}; dnp is the base (default-variant) population.
    fields: {variant: {ref: {field: value}}} overrides, e.g. Value and MPN."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="overwrite a schematic that already has symbols")
    args = ap.parse_args()
    if sch_path.exists() and "(lib_id " in sch_path.read_text() and not args.force:
        sys.exit(f"{sch_path} already has symbols; edit it in KiCad or rerun with --force")
    variants = {n: set(v) for n, v in (variants or {}).items()}
    build(name, title, ref_base, parts, flags, notes, paper).save(str(sch_path))
    fields = fields or {}
    post_process(sch_path, set(dnp), variants, fields)
    check_netlist(sch_path, nets)
    if variants:
        register_variants(sch_path.with_suffix(".kicad_pro"), variants)
        check_variant_boms(sch_path, parts, variants, fields)
    print("wrote", sch_path)
