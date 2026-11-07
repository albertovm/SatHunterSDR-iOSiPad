"""Calibrate the HackRF against the receiver itself (no BB60C at hand).

    python tools/lab/hackrf_rxcal.py --ip 192.168.1.237 --atten 70.5

Transfer standard: the RTL-SDR in the phone app, whose level scale was measured with the VSG60A
on 2026-11-02 (measurements/2026-11-02_1028_system-a): at RTL gain 12.4 dB, decimation 2,
436.6 MHz, a CW tone at the LNA input L dBm gave a peak of L + 80.0 dBFS (1.00 dB/dB, -123 ... -85
dBm), and the LNA gain at 436.6 MHz is 46.8 dB (lna-comb, 436.5 / 436.7 MHz: 46.35 / 47.16 dB).
So at the RTL input: P = peak_dBFS - 80.0 + 46.8 = peak_dBFS - 33.2 dBm.

The HackRF plays CW at 436.6 MHz over its txvga range (amplifier off and on); for each step the
phone's peak gives the level at the RTL input and so P0 (the HackRF output at txvga 0, full digital
scale, referred through the --atten chain). The frequency offset gives the HackRF's ppm.
Accuracy: about +-2 dB (VSG60 level, LNA gain, RTL unit-to-unit if another dongle, temperature).
The BB60C calibration (hackrf_cal.py) replaces it when the lab is in reach.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from hackrf_gen import HackRfGen  # noqa: E402
from lab import Phone  # noqa: E402

HZ = 436.6e6
DBFS_TO_RTL_DBM = -80.0 + 46.8  # see the docstring
DBFS_TO_LNA_IN_DBM = -80.0  # the same chain as system-a: levels at the LNA input


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ip", default="192.168.1.237")
    ap.add_argument("--pin", default="1027")
    ap.add_argument("--atten", type=float, required=True)
    ap.add_argument("--txvga", default="0,4,8,12,16,20,24,28,32,36,40,44,47")
    ap.add_argument("--rtl-ppm", type=float, default=None, help="the phone's ppm setting is used when omitted")
    ap.add_argument("--no-lna", action="store_true", help="HackRF chain straight into the RTL (default: through the Spacewalker LNA, bias tee on)")
    a = ap.parse_args()
    ph = Phone(a.ip, a.pin)
    st0 = ph.status()
    ph.cmd(cmd="gain", db=12.4)
    ph.cmd(cmd="bias_tee", on=not a.no_lna)
    conv = DBFS_TO_RTL_DBM if a.no_lna else DBFS_TO_LNA_IN_DBM
    ph.cmd(cmd="decimation", factor=2)
    ph.cmd(cmd="center", hz=HZ - 100e3)  # the tone away from the RTL's DC spike
    ph.cmd(cmd="tune", hz=HZ)
    time.sleep(1.5)
    st = ph.status()
    print("phone:", st.get("source_status"), "gain", st.get("gain"))
    gen = HackRfGen(a.atten, cal="-")
    gen.silence()
    rows = []
    try:
        floor = ph._req("GET", "/measure?hz=%d&bw=2000&secs=2" % HZ)
        print("floor %.1f dBFS per bin" % floor["noise_dbfs_per_bin"])
        for amp in (False,):
            for tx in [int(x) for x in a.txvga.split(",")]:
                gen.settings = lambda hz, dbm, tx=tx, amp=amp: (tx, amp, 0.0)  # force this txvga, full scale
                gen.cw(HZ, 0.0)
                time.sleep(0.5)
                m = ph._req("GET", "/measure?hz=%d&bw=2000&secs=1.5" % HZ)
                p_rtl = m["peak_dbfs"] + conv
                row = {"amp": amp, "txvga": tx, "peak_dbfs": m["peak_dbfs"], "snr_db": m["peak_snr_db"],
                       "rtl_dbm": p_rtl, "p0": p_rtl + a.atten - tx, "offset_hz": m["offset_hz"]}
                rows.append(row)
                print("amp %d txvga %2d: %6.1f dBFS (SNR %4.1f) -> %7.1f dBm at the RTL, P0 %6.1f, offset %+6.0f Hz" % (
                    amp, tx, row["peak_dbfs"], row["snr_db"], p_rtl, row["p0"], row["offset_hz"]))
    finally:
        gen.close()
        ph.cmd(cmd="gain", db=st0.get("gain"))
        ph.cmd(cmd="decimation", factor=st0.get("decimation", 8))

    lv = [r["peak_dbfs"] for r in rows if not r["amp"]]
    if max(lv) - min(lv) < 10:
        raise SystemExit("the level does not follow txvga (%.1f dB range): no HackRF signal at %.3f MHz?" % (max(lv) - min(lv), HZ / 1e6))
    # usable points: well above the floor (SNR > 20 dB) and below the ADC clip (< -6 dBFS)
    good = [r for r in rows if r["snr_db"] > 20 and r["peak_dbfs"] < -6]
    cal = {"p0": {}, "p0_amp": {}, "ppm": None, "atten_db": a.atten, "method": "receiver transfer (system-a VSG60 scale), levels at the " + ("RTL input" if a.no_lna else "LNA input"),
           "made": time.strftime("%Y-%m-%d %H:%M")}
    for amp, key in ((False, "p0"), (True, "p0_amp")):
        g = [r for r in good if r["amp"] == amp and r["txvga"] <= 40]
        if len(g) >= 2:
            k, p0 = np.polyfit([r["txvga"] for r in g], [r["rtl_dbm"] + a.atten for r in g], 1)
            cal[key]["%.0f" % HZ] = round(float(p0), 2)
            cal["txvga_slope_" + ("amp" if amp else "noamp")] = round(float(k), 3)
    rtl_ppm = a.rtl_ppm if a.rtl_ppm is not None else 0.0  # the phone already corrects its own ppm
    offs = [r["offset_hz"] for r in good]
    if offs:
        cal["ppm"] = round(float(np.median(offs)) / HZ * 1e6 + rtl_ppm, 3)
    path = os.path.join(os.path.dirname(__file__), "hackrf_cal.json")
    json.dump(cal, open(path, "w"), indent=1)
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_hackrf-rxcal")
    os.makedirs(out, exist_ok=True)
    json.dump({"rows": rows, "cal": cal, "floor": floor, "phone": st}, open(os.path.join(out, "results.json"), "w"), indent=1)
    print("\n", json.dumps(cal), "\nwritten", path, "and", out)


if __name__ == "__main__":
    main()
