# Thru check: VSG60A + BB60C without the LNA (dropouts, generator two-tone IMD)

Run: 2026-11-05 08:56-09:12, `tools/lab/thru_check.py`. Path: VSG60A - 20 dB - long coax - bias tee (no DC) -
30 dB - BB60C, the LNA taken out (the coax goes straight into the bias tee; no barrel, about 0.1 dB).
Raw data: [results.json](results.json).

## Results

| Test | Result |
|---|---|
| Level dropouts, CW 436 MHz at +6 dBm, 10 min | **0 of 5027 readings**; level -49.11 dBm at the BB60C, 0.12 dB peak to peak |
| VSG60A two-tone IM3, 20 kHz - 4 MHz spacing, set level -12 ... +2 dBm | **-53 ... -59 dBc** |
| same, set level +4 ... +8 dBm | -52 ... -47 dBc (rises with level) |
| same, set level -20 ... -14 dBm | -48 ... -53 dBc: **analyser floor** (IM3 at about -130 dBm), upper bounds only |

## What it means for the LNA results

- **Dropouts.** Without the LNA, and without DC on the bias tee, the generator and the analyser never
  dropped out in 5027 readings. The dropouts seen with the LNA (1 in 315 readings in the stability run,
  and in compression sweeps, often at the highest drive) therefore come from the LNA side: the LNA
  itself, its supply, or the bias tee's DC path / connectors. To check next: the supply in constant
  voltage mode with margin on the current limit, the bias-tee DC connection, and a dropout watch with
  the LNA powered directly.
- **Generator IMD.** In the LNA two-tone runs the generator was set to (input per tone + 6 dB + 24.3 dB
  input loss): at -40 dBm per tone that is -10 dBm, where the VSG60A makes about -56 dBc of IM3 itself.
  The LNA's own IM3 there is about -42 dBc, so the generator moves the LNA's IIP3 by up to ±0.8 dB. At
  -50 ... -46 dBm per tone both are -50 ... -55 dBc and the generator dominates, which is why the LNA's IM3
  slope was under 3 at low drive. **The LNA's IIP3 is best read at -36 ... -32 dBm per tone**, where the
  LNA's IM3 is 25-35 dB above the generator's: -18.4 ... -17.5 dBm at 436 MHz.
- The lower IIP3 at 1 and 4 MHz spacing (-21.8, -25.0 dBm at -40 dBm per tone) is **not** explained by the
  generator: its IM3 is the same at all spacings (-55 ... -59 dBc). It is a property of the LNA's cascade
  (IM3 products of the first stage fall inside the following SAW's passband and add with the second
  stage's), measured on top of the passband ripple.
