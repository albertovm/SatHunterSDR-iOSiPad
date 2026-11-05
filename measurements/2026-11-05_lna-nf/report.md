# Spacewalker LNA 434 MHz v1.4: noise figure (BB60C gain method)

Runs 2026-11-05 10:23-10:47, LNA at 5.0 V / 131 mA on the board:

| Run | Setup | What it gives |
|---|---|---|
| [lna-nf-nopad](../2026-11-05_1023_lna-nf-nopad/results.json) | VSG60 (RF off) - 20 dB - coax - LNA - bias tee - BB60C, **no output pad**; also a 5 min gain watch | output noise density, tone gain through the same path |
| [input-path-cal](../2026-11-05_1031_input-path-cal/results.json) | VSG60 - 20 dB - coax - BB60C | input-side loss: **23.2-23.7 dB** (23.68 dB at 436 MHz) |
| [vsg-off-noise](../2026-11-05_1032_vsg-off-noise/results.json) | same, VSG RF off | the BB60C's own floor: -163 dBm/Hz |
| [lna-noise-50ohm](../2026-11-05_1046_lna-noise-50ohm/results.json) | **50 Ω load** - LNA - bias tee - BB60C | output noise density with a clean 290 K source |

Method: NF = N_out - P_out + P_in + 174 dBm/Hz, where N_out is the output noise density with the input
terminated (BB60C, power-averaged, 10 kHz flat-top RBW, its own floor subtracted), and P_out - P_in is the
gain of a -60 dBm tone measured through exactly the same output path (bias tee, cable, BB60C), so the
output-side loss cancels. P_in comes from the measured input path (VSG60 - 20 dB - coax, read on the BB60C).

## Results

| MHz | Output noise over the BB60C floor | NF, VSG60 (RF off) + 20 dB on the input | NF, 50 Ω load on the input |
|---|---|---|---|
| 430 | 41 dB | 2.8 dB | **2.6 dB** |
| 433 | 43 dB | 3.6 dB | **3.0 dB** |
| 436 | 38 dB | 3.6 dB | **3.7 dB** |
| 439 | 42 dB | 3.5 dB | **3.5 dB** |
| 441 | 41 dB | 4.2 dB | **4.1 dB** |

Gain during the run: 46.06 dB at 436 MHz (with the output-side assumption of this run), constant within
±0.01 dB over 5 minutes, no dropouts.

## Findings and open question

1. With the 50 Ω load the result is the same as with the generator on the input (within 0.5 dB): the
   VSG60's output noise with RF off does not affect the measurement.
2. By this method the LNA's NF is **2.6-4.1 dB** in 430-441 MHz, 3.7 dB at 436 MHz. It is highest where the
   gain is lowest (the 436 MHz ripple dip), consistent with loss in front of the first transistor (the first
   SAW) that varies across the band.
3. **This disagrees with the 2.0 dB system NF** measured on 2026-11-02 with the phone
   ([System A](../2026-11-02_1028_system-a/report.md)): the LNA alone cannot be noisier than the chain it
   leads. One of the two absolute references is off by about 1.5 dB: here the BB60C's noise-density reading
   (detector, flat-top noise bandwidth, its amplitude accuracy), there the VSG60's absolute level at
   -120...-140 dBm through 80 dB of attenuation. Neither instrument is a noise-figure reference.
4. **Next: a Y-factor measurement with a calibrated noise source** (ENR table) on the BB60C or the phone
   settles the absolute value. Until then the LNA's NF is quoted as **2-4 dB** (2.0 dB from the chain
   measurement, 2.6-4.1 dB from this one).

The [earlier estimate](../2026-11-04_1556_lna-extra/report.md) through the 30 dB output pad (1.7-3.0 dB) used
an assumed input loss 0.6-1.2 dB too high; corrected, it agrees with the values above.
