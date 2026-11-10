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
| 2026-11-04 | [LNA further characterisation](2026-11-04_1556_lna-extra/report.md) | VSG60 + BB60C, LNA alone | gain stable 0.15 dB p-p over 10 min, OP1dB +15.5...+21 dBm (426-443 MHz), IIP3 -17...-19 dBm, no desense from -18 dBm blockers at +-15/18 MHz, harmonics < -64 dBc, no oscillation, NF estimate 1.7-3.0 dB |
| 2026-11-05 | [Thru check](2026-11-05_0856_thru-check/report.md) | VSG60 + BB60C, no LNA | 0 dropouts in 5027 readings (the LNA-side dropouts are not the instruments); VSG60 two-tone IM3 -53...-59 dBc |
| 2026-11-05 | [LNA supply sweep](2026-11-05_lna-supply-sweep/report.md) | VSG60 + BB60C, LNA at 4.5 / 5.0 / 5.5 V on the board | 117 / 131 / 146 mA; gain +0.7 dB, OP1dB +15.4...+16.2 dBm, OIP3 +26...+28 dBm; 1.7 Ω feed drop |
| 2026-11-05 | [LNA noise figure](2026-11-05_lna-nf/report.md) | BB60C gain method, no output pad, 50 Ω load on the input | 2.6-4.1 dB (3.7 dB at 436 MHz); disagrees with the 2.0 dB chain NF by ~1.5 dB: Y-factor with a noise source next |
| 2026-11-05 | [LNA reverse isolation](2026-11-05_1053_lna-reverse-s12/report.md) | LNA reversed, VSG60 + BB60C | S12 -74...-79 dB in the passband, -84...-106 dB out of band, -44 dB at 900 MHz |
| 2026-11-05 | [RTL-SDR warm-up drift](2026-11-05_1148_rtl-drift-hub/report.md) | RTL-SDR V3 on a powered OTG hub, cold start, 90 min | 130 Hz (0.3 ppm) warm-up in 5 min at 436 MHz, then within ±8 Hz; plug in 5-10 min before AOS |
| 2026-11-05 | [SSTV Robot 36](2026-11-05_sstv-summary/report.md) | VSG60 -> LNA -> RTL-SDR -> Mi 10 (lab11), NFM 12.5 kHz | clean picture down to -132 dBm, usable at -134 dBm, VIS lost at -138 dBm |
| 2026-11-10 | [VSG60A straight into the BB60C](2026-11-10_1007_vsg-direct-0dbm/report.md) | VSG60A -> DC block -> BB60C | the two disagree by +2.6-2.8 dB on 70 cm (step at 325-350 MHz), 10 dB at 5.8 GHz; all levels here are BB60C-referenced |
| 2026-11-10 | [VSG60A swept against the SA44](2026-11-10_1110_vsg60a-sweep-sa44-sw205-cw/report.md) | VSG60A -> DC block -> SA44, software 2.0.5 | 125-340 MHz within 0.2 dB; **342-1700 MHz 2.6-4.1 dB low** (sharp edges at 341 and 1712 MHz); ARB = CW |
| 2026-11-10 | [VSG60A into the SA44 (third reference)](2026-11-10_1028_ref-compare-sa44/report.md) | VSG60A -> DC block -> SA44 | SA44 and BB60C agree within 0.3 dB on 70 cm; the VSG60A puts out ~2.7 dB less than set above ~340 MHz; levels in this repo (BB60C-referenced) stand |
| 2026-11-09 | [HackRF #1 calibrated 50 MHz - 6 GHz](2026-11-09_1400_hackrf1-cal-direct/report.md) | HackRF #1 -> DC block -> BB60C | 436.6 MHz: -47.8 dBm at TX VGA 0, -4.3 dBm max; amp broken; -0.71 ppm; full data in z2labs/hackrf_calibrations |
| 2026-11-09 | [Home chain loss 50 MHz - 6 GHz](2026-11-09_1115_path-cal-hackrf-chain-wide/report.md) | VSG60A -> chain -> BB60C | 69-83 dB; at 436.6 MHz the VSG says 72.8 dB, the HackRF straight vs through says 70.3 dB |
| 2026-11-09 | [VSG60A level with slow ARB waveforms](2026-11-09_1113_vsg-arb-level/report.md) | VSG60A -> chain -> BB60C | SSTV at 25-1000 kS/s within -0.3 dB of CW: lab SSTV levels are right |
| 2026-11-09 | [HackRF spurs around a tone](2026-11-09_1027_hackrf-spurs/report.md) | HackRF -> 72.8 dB -> BB60C | nothing within +-100 kHz down to ~-48 dBc: the +-36.6 kHz sidebands of the home panorama come from the receiver |
| 2026-11-09 | [HackRF calibrated on the BB60C](2026-11-09_1009_hackrf-cal-bb60c/report.md) | HackRF -> 30+30+10 dB + coax (72.8 dB) -> BB60C | -118.1 dBm at the LNA input at TX VGA 0; home HackRF levels of 11-07/08 were 1.8-2.1 dB too high (sensitivities ~2 dB better); amp broken; -0.80 ppm |
| 2026-11-08 | [Drift HackRF vs RTL-SDR, 7 h night](2026-11-08_2313_drift-hackrf-night3/report.md) | HackRF (TCXO) -> 70.5 dB -> LNA -> RTL-SDR V3 -> Mi 10 | median +33.6 Hz (+0.077 ppm), 14 Hz peak to peak; same as the first night within 0.2 Hz |
| 2026-11-08 | [CW decoder vs Doppler, tracking rework](2026-11-08_1421_doppler-hackrf-lab2-fresh/report.md) | HackRF -> 70.5 dB -> LNA -> RTL-SDR -> Mi 10 (beta12-lab2) | 13/15 OK from 0 to 200 Hz/s down to 32.5 dB-Hz; the earlier failures were stale looped chirps |
| 2026-11-07 | [9k6 G3RUH on beta 12: level and deviation](2026-11-07_2253_g3ruh-beta12/report.md) | HackRF -> 70.5 dB -> LNA -> RTL-SDR -> Mi 10 (v0.2.0-beta12) | 90 % frames: -110.8 / -114.7 / -117.1 dBm at 2 / 3 / 4.5 kHz deviation (NFM 20 kHz); 25 kHz filter 0.3-1 dB worse |
| 2026-11-07 | [APRS regression on beta 12](2026-11-07_2336_aprs-beta12/report.md) | as above | 90 % at about -119.3 dBm, unchanged |
| 2026-11-07 | [CW decoder vs Doppler ramp](2026-11-07_2342_doppler-hackrf/report.md) | as above | clean to 25 Hz/s down to 32 dB-Hz; the errors at 50-200 Hz/s were mostly a test artifact (frequency jump at the loop seam), see the correction |
| 2026-11-07 | [Two-tone in-band IM (HackRF)](2026-11-07_2352_twotone-hackrf/report.md) | as above, RTL gain 12.5 / 29.7 dB | ADC clips at about -85 / -105 dBm per tone; IM3 below that limited by the HackRF, real IIP3 needs the VSG |
| 2026-11-07 | [Drift, second night (aborted)](2026-11-07_2354_drift-hackrf-night2/report.md) | as above | +40 Hz for 4.5 min, then stale scheduled tasks took over the HackRF |
| 2026-11-07 | [9k6 G3RUH, retuned decoder](2026-11-07_1829_g3ruh-hackrf/report.md) | as above (lab22) | 90 % frames at about -114.8 dBm, 2.3 dB better; found with the phone's discriminator recorded over /fm |
| 2026-11-07 | [9k6 G3RUH frame success](2026-11-07_1624_g3ruh-hackrf/report.md) | HackRF -> 70.5 dB -> LNA -> RTL-SDR -> Mi 10 (lab20) | 90 % frames at about -112.5 dBm (NFM 20 kHz); about 5 dB short of the simulation |
| 2026-11-07 | [5 h drift, HackRF vs RTL-SDR](2026-11-07_0356_drift-hackrf-night/report.md) | HackRF CW -> LNA -> RTL-SDR -> Mi 10, 30 s readings | +33 Hz median (+0.08 ppm), 12 Hz peak to peak over 5 h |
| 2026-11-07 | [Home lab with a HackRF](2026-11-07_home-hackrf/report.md) | HackRF (receiver-transfer calibration) -> 70.5 dB -> LNA -> RTL-SDR -> Mi 10 | panorama: flat to +-58 kHz of 128 kHz, aliases near the edges; APRS 90 % at about -119 dBm (3 dB under the lab: home floor); SSTV 12 dB worse than the lab: lab SSTV levels suspect |
| 2026-11-06 | [Terrestrial APRS field log](2026-11-06_1635_aprs-ground/report.md) | RTL-SDR on a 2 m antenna at a window, Mi 10, 144.800 MHz | 12 frames / 4 stations in 15 min, positions 4-44 km on the map; Mic-E positions added after it |
| 2026-11-06 | [Decoders on SatNOGS recordings](2026-11-06_satnogs-vectors/report.md) | real satellite audio (ISS, PCSAT, 68795, RS18S) | AFSK: 2/29/21 frames vs SatNOGS 2/24/15; RS18S Robot 36 picture decoded that SatNOGS lost |
| 2026-11-06 | [SSTV Robot 36 limit, lab15](2026-11-06_0941_sstv-robot36-lab15/report.md) | VSG60 -> LNA -> RTL-SDR -> Mi 10 (lab15, sync re-acquisition) | recognisable picture down to -136 dBm (error 40, was 94 on lab11); VIS lost at -137 dBm |
| 2026-11-06 | [SSTV PD120](2026-11-06_0832_sstv-pd120/report.md) | VSG60 -> LNA -> RTL-SDR -> Mi 10 (lab12) | every picture decoded down to -134 dBm, mean error 4.3 (-110 dBm) ... 19.9 (-134 dBm) |
| 2026-11-05 | [Decoder plugins live](2026-11-05_1425_plugins-live/report.md) | APRS from the VSG60, lab11 | 38 frames -> 76 plugin outputs (text + map pin), no errors; plugin runtime ships in the APK |

## Planned

- APRS: an IQ-domain (coherent) AFSK detector for several more dB.
- BB60C check of the VSG60 absolute level (the last dB of the NF).
- Spacewalker LNA: Y-factor NF with a calibrated noise source; the source of the rare dropouts (LNA, supply, bias tee); S11/S22 need a VNA or coupler.
- Simulated satellite pass with Doppler.
