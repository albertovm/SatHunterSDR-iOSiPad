#!/usr/bin/env python3
"""LNA characterisation with the VSG60 and the BB60C: gain and passband, out-of-band rejection, P1dB,
two-tone IIP3. Path: VSG60 - input pad - coax - LNA - bias tee - output pad - BB60C. The path without
the LNA is measured first with path_cal.py; the output side (pad + bias tee) is given as --out-loss.

    python tools/lab/lna_char.py --cal measurements/<date>_path-cal/results.json --out-loss 30.5 --name lna

Levels in the report are at the LNA's input and output connectors.
"""

import argparse, glob, json, math, os, sys, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import Vsg60Gen, wait_idle  # noqa: E402
from bb60 import BB60  # noqa: E402

VSG_MAX = 8.0  # dBm, a little under the VSG60's +10 dBm


def two_tone(rate, df, n=20_000):
    t = np.arange(n) / rate
    return [complex(v) for v in 0.5 * (np.exp(-1j * np.pi * df * t) + np.exp(1j * np.pi * df * t))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--vsg-dir", default=r"C:\sathunter_lab")
    ap.add_argument("--cal", help="path_cal results.json (default: the newest measurements/*path-cal*)")
    ap.add_argument("--out-loss", type=float, default=30.5, help="output pad + bias tee, dB")
    ap.add_argument("--max-in", type=float, default=-12.0, help="highest level at the LNA input, dBm (its maximum is 0 dBm)")
    ap.add_argument("--f0", type=float, default=436.0e6)
    ap.add_argument("--parts", default="gain,p1db,ip3")
    ap.add_argument("--freqs", help="gain part: MHz list or start:stop:step (default: the calibration frequencies)")
    ap.add_argument("--pins", default="-60,-35,-20", help="gain part: input levels tried in turn until the output is 25 dB over the floor")
    ap.add_argument("--rbw", type=float, default=300.0, help="gain part RBW, Hz (lower = lower floor)")
    ap.add_argument("--name", default="lna")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    cal_path = a.cal or sorted(glob.glob(os.path.join(root, "measurements", "*path-cal*", "results.json")))[-1]
    cal = json.load(open(cal_path))
    cf = np.array([p["freq_hz"] for p in cal["points"]])
    cl = np.array([p["loss_db"] for p in cal["points"]])

    def total_loss(f):
        return float(np.interp(f, cf, cl))

    def in_loss(f):
        return total_loss(f) - a.out_loss

    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "cal": os.path.relpath(cal_path, root), "out_loss_db": a.out_loss, "note": a.note}

    def save():
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)

    host, port = (a.vsg.split(":") + ["5124"])[:2]
    gen = Vsg60Gen(0.0, host, int(port), a.vsg_dir, None)
    bb = BB60()
    parts = a.parts.split(",")
    try:
        wait_idle()
        gen.off()
        # gain vs frequency: -60 dBm in; where the output is near the floor, -35 dBm in
        if "gain" in parts:
            res["gain"] = []
            if a.freqs and ":" in a.freqs:
                f0_, f1_, st_ = (float(x) for x in a.freqs.split(":"))
                freqs = [x * 1e6 for x in np.arange(f0_, f1_ + st_ / 2, st_)]
            elif a.freqs:
                freqs = [float(x) * 1e6 for x in a.freqs.split(",")]
            else:
                freqs = list(cf)
            for f in freqs:
                row = None
                for pin in (float(x) for x in a.pins.split(",")):
                    vsg = pin + in_loss(f)
                    if vsg > VSG_MAX:
                        break
                    gen.cw(f, vsg)
                    time.sleep(0.15)
                    ref = min(10.0, pin + 50 - a.out_loss + 10)
                    p, fp = bb.peak(f, span=50e3, rbw=a.rbw, ref_dbm=ref)
                    nz = bb.noise(f + 20e3, span=20e3, rbw=a.rbw, ref_dbm=ref)  # beside the tone, same settings
                    pout = p + a.out_loss
                    row = {"freq_hz": f, "pin_dbm": pin, "pout_dbm": pout, "gain_db": pout - pin, "snr_db": p - nz,
                           "peak_offset_hz": fp - f, "below_floor": p - nz < 6}
                    if p - nz > 25:
                        break
                res["gain"].append(row)
                print(f"{f / 1e6:7.1f} MHz: gain {row['gain_db']:6.2f} dB (in {row['pin_dbm']:.0f} dBm, margin {row['snr_db']:.0f} dB)", flush=True)
                save()
            gen.off()
        # P1dB at f0
        if "p1db" in parts:
            res["p1db"] = []
            f = a.f0
            for pin in np.arange(-60.0, a.max_in + 0.01, 1.0):
                vsg = pin + in_loss(f)
                if vsg > VSG_MAX:
                    break
                gen.cw(f, vsg)
                time.sleep(0.15)
                p, _ = bb.peak(f, span=100e3, ref_dbm=min(10.0, pin + 50 - a.out_loss + 10))
                res["p1db"].append({"pin_dbm": float(pin), "pout_dbm": p + a.out_loss, "gain_db": p + a.out_loss - pin})
            gen.off()
            g0 = np.median([r["gain_db"] for r in res["p1db"][:10]])
            comp = [r for r in res["p1db"] if r["gain_db"] <= g0 - 1.0]
            res["p1db_summary"] = {"small_signal_gain_db": float(g0),
                                   "ip1db_dbm": comp[0]["pin_dbm"] if comp else None, "op1db_dbm": comp[0]["pout_dbm"] if comp else None,
                                   "max_compression_db": float(g0 - min(r["gain_db"] for r in res["p1db"]))}
            print("P1dB:", res["p1db_summary"], flush=True)
            save()
        # two-tone IIP3 at f0, tones 100 kHz apart
        if "ip3" in parts:
            res["ip3"] = []
            df = 100e3
            f1, f2 = a.f0 - df / 2, a.f0 + df / 2
            i1, i2 = f1 - df, f2 + df
            iq = two_tone(1e6, df)
            for pin in np.arange(-50.0, min(a.max_in - 6, -20) + 0.01, 2.0):  # per tone
                vsg = pin + 6.02 + in_loss(a.f0)  # set level = peak = tone + 6 dB
                if vsg > VSG_MAX:
                    break
                gen.play(a.f0, vsg, "sathunter_twotone_100k.cf32", iq, 1e6)
                time.sleep(0.15)
                ref = min(10.0, pin + 50 - a.out_loss + 10)
                p1, _ = bb.peak(f1, span=20e3, rbw=300, ref_dbm=ref)
                p2, _ = bb.peak(f2, span=20e3, rbw=300, ref_dbm=ref)
                q1, _ = bb.peak(i1, span=20e3, rbw=300, ref_dbm=ref)
                q2, _ = bb.peak(i2, span=20e3, rbw=300, ref_dbm=ref)
                po = (p1 + p2) / 2 + a.out_loss
                pim = max(q1, q2) + a.out_loss
                oip3 = po + (po - pim) / 2
                res["ip3"].append({"pin_per_tone_dbm": float(pin), "pout_per_tone_dbm": po, "im3_dbm": pim, "oip3_dbm": oip3,
                                   "iip3_dbm": oip3 - (po - pin)})
                print(f"two-tone {pin:.0f} dBm/tone: out {po:.1f}, IM3 {pim:.1f} dBm -> OIP3 {oip3:.1f}, IIP3 {oip3 - (po - pin):.1f} dBm", flush=True)
                save()
            gen.off()
    finally:
        gen.close()
        bb.close()
        res["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save()
    print(f"Results: {out}")


if __name__ == "__main__":
    main()
