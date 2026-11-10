"""Compare a source's set level with what an analyzer reads (VSG60A -> DC block -> SA44 or BB60C).

    python tools/lab/ref_compare.py --analyzer sa44 --levels 0,-30,-60 --freqs 50,145.8,300,325,350,375,436.6,1000,2400,4000

Writes measurements/<date>_ref-compare-<analyzer>/results.json and prints set - read per point.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from lab import Vsg60Gen  # noqa: E402


def freq_list(spec):
    out = set()
    for item in spec.split(","):
        if ":" in item:
            a, b, st = (float(x) for x in item.split(":"))
            n = int(round((b - a) / st))
            out.update(round(a + i * st, 3) for i in range(n + 1))
        else:
            out.add(float(item))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analyzer", choices=["sa44", "bb60"], default="sa44")
    ap.add_argument("--levels", default="0,-30,-60")
    ap.add_argument("--freqs", default="50,145.8,300,325,350,375,436.6,1000,2400,4000",
                    help="MHz list; items may be ranges start:stop:step (e.g. 50:4400:10,300:400:2)")
    ap.add_argument("--name", default=None)
    ap.add_argument("--modes", default="arb", help="VSG60A modes to compare: arb (CW as an ARB waveform, as the lab "
                    "scripts play it), cw (modulation off, the plain carrier); e.g. arb,cw")
    ap.add_argument("--ref", type=float, default=None, help="analyzer reference level, dBm (default: level + 5)")
    ap.add_argument("--path-db", type=float, default=0.0, help="known loss between them (DC block, adapters)")
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--note", default="VSG60A - SMA adapter - 100 pF DC block - SMA adapter - analyzer")
    a = ap.parse_args()
    if a.analyzer == "sa44":
        from sa44 import SA44
        an = SA44()
    else:
        from bb60 import BB60
        an = BB60()
    host, port = (a.vsg.split(":") + ["5124"])[:2]
    gen = Vsg60Gen(a.path_db, host, int(port), r"C:\sathunter_lab", None)
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + (a.name or "ref-compare-" + a.analyzer))
    os.makedirs(out, exist_ok=True)
    info = {}
    for q in ("*IDN?", ":SYSTem:TEMPerature?", ":SOURce:POWer:OFFSet?", ":OUTPut:CORRection:IMBalance?"):
        try:
            info[q] = gen.query(q)
        except Exception as e:  # noqa: BLE001
            info[q] = "error %s" % e
    try:
        gen.query(":SYSTem:ERRor?")
    except Exception:  # noqa: BLE001
        pass
    print("   VSG60A:", info, flush=True)
    rows = []
    try:
        for lvl in [float(x) for x in a.levels.split(",")]:
            for mode in a.modes.split(","):
                if mode == "cw":
                    gen.write(":OUTPut:MODulation:STATe OFF")
                    gen.loaded = None
                for mhz in freq_list(a.freqs):
                    hz = mhz * 1e6
                    if mode == "cw":
                        gen.write(f":SOURce:FREQuency {hz:.0f}")
                        gen.write(f":SOURce:POWer {lvl + a.path_db:.2f}")
                        gen.write(":OUTPut:STATe ON")
                        gen.opc()
                    else:
                        gen.cw(hz, lvl)
                    time.sleep(0.5)
                    p, f = an.peak(hz, span=20e3, rbw=100, ref_dbm=a.ref if a.ref is not None else lvl + 5)
                    rows.append({"mode": mode, "mhz": mhz, "set_dbm": lvl, "read_dbm": round(p, 2), "diff_db": round(lvl - p, 2),
                                 "peak_offset_hz": round(f - hz)})
                    json.dump({"rows": rows, "partial": True}, open(os.path.join(out, "results.json"), "w"))
                    print(mode, "%7.1f MHz %6.1f dBm: read %7.2f dBm, set - read %+.2f dB" % (mhz, lvl, p, lvl - p), flush=True)
    finally:
        gen.off()
    json.dump({"analyzer": a.analyzer, "serial": getattr(an, "serial", None), "note": a.note, "vsg": info, "rows": rows,
               "made": time.strftime("%Y-%m-%d %H:%M")}, open(os.path.join(out, "results.json"), "w"), indent=1)
    print("Results:", out)


if __name__ == "__main__":
    main()
