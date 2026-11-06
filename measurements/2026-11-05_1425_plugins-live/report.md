# Decoder plugins live: APRS from the VSG60 through the Luau plugins

Run: 2026-11-05 14:25, [plugcheck.py](plugcheck.py), SatHunterSDR v0.2.0-beta10-lab11 (the first build that ships
`libc++_shared.so` and runs the Luau plugins inside the engine). The VSG60A plays the lab APRS waveform (AFSK1200,
3 kHz deviation) at -105 dBm on 436.6 MHz for 40 s; NFM 12.5 kHz; APRS decoder and plugins on; no ISS selected, so the
generic `aprs-map` plugin applies (with the ISS selected, `iss-aprs` takes over). Raw data: [results.json](results.json).

| | |
|---|---|
| APRS frames decoded | 38 (1 bad CRC) |
| Plugins loaded | `iss-aprs`, `aprs-map`; no load or run errors |
| Plugin output | 76 lines: a text line and a map pin for every frame |
| Example | `HG0LAB-1 > APRS via WIDE1-1: !4729.87N/01902.41E>SatHunter lab packet 05`, `map 47.497833 19.040167 HG0LAB-1` |

The app started normally with the plugin runtime linked in (the lab7 start crash, a missing `libc++_shared.so`, does
not return: the CI now checks that every ABI in the APK carries it).
