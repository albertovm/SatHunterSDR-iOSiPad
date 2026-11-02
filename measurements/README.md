# Measurements

Lab measurements of the SatHunterSDR receive chain. Each run has its own folder with an English
`report.md` (setup, results, notes), plots, the raw `results.json` and CSV files. The runs are made with
[`tools/lab/lab.py`](../tools/lab/lab.py): it drives the signal generator over SCPI and the phone over the
lab link (see [docs/LAB.md](../docs/LAB.md)).

| Date | Run | Chain | Key results |
|---|---|---|---|
| 2026-11-02 | [System A](2026-11-02_1028_system-a/report.md) | VSG60 -> Spacewalker LNA 434 -> RTL-SDR V3 -> Mi 10 | NF 2.0 dB, best RTL gain 12.5 dB, +0.34 ppm |
| 2026-11-02 | [System A2](2026-11-02_1044_system-a2-mds/report.md) | as A, +30 dB attenuator | MDS -154.4 dBm (31 Hz), CW decode to -145 dBm (29 dB-Hz) |
| 2026-11-02 | [DSP check A](2026-11-02_1124_dsp-check/report.md) | rates x decimations | decimation OK (> 50 dB alias rejection); frequency error depends on the rate (+5 / +155 / +210 Hz) |
| 2026-11-02 | [DSP check B](2026-11-02_1134_dsp-check-bw/report.md) | modes x filter bandwidths | SSB/CW/WFM OK; AM capped at 4 kHz audio; NFM volume depends on the bandwidth |
| 2026-11-02 | [DSP check C](2026-11-02_1234_dsp-check-lab5/report.md) | after the fixes (lab5) | frequency error the same at every rate (+40 Hz, 0.09 ppm); AM and NFM fixed; RTL warm-up drift ~400 Hz |
| 2026-11-02 | [Two-tone](2026-11-02_1337_twotone/report.md) | in-band intermodulation | no IM3 before ADC clipping (-85 dBm/tone at gain 12.5); ~66 dB spur-free range |

## Planned

- RTL warm-up drift vs time from a cold start (for the satellite campaign).
- BB60C check of the VSG60 absolute level (the last dB of the NF).
- Spacewalker LNA 434 MHz alone (VSG60 -> LNA -> BB60C): gain and passband, out-of-band rejection, P1dB, IIP3, current.
- Simulated satellite pass with Doppler.
