"""Panorama sweep: how the app's spectrum shows a signal across the whole visible span.

    python tools/lab/pano_sweep.py --gen hackrf --atten 70 --level -90 --decimations 1,2,4,8 --points 201

The receiver stays on one centre; a CW tone steps across the span (and 10 % beyond each edge)
in `--points` steps, for every decimation (and sample rate, --rates). At each step the phone's
display spectrum (/spectrum, as the app draws it) is read and the script records:
  - the tone's level where it should be (the passband shape, edges, roll-off),
  - the strongest other bin and its frequency (images: IQ mirror at -offset, aliases folding in
    from outside the span),
  - the noise floor (median).
Writes results.json, pano.png (level vs offset per decimation, images and aliases) and report.md
to measurements/<date_time>_pano-sweep/.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from lab import Phone, Vsg60Gen  # noqa: E402


def open_gen(a):
    if a.gen == "hackrf":
        from hackrf_gen import HackRfGen
        return HackRfGen(a.atten)
    host, _, port = a.vsg.partition(":")
    return Vsg60Gen(a.atten, host, int(port or 5124), a.vsg_dir, None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ip", default="192.168.1.11")
    ap.add_argument("--pin", default="1027")
    ap.add_argument("--gen", choices=["hackrf", "vsg60"], default="hackrf")
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--vsg-dir", default=r"C:\sathunter_lab")
    ap.add_argument("--atten", type=float, required=True)
    ap.add_argument("--center", type=float, default=436.0e6)
    ap.add_argument("--level", type=float, default=-90.0, help="tone level at the receiver, dBm")
    ap.add_argument("--decimations", default="1,2,4,8")
    ap.add_argument("--rates", default="", help="sample rates to sweep as well (comma list, Hz; default: as set)")
    ap.add_argument("--points", type=int, default=201)
    ap.add_argument("--beyond", type=float, default=0.1, help="fraction of the span swept beyond each edge")
    ap.add_argument("--secs", type=float, default=0.6)
    ap.add_argument("--gain", type=float)
    ap.add_argument("--name", default="pano-sweep")
    a = ap.parse_args()

    ph = Phone(a.ip, a.pin)
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)
    gen = open_gen(a)
    if a.gain is not None:
        ph.cmd(cmd="gain", db=a.gain)
    rates = [float(r) for r in a.rates.split(",") if r.strip()] or [None]
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "generator": gen.name, "atten": a.atten, "level": a.level, "runs": []}
    try:
        for rate in rates:
            if rate:
                ph.cmd(cmd="rate", hz=rate)
            for dec in [int(x) for x in a.decimations.split(",")]:
                ph.cmd(cmd="decimation", factor=dec)
                ph.cmd(cmd="center", hz=a.center)
                time.sleep(1.0)
                getattr(gen, "silence", gen.off)()
                floor = ph._req("GET", "/spectrum?secs=2")
                c, fs, n = floor["center_hz"], floor["rate"], floor["bins"]
                base = np.array(floor["db"])
                span = fs
                offs = np.linspace(-(0.5 + a.beyond) * span, (0.5 + a.beyond) * span, a.points)
                ph.phase("pano sweep", dec, 8, "decimation %d, span %.0f kHz" % (dec, span / 1e3))
                pts = []
                for k, off in enumerate(offs):
                    st = gen.cw(c + off, a.level)
                    time.sleep(0.15)
                    sp = ph._req("GET", "/spectrum?secs=%.2f" % a.secs)
                    if abs(sp["center_hz"] - c) > 1 or sp["rate"] != fs:
                        continue
                    d = np.array(sp["db"])
                    bin_hz = fs / n
                    f = c + (np.arange(n) - n / 2) * bin_hz
                    inside = abs(off) <= span / 2
                    kt = int(round(off / bin_hz + n / 2)) if inside else None
                    lvl = float(d[max(0, kt - 2):kt + 3].max()) if inside and 0 <= kt < n else None
                    excess = d - base  # what the tone added, bin by bin
                    mask = np.ones(n, bool)
                    if inside and kt is not None:
                        mask[max(0, kt - 4):kt + 5] = False
                    mask[n // 2 - 3:n // 2 + 4] = False  # DC
                    ko = int(np.argmax(np.where(mask, excess, -1e9)))
                    pts.append({"offset": float(off), "inside": bool(inside), "level_db": lvl,
                                "other_db": float(d[ko]), "other_rise_db": float(excess[ko]), "other_offset": float(f[ko] - c),
                                "floor_db": float(np.median(d)), "gen": st})
                    if k % 20 == 0:
                        print("dec %d %+9.0f Hz: %s dB, other %+.1f dB rise at %+.0f Hz" % (
                            dec, off, "%.1f" % lvl if lvl is not None else "  - ", excess[ko], f[ko] - c))
                res["runs"].append({"rate": fs * dec if rate is None else rate, "decimation": dec, "span": span, "bins": n, "center": c, "points": pts})
                json.dump(res, open(os.path.join(out, "results.json"), "w"), indent=1)
    finally:
        gen.close()
    plot(out, res)


def plot(out, res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    runs = res["runs"]
    fig, ax = plt.subplots(len(runs), 1, figsize=(10, 2.6 * len(runs)), squeeze=False)
    lines = ["# Panorama sweep: the app's spectrum across the span", "",
             "Generator %s, %.1f dBm at the receiver, %s. A CW tone stepped across the span and 10 %% beyond; "
             "the phone's display spectrum read at each step." % (res["generator"], res["level"], res["started"]), "",
             "| Decimation | Span | Flat (±1 dB) | -3 dB edges | Worst image / alias (dB below the tone) |", "|---|---|---|---|---|"]
    for r, axx in zip(runs, ax[:, 0]):
        p = [x for x in r["points"] if x["inside"] and x["level_db"] is not None]
        off = np.array([x["offset"] for x in p]) / 1e3
        lv = np.array([x["level_db"] for x in p])
        ref = np.median(lv[np.abs(off) < r["span"] / 1e3 / 4]) if len(lv) else 0
        axx.plot(off, lv - ref, ".-", ms=3, lw=0.8, label="tone level (rel. to mid-band)")
        oth = [x for x in r["points"] if x["other_rise_db"] > 6]
        axx.plot([x["offset"] / 1e3 for x in oth], [x["other_db"] - ref for x in oth], "x", ms=4, color="#c0392b", label="image / alias seen")
        axx.axvline(-r["span"] / 2e3, color="#888", lw=0.6)
        axx.axvline(r["span"] / 2e3, color="#888", lw=0.6)
        axx.set_ylim(-70, 5)
        axx.set_ylabel("dB")
        axx.set_title("decimation %d, span %.0f kHz" % (r["decimation"], r["span"] / 1e3), fontsize=9)
        axx.grid(alpha=0.3)
        flat = off[np.abs(lv - ref) <= 1.0]
        e3 = off[lv - ref >= -3.0]
        worst = max([x["other_db"] - x.get("level_db", 0) for x in r["points"] if x["inside"] and x["level_db"] is not None and x["other_rise_db"] > 6] or [float("nan")])
        lines.append("| %d | %.0f kHz | %s | %s | %s |" % (
            r["decimation"], r["span"] / 1e3,
            "%.0f ... %+.0f kHz" % (flat.min(), flat.max()) if len(flat) else "-",
            "%.0f ... %+.0f kHz" % (e3.min(), e3.max()) if len(e3) else "-",
            "%.0f" % -worst if worst == worst else "none above 6 dB"))
    ax[0, 0].legend(fontsize=8, loc="lower center")
    ax[-1, 0].set_xlabel("tone offset from the centre, kHz")
    fig.tight_layout()
    fig.savefig(os.path.join(out, "pano.png"), dpi=130)
    lines += ["", "![Panorama](pano.png)", "", "Raw data: [results.json](results.json)."]
    open(os.path.join(out, "report.md"), "w").write("\n".join(lines) + "\n")
    print("report:", os.path.join(out, "report.md"))


if __name__ == "__main__":
    main()
