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
| 2026-11-02 | [Doppler CW](2026-11-02_1424_doppler/report.md) | keyed CW with frequency ramps | decodes at 0-100 Hz/s down to -138 dBm; 170 Hz/s: 12-14 of 15 characters (2-3 kHz filter) |
| 2026-11-03 | [APRS](2026-11-03_1119_aprs/report.md) | AFSK 1200 / AX.25, 3 kHz deviation, NFM 12.5 kHz | 90 % packets at about -121.5 dBm |
| 2026-11-03 | [APRS 1 kHz dev.](2026-11-03_1128_aprs-1k/report.md) | 1 kHz deviation, NFM 6 / 9 / 12.5 kHz | 90 % at -122.3 / -121.3 / -120.8 dBm; limit is the FM-discriminator AFSK (Eb/N0 ~19 dB) |
| 2026-11-03 | [APRS decoder v2](2026-11-03_1554_aprs-lab9-3k/report.md) | lab9: narrower detector filter, soft bit repair | 90 % at -122.5 dBm (+1.0 dB), 50 % at -124.5 dBm (+1.5 dB) |
| 2026-11-04 | [APRS v2, 1 kHz dev.](2026-11-04_1142_aprs-lab9-1k/report.md) | lab9, 1 kHz deviation, NFM 6 / 12.5 kHz | 90 % at -123.2 / -122.2 dBm (+0.9 / +1.4 dB) |
| 2026-11-04 | [Simulated pass](2026-11-04_1204_pass-sim/report.md) | COSMOS 2491, 88° pass, VSG follows the Doppler, phone tracks | tracking within ±13 Hz, CW decoded 28 of 29 times at -130 dBm |
| 2026-11-04 | [Simulated LEO pass](2026-11-04_1331_pass-sim-leo-lab10/report.md) | STARS, 61°, up to 118 Hz/s | not valid at the closest point: the VSG60 cannot retune fast over SCPI (13.5 s per retune; writes interrupt the output) |
| 2026-11-04 | [Fast pass, Doppler in the waveform](2026-11-04_1447_fast-pass/report.md) | CAPE-1, 79°, up to 116 Hz/s, independent SGP4 | carrier within ±9 Hz (1σ) of the VFO, CW decoded through TCA; phone orbit = SGP4 to 0.16 Hz |
| 2026-11-04 | [Spacewalker LNA 434 MHz](2026-11-04_1530_spacewalker-lna/report.md) | VSG60 + BB60C, LNA alone | gain 45.6-51.2 dB in 435-438 MHz, passband ~425-444 MHz, rejection 72->80 dB out of band, IP1dB -29 dBm, IIP3 -18.4 dBm, 5 V 125 mA |
| 2026-11-04 | [LNA transfer sweep](2026-11-04_1546_lna-comb/transfer.png) | VSG60 90-tone comb + BB60C | 380-490 MHz in 200 kHz steps; peak 50.9 dB at 438.5 MHz, 5.5 dB SAW-cascade ripple in 430-440 MHz |

## Planned

- RTL warm-up drift vs time from a cold start (for the satellite campaign).
- APRS: an IQ-domain (coherent) AFSK detector for several more dB.
- BB60C check of the VSG60 absolute level (the last dB of the NF).
- Spacewalker LNA: noise figure (gain method), reverse isolation, gain and current vs supply voltage, P1dB vs frequency; S11/S22 need a VNA or coupler.
- Simulated satellite pass with Doppler.
