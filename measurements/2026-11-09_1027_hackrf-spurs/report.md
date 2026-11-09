# Are the +-36.6 kHz sidebands in the HackRF's output?

2026-11-09 10:27, G7, `tools/lab/hackrf_spurs.py --atten 72.8`. HackRF -> 30+30+10 dB + 1 m coax -> BB60C.
CW at 436.6 MHz (250 kHz above the HackRF's LO, as in every home run), TX VGA 0/20/40 and digital scale
1/0.3/0.1. BB60C trace +-100 kHz, RBW 100 Hz, 5 sweeps max-hold; a spur is any peak 15 dB over the floor.

| TX VGA | Scale 1.0 | 0.3 | 0.1 |
|---|---|---|---|
| 0 | -122.5 dBm* | -130.0 dBm | -138.0 dBm |
| 20 | -97.4 dBm | -107.7 dBm | -116.7 dBm |
| 40 | -79.1 dBm | -89.4 dBm | -98.7 dBm |

No spur anywhere in +-100 kHz at any setting. Floor -143 dBm per 100 Hz, so with the tone at -79 dBm
anything above about -48 dBc would have shown. The home panorama
([2026-11-07 home lab](../2026-11-07_home-hackrf/report.md), [pano sweep](../2026-11-07_0249_pano-sweep/report.md)) saw sidebands at +-36.6 kHz at about -40 dBc:
**they are not in the HackRF's output, so the receiver (RTL-SDR, phone DSP or the display) makes them.**
Next: look for them with the VSG60 on system A, and in the RTL-SDR IQ before the phone's DSP.

The digital scale is accurate even at the bottom: 0.3 and 0.1 give -10.3 and -19.3 dB at TX VGA 20, and
-138.0 dBm at TX VGA 0 / scale 0.1 is 20 dB under the calibration's -118.1 dBm. *The first point after
the start read 4 dB low (not settled yet).
