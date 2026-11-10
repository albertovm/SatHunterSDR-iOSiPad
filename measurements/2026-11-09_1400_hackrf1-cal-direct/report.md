# HackRF #1 calibrated 50 MHz - 6 GHz, straight into the BB60C

2026-11-09 14:00-14:48, G7. HackRF #1 (sticker "#1", serial 0000000000000000308066e62240564b, clone with
TCXO) -> SMA adapter - 100 pF DC block - SMA adapter -> BB60C. `hackrf_cal.py --atten 0`, 44 frequencies,
TX VGA 0/10/20/30/40/47, amp off and on, each reading repeated until two agree within 0.3 dB.

The full calibration (table, plot, per-frequency `hackrf_cal.json` referred to the SMA) is kept with the
unit in the private repo **z2labs/hackrf_calibrations**, folder `hackrf_id1`. In short:

- 436.6 MHz: -47.8 dBm at TX VGA 0, -4.3 dBm at TX VGA 47; 0.98 dB per dB of TX VGA.
- 50-800 MHz: -4 ... -8 dBm max; 900-2000 MHz falling to -19 dBm; 2.25-2.5 GHz up to +4.7 dBm (mixer
  bypassed); 2.75-5 GHz about -20 dBm; 6 GHz -34 dBm.
- RF amplifier broken: 20-40 dB less output with it on, at every frequency.
- -0.71 ppm against the BB60C; no drift in 5 minutes after hours of streaming.

**Chain loss, two ways:** at TX VGA 0 the SMA gives -47.8 dBm and the home chain's output read -118.1 dBm,
so the chain loses 70.3 dB on the BB60C alone; the VSG60A path calibration said 72.8 dB. The VSG60A's set
level thus reads about 2.5 dB lower on the BB60C (VSG60A or BB60C absolute error at these levels). The home
HackRF levels are not affected (they are referred to the BB60C at the chain output); lab levels set with the
VSG60A through VSG-calibrated paths are not affected either (the error cancels). To settle which instrument
is off: VSG60A straight into the BB60C at 0 dBm and at -60 dBm.

[Earlier wideband run through the chain](../2026-11-09_1300_hackrf1-cal-wide-hi/results.json) (and its
[first half, log only](../2026-11-09_1126_hackrf1-cal-wide/run.log)): superseded by this one; some low-TX-VGA
points there read the previous setting's level, which led to the read-until-stable change in hackrf_cal.py.
