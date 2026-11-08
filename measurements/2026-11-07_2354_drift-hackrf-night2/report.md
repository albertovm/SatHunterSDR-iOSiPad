# Drift HackRF vs RTL-SDR, second night (aborted)

Started 2026-11-07 23:54 for 4 h, readings every 30 s. Only the first 4.5 minutes are valid: offset
+37.7 ... +42.0 Hz (median about +40 Hz), the same as the [first night](../2026-11-07_0356_drift-hackrf-night/report.md)
(+33 Hz median, 12 Hz peak to peak).

At 23:59 the one-shot scheduled tasks from the earlier home-lab runs (HackRFServer, PanoSweep,
NightHackRF, DriftNight, G3ruhRun, FmRec) all fired at once: they had been created with `/SC ONCE /ST 23:59`
on the same day, which Windows treats as tonight, not as "never". They retuned the phone and the HackRF, the
measurement lost the carrier (SNR 52 -> 1 dB) and stopped with an out-of-span error at 00:05. Their output
folders (2026-11-07_2359_*, 2026-11-08_0011_*, 0021_*) are mixed signals and were not kept. Lesson for the
lab scripts: create scheduled tasks with a start time in the past, or delete them after use.
