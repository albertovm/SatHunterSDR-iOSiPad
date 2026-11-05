# Lab measurements over the LAN

The phone's receiver becomes a measuring instrument a PC script can drive: a signal generator
puts known signals in, the script reads back what the receiver measured and decoded, and writes
a report. First in the lab (cables, attenuators), later in the field (a real pass).

```
 VSG60 / any generator ──[attenuators]──> RTL-SDR ── phone (SatHunterSDR, debug mode)
        │ USB                                              │ Wi-Fi / USB Ethernet
        └──────────────── PC: tools/lab/lab.py ◄───────────┘  HTTP, port 8765, PIN
```

## On the phone

Settings → Debug → **Debug mode (lab link)**. The **lab console** appears on the receiver screen
(drag it anywhere, tap to fold): the phone's LAN addresses, the **PIN**, the command to type on
the PC, who is connected, the measurement phase with a progress bar and the last log lines.
Debug mode is remembered; switch it off when done (the server listens on the LAN while on).

## On the PC

Same network as the phone, Python 3, no packages:

```
python tools/lab/lab.py --phone <address> --pin <PIN> --gen demo                    # self test
python tools/lab/lab.py --phone <address> --pin <PIN> --gen manual --freq 437.1e6 --atten 80
python tools/lab/lab.py --phone <address> --pin <PIN> --gen vsg60  --freq 437.1e6 --atten 80 \
    --levels=-60,-70,-80,-90,-100,-110,-115,-120,-125,-130 --note "SMA 1 m, 40+40 dB pads"
```

- `demo`: no generator; the phone switches to the demo source and measures its CW beacon.
  Checks the whole chain (LAN, PIN, commands, measurement, CW decode) in a minute.
- `manual`: the script tells you what to set on any generator and waits for Enter.
- `vsg60`: Signal Hound VSG60A through the **VSG software's SCPI server** (TCP, `--vsg
  192.168.1.199:5124` by default), ARB mode, as in the lab's VSG60 guide:
  - VSG software: Edit → Preferences → SCPI enabled, port 5124 (restart after a change), a
    firewall rule for the port, **one** VSG software instance, and no other SCPI client while
    lab.py runs.
  - The script writes its waveforms (`sathunter_cw.cf32`, `sathunter_key_*.cf32`: float32 IQ,
    100 kS/s) into `--vsg-dir` (default `C:\sathunter_lab`) and has the VSG software load them by
    the path the VSG PC sees (`--vsg-path`, default the same): simplest is to run lab.py on the
    VSG PC itself.
  - It sets ARB, Auto Scale ON, **Output Signal Average OFF** (so |IQ| = 1 is the set level),
    sample offset 0 and count = period = file length, continuous trigger; every heavy command is
    followed by `*OPC` / `*ESR?` polling and `:SYSTem:ERRor?` is read until empty; RF is OFF
    while the phone is set up and during the noise floor.
  - The level sweep runs `--passes` times (default 2), each in a random order, and the report
    shows the mean and the spread per level.
  - `tools/lab/mock_vsg.py` answers like the VSG software and logs the commands: a dry run
    without the generator.

`--atten` is everything between the generator and the receiver input (the 3–10 dB pad that
always sits on the VSG60 output, cables, fixed and step attenuators; measure it); all levels in
the report are at the receiver input. The VSG60's absolute level is ±2 dB; warm it up ~30
minutes. Satellite-like levels (−120 … −140 dBm) need good shielding: below about −80 dBm the
leakage from the VSG60's case and USB cable matters; the noise-floor phase (generator OFF) warns
when the test frequency is not clean.

## Phases

1. **connect** — phone, receiver and settings into the report
2. **setup** — frequency, decimation /8, CW mode (gain as set on the phone, or `--gain`)
3. **noise floor** — generator off
4. **frequency accuracy** — CW carrier: offset in Hz and ppm (put the ppm into Settings)
5. **level sweep** — CW carrier at each level: peak level, SNR, C/N0, offset; sensitivity
   (level of 3 dB SNR in one FFT bin)
6. **CW decode** — a keyed message at each level: decoded text, OK / not, speed

## The report

`docs/lab/<date_time>/`: `report.md` (tables), `sweep.csv`, `results.json`. Commit and push it
(from the PC, author Zoltan Doczi): that is how the measurement reaches the other machines and
the cloud Claude session, which cannot reach the LAN.

## API (for other scripts)

Port 8765, PIN as `?pin=` or `X-Lab-Pin`: `GET /status`, `POST /cmd` (the app's JSON commands),
`GET /measure?hz=&bw=&secs=`, `GET /cw?secs=`, `GET /iq?secs=` (WAV), `GET /audio?secs=` (demodulated audio, 16-bit WAV, 48 kHz), `GET /aprs?since=` (APRS frames decoded after number `since`; decoder on with `{"cmd":"aprs","on":true}`), `POST /cmd {"cmd":"update"}` (the app looks for a newer GitHub release and opens the installer; one tap on the phone), `POST /phase`, `POST /log`,
`GET /log`. Without a phone: `cargo run --release -p sh-engine --example lab_demo` runs the engine
with the demo source and the lab link on this computer.

## RF instruments: VSG60A + BB60C (component tests)

For measuring a front-end part on its own (an LNA, a filter, a cable) the phone is replaced by a
Signal Hound BB60C spectrum analyser. All scripts run on the PC that has both instruments (the G7
laptop) and write `measurements/<date_time>_<name>/results.json`; reports and plots are made from that.

```
VSG60A ── 20 dB ── coax ── [DUT] ── bias tee ── 30 dB ── BB60C
                                       │ DC (lab supply)
```

| Script | What it measures |
|---|---|
| `tools/lab/bb60.py` | BB60C through its C API (`bb_api.dll` from the Spike folder, ctypes): `peak()`, `trace()`, `noise()`, `noise_density()` (power-averaged, dBm/Hz). Spike must not run at the same time. |
| `tools/lab/path_cal.py` | Loss of the path without the DUT, 50 MHz - 1 GHz (VSG60 CW in, BB60C reads). Everything else refers levels to the DUT's connectors with it. |
| `tools/lab/lna_char.py` | Gain vs frequency (CW, level stepped up until 25 dB over the floor), P1dB at one frequency, two-tone IIP3 (100 kHz). |
| `tools/lab/comb_sweep.py` + `plot_comb.py` | Fast transfer function: 90 tones at once (Newman phases, 2.5 dB crest factor, half a step off the carrier) from a 40 MS/s ARB, read in one span; 380-490 MHz in 200 kHz steps in about a minute. |
| `tools/lab/lna_extra.py` + `plot_lna_extra.py` | Gain stability over time, P1dB vs frequency (with re-reads of outliers), IIP3 vs tone spacing, close-in blocking (wanted tone + blocker from one ARB), harmonics, spur / oscillation scan 20 MHz - 3 GHz, noise-figure estimate from the output noise hump. `--out-loss` / `--cal-out-loss` when the output pad is changed after the path calibration. |
| `tools/lab/thru_check.py` | Without the DUT: dropout watch and the VSG60A's own two-tone IMD. |
| `tools/lab/plot_supply.py` | Summary of `lna_char.py` runs at several supply voltages. |
| `tools/lab/fast_pass.py` + `plot_pass_explainer.py` | A real satellite pass played to the phone (SGP4 Doppler written into the ARB) and the explainer figure. |

### VSG60A and BB60C notes (learned the hard way)

- **One SCPI client at a time.** Stopping a client mid-session can kill the VSG software's SCPI
  server; restart `VSG.exe` before each script (the `D:\Measurements\*.ps1` wrappers do).
- **Unacknowledged writes crash the VSG software** when sent quickly: pace every write with a query
  (`Vsg60Gen.tune()` writes the frequency and reads it back).
- `*OPC` with an ARB playing completes only at the end of the waveform period (13.5 s for a long
  keyed message): do not use it after a retune.
- Every frequency write interrupts the output for 0.02-0.35 s: for Doppler, write the Doppler into the
  waveform instead of retuning.
- After 2-3 loads of **large** ARB files the VSG software crashes: restart it between big waveforms.
- ARB rates: **20 kS/s plays about 16 % slow**; 25 and 50 kS/s play at the right rate (checked with a
  linear chirp). Small multi-tone files at 1-40 MS/s are fine.
- `:ARB:STATe OFF` then `ON` restarts the waveform at sample 0 (used to start a pass on time).
- The VSG60A's own two-tone IM3 is -53 ... -59 dBc at set levels -12 ... +2 dBm and rises above
  +4 dBm; keep the DUT's IM3 well above that (read IIP3 at the higher drive levels).
- The VSG60A reference is about +0.29 ppm high relative to the BB60C.
- The BB60C has internal spurs at multiples of 80 MHz (seen at 400, 480, 800 MHz and up); they stay
  with the generator off. The scripts flag them.
- Gaps in the generator output can come from CPU load on the PC (a build running): every script
  waits until the CPU is under 70 % (`wait_idle`).
