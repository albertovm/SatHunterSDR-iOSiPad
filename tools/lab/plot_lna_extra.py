#!/usr/bin/env python3
"""Plots for an lna_extra.py run (and an optional separate spur/NF run).

    python tools/lab/plot_lna_extra.py measurements/<date>_lna-extra [--spur-nf measurements/<date>_lna-spur-nf] [--comb <comb run>]

--comb: per-frequency gain from a comb_sweep.py run for NF rows that carry no gain of their own.
"""

import argparse, json, math, os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--spur-nf")
    ap.add_argument("--comb")
    a = ap.parse_args()
    d = json.load(open(os.path.join(a.run, "results.json"), encoding="utf-8"))
    sn = json.load(open(os.path.join(a.spur_nf, "results.json"), encoding="utf-8")) if a.spur_nf else d
    summ = {}
    fig, ax = plt.subplots(3, 2, figsize=(13, 13))

    # stability
    t = np.array([r["t"] for r in d["stab"] for _ in r["gains_db"]])
    g = np.array([v for r in d["stab"] for v in r["gains_db"]])
    good = np.abs(g - np.median(g)) < 3
    x = ax[0, 0]
    x.plot(t[good] / 60, g[good], ".", ms=3)
    x.set_ylim(np.median(g) - 0.5, np.median(g) + 0.5)
    for tt in t[~good]:
        x.axvline(tt / 60, color="#d9480f", lw=1)
    x.set_title(f"Gain at 436 MHz, -60 dBm in, {len(g)} readings over {t.max() / 60:.0f} min\n"
                f"spread {g[good].max() - g[good].min():.2f} dB p-p; dropouts (red): {int((~good).sum())}, lowest {g.min():.1f} dB")
    x.set_xlabel("minutes"); x.set_ylabel("gain, dB"); x.grid(alpha=0.3)
    summ["stab"] = {"readings": int(len(g)), "pp_db": float(g[good].max() - g[good].min()), "dropouts": int((~good).sum())}

    # P1dB
    x = ax[0, 1]
    summ["p1db"] = {}
    for f, s in d["p1db_multi"].items():
        pin = np.array([r["pin_dbm"] for r in s["rows"]]); gg = np.array([r["gain_db"] for r in s["rows"]])
        x.plot(pin, gg - s["small_signal_gain_db"], ".-", ms=3, lw=0.8, label=f"{f} MHz: G {s['small_signal_gain_db']:.1f}, IP1dB {s['ip1db_dbm']:.0f}, OP1dB {s['op1db_dbm']:+.1f}")
        summ["p1db"][f] = {"gain_db": s["small_signal_gain_db"], "ip1db_dbm": s["ip1db_dbm"], "op1db_dbm": s["op1db_dbm"]}
    x.axhline(-1, color="k", lw=0.6, ls="--")
    x.set_ylim(-6, 1.5); x.set_xlabel("input, dBm"); x.set_ylabel("gain change, dB"); x.grid(alpha=0.3)
    x.set_title("Compression vs frequency (gain relative to small-signal)")
    x.legend(fontsize=7)

    # IP3
    x = ax[1, 0]
    summ["ip3"] = []
    for c in d["ip3_multi"]:
        pin = np.array([r["pin_per_tone_dbm"] for r in c["rows"]])
        im = np.array([max(r["im3_low_dbm"], r["im3_high_dbm"]) for r in c["rows"]])
        ii = np.array([r["iip3_dbm"] for r in c["rows"]])
        k = int(np.argmin(np.abs(pin + 40)))
        lab = f"{c['fc_hz'] / 1e6:.0f} MHz, {c['spacing_hz'] / 1e3:g} kHz: IIP3 {ii[k]:.1f} dBm @ -40"
        x.plot(pin, im, ".-", ms=3, lw=0.8, label=lab)
        slope = float(np.polyfit(pin[(pin >= -46) & (pin <= -38)], im[(pin >= -46) & (pin <= -38)], 1)[0])
        summ["ip3"].append({"fc_mhz": c["fc_hz"] / 1e6, "spacing_khz": c["spacing_hz"] / 1e3, "iip3_at_m40_dbm": float(ii[k]),
                            "oip3_at_m40_dbm": float(c["rows"][k]["oip3_dbm"]), "im3_slope_m46_m38": slope})
    c0 = d["ip3_multi"][1]
    x.plot([r["pin_per_tone_dbm"] for r in c0["rows"]], [r["pout_per_tone_dbm"] for r in c0["rows"]], "k-", lw=1.2, label="fundamental per tone (436 MHz)")
    x.set_xlabel("input per tone, dBm"); x.set_ylabel("output, dBm"); x.grid(alpha=0.3)
    x.set_title("Two-tone: higher IM3 product vs input level")
    x.legend(fontsize=7)

    # blocking
    x = ax[1, 1]
    summ["block"] = []
    for b in d["block"]:
        pb = np.array([r["blocker_dbm"] for r in b["rows"]]); gw = np.array([r["wanted_gain_db"] for r in b["rows"]])
        x.plot(pb, gw - b["gain_unblocked_db"], ".-", ms=3, lw=0.8, label=f"blocker {b['offset_hz'] / 1e6:+.0f} MHz ({(436e6 + b['offset_hz']) / 1e6:.0f} MHz)")
        summ["block"].append({"offset_mhz": b["offset_hz"] / 1e6, "max_blocker_dbm": float(pb.max()), "desense_at_max_db": float(b["gain_unblocked_db"] - gw[-1])})
    x.axhline(-1, color="k", lw=0.6, ls="--")
    x.set_ylim(-1.5, 0.5); x.set_xlabel("blocker at the LNA input, dBm"); x.set_ylabel("wanted-tone gain change, dB"); x.grid(alpha=0.3)
    x.set_title("Close-in blocking: wanted tone at 436 MHz, 40 dB under the blocker")
    x.legend(fontsize=7)

    # spur scan
    x = ax[2, 0]
    sp = sn.get("spur", [])
    for s in sp:
        col = "#999999" if s["mult_80mhz"] else ("#d9480f" if abs(s["freq_hz"] - 436e6) > 1e6 else "#2a6fdb")
        x.plot([s["freq_hz"] / 1e6] * 2, [-115, s["bb_dbm"]], color=col, lw=1.5)
    if sp:
        x.axhline(np.median([s["floor_dbm"] for s in sp]), color="k", lw=0.6, ls="--", label="median floor (30 kHz RBW)")
    x.plot([], [], color="#999999", label="BB60C spurs (n x 80 MHz)")
    x.plot([], [], color="#2a6fdb", label="436 MHz: VSG60 leakage with its output off")
    x.plot([], [], color="#d9480f", label="other")
    x.set_xlim(20, 3000); x.set_ylim(-115, -70); x.set_xlabel("MHz"); x.set_ylabel("dBm at the BB60C")
    x.set_title("No input: peaks > 10 dB over the floor, 20 MHz - 3 GHz"); x.grid(alpha=0.3); x.legend(fontsize=7)
    summ["spur_other"] = [round(s["freq_hz"] / 1e6, 3) for s in sp if not s["mult_80mhz"] and abs(s["freq_hz"] - 436e6) > 1e6]

    # NF
    x = ax[2, 1]
    nf = sn.get("nf")
    if nf:
        cg = None
        if a.comb:
            c = json.load(open(os.path.join(a.comb, "results.json"), encoding="utf-8"))
            cf = np.array([p["freq_hz"] for p in c["points"]]); cgv = np.array([p["gain_db"] for p in c["points"]])
            cg = lambda f: float(np.interp(f, cf, cgv))  # noqa: E731
        rows = []
        for r in nf["rows"]:
            gain = r.get("gain_db") or (cg(r["freq_hz"]) if cg else nf["gain_436_db"])
            lna_out = 10 * math.log10(10 ** (r["density_dbm_hz"] / 10) - 10 ** (nf["floor_dbm_hz"] / 10)) + sn["out_loss_db"]
            rows.append({"freq_mhz": r["freq_hz"] / 1e6, "gain_db": gain, "hump_db": r["hump_db"], "nf_db": lna_out + 174 - gain})
        x.bar([r["freq_mhz"] for r in rows], [r["nf_db"] for r in rows], width=1.5, color="#2a6fdb")
        for r in rows:
            x.text(r["freq_mhz"], r["nf_db"] + 0.1, f"{r['nf_db']:.1f} dB\n(hump {r['hump_db']:.1f})", ha="center", fontsize=8)
        x.set_ylim(0, 5); x.set_xlabel("MHz"); x.set_ylabel("NF, dB")
        x.set_title("Noise figure estimate (gain method through the 30 dB output pad)")
        x.grid(alpha=0.3, axis="y")
        summ["nf"] = rows
    fig.suptitle("Spacewalker LNA 434 v1.4, 5.0 V: further characterisation", fontsize=13)
    fig.tight_layout()
    fig.savefig(os.path.join(a.run, "plots.png"), dpi=110)
    json.dump(summ, open(os.path.join(a.run, "summary.json"), "w", encoding="utf-8"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
