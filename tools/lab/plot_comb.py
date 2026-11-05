#!/usr/bin/env python3
"""Plot a comb_sweep.py run: transfer function (gain vs frequency), passband zoom, and summary numbers.

    python tools/lab/plot_comb.py measurements/<date>_lna-comb [--cw measurements/<date>_lna-passband/results.json]
"""

import argparse, json, os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MIN_MARGIN = 10.0  # dB over the analyser floor for a point to count as measured


def edges(f, g, level):
    above = f[g >= level]
    return (float(above.min()), float(above.max())) if len(above) else (None, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--cw", action="append", default=[], help="lna_char.py results.json with CW gain points to overlay")
    a = ap.parse_args()
    r = json.load(open(os.path.join(a.run, "results.json")))
    P = r["points"]
    f = np.array([p["freq_hz"] for p in P]) / 1e6
    g = np.array([p["gain_db"] for p in P])
    mg = np.array([p["floor_margin_db"] for p in P])
    ok = mg >= MIN_MARGIN
    peak = float(g[ok].max())
    s = {"points": len(P), "peak_gain_db": peak, "peak_freq_mhz": float(f[ok][g[ok].argmax()])}
    for lvl in (1, 3, 10, 40, 60):
        lo, hi = edges(f[ok], g[ok], peak - lvl)
        s[f"bw_{lvl}db_mhz"] = [lo, hi]
    for lo_, hi_ in ((435.0, 438.0), (430.0, 440.0), (426.0, 443.0)):
        m = ok & (f >= lo_) & (f <= hi_)
        s[f"gain_{lo_:.0f}_{hi_:.0f}"] = {"min": float(g[m].min()), "max": float(g[m].max()), "mean": float(g[m].mean()),
                                         "ripple_pp_db": float(g[m].max() - g[m].min())}
    m = ok & (f >= 426) & (f <= 443)
    # ripple period: strongest component of the detrended passband gain
    ff, gg = f[m], g[m] - np.polyval(np.polyfit(f[m], g[m], 2), f[m])
    fr = np.fft.rfftfreq(len(gg), d=float(np.median(np.diff(ff))))
    sp = np.abs(np.fft.rfft(gg * np.hanning(len(gg))))
    k = 1 + int(sp[1:].argmax())
    s["ripple_period_mhz"] = float(1 / fr[k])
    r["summary"] = s
    json.dump(r, open(os.path.join(a.run, "results.json"), "w", encoding="utf-8"), indent=1)

    fig, ax = plt.subplots(2, 1, figsize=(11, 8.5))
    for axi, (x0, x1) in zip(ax, ((f.min(), f.max()), (420, 450))):
        sel = (f >= x0) & (f <= x1)
        axi.plot(f[sel & ok], g[sel & ok], ".-", ms=2.5, lw=0.8, color="#2a6fdb", label="comb sweep, 200 kHz steps")
        axi.plot(f[sel & ~ok], g[sel & ~ok], ".", ms=2, color="#bbbbbb", label="under the floor (+10 dB): upper bound")
        for c in a.cw:
            cr = json.load(open(c))
            cf = np.array([p["freq_hz"] for p in cr["gain"]]) / 1e6
            cg = np.array([p["gain_db"] for p in cr["gain"]])
            cs = (cf >= x0) & (cf <= x1)
            axi.plot(cf[cs], cg[cs], "o", mfc="none", ms=5, color="#d9480f", label="CW points (lna_char.py)" if c == a.cw[0] else None)
        axi.axvspan(435, 438, color="#2f9e44", alpha=0.08, label="435-438 MHz satellite band")
        axi.set_xlim(x0, x1)
        axi.set_xlabel("MHz")
        axi.set_ylabel("gain, dB")
        axi.grid(alpha=0.3)
    ax[0].set_title("Spacewalker LNA 434 v1.4: transfer function (S21 magnitude), 5.0 V")
    ax[0].legend(loc="upper right", fontsize=8)
    ax[1].set_ylim(peak - 20, peak + 3)
    ax[1].set_title(f"Passband: peak {peak:.1f} dB, 435-438 MHz {s['gain_435_438']['min']:.1f}-{s['gain_435_438']['max']:.1f} dB, "
                    f"ripple period ~{s['ripple_period_mhz']:.1f} MHz")
    fig.tight_layout()
    fig.savefig(os.path.join(a.run, "transfer.png"), dpi=130)
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
