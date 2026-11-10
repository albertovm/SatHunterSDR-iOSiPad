# VSG60A straight into the BB60C

2026-11-10 10:07, G7. VSG60A -> SMA adapter - 100 pF DC block - SMA adapter -> BB60C, `path_cal.py` at
0 dBm ([results](results.json)) and -60 dBm ([results](../2026-11-10_1007_vsg-direct-m60dbm/results.json)).
The adapters and DC block lose well under 0.5 dB above 100 MHz, so the "loss" is the two instruments'
disagreement: VSG60A set level minus BB60C reading.

| MHz | 0 dBm | -60 dBm |
|---|---|---|
| 50 | +0.8 dB | +0.5 dB |
| 145.8 | -0.5 dB | -0.8 dB |
| 250 | - | -0.7 dB |
| 300 | -0.3 dB | -0.3 dB |
| 325 | - | -1.0 dB |
| **350** | **+2.5 dB** | **+2.8 dB** |
| 375 | - | +3.2 dB |
| **436.6** | **+2.6 dB** | **+2.8 dB** |
| 1000 | +3.2 dB | +2.3 dB |
| 2400 | +1.1 dB | +0.9 dB |
| 5800 | +10.0 dB | +10.6 dB |

- Between 325 and 350 MHz the two instruments' agreement jumps by about 3.8 dB, the same at 0 and -60 dBm:
  a band edge in one of them (VSG60A output filter bank or BB60C preselector), not a level effect.
- On 70 cm the VSG60A's set level reads **2.6-2.8 dB lower** on the BB60C. This is the 2.5 dB gap between
  the VSG-based chain loss (72.8 dB) and the HackRF-based one (70.3 dB) of
  [2026-11-09](../2026-11-09_1400_hackrf1-cal-direct/report.md): the chain itself loses 70.3 dB.
- At 5.8 GHz the VSG60A puts out (or the BB60C reads) 10 dB less than set.

**What it means for the measurements.** Every lab level is set through a `path_cal.py` path, i.e. VSG60A set
level minus the BB60C's reading, so the lab levels are **BB60C-referenced**; the HackRF calibrations are
BB60C-referenced too. Lab and home numbers are therefore consistent with each other. Their absolute accuracy
is the BB60C's (Signal Hound specifies +-2 dB): if the VSG60A is the right one on 70 cm, every level in this
repo is about 2.7 dB too low (sensitivities 2.7 dB worse than written); if the BB60C is right, nothing
changes. Which one is right needs a third reference (a power meter or a recently calibrated analyzer).
