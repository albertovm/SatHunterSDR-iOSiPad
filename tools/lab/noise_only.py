#!/usr/bin/env python3
"""Output noise density at a few frequencies (BB60C, power-averaged), with the VSG60 output off: for a noise
figure with the DUT input terminated (gain and output loss from other runs), or to look at what the VSG60
puts out with its RF off.

    python tools/lab/noise_only.py --freqs 430,433,436,439,441 --floor-freqs 400,410,460,470 --name lna-noise-term
"""

import argparse, json, os, sys, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import Vsg60Gen  # noqa: E402
from bb60 import BB60  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vsg", default="127.0.0.1:5124", help="VSG60 SCPI (to make sure its RF is off); 'none' to skip")
    ap.add_argument("--freqs", default="430,433,436,439,441")
    ap.add_argument("--floor-freqs", default="400,410,460,470")
    ap.add_argument("--ref", type=float, default=-60.0)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--name", default="noise")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)
    if a.vsg != "none":
        host, port = (a.vsg.split(":") + ["5124"])[:2]
        gen = Vsg60Gen(0.0, host, int(port), r"C:\sathunter_lab", None)
        gen.off()
        gen.close()
    bb = BB60()
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "note": a.note, "ref_dbm": a.ref, "rows": [], "floor": []}
    try:
        for key, fl in (("rows", a.freqs), ("floor", a.floor_freqs)):
            for f in (float(x) * 1e6 for x in fl.split(",")):
                v = [bb.noise_density(f, span=1e6, rbw=10e3, ref_dbm=a.ref) for _ in range(a.repeats)]
                res[key].append({"freq_hz": f, "density_dbm_hz": float(10 * np.log10(np.mean(10 ** (np.array(v) / 10)))), "repeats": v})
                print(f"{key} {f / 1e6:.0f} MHz: {res[key][-1]['density_dbm_hz']:.2f} dBm/Hz (spread {max(v) - min(v):.2f} dB)", flush=True)
    finally:
        bb.close()
        res["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
    print(f"Results: {out}")


if __name__ == "__main__":
    main()
