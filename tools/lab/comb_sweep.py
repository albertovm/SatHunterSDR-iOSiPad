#!/usr/bin/env python3
"""Fast, fine transfer sweep with a frequency comb: the VSG60 plays up to ~180 tones at once (Newman
phases, low crest factor), the BB60C reads them all in one span; a few overlapping segments cover the
band. Gain per tone = output - input, the input from the comb's own peak-to-tone ratio and the path loss
measured without the DUT (path_cal.py), the output corrected by --out-loss.

    python tools/lab/comb_sweep.py --start 380 --stop 490 --spacing 0.2 --pin -70 --name lna-comb
"""

import argparse, glob, json, os, sys, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import Vsg60Gen, wait_idle  # noqa: E402
from bb60 import BB60  # noqa: E402


def comb(rate, spacing, half_span):
    """Tones at (k + 1/2) x spacing: none at the carrier (the VSG's LO leakage stays off the tones) and
    each tone's I/Q image lands on another tone."""
    m = int(half_span // spacing)
    offs = (np.arange(-m, m) + 0.5) * spacing
    n = int(round(2 * rate / spacing)) * 2
    t = np.arange(n) / rate
    ph = np.pi * (np.arange(len(offs)) ** 2) / len(offs)  # Newman phases: crest factor ~2.5 dB
    x = np.zeros(n, complex)
    for o, p in zip(offs, ph):
        x += np.exp(1j * (2 * np.pi * o * t + p))
    peak = np.abs(x).max()
    return x / peak, offs, 20 * np.log10(1 / peak)  # samples, tone offsets, tone level vs set (peak) level, dB


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--vsg-dir", default=r"C:\\sathunter_lab")
    ap.add_argument("--cal", help="path_cal results.json (default: newest)")
    ap.add_argument("--out-loss", type=float, default=30.5)
    ap.add_argument("--start", type=float, default=380.0, help="MHz")
    ap.add_argument("--stop", type=float, default=490.0, help="MHz")
    ap.add_argument("--spacing", type=float, default=0.2, help="tone spacing, MHz")
    ap.add_argument("--pin", type=float, default=-70.0, help="level per tone at the DUT input, dBm")
    ap.add_argument("--pin-oob", type=float, help="level per tone for segments clear of --pband (more range for the rejection)")
    ap.add_argument("--pband", default="420:450", help="MHz; segments overlapping it use --pin")
    ap.add_argument("--rate", type=float, default=40e6, help="ARB rate (segment width ~0.9 x rate)")
    ap.add_argument("--rbw", type=float, default=3e3)
    ap.add_argument("--name", default="comb")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    cal_path = a.cal or sorted(glob.glob(os.path.join(root, "measurements", "*path-cal*", "results.json")))[-1]
    cal = json.load(open(cal_path))
    cf = np.array([p["freq_hz"] for p in cal["points"]]); cl = np.array([p["loss_db"] for p in cal["points"]])
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)

    half = 0.45 * a.rate / 2
    x, offs, tone_db = comb(a.rate, a.spacing * 1e6, half)
    sp = a.spacing * 1e6
    step = round(2 * half * 0.95 / sp) * sp
    centres = np.arange(round((a.start * 1e6 + half) / sp) * sp, a.stop * 1e6 + half, step)
    pb0, pb1 = (float(v) * 1e6 for v in a.pband.split(":"))
    host, port = (a.vsg.split(":") + ["5124"])[:2]
    gen = Vsg60Gen(0.0, host, int(port), a.vsg_dir, None)
    bb = BB60()
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "cal": os.path.relpath(cal_path, root), "out_loss_db": a.out_loss,
           "pin_per_tone_dbm": a.pin, "tones_per_segment": len(offs), "tone_vs_set_db": tone_db, "note": a.note, "points": []}
    try:
        wait_idle()
        for i, c in enumerate(centres):
            in_loss = float(np.interp(c, cf, cl)) - a.out_loss
            pin_seg = a.pin if (a.pin_oob is None or (c + half > pb0 and c - half < pb1)) else a.pin_oob
            set_lvl = pin_seg - tone_db + in_loss
            if set_lvl > 8.0:
                print(f"segment at {c / 1e6:.1f} MHz: VSG level {set_lvl:.1f} dBm too high, skipped")
                continue
            gen.play(c, set_lvl, "sathunter_comb.cf32", list(x), a.rate)
            time.sleep(0.3)
            f, v = bb.trace(c, 2 * half + 1e6, a.rbw, ref_dbm=min(10.0, pin_seg + 52 - a.out_loss + 10))
            for o in offs:
                ft = c + o
                if not (a.start * 1e6 <= ft <= a.stop * 1e6):
                    continue
                m = (f > ft - 3 * a.rbw) & (f < ft + 3 * a.rbw)
                lvl = float(v[m].max())
                floor = float(np.median(v[(f > ft + 0.3 * a.spacing * 1e6) & (f < ft + 0.7 * a.spacing * 1e6)]))
                pin = pin_seg + (in_loss - (float(np.interp(ft, cf, cl)) - a.out_loss))  # the input pad / coax loss at this tone
                res["points"].append({"freq_hz": ft, "pin_dbm": pin, "pout_dbm": lvl + a.out_loss, "gain_db": lvl + a.out_loss - pin,
                                      "floor_margin_db": lvl - floor, "segment": i, "seg_centre_hz": c})
            print(f"segment {i + 1}/{len(centres)} at {c / 1e6:.1f} MHz done", flush=True)
        gen.off()
    finally:
        gen.close()
        bb.close()
        res["points"].sort(key=lambda p: p["freq_hz"])
        res["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
    print(f"Results: {out}")


if __name__ == "__main__":
    main()
