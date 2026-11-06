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

Whole passes (not stored here): SatNOGS's decoder found 2 / 24 / 15 frames, SatHunterSDR 2 / 29 / 21, and every
frame SatNOGS found on ISS and PCSAT, 22 of its 24 on 68795.
