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

- Up to 25 Hz/s the decoder copied perfectly down to 32 dB-Hz; at 50-100 Hz/s it lost single characters,
  at 200 Hz/s it fell apart. The level hardly mattered.
- **Correction (2026-11-08):** most of these failures were the test, not the decoder. The waveform was one
  chirp looped, so at every loop seam the tone jumped back by the whole sweep (692 Hz at 50 Hz/s, 1384 Hz at
  100 Hz/s), and every error sits on the first letter after the seam ("TEST UVV"). At 200 Hz/s the sweep
  (2.8 kHz) also ran out of the 2 kHz CW filter. The reported drift (one tenth of the ramp) is the fit over
  that sawtooth. Offline with a continuous ramp the old decoder copied 100 Hz/s at 10 dB in 100 Hz, but lost
  letters at 150-200 Hz/s and below 8 dB.
- Fixed since: the decoder sums each 0.5 s block along drift lines up to 400 Hz/s and extrapolates the tone
  along the end slope (`sh-dsp/src/cw.rs`, test `follows_uncorrected_doppler`); the lab chirp now ramps up
  and down (no jump at the seam) and the CW filter is 3 kHz. To be measured again with the HackRF.
