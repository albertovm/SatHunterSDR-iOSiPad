# Home attenuator chain, 50 MHz - 6 GHz

2026-11-09 11:15, `path_cal.py --level 0`, VSG60A -> 30+30+10 dB + 1 m coax -> BB60C. Loss 69.0-70.5 dB up
to 300 MHz, 72.5-74 dB from 350 MHz to 1.25 GHz (a step of about 3 dB between 300 and 350 MHz, most likely an
instrument band edge), 72-75 dB to 2.75 GHz, 77 dB at 3-3.75 GHz, 82-83 dB at 5.5-6 GHz.

These are VSG60A set level minus BB60C reading; at 436.6 MHz the HackRF measured straight and through the
chain gives 70.3 dB instead of 72.8 dB ([see](../2026-11-09_1400_hackrf1-cal-direct/report.md)).
