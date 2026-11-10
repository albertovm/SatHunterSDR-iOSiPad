# VSG60A level with slow ARB waveforms

2026-11-09 11:13, `tools/lab/vsg_arb_level.py --atten 72.8`. VSG60A -> home chain (30+30+10 dB + 1 m coax)
-> BB60C, 436.6 MHz, set level -90 dBm at the chain output, BB60C 30 kHz RBW (holds the whole FM signal),
3 readings each.

| Waveform | ARB rate | Read | Error |
|---|---|---|---|
| CW | 100 kS/s | -90.33 dBm | -0.33 dB |
| Robot 36 SSTV, 3 kHz FM | 25 kS/s | -90.29 dBm | -0.29 dB |
| same | 50 kS/s | -90.30 dBm | -0.30 dB |
| same | 100 kS/s | -90.30 dBm | -0.30 dB |
| same | 1000 kS/s | -90.31 dBm | -0.31 dB |
| FM tone 1900 Hz | 25 kS/s | -90.30 dBm | -0.30 dB |

The VSG60A puts out the same level at every ARB rate, so **the lab SSTV levels are right**; the home SSTV
runs that came out about 10 dB worse (12 dB before the [HackRF level correction](../2026-11-09_1009_hackrf-cal-bb60c/report.md))
need another explanation. Suspects: the HackRF client's waveform cache (it was keyed on the name only until
2026-11-08, so an older SSTV waveform may have played) and the HackRF's resampling of the 25 kS/s waveform.
Next: repeat the home SSTV run with the fixed cache.
