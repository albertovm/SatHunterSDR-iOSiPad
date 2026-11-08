# CW decoder against a Doppler ramp (HackRF)

2026-11-07 23:42, same chain as the [9k6 run](../2026-11-07_2253_g3ruh-beta12/report.md), beta 12. Keyed CW
"VVV DE HG0LAB TEST" at 15 WPM whose frequency ramps linearly, CW filter 2 kHz. A run counts as OK when the
whole text comes out right.

| Ramp | -130 dBm (C/N0 39 dB-Hz) | -135 dBm (35 dB-Hz) | -138 dBm (32 dB-Hz) |
|---|---|---|---|
| 0 Hz/s | OK | OK | OK |
| 10 Hz/s | OK | OK | OK |
| 25 Hz/s | OK | OK | OK |
| 50 Hz/s | OK | 1 letter wrong | OK |
| 100 Hz/s | 1 letter wrong | 1 letter wrong | 1 letter wrong |
| 200 Hz/s | broken | broken | broken |

- Up to 25 Hz/s the decoder copies perfectly down to 32 dB-Hz; at 50-100 Hz/s it loses single characters,
  at 200 Hz/s it falls apart. The level hardly matters: the limit is tracking speed, not the signal.
- Uncorrected Doppler on 437 MHz changes by up to about 170 Hz/s at TCA on an overhead 500 km pass
  (f v^2 / (c h)), lower on low passes, so CW needs TLE tracking on (residual drift then stays well below 10 Hz/s). Worth adding faster tracking of the CW tone in
  the decoder for passes without TLE.
