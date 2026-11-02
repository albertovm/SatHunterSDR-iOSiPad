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
    --levels -60,-70,-80,-90,-100,-110,-115,-120,-125,-130 --note "SMA 1 m, 40+40 dB pads"
```

- `demo`: no generator; the phone switches to the demo source and measures its CW beacon.
  Checks the whole chain (LAN, PIN, commands, measurement, CW decode) in a minute.
- `manual`: the script tells you what to set on any generator and waits for Enter.
- `vsg60`: Signal Hound VSG60 through its C API (`vsg_api.dll` from the Signal Hound SDK next to
  the script, or `--vsg-lib`). The function names follow the VSG API; if your SDK differs, only
  the `Vsg60Gen` class needs a touch.

`--atten` is everything between the generator and the receiver input; all levels in the report
are at the receiver input. The generator's own range ends around −40 dBm (check the data sheet),
so satellite-like levels (−120 … −140 dBm) need fixed and step attenuators and good shielding:
with poor shielding the leakage around the attenuators sets the level, not the attenuators.

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
`GET /measure?hz=&bw=&secs=`, `GET /cw?secs=`, `GET /iq?secs=` (WAV), `POST /phase`, `POST /log`,
`GET /log`. Without a phone: `cargo run --release -p sh-engine --example lab_demo` runs the engine
with the demo source and the lab link on this computer.
