"""Calibrate a HackRF One (as the lab generator, hackrf_gen.py) against the BB60C.

    python tools/lab/hackrf_cal.py --atten 70.3 [--freqs 144.8e6,145.8e6,435e6,436e6,437e6,438e6]

Needs hackrf_server.py running on the PC with the HackRF (the BB60C on the same PC).
Chain: HackRF -> the attenuators and cable used at the measurements (--atten, their total as
measured with the VSG60/BB60C path calibration) -> BB60C. For every frequency, txvga step and amplifier
setting it plays a CW tone at full digital scale and reads the BB60C: output power, frequency error,
and the LO leakage OFFSET below the tone. Then it repeats the 436 MHz point every minute for --warm
minutes (drift). Writes hackrf_cal.json (P0 per frequency, the txvga law, ppm) next to this script
and a report folder in measurements/.
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
    ap.add_argument("--atten", type=float, required=True, help="dB between the HackRF and the BB60C input")
    ap.add_argument("--freqs", default="50e6,100e6,144.8e6,145.8e6,200e6,300e6,400e6,430e6,435e6,436e6,437e6,438e6,440e6,500e6,800e6,1000e6,1300e6,1700e6")
    ap.add_argument("--txvga", default="0,5,10,15,20,25,30,35,40,45,47")
    ap.add_argument("--warm", type=float, default=20, help="minutes of drift readings at 436 MHz")
    ap.add_argument("--name", default="hackrf-cal")
    a = ap.parse_args()
    freqs = [float(x) for x in a.freqs.split(",")]
    tvs = [int(x) for x in a.txvga.split(",")]
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)

    gen = HackRfGen(0.0, cal="-")  # no calibration while calibrating
    bb = BB60()
    rows = []
    try:
        for f in freqs:
            for amp in (False, True):
                for tx in tvs:
                    gen.cal = {}
                    gen.settings = lambda hz, dbm, tx=tx, amp=amp: (tx, amp, 0.0)  # this txvga, full scale
                    gen.cw(f, 0.0)
                    time.sleep(0.3)
                    p, fh = bb.peak(f, span=50e3, rbw=100, ref_dbm=10.0 - a.atten)
                    lo, _ = bb.peak(f - gen.OFFSET, span=20e3, rbw=100, ref_dbm=10.0 - a.atten)
                    row = {"hz": f, "amp": amp, "txvga": tx, "out_dbm": p + a.atten, "err_hz": fh - f, "lo_dbc": lo - p}
                    rows.append(row)
                    print("%8.3f MHz amp %d txvga %2d: %+6.1f dBm out, %+7.0f Hz, LO %+5.1f dBc" % (
                        f / 1e6, amp, tx, row["out_dbm"], row["err_hz"], row["lo_dbc"]))
        drift = []
        t0 = time.time()
        while time.time() - t0 < a.warm * 60:
            gen.settings = lambda hz, dbm: (20, False, 0.0)
            gen.cw(436e6, 0.0)
            p, fh = bb.peak(436e6, span=50e3, rbw=100, ref_dbm=10.0 - a.atten)
            drift.append({"t": time.time() - t0, "out_dbm": p + a.atten, "err_hz": fh - 436e6})
            print("drift %4.0f s: %+6.2f dBm %+6.0f Hz" % (drift[-1]["t"], drift[-1]["out_dbm"], drift[-1]["err_hz"]))
            time.sleep(60)
    finally:
        gen.close()
        bb.close()

    # P0 = output at txvga 0, from a straight-line fit over txvga 0..40 (above that the
    # output can compress), per frequency and amplifier setting
    cal = {"p0": {}, "p0_amp": {}, "txvga_slope": {}, "ppm": None, "atten_db": a.atten, "made": time.strftime("%Y-%m-%d %H:%M")}
    for f in freqs:
        for amp in (False, True):
            r = [x for x in rows if x["hz"] == f and x["amp"] == amp and x["txvga"] <= 40]
            k, p0 = np.polyfit([x["txvga"] for x in r], [x["out_dbm"] for x in r], 1)
            cal["p0_amp" if amp else "p0"]["%.0f" % f] = round(float(p0), 2)
            cal["txvga_slope"]["%.0f_%d" % (f, amp)] = round(float(k), 3)
    errs = [x["err_hz"] / x["hz"] * 1e6 for x in rows if x["hz"] >= 100e6]
    cal["ppm"] = round(float(np.median(errs)), 3)
    json.dump(cal, open(os.path.join(os.path.dirname(__file__), "hackrf_cal.json"), "w"), indent=1)
    json.dump({"rows": rows, "drift": drift, "cal": cal}, open(os.path.join(out, "results.json"), "w"), indent=1)
    print("\nppm %.3f; P0 at 436 MHz %.1f dBm (amp off) / %.1f dBm (amp on); written hackrf_cal.json and %s" % (
        cal["ppm"], cal["p0"]["436000000"], cal["p0_amp"]["436000000"], out))


if __name__ == "__main__":
    main()
