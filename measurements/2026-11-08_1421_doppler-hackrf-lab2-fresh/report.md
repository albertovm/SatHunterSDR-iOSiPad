# CW decoder against Doppler ramps, after the tracking rework (HackRF, lab2)

> **Level correction (2026-11-09):** the HackRF levels in this report are 1.8-2.1 dB too high; the BB60C calibration ([2026-11-09_1009](../2026-11-09_1009_hackrf-cal-bb60c/report.md)) shows the signal at the LNA was weaker, so sensitivities are about 2 dB better than written here.

2026-11-08 14:21, SatHunterSDR v0.2.0-beta12-lab2 on the Mi 10. Chain: HackRF -> 30+30+10 dB -> 1 m coax ->
Spacewalker LNA -> RTL-SDR V3 (gain 12.5 dB). Levels at the LNA input. Keyed CW "VVV DE HG0LAB TEST" at
15 WPM, CW filter 3 kHz. The tone ramps up through one copy of the text and down through the next, so the
looped waveform has no frequency jump; the run counts as OK when one full copy comes out right.

| Ramp | Sweep per copy | -130 dBm (39 dB-Hz) | -135 dBm (35 dB-Hz) | -138 dBm (32.5 dB-Hz) |
|---|---|---|---|---|
| 0 Hz/s | 0 | OK | OK | OK |
| 50 Hz/s | 692 Hz | OK | OK | OK |
| 100 Hz/s | 1384 Hz | OK | OK | OK |
| 150 Hz/s | 2076 Hz | OK | OK | 2 letters wrong |
| 200 Hz/s | 2768 Hz | first letter of a copy wrong | OK | OK |

**13 of 15 OK.** The two misses are single letters, and the first dot of "VVV" right after the turn of the
ramp (where the tone reverses at 150-200 Hz/s) is often lost ("TVV"). A real pass has no such turn: the
Doppler rate keeps its sign through the whole pass. So the decoder now copies uncorrected 70 cm Doppler
(up to about 170 Hz/s at TCA on an overhead 500 km pass) down to about 32 dB-Hz.

What changed in the decoder (`sh-dsp/src/cw.rs`): each 0.5 s block is summed along drift lines up to
+-400 Hz/s instead of straight down; between two tone readings the blocks' own drift lines are blended (a
chord between block centres cut the corner); past the ends the tone follows the chord of the outer
readings. Offline tests: `follows_uncorrected_doppler` (+-150 Hz/s at 8 dB in 100 Hz, +-200 Hz/s at 10 dB)
and `follows_a_turning_drift`.

## Runs that do not count

- [2026-11-07_2342](../2026-11-07_2342_doppler-hackrf/report.md) (beta 12): a single chirp looped, so the tone
  jumped back by the whole sweep at every seam.
- [2026-11-08_0959 lab1](../2026-11-08_0959_doppler-hackrf-lab1/results.json) and
  [2026-11-08_1350 lab2](../2026-11-08_1350_doppler-hackrf-lab2-stale/results.json): the HackRF client cached
  waveform files by name only, so 50, 100 and 200 Hz/s still played the old jumping chirps (only 150 Hz/s was
  new, and it passed in both). The cache key now includes the waveform's checksum (`hackrf_gen.py`). The
  error at 50-100 Hz/s ("TESE UVV") was that seam every time.
- Because of this the phone run cannot separate the two decoder changes (lab1: drift lines; lab2: blended
  lines at turns); the offline test `follows_a_turning_drift` fails without the lab2 change.
