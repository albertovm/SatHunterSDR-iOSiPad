"""RTL-SDR drift plot (run from the repository root)."""
import json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
D = "measurements/2026-11-05_1148_rtl-drift-hub/"
d = json.load(open(D + "results.json"))
t = np.array([r["t"] for r in d["rows"]]) / 60
f = np.array([r["offset_hz"] for r in d["rows"]])
fig, ax = plt.subplots(figsize=(10, 3.8))
ax.plot(t, f, ".-", ms=2, lw=0.8, color="#2a6fdb")
ax.axhspan(f[t > 10].min(), f[t > 10].max(), color="#2f9e44", alpha=0.12, label=f"after 10 min: {f[t > 10].min():+.0f} ... {f[t > 10].max():+.0f} Hz")
ax.set_xlabel("minutes since the start (dongle plugged in ~1 min before)")
ax.set_ylabel("frequency error at 436.6 MHz, Hz")
ax2 = ax.secondary_yaxis("right", functions=(lambda h: h / 436.6, lambda p: p * 436.6))
ax2.set_ylabel("ppm")
ax.set_title("RTL-SDR Blog V3 warm-up drift (app ppm -0.2, powered OTG hub)")
ax.grid(alpha=0.3); ax.legend(fontsize=8, loc="lower right")
fig.tight_layout(); fig.savefig(D + "plots.png", dpi=120)
