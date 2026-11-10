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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analyzer", choices=["sa44", "bb60"], default="sa44")
    ap.add_argument("--levels", default="0,-30,-60")
    ap.add_argument("--freqs", default="50,145.8,300,325,350,375,436.6,1000,2400,4000")
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
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_ref-compare-" + a.analyzer)
    os.makedirs(out, exist_ok=True)
    rows = []
    try:
        for lvl in [float(x) for x in a.levels.split(",")]:
            for mhz in [float(x) for x in a.freqs.split(",")]:
                hz = mhz * 1e6
                gen.cw(hz, lvl)
                time.sleep(0.5)
                p, f = an.peak(hz, span=20e3, rbw=100, ref_dbm=a.ref if a.ref is not None else lvl + 5)
                rows.append({"mhz": mhz, "set_dbm": lvl, "read_dbm": round(p, 2), "diff_db": round(lvl - p, 2),
                             "peak_offset_hz": round(f - hz)})
                print("%7.1f MHz %6.1f dBm: read %7.2f dBm, set - read %+.2f dB" % (mhz, lvl, p, lvl - p), flush=True)
    finally:
        gen.off()
    json.dump({"analyzer": a.analyzer, "serial": getattr(an, "serial", None), "note": a.note, "rows": rows,
               "made": time.strftime("%Y-%m-%d %H:%M")}, open(os.path.join(out, "results.json"), "w"), indent=1)
    print("Results:", out)


if __name__ == "__main__":
    main()
