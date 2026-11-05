"""Reverse isolation plot: S12 (this run) with the forward gain (comb sweep). Run from the repository root."""
import json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
D = "measurements/2026-11-05_1053_lna-reverse-s12/"
r = json.load(open(D + "results.json"))
inc = json.load(open("measurements/2026-11-05_1031_input-path-cal/results.json"))["points"]
ifr = np.array([p["freq_hz"] for p in inc]); il = np.array([p["loss_db"] for p in inc])
cal = json.load(open("measurements/2026-11-04_1523_path-cal/results.json"))["points"]
cf = np.array([p["freq_hz"] for p in cal]); cl = np.array([p["loss_db"] for p in cal])
BIAS_TEE = 1.0  # bias tee + short cable, dB (from the no-pad gain run)
rows = []
for p in r["points"]:
    f = p["freq_hz"]
    lin = np.interp(f, ifr, il) if 380e6 <= f <= 480e6 else np.interp(f, cf, cl) - 31.1
    rows.append({"freq_mhz": f / 1e6, "s12_db": -(p["loss_db"] - lin - BIAS_TEE), "margin_db": p["margin_db"],
                 "bb60_spur": abs(f / 80e6 - round(f / 80e6)) < 1e-9})
json.dump(rows, open(D + "s12.json", "w"), indent=1)
c = json.load(open("measurements/2026-11-04_1546_lna-comb/results.json"))
f = np.array([p["freq_hz"] for p in c["points"]]) / 1e6; g = np.array([p["gain_db"] for p in c["points"]])
ok = np.array([p["floor_margin_db"] for p in c["points"]]) >= 10
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
for a, (x0, x1) in zip(ax, ((30, 950), (375, 485))):
    a.plot(f[ok], g[ok], "-", color="#2a6fdb", lw=1.2, label="forward gain S21 (comb)")
    good = [x for x in rows if not x["bb60_spur"] and x0 <= x["freq_mhz"] <= x1]
    a.plot([x["freq_mhz"] for x in good], [x["s12_db"] for x in good], "o-", color="#e8590c", ms=4, label="reverse isolation S12")
    a.set_xlim(x0, x1); a.grid(alpha=0.3); a.set_xlabel("MHz"); a.set_ylabel("dB")
ax[0].set_title("Forward gain and reverse isolation"); ax[0].legend(fontsize=8)
ax[1].set_title("Around the passband"); ax[1].set_ylim(-110, 60)
fig.tight_layout(); fig.savefig(D + "plots.png", dpi=120)
for x in rows: print(x)
