# APRS 1200 bd regression on the release build (beta 12)

2026-11-07 23:36, same chain as the [9k6 run](../2026-11-07_2253_g3ruh-beta12/report.md), 3 kHz deviation,
NFM 12.5 kHz, 30 s per level (about 29 packets).

| Level | -110 ... -119 dBm | -120 dBm | -121 dBm | -122 dBm | -124 dBm |
|---|---|---|---|---|---|
| Packets | 100 % | 66 % | 69 % | 7 % | 0 % |

90 % at about -119.3 dBm: the same as the beta 11 home run (about -119 dBm,
[2026-11-07_home-hackrf](../2026-11-07_home-hackrf/report.md)). No regression from the 9k6 work.
