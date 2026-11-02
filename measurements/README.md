# Measurements

Lab measurements of the SatHunterSDR receive chain. Each run has its own folder with an English
`report.md` (setup, results, notes), plots, the raw `results.json` and CSV files. The runs are made with
[`tools/lab/lab.py`](../tools/lab/lab.py): it drives the signal generator over SCPI and the phone over the
lab link (see [docs/LAB.md](../docs/LAB.md)).

| Date | Run | Chain | Key results |
|---|---|---|---|
| 2026-11-02 | [System A](2026-11-02_1028_system-a/report.md) | VSG60 -> Spacewalker LNA 434 -> RTL-SDR V3 -> Mi 10 | NF 2.0 dB, +0.34 ppm, CW decoded at -123 dBm |

## Planned

- System A2: MDS and CW decode threshold with an external attenuator (below -123 dBm).
- Spacewalker LNA 434 MHz alone (VSG60 -> LNA -> BB60C): gain and passband, out-of-band rejection, P1dB, IIP3, current.
- Simulated satellite pass with Doppler.
