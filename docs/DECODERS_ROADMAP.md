# Decoder plugins: roadmap

Goal: the popular satellites decode in the app, each through a small Luau plugin
(see PLUGINS.md); the core does the radio chain. Status: the manifest and catalog format exist,
the CW decoder works on recordings (`sh-dsp::cw`, ITUPSAT 1 decoded from a field recording),
the IQ recorder gives real test data. Missing: the Luau runtime, the streaming chains, the
decoder panel in the UI.

## Chains (core, Rust) and who needs them

| Chain | Satellites (popular, check the status in SatNOGS before starting) | Plugin work | Core work |
|---|---|---|---|
| `cw` | FO-29, RS-44 beacons, XW-2 series, CAS-4A/B, ITUPSAT 1, many CubeSat beacons | easy: text, parse telemetry words | streaming CW decoder (now batch), frames = words / lines |
| `afsk1200` + AX.25 | ISS APRS digipeater (145.825), APRS-capable CubeSats | easy (iss-aprs exists) | AFSK demod (Bell 202), NRZI, HDLC, CRC |
| `audio` → SSTV | ISS SSTV events (145.800), classroom favourite | medium: Robot36 / PD120 in Luau or core | audio blocks to the plugin, `show.image` |
| `fsk9600` (G3RUH) + AX.25 | the most common CubeSat telemetry mode on SatNOGS | easy per satellite (field maps) | FSK demod, G3RUH descrambler, clock recovery |
| `gmsk` | GRBAlpha and others at 4k8 / 9k6 | easy per satellite | GMSK demod, sync words, often RS / CCSDS |
| `bpsk` 1200 (FUNcube) | AO-73, EO-88, JO-97 and other FUNcube-family | medium: telemetry layout | BPSK demod, Viterbi + RS (FUNcube FEC) |
| Fox DUV | AO-91, AO-92 (low-speed telemetry under the FM voice) | medium | 200 bps FSK under voice, 8b/10b |
| `iq` → LRPT | Meteor-M2-3 / M2-4 images (137.9 MHz) | advanced | QPSK 72k, Viterbi, RS, JPEG (heavy: maybe desktop first) |

NOAA APT is not on the list: NOAA-15/18/19 were switched off in 2025.

## Milestones (proposed)

| Milestone | Target | Contents |
|---|---|---|
| **M1 — Plugin runtime + CW** | 2026-11-15, beta 10 | Luau runtime (sandboxed: `show.*`, `bytes.*`), loader for built-in and catalog plugins; streaming CW chain; decoder panel under the waterfall (log, live values); generic `cw-beacon` plugin; ITUPSAT 1 test from the 2026-11-01 recording; CI runs plugin tests |
| **M2 — APRS + SSTV** | 2026-11-29, beta 11 | AFSK1200 / HDLC / AX.25 chain; `iss-aprs` live with map pins; SSTV (Robot36, PD120) for ISS events; IQ / audio test vectors from SatNOGS observations |
| **M3 — 9k6 telemetry** | 2026-12-13, beta 12 | G3RUH FSK9600 and GMSK chains; a generic AX.25 telemetry plugin; plugins for 2–3 of the best-heard 9k6 satellites (by the "Best heard" list) |
| **M4 — FUNcube and Fox** | 2027-01-17, 0.3 | BPSK 1200 with FUNcube FEC; Fox DUV; their telemetry plugins |
| **M5 — Meteor LRPT** | 2027-02-28, 0.4 | QPSK / Viterbi / RS / JPEG; first on the desktop tools, on the phone if the CPU allows |

## Test data

Every plugin ships `test/` data the CI runs: frames for the easy ones, audio or IQ for the chain
tests. Sources: our own IQ recordings (the red dot in the app; SDR++ compatible WAV with the
satellite and settings inside, see MEASUREMENTS.md) and SatNOGS observation audio / IQ.
