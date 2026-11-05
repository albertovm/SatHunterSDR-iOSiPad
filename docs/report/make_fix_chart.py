"""Before / after charts of the main fixes (frequency error vs sample rate, APRS decoder) for the summary report."""
import json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

M = "measurements/"
a = json.load(open(M + "2026-11-02_1124_dsp-check/results.json"))
before = {}
for x in a["decim"]:
    before.setdefault(x["rate"], []).append(np.median([i["offset_hz"] for i in x["inband"]]))
after = {}
for x in json.load(open(M + "2026-11-02_1234_dsp-check-lab5/freq_interleaved.json")):
    after.setdefault(x["rate"], []).append(x["offset_hz"])
rates = [250e3, 1024e3, 2400e3]

fig, ax = plt.subplots(1, 2, figsize=(11, 3.3))
x = np.arange(3)
ax[0].bar(x - 0.2, [np.median(before[r]) for r in rates], 0.4, color="#adb5bd", label="before (lab4)")
ax[0].bar(x + 0.2, [np.median(after[r]) for r in rates], 0.4, color="#2a6fdb", label="after the R820T2 PLL fix (lab5)")
ax[0].set_xticks(x); ax[0].set_xticklabels(["250 kS/s", "1.024 MS/s", "2.4 MS/s"])
ax[0].set_ylabel("frequency error, Hz @ 436.6 MHz"); ax[0].grid(alpha=0.3, axis="y"); ax[0].legend(fontsize=8)
ax[0].set_title("Frequency error vs sample rate", fontsize=10)

for name, lab, col in (("2026-11-03_1119_aprs", "decoder v1", "#adb5bd"), ("2026-11-03_1554_aprs-lab9-3k", "decoder v2 (lab9)", "#2a6fdb")):
    rows = [r for r in json.load(open(M + name + "/results.json"))["aprs"]["rows"] if r.get("bw_hz", 12500.0) == 12500.0]
    ax[1].plot([r["level_dbm"] for r in rows], [100 * r["success"] for r in rows], "o-", color=col, label=lab)
ax[1].axhline(90, color="k", lw=0.6, ls="--")
ax[1].set_xlabel("level at the receiver input, dBm"); ax[1].set_ylabel("packets decoded, %")
ax[1].set_title("APRS (AFSK1200, 3 kHz dev., NFM 12.5 kHz)", fontsize=10); ax[1].grid(alpha=0.3); ax[1].legend(fontsize=8)
fig.tight_layout()
fig.savefig("docs/report/fixes.png", dpi=150)
