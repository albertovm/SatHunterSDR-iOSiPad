# Terrestrial APRS field log

First field test of the terrestrial APRS mode (0.2.0-beta11): RTL-SDR V3 straight on a 2 m antenna at a window in
Budapest (no LNA, bias tee off), Mi 10, 144.800 MHz NFM 12.5 kHz. The phone decodes, the lab link logs.

Run: 2026-11-06 16:35, 15 min (stopped early), `tools/lab/aprs_log.py`, source rtl, 144.800 MHz NFM, gain 40.1 dB, decimation 8.

| | |
|---|---|
| Frames (good CRC) | 12 (48 per hour) |
| Stations heard (source calls) | 4 |
| Heard direct / via a digipeater | 5 / 7 |
| Bad-CRC flags (noise and broken frames) | 415 |
| Signal level (channel), median / max | -53.1 / -52.4 dB |
| Dropped blocks | 0 |

![Timeline](timeline.png)

## Packet types

| Type | Frames |
|---|---|
| position (time) | 6 |
| telemetry | 5 |
| Mic-E | 1 |

## Stations

| Station | Frames | Position | Distance, bearing |
|---|---|---|---|
| HG5PBP-1 | 5 | 47.4938, 18.9875 | 4.3 km, 239° |
| HG4HNA-1 | 4 | 47.2585, 18.5968 | 43.6 km, 230° |
| HG7PDK-2 | 2 | 47.7187, 18.8918 | 25.2 km, 335° |
| HA5UDS-7 | 1 | - | - |

## Digipeaters (frames repeated by)

| Digipeater | Frames |
|---|---|
| HG5PBP-1 | 7 |
| WIDE1 | 1 |

![Positions](map.png)

All frames: [frames.jsonl](frames.jsonl); receiver status every 5 s: [status.csv](status.csv).

## Findings

1. The terrestrial mode works end to end: 12 frames from 4 stations in 15 min, 3 of them with positions on the map
   (the local iGate/digipeater HG5PBP-1 at 4 km, HG7PDK-2 at 25 km and HG4HNA-1 at 44 km, the last two
   relayed by HG5PBP-1).
2. HA5UDS-7 sent a **Mic-E** report, which the app did not place on the map: Mic-E keeps the latitude in the
   destination address (`TWSS85`). Fixed after this run: `mic_e_position()` in the engine and in the plugin
   runtime (`aprs.position(info, dst)`), test with this frame; it decodes to 47.5642 N, 19.1052 E.
3. Traffic is light at this location (48 frames per hour, mostly the digipeater's own beacons and telemetry);
   the bad-CRC count (415) is the HDLC flag detector triggering on noise, not lost frames.
