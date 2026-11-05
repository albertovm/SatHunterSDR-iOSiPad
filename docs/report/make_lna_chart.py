"""Compact LNA transfer chart for the summary report (comb sweep + CW points)."""
import json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

c = json.load(open("measurements/2026-11-04_1546_lna-comb/results.json"))
f = np.array([p["freq_hz"] for p in c["points"]]) / 1e6
g = np.array([p["gain_db"] for p in c["points"]])
ok = np.array([p["floor_margin_db"] for p in c["points"]]) >= 10
cw = []
for n in ("2026-11-04_1532_spacewalker-lna-passband", "2026-11-04_1535_spacewalker-lna-oob"):
    cw += json.load(open(f"measurements/{n}/results.json"))["gain"]
cf = np.array([p["freq_hz"] for p in cw]) / 1e6
cg = np.array([p["gain_db"] for p in cw])
fig, ax = plt.subplots(1, 2, figsize=(8, 3.6), gridspec_kw={"width_ratios": [1.3, 1]})
for a, (x0, x1) in zip(ax, ((380, 490), (422, 447))):
    s = (f >= x0) & (f <= x1)
    a.plot(f[s & ok], g[s & ok], "-", color="#2a6fdb", lw=1.2, label="comb, 200 kHz steps")
    a.plot(f[s & ~ok], g[s & ~ok], ".", color="#ced4da", ms=2, label="under the floor")
    m = (cf >= x0) & (cf <= x1) & ~np.isin(cf, (400.0, 480.0, 800.0))
    a.plot(cf[m], cg[m], "o", mfc="none", color="#e8590c", ms=3.5, label="CW points")
    a.axvspan(435, 438, color="#2f9e44", alpha=0.12)
    a.set_xlim(x0, x1); a.grid(alpha=0.3); a.set_xlabel("MHz")
ax[0].set_ylabel("gain, dB"); ax[0].set_title("380-490 MHz", fontsize=9); ax[0].legend(fontsize=7, loc="upper right")
ax[1].set_ylim(30, 54); ax[1].set_title("passband (green: 435-438 MHz)", fontsize=9)
fig.tight_layout()
fig.savefig("docs/report/lna.png", dpi=170)
