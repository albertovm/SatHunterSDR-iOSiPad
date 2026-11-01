# Field measurements

Recordings decoded with `cargo run --release -p sh-dsp --example cw_decode -- audio.f32`
(audio from a screen recording: `ffmpeg -i rec.mp4 -vn -ac 1 -ar 48000 -f f32le audio.f32`).

## 2026-11-01 10:41 local, ITUPSAT 1, 70 cm CW beacon

Setup: 6-element 70 cm Yagi (no rear reflector), SkywalkerLNA (bias tee on), RTL-SDR v3,
Xiaomi 10 Pro, app with Doppler tracking on, USB 2.8 kHz, max elevation ~19 deg.

| | |
|---|---|
| Decoded | `(1)KS ITUPSAT HR` · ~1 s carrier · `E` · `TA1KS ITUPS(AT…)` (fade-out at the end) |
| Speed | 12.2 WPM (dot 98 ms); letter gaps ~3.7 units, word gaps ~11 units |
| Signal | 21 dB over the noise in 105 Hz, C/N0 about 41 dB-Hz (lower bound: measured after the app's audio AGC and the recorder's AAC) |
| Offset | the beat tone 2325 Hz at the start (USB): the carrier 2.3 kHz (5.3 ppm) above the tracked frequency. An RTL-SDR v3 TCXO is within ~1 ppm, so most of it is the satellite's transmitter offset and / or the TLE |
| Residual drift | 2325 -> 2219 Hz in 30 s, -2.2 Hz/s on average (-3.7 Hz/s in the first 15 s): the predicted Doppler slope is a little off (TLE age); the tracker's offset (drag the VFO onto the trace) takes care of the constant part |
| Display | the beacon was right under the VFO line on the waterfall (fixed: the line is faint there now) |

## Recording IQ for analysis

The red dot next to the play button records what the receiver gets (after decimation) as a
2-channel 16-bit WAV with an SDR++ style name (`baseband_<Hz>Hz_<time>_<date>.wav`); Android 10+
saves into Downloads/SatHunter. A JSON chunk in the file keeps the receiver settings, the
selected satellite and transmitter, the station and every retune.

Analyse a recording (spectrum, carriers, CW at the VFO, waterfall image):

    cargo run --release -p sh-engine --example iq_analyze -- baseband_....wav [vfo_hz] [waterfall.pgm]

/8 decimation keeps the files small: 300 kS/s = 1.2 MB/s (a 10-minute pass: ~720 MB);
the full 2.4 MS/s is 9.6 MB/s.

## 2026-11-01 11:44 UTC, CUBEBUG-2 (LO-74) AFSK1200 + a second signal, IQ recording

`baseband_437246965Hz_11-44-52_01-11-2026.wav`: 170.6 s at 1.024 MS/s (no decimation), RTL-SDR v3,
manual gain 12.4 dB, bias tee on (SkywalkerLNA), tracking CUBEBUG-2; the antenna was turned
between two satellites during the recording. No lost blocks.

| | |
|---|---|
| CUBEBUG-2 frames | every 32.6 s, 1.75 s long: ~240 ms 1200 Hz, ~750 ms of HDLC flags, then the frame. Decoded 3 of 5 with a good CRC (prototype AFSK1200 + PLL clock recovery + HDLC): `CUBEB2-6>CQ: Manolito ad astra! 73 to LU1VZ, LU7AA, and all my HAM friends!` |
| CUBEBUG-2 signal | carrier 42 dB over the noise in a 15.6 Hz bin, about C/N0 55 dB-Hz (the simulator's budget predicted 50–60). FM deviation small (~±660 Hz), Bell 202 tones 1200 / 2200 Hz |
| Doppler | burst centres 437.4501 → 437.4406 MHz over 131 s (−72 Hz/s); zero crossing ~437.4466 MHz, i.e. +1.6 kHz (3.7 ppm) over the 437.445 MHz in the database |
| 437.2017 MHz | a 6 s burst and a 0.75 s one every ~60 s, ~8 kHz wide, no Doppler between bursts 60 s apart and the same audio content each time: a terrestrial periodic transmission, not a LEO satellite |
| Other | spurs at 437.120 and 437.497 MHz all the time; a 5-line comb (437.459…437.535 MHz, 19 kHz apart) for 11 s at t = 37 s, no Doppler: local interference / intermodulation. The noise floor steps with the antenna turning between sky and ground |
| Level | total −28.5 dBFS, no clipping: with the LNA the noise is ~16 dB over the ADC's own, 12.4 dB gain loses ~0.1 dB; anything from 12 to 25 dB is fine with this chain |

The CUBEBUG-2 burst is kept as a test vector for the AFSK1200 / AX.25 chain (M9):
`core/crates/sh-dsp/testdata/cubebug2_afsk1200_64k.wav` (64 kS/s IQ centred on the burst, 2.4 s,
the expected text in its "shmd" chunk). Lessons for the chain: a PLL clock recovery is needed
(a fixed sampling phase loses the frame over ~1000 bits), and the long flag preamble must not
confuse the squelch / AGC.

Since this recording the recorder also logs, with their time, satellite changes and VFO jumps
of more than 5 kHz ("events" in the JSON chunk), so a recording that hops between satellites
can be cut apart.
