#!/usr/bin/env python3
"""Supply sweep summary: lna_char.py runs at several supply voltages -> plots + summary.json in the first run.

    python tools/lab/plot_supply.py out_dir run_4.5V:4.5:117 run_5.0V:5.0:131 run_5.5V:5.5:146

Each argument: run folder, board voltage (V), board current (mA). P1dB readings more than 15 dB under the
small-signal gain are dropouts (see the lna-extra report) and are left out.
"""

import json, os, sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    out = sys.argv[1]
    rows = []
    for arg in sys.argv[2:]:
        run, v, ma = arg.rsplit(":", 2)
        d = json.load(open(os.path.join(run, "results.json"), encoding="utf-8"))
        p = d["p1db"]
        g0 = float(np.median([x["gain_db"] for x in p[:10]]))
        ok = [x for x in p if x["gain_db"] > g0 - 15]
        comp = [x for x in ok if x["gain_db"] <= g0 - 1]
        ip = {x["pin_per_tone_dbm"]: x for x in d["ip3"]}
        rows.append({"run": os.path.basename(run), "v": float(v), "ma": float(ma), "w": float(v) * float(ma) / 1000,
                     "gain": {f"{g['freq_hz'] / 1e6:.0f}": g["gain_db"] for g in d["gain"]},
                     "g0_436": g0, "ip1db": comp[0]["pin_dbm"], "op1db": comp[0]["pout_dbm"], "psat": max(x["pout_dbm"] for x in ok),
                     "dropouts_in_dbm": [x["pin_dbm"] for x in p if x["gain_db"] <= g0 - 15],
                     "iip3_m40": ip[-40.0]["iip3_dbm"], "oip3_m40": ip[-40.0]["oip3_dbm"],
                     "p1db_curve": [(x["pin_dbm"], x["pout_dbm"]) for x in ok]})
    V = np.array([r["v"] for r in rows])
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.8))
    x = ax[0]
    for f in rows[0]["gain"]:
        x.plot(V, [r["gain"][f] for r in rows], "o-", label=f"{f} MHz")
    x.set_xlabel("supply on the board, V"); x.set_ylabel("gain, dB"); x.set_title("Small-signal gain vs supply"); x.grid(alpha=0.3); x.legend(fontsize=7, ncol=2)
    x = ax[1]
    x.plot(V, [r["ma"] for r in rows], "o-", color="#2a6fdb", label="current, mA")
    x2 = x.twinx(); x2.plot(V, [r["w"] * 1000 for r in rows], "s--", color="#e8590c", label="power, mW")
    x.set_xlabel("supply on the board, V"); x.set_ylabel("current, mA"); x2.set_ylabel("power, mW")
    x.set_title("Supply current and power"); x.grid(alpha=0.3)
    x.legend(loc="upper left", fontsize=8); x2.legend(loc="lower right", fontsize=8)
    x = ax[2]
    for r in rows:
        c = np.array(r["p1db_curve"]); x.plot(c[:, 0], c[:, 1], ".-", ms=3, label=f"{r['v']:.1f} V: OP1dB {r['op1db']:+.1f}, OIP3 {r['oip3_m40']:+.1f} dBm")
    x.set_xlabel("input at 436 MHz, dBm"); x.set_ylabel("output, dBm"); x.set_title("Output vs input, 436 MHz"); x.grid(alpha=0.3); x.legend(fontsize=8)
    fig.suptitle("Spacewalker LNA 434 v1.4: supply voltage sweep", fontweight="bold")
    fig.tight_layout()
    os.makedirs(out, exist_ok=True)
    fig.savefig(os.path.join(out, "plots.png"), dpi=120)
    for r in rows:
        r.pop("p1db_curve")
    json.dump(rows, open(os.path.join(out, "summary.json"), "w", encoding="utf-8"), indent=1)
    for r in rows:
        print(r["v"], r["ma"], round(r["g0_436"], 2), r["ip1db"], round(r["op1db"], 1), round(r["psat"], 1), round(r["iip3_m40"], 1), round(r["oip3_m40"], 1), r["dropouts_in_dbm"])


if __name__ == "__main__":
    main()
