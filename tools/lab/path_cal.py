#!/usr/bin/env python3
"""Loss of a cable / attenuator path vs frequency: VSG60 CW in, BB60C measures what comes out.

    python tools/lab/path_cal.py --level -10 --name path-cal --note "VSG - 20 dB - coax - bias tee - 30 dB - BB60C"

The result (loss_db per frequency) is used by lna_char.py to refer levels to the LNA. With nothing in the
path apart from short cables it is also a check of the VSG60's absolute level against the BB60C.
"""

import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import Vsg60Gen, wait_idle  # noqa: E402
from bb60 import BB60  # noqa: E402

DEFAULT_FREQS = ([50e6, 100e6, 145e6, 200e6, 300e6, 350e6, 380e6] + [f * 1e6 for f in range(390, 491, 10)]
                 + [500e6, 550e6, 600e6, 700e6, 800e6, 900e6, 1000e6])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--vsg-dir", default=r"C:\sathunter_lab")
    ap.add_argument("--level", type=float, default=-10.0, help="VSG60 output level, dBm")
    ap.add_argument("--ref", type=float, help="BB60C reference level, dBm (default: level - 20); lower for a high-loss path")
    ap.add_argument("--freqs", help="comma separated MHz (default 50-1000 MHz, 10 MHz steps around 434)")
    ap.add_argument("--name", default="path-cal")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    freqs = [float(x) * 1e6 for x in a.freqs.split(",")] if a.freqs else DEFAULT_FREQS
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)

    host, port = (a.vsg.split(":") + ["5124"])[:2]
    gen = Vsg60Gen(0.0, host, int(port), a.vsg_dir, None)
    bb = BB60()
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "vsg_level_dbm": a.level, "note": a.note,
           "bb60": {"serial": bb.serial, "api": bb.version}, "points": []}
    try:
        wait_idle()
        gen.off()
        for f in freqs:
            gen.cw(f, a.level)
            time.sleep(0.2)
            ref = a.ref if a.ref is not None else a.level - 20
            p, fp = bb.peak(f, span=20e3, rbw=300, ref_dbm=ref)
            nz = bb.noise(f + 5e6, span=20e3, rbw=300, ref_dbm=ref)
            row = {"freq_hz": f, "bb_dbm": p, "bb_peak_hz": fp, "loss_db": a.level - p, "noise_dbm_300hz": nz, "margin_db": p - nz}
            res["points"].append(row)
            print(f"{f / 1e6:7.1f} MHz: {p:7.2f} dBm at the BB60C, path loss {a.level - p:6.2f} dB (peak {fp - f:+.0f} Hz)", flush=True)
        gen.off()
    finally:
        gen.close()
        bb.close()
        res["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
    print(f"Results: {out}")


if __name__ == "__main__":
    main()
