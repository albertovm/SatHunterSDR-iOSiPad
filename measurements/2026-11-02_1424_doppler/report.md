# CW decoding under a Doppler ramp

Run: 2026-11-02 14:24-14:34, `tools/lab/rx_extra.py --part doppler`, SatHunterSDR v0.2.0-beta10-lab5.
Chain as in [System A2](../2026-11-02_1044_system-a2-mds/report.md); CW mode, 2 kHz filter, RTL gain 12.5 dB,
1.024 MS/s / 8. The keyed message "VVV DE HG0LAB TEST" (15 WPM, 13.8 s) is played with a linear frequency
ramp centred on the VFO (zero in the middle of the message, sawtooth when the waveform repeats). No TLE
tracking: the ramp stands for the uncorrected Doppler rate. For reference, a 500 km pass at 437 MHz has up
to about 170 Hz/s at the closest point; with TLE tracking only a few Hz/s remain.

| Ramp | Sweep per message | -130 dBm (C/N0 ~43 dB-Hz) | -138 dBm (C/N0 ~35 dB-Hz) |
|---|---|---|---|
| 0 Hz/s | 0 Hz | OK | OK |
| 10 Hz/s | 138 Hz | OK | OK |
| 25 Hz/s | 346 Hz | OK | OK |
| 50 Hz/s | 692 Hz | OK | OK |
| 100 Hz/s | 1384 Hz | OK | OK |
| 170 Hz/s | 2353 Hz | partial: the ends of the sweep fall outside the 2 kHz filter ("V DE HG0LAB T.ST") | partial |

OK = "VVV DE HG0LAB TEST" decoded complete (the first character of each copy is cut by the decode window).
Levels at the LNA input (attenuation calibrated 34.7 dB).

## Findings

1. The CW decoder follows ramps up to at least 100 Hz/s without loss, at 35 dB-Hz too: even an
   untracked pass decodes except for the few seconds around the closest point.
2. At 170 Hz/s the message runs out of the 2 kHz filter, not out of the decoder's tracking: with TLE
   tracking the residual is far below this; without it a wider CW filter (3-4 kHz) would cover it.
3. The decoder's drift estimate (`drift_hz_s` in the JSON) reads about 1/15 of the ramp here. That is the
   test signal, not the decoder: the estimate is a straight-line fit over the 31 s decode window, and the
   waveform jumps back every 13.8 s (sawtooth), so the fit sees little net slope. A real pass is monotonic.

## Notes on the method

- The VSG software (v6, SCPI) crashes after loading two or three long ARB waveforms in a row (1.4 M samples
  at 100 kS/s, and again at 25 kS/s): `tools/lab` restarts the VSG software between waveforms for this test.
  Stopping a SCPI client in the middle of a session also stops the SCPI server.
- Earlier attempts on the same afternoon failed at every level, even at -110 dBm, while the laptop driving
  the VSG60 was fully loaded by an unrelated build (8 compile jobs). The VSG60 is fed over USB; the keying
  came out broken (decoded at 29 WPM, letters T and E). With the laptop idle, the same waveform decodes to
  -138 dBm. Run VSG60 measurements on an idle PC.
