#!/usr/bin/env python3
"""Generator + analyser check without the DUT (VSG60 - pads - BB60C): level dropouts over time, and the
VSG60's own two-tone IMD at the waveforms and levels lna_extra.py uses (to bound the LNA's IIP3 result).

    python tools/lab/thru_check.py --mins 10 --name thru-check
"""

import argparse, json, math, os, sys, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import Vsg60Gen, wait_idle  # noqa: E402
from bb60 import BB60  # noqa: E402
from lna_extra import tones  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--vsg-dir", default=r"C:\\sathunter_lab")
    ap.add_argument("--f0", type=float, default=436e6)
    ap.add_argument("--level", type=float, default=6.0, help="CW level for the dropout watch, dBm at the VSG")
    ap.add_argument("--mins", type=float, default=10)
    ap.add_argument("--spacings", default="0.02,0.1,1,4", help="MHz")
    ap.add_argument("--parts", default="drop,imd")
    ap.add_argument("--name", default="thru-check")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "f0_hz": a.f0, "note": a.note}

    def save():
        txt = json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as fh:
            fh.write(txt)

    host, port = (a.vsg.split(":") + ["5124"])[:2]
    gen = Vsg60Gen(0.0, host, int(port), a.vsg_dir, None)
    bb = BB60()
    try:
        wait_idle()
        if "drop" in a.parts:
            gen.cw(a.f0, a.level)
            time.sleep(0.3)
            ref = a.level - 50
            vals, t0 = [], time.time()
            while time.time() - t0 < a.mins * 60:
                p, _ = bb.peak(a.f0, span=50e3, rbw=1e3, ref_dbm=ref)
                vals.append((time.time() - t0, p))
            v = np.array([x[1] for x in vals])
            med = float(np.median(v))
            drops = [{"t": t, "dbm": p} for t, p in vals if p < med - 3]
            res["drop"] = {"vsg_dbm": a.level, "readings": len(vals), "median_dbm": med, "pp_db": float(v[v > med - 3].ptp()),
                           "dropouts": drops, "trace": vals}
            print(f"dropout watch: {len(vals)} readings, median {med:.2f} dBm, {len(drops)} dropouts", flush=True)
            save()
            gen.off()
        if "imd" in a.parts:
            res["imd"] = []
            for df in (float(x) * 1e6 for x in a.spacings.split(",")):
                rate = min(40e6, max(1e6, 10 * df))
                x, lv = tones(rate, [-df / 2, df / 2], [1, 1], df / 2)
                rows = []
                for vsg in np.arange(-20.0, 8.01, 2.0):  # set (peak) level: the range lna_extra.py used
                    gen.play(a.f0, float(vsg), f"sathunter_2t_{int(df)}.cf32", list(x), rate)
                    time.sleep(0.2)
                    ref = vsg - 50
                    span, rbw = min(200e3, df / 2), min(1e3, df / 20)
                    p = [bb.peak(f, span, rbw, ref)[0] for f in (a.f0 - df / 2, a.f0 + df / 2, a.f0 - 1.5 * df, a.f0 + 1.5 * df)]
                    tone = (p[0] + p[1]) / 2
                    rows.append({"vsg_set_dbm": float(vsg), "tone_dbm": tone, "im3_low_dbm": p[2], "im3_high_dbm": p[3],
                                 "im3_dbc": max(p[2], p[3]) - tone})
                gen.loaded = None
                res["imd"].append({"spacing_hz": df, "rate": rate, "rows": rows})
                print(f"VSG IMD {df / 1e3:g} kHz: " + ", ".join(f"{r['vsg_set_dbm']:+.0f}:{r['im3_dbc']:.0f}" for r in rows), flush=True)
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
