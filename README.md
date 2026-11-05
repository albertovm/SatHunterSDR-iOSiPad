# SatHunterSDR

![SatHunterSDR: hunt satellites with your phone](docs/img/banner.png)

A satellite-hunting SDR receiver for Android: pick a satellite, the app tunes to it and follows
its Doppler shift, and a sky radar turns with your phone so you can point the antenna.
Made for classrooms first: it runs without hardware (a simulated RTL-SDR with a simulated pass),
and decoders are small plugins that students can write.

## Features (0.2 beta)

- **Satellites**: SatNOGS DB and CelesTrak data, pass prediction (SGP4, checked against Skyfield), filters by band, mode, status; favourites first, "Next pass" or "Best heard" (SatNOGS reception) order.
- **Doppler tracking**: tunes to the selected downlink and follows it. Your own retuning is kept as an offset (linear transponders).
- **Radar**: the whole pass with AOS/LOS times, the satellite, others overhead. A compass mode follows the phone; aim mode guides you to the satellite.
- **Receiver**: GPU spectrum and waterfall, NFM / WFM / AM / USB / LSB / CW, pinch zoom, drag to tune, full-screen mode with floating controls that fade away.
- **SDRs**: RTL-SDR and ESP32-S3 (ESP-SDR firmware, 2204–2804 MHz, smooth in-stream tuning), plug and play over USB OTG.
- **Demo source**: FM broadcast, airband, APRS, a CW beacon, ISM bursts and the selected satellite at its real Doppler frequency, with "Simulate this pass now".

Coming next: decoder plugins (AX.25 / APRS first), the ESP-SDR wideband spectrum mode and firmware updater, rtl_tcp, more sources.

## How it works

![SatHunterSDR block diagram](docs/img/sathunter-block-diagram.png)

From the satellite to the screen: RF front end, the Rust core (sources, engine, DSP, orbits, plugins), the
Android UI, and the lab instruments that replace the sky for repeatable tests. Details in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

![A satellite pass replayed in the lab](docs/img/pass-simulation.png)

A real pass (CAPE-1, 79°) replayed by a VSG60A with the Doppler from an independent SGP4: the phone follows the
satellite within ±9 Hz (1σ) at 116 Hz/s and decodes its CW through the closest point at -130 dBm.

**Summary for engineers** (3 pages: bugs found and fixed, lab and field results):
[docs/report/SatHunterSDR-lab-field-summary.pdf](docs/report/SatHunterSDR-lab-field-summary.pdf)

## Measurements

Receive chain measured in the lab ([all runs](measurements/README.md)):
VSG60 -> Spacewalker LNA 434 MHz -> RTL-SDR Blog V3 -> SatHunterSDR on a Xiaomi Mi 10.

| Quantity | Result |
|---|---|
| System noise figure at 436.6 MHz | 2.0 dB |
| Frequency error | +0.34 ppm |
| Sensitivity (MDS, 3 dB SNR in 31 Hz) | -154.4 dBm |
| Keyed CW at 15 WPM | decoded down to -145 dBm (C/N0 29 dB-Hz) |
| APRS (AFSK 1200) | 90 % packets at -122.5 dBm (3 kHz dev.), -123.2 dBm (1 kHz dev., 6 kHz channel) |
| Simulated pass (88°, Doppler tracking) | VFO within ±13 Hz of the satellite, CW decoded all pass long |
| Fast LEO pass (116 Hz/s) | carrier within ±9 Hz (1σ), CW decoded through the closest point; orbit model = independent SGP4 to 0.16 Hz |
| Spacewalker LNA 434 MHz ([full characterisation](docs/LNA-CHARACTERISATION.md)) | 45-51 dB gain in 425-444 MHz, NF 2-4 dB, > 72 dB out-of-band rejection, OP1dB +16...+21 dBm, IIP3 about -18 dBm, 131 mA at 5 V |
| Frequency error (after warm-up) | +0.09 ppm, the same at every sample rate |
| Decimation alias rejection | > 48-58 dB in the central 84 % of the span |

![Gain sweep and level sweep](measurements/2026-11-02_1028_system-a/plots.png)

![Sensitivity and CW decode](measurements/2026-11-02_1044_system-a2-mds/plots.png)

## Layout

```
core/       Rust: sh-sat, sh-dsp, sh-sources, sh-plugin, sh-engine, sh-android (JNI)
android/    Kotlin + Jetpack Compose app
catalog/    satellite profiles (index.json)
plugins/    decoder plugins (Luau), one folder each
docs/       ARCHITECTURE.md, LAB.md, LNA-CHARACTERISATION.md, MEASUREMENTS.md (field), PLUGINS.md, report/ (summary PDF)
measurements/  lab runs: report.md, plots and raw data per run (index: measurements/README.md)
tools/lab/  lab scripts (phone lab link, VSG60A, BB60C)
```

## Build

```
cd core && cargo test --release --workspace
cargo install cargo-ndk
cd core && cargo ndk -t arm64-v8a -t armeabi-v7a -t x86_64 -P 26 -o ../android/app/src/main/jniLibs build --release -p sh-android
cd android && ./gradlew assembleRelease
```

CI builds the APK on every push; it is under Actions → Build → artifacts. Tags `v*` make a release.

## License

GPL-3.0-or-later. Satellite data: SatNOGS DB (CC BY-SA 4.0), CelesTrak.
SGP4 by the `sgp4` crate (MIT), FFT by `rustfft` (MIT / Apache-2.0).
