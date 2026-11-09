"""Spurs around a HackRF CW tone, read by the BB60C (on the PC with both).

    python tools/lab/hackrf_spurs.py --atten 72.8 [--hz 436.6e6] [--span 200e3]

Question it answers: the home panorama sweep (2026-11-07) showed sidebands at +-36.6 kHz around every
tone at about -40 dBc. Are they in the HackRF's output, or made in the receiver? For TX VGA 0/20/40 and
digital scales 1, 0.3 and 0.1 it plays the tone (250 kHz above the LO, as hackrf_gen does), takes a
BB60C trace and lists every peak 15 dB over the floor with its offset from the tone and level in dBc.
Writes measurements/<date>_hackrf-spurs/results.json.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from bb60 import BB60  # noqa: E402
from hackrf_gen import HackRfGen  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--atten", type=float, required=True)
    ap.add_argument("--hz", type=float, default=436.6e6)
    ap.add_argument("--span", type=float, default=200e3)
    ap.add_argument("--rbw", type=float, default=100.0)
    ap.add_argument("--name", default="hackrf-spurs")
    a = ap.parse_args()
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)
    gen = HackRfGen(0.0, cal="-")
    bb = BB60()
    res = []
    try:
        for tx in (0, 20, 40):
            for scale in (1.0, 0.3, 0.1):
                gen.settings = lambda hz, dbm, tx=tx: (tx, False, 0.0)
                gen.cw(a.hz, 0.0)
                gen._cmd(cmd="cw", offset=round(a.hz - gen.lo), scale=scale)
                time.sleep(2.0)  # the server has about a second of samples queued
                tone, fpk = bb.peak(a.hz, span=20e3, rbw=a.rbw, ref_dbm=tone_ref(tx, a.atten))
                f, p = bb.trace(a.hz, a.span, a.rbw, ref_dbm=tone + 5, sweeps=5)
                f, p = np.asarray(f), np.asarray(p)
                floor = float(np.median(p))
                spurs = []
                for i in range(2, len(p) - 2):
                    if p[i] > floor + 15 and p[i] == p[i - 2:i + 3].max() and abs(f[i] - fpk) > 3 * a.rbw:
                        spurs.append({"offset_hz": round(float(f[i] - fpk)), "dbc": round(float(p[i] - tone), 1)})
                row = {"txvga": tx, "scale": scale, "tone_dbm": round(float(tone), 1), "floor_dbm": round(floor, 1),
                       "spurs": spurs}
                res.append(row)
                print("txvga %2d scale %.1f: tone %.1f dBm, floor %.1f dBm; %s" % (
                    tx, scale, tone, floor, ", ".join("%+.1f kHz %.1f dBc" % (s["offset_hz"] / 1e3, s["dbc"]) for s in spurs) or "no spurs"))
    finally:
        gen.off()
    json.dump({"hz": a.hz, "atten_db": a.atten, "rbw_hz": a.rbw, "span_hz": a.span, "lo_offset_hz": gen.OFFSET,
               "rows": res, "made": time.strftime("%Y-%m-%d %H:%M")}, open(os.path.join(out, "results.json"), "w"), indent=1)
    print("Results:", out)


def tone_ref(tx, atten):
    return -45.0 + tx - atten + 10.0


if __name__ == "__main__":
    main()
