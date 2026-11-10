# Third reference: VSG60A into the SA44

2026-11-10 10:28-10:31, G7. VSG60A -> SMA adapter - 100 pF DC block - SMA adapter -> SA44 (serial
30300380), `tools/lab/ref_compare.py`, set level minus SA44 reading. Same path as the
[VSG60A -> BB60C check](../2026-11-10_1007_vsg-direct-0dbm/report.md) an hour earlier.

| MHz | SA44, 0 dBm | SA44, -30 dBm ([run](../2026-11-10_1030_ref-compare-sa44/results.json)) | BB60C, 0 dBm |
|---|---|---|---|
| 50 | +1.1 dB | - | +0.8 dB |
| 145.8 | -1.3 dB | +0.6 dB | -0.5 dB |
| 300 | -0.2 dB | +0.5 dB | -0.3 dB |
| 325 | -0.4 dB | +0.2 dB | - |
| **350** | **+3.1 dB** | **+5.5 dB** | **+2.5 dB** |
| 375 | +2.8 dB | - | - |
| **436.6** | **+2.6 dB** | **+2.9 dB** | **+2.6 dB** |
| 1000 | +2.9 dB | +3.1 dB | +3.2 dB |
| 2400 | +0.8 dB | - | +1.1 dB |
| 4000 | +3.0 dB | - | - |

**Two independent analyzers read the VSG60A 2.6-2.9 dB low on 70 cm, with the same step between 325 and
350 MHz.** So it is the VSG60A that puts out about 2.7 dB less than set above ~340 MHz (an output-filter band
edge), not the BB60C reading high. The BB60C and the SA44 agree within about 0.3 dB on 70 cm.

Consequences:
- The levels in this repo are BB60C-referenced (every path is calibrated VSG60A -> path -> BB60C), and the
  BB60C is confirmed by the SA44: **they stand as written.**
- Anything that used the VSG60A's set level without a BB60C path calibration is 2.7 dB too high on 70 cm.
- The home chain loses 70.3 dB on 70 cm (the 72.8 dB from the VSG path cal includes the VSG60A's error).
  `tools/lab/hackrf_cal.json` with `--atten 72.8` still gives the right level at the chain output, because
  its P0 was made with the same 72.8; the HackRF's own output is in z2labs/hackrf_calibrations.
- The SA44 run at -60 dBm (first run in [this folder](results.json), second half) is invalid: the reference
  level followed the set level and the SA44 lost the tone; the -30 dBm run used a fixed reference.
