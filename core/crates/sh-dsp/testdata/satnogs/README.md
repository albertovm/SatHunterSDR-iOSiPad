# SatNOGS test vectors

Real satellite recordings from the [SatNOGS network](https://network.satnogs.org): the station's demodulated
audio (Ogg Vorbis, 48 kHz mono), cut to the part with the signal (`ffmpeg -ss ... -to ... -c copy`, no re-encoding).
SatNOGS observation data is published under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/);
credit to the station owners named below. Tests: [tests/satnogs.rs](../../tests/satnogs.rs).

| File | Observation | Satellite, downlink | Station | Cut (s from start) | What the station's own decoder got | SatHunterSDR |
|---|---|---|---|---|---|---|
| `satnogs_15339570_iss_afsk1200.ogg` | [15339570](https://network.satnogs.org/observations/15339570/) | ISS, 437.825 MHz AFSK1200 | DB0RBX | 222-242 | the RS0ISS beacon | the beacon (only with the merged detectors) |
| `satnogs_15372907_68795_afsk1200.ogg` | [15372907](https://network.satnogs.org/observations/15372907/) | NORAD 68795, 437.505 MHz AFSK1200 | JA1HCB-pi3 | 26-92 | 8 frames in this cut, 24 in the pass | 7 in this cut, 29 in the pass (5 with the discriminator alone) |
| `satnogs_15370705_pcsat_afsk1200.ogg` | [15370705](https://network.satnogs.org/observations/15370705/) | PCSAT (26931), 144.39 MHz APRS | KI5YNG | 80-150 | 3 frames in this cut, 15 in the pass | 2 in this cut, 21 in the pass |
| `satnogs_15332613_rs18s_robot36.ogg` | [15332613](https://network.satnogs.org/observations/15332613/) | RS18S (67290), 437.35 MHz SSTV | PE0SAT-21 | 205-248 | picture lost (noise) | the whole Robot 36 picture, 157 line syncs |
| `satnogs_15370627_57175_g3ruh9k6.ogg` | [15370627](https://network.satnogs.org/observations/15370627/) | NORAD 57175, 9k6 G3RUH FSK, AX.25 | Piszkesteto UHF | 225-320 | 6 frames | 6 AX.25 frames |
| `satnogs_15388314_98914_g3ruh9k6.ogg` | [15388314](https://network.satnogs.org/observations/15388314/) | NORAD 98914, 9k6 G3RUH FSK (HDLC, not AX.25) | UX5UL | 240-345 | 6 frames | 6 frames |
| `satnogs_15383314_98193_g3ruh9k6.ogg` | [15383314](https://network.satnogs.org/observations/15383314/) | NORAD 98193, 9k6 G3RUH FSK | Swallowview | 365-450 | 12 frames | 6 (the case to improve) |
| `phone_fm_g3ruh9k6_114dBm.ogg` | lab, not SatNOGS | HackRF 9k6 G3RUH lab frames, -114 dBm at the LNA input | the phone's own discriminator (`/fm`, 64 kHz), Vorbis q8 | 0-12 | - | 66 of 77 frames (75 from the original WAV) |

Whole passes, 9k6 (unique frames, ours / station's, every one of ours also in the station's list): 57175 23 / 22,
98914 28 / 29, 98193 5 / 26.

Whole passes (not stored here): SatNOGS's decoder found 2 / 24 / 15 frames, SatHunterSDR 2 / 29 / 21, and every
frame SatNOGS found on ISS and PCSAT, 22 of its 24 on 68795.
