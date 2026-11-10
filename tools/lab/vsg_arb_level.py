"""Does the VSG60A put out the set level with slow ARB waveforms? (VSG60 -> path -> BB60C)

    python tools/lab/vsg_arb_level.py --atten 72.8 [--level -90] [--hz 436.6e6]

Why: the home HackRF runs found SSTV about 10 dB less sensitive than the lab's VSG60 runs, while APRS and
9k6 agreed within 1-2 dB. The lab SSTV waveforms are FM at a 25 kS/s ARB rate (the only rate at which the
VSG60 plays them at the right speed), CW and APRS at 100 kS/s and more. This plays the same set level as
CW, as the Robot 36 SSTV waveform at 25, 50, 100 and 1000 kS/s, and as a plain FM tone at 25 kS/s, and reads
the total power with the BB60C (30 kHz RBW holds the whole FM signal). Each reading is repeated 3 times.
Writes measurements/<date>_vsg-arb-level/results.json.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from bb60 import BB60  # noqa: E402
from lab import Vsg60Gen  # noqa: E402
import sstv_test  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--atten", type=float, required=True, help="dB between the VSG60 and the BB60C")
    ap.add_argument("--level", type=float, default=-90.0, help="set level after --atten, dBm")
    ap.add_argument("--hz", type=float, default=436.6e6)
    ap.add_argument("--dev", type=float, default=3000.0, help="SSTV FM deviation, Hz")
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--vsg-dir", default=r"C:\sathunter_lab")
    ap.add_argument("--name", default="vsg-arb-level")
    a = ap.parse_args()
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)
    host, port = (a.vsg.split(":") + ["5124"])[:2]
    gen = Vsg60Gen(a.atten, host, int(port), a.vsg_dir, None)
    bb = BB60()
    ref = a.level + 10.0
    img = sstv_test.test_image()
    tones = sstv_test.robot36_tones(img)
    cases = [("cw", None, None)]
    for rate in (25e3, 50e3, 100e3, 1000e3):
        cases.append(("sstv_robot36", rate, None))
    cases.append(("fm_tone_1900", 25e3, None))
    rows = []
    try:
        for kind, rate, _ in cases:
            if kind == "cw":
                gen.cw(a.hz, a.level)
            elif kind == "sstv_robot36":
                iq, secs = sstv_test.fm_iq(tones[: max(1, len(tones) // 8)], rate, a.dev)  # ~5 s is enough
                gen.play(a.hz, a.level, "lvl_sstv_%dk.cf32" % (rate / 1e3), list(iq), rate)
            else:
                n = int(rate * 2)
                ph = np.cumsum(2 * np.pi * a.dev * np.sin(2 * np.pi * 1900 * np.arange(n) / rate) / rate)
                gen.play(a.hz, a.level, "lvl_fm1900_%dk.cf32" % (rate / 1e3), list(np.exp(1j * ph)), rate)
            time.sleep(1.0)
            vals = []
            for _ in range(3):
                p, f = bb.peak(a.hz, span=200e3, rbw=30e3, ref_dbm=ref)
                vals.append(p)
                time.sleep(0.3)
            row = {"kind": kind, "arb_rate": rate, "set_dbm": a.level, "read_dbm": round(float(np.mean(vals)), 2),
                   "spread_db": round(float(np.ptp(vals)), 2)}
            row["error_db"] = round(row["read_dbm"] - a.level, 2)
            rows.append(row)
            print("%-14s %8s: set %.1f dBm, read %.2f dBm (%+.2f dB, spread %.2f)" % (
                kind, "%g kS/s" % (rate / 1e3) if rate else "", a.level, row["read_dbm"], row["error_db"], row["spread_db"]))
    finally:
        gen.off()
    json.dump({"hz": a.hz, "atten_db": a.atten, "set_dbm": a.level, "rows": rows,
               "made": time.strftime("%Y-%m-%d %H:%M")}, open(os.path.join(out, "results.json"), "w"), indent=1)
    print("Results:", out)


if __name__ == "__main__":
    main()
