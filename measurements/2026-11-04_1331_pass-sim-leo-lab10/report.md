# Simulated LEO pass (STARS, 61°): not valid at the closest point — a generator limit

Runs: 2026-11-04 12:53, 13:08 and 13:31 (this folder), `tools/lab/pass_sim.py --norad 33498`, STARS
(437.274 MHz, ~600 km orbit, Doppler ±10.2 kHz, up to 118 Hz/s). Same setup as the
[COSMOS 2491 pass](../2026-11-04_1204_pass-sim/report.md); the last run with v0.2.0-beta10-lab10.

Result: CW decoded complete at low elevation in every run; around the closest point (elevation above
~35°) most decodes failed (11 of 19 OK in this run).

## Why: the VSG60 cannot follow fast Doppler over SCPI

Found with `steptest.py` and `tunetime.py` (2026-11-04, phone VFO fixed, keyed CW at -130 dBm):

| Generator retuning | Result |
|---|---|
| `:SOURce:FREQuency` + `*OPC` (as `pass_sim` did) | each retune takes **13.5 s**: `*OPC` waits for the end of the 13.8 s ARB period |
| frequency write + query, ~3 times a second | every write interrupts the output: CW undecodable **even when the frequency does not change** |
| no retune | decoded |

So in the pass runs the VSG moved only every 13.5 s: in 1.6 kHz jumps at 118 Hz/s (out of the 2 kHz CW
filter half of the time), in 530 Hz jumps for COSMOS 2491 at 39 Hz/s (inside the filter: that pass
decoded). The failures at the closest point are the generator, not the phone. The phone's own tracking
(VFO against its orbit model) stayed within ±13 Hz in all runs.

## What it changed

- v0.2.0-beta10-lab10 makes the phone's VFO glide at the Doppler rate between its 200 ms control ticks
  (before: steps of up to 24-35 Hz at a LEO's closest point). Useful anyway; not verified by this test.
- `Vsg60Gen.tune` no longer waits for `*OPC`.

## How to test a fast pass properly

Put the Doppler in the waveform instead of retuning: compute the ±60 s around the closest point with an
independent SGP4 (the satellite's TLE, the phone's station and its simulated pass time), write it as one
ARB file (~3 M samples at 25 kS/s) and start it with a trigger at the right moment. The CW chirp test
([Doppler CW](../2026-11-02_1424_doppler/report.md)) already shows the decoder follows 100 Hz/s.
