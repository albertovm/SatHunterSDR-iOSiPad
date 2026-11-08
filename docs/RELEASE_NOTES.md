# SatHunterSDR 0.2.0 beta 13

Android satellite-hunting SDR receiver. Install the APK below (allow installs from your browser or
file manager when asked).

**Coming from beta 1 or beta 2: uninstall the old app once** (Android says it "conflicts with an
existing package"). Those builds had a throw-away signature; from beta 3 on every APK is signed
with the same Z2Labs key and installs over the previous one.

## New in beta 13

- **CW without TLE tracking**: the Morse decoder now follows the beat tone while it drifts by up to a few
  hundred Hz/s (uncorrected Doppler on 70 cm reaches about 170 Hz/s at the closest approach). Measured with
  the HackRF: clean copy from 0 to 200 Hz/s down to about 32 dB-Hz (13 of 15 runs perfect, the other two
  with one wrong letter). With tracking on it behaves as before.
- **Build**: the Android build no longer fails when GitHub's Gradle download is slow.

## New in beta 12

- **9600 bd G3RUH FSK telemetry** (Settings, "9600 bd FSK"): the most common cubesat downlink. AX.25 frames
  appear in the frame list with the APRS ones, other HDLC frames (AX.100, CSP) as hex; the new
  `hdlc-telemetry` plugin turns them into readable lines and puts positions on the map. NFM is widened to
  20 kHz when it is switched on. On the phone: 90 % of the frames at about -115 dBm at the LNA input; on
  SatNOGS recordings as many frames as the stations' own decoders.
- **Receiver view**: the VFO is a red marker on the spectrum's top edge and the channel a faint band, so a
  signal right on the VFO is no longer hidden; the lab, SSTV and APRS panels fold into one-line chips (tap to
  open), and their ✕ switches the decoder off.
- **Fixes**: an RTL-SDR whose EEPROM read failed kept its bias tee on; the status line now shows a bias tee
  forced on by the dongle.

## New in beta 11

Decoders, a world map and a lot of lab work: the receive chain, the Spacewalker LNA and every decoder
measured with a Signal Hound VSG60A / BB60C (results in measurements/ and docs/).

- **APRS / AX.25** (AFSK 1200): frame list on the receiver, 90 % packets at about -122.5 dBm in the
  lab. Three detectors run on the same audio and each frame is shown once; on real SatNOGS
  recordings it decodes as many frames as the stations' own decoders or more (ISS 2/2, PCSAT 21/15).
- **Terrestrial APRS mode** (Settings): the local APRS network on 144.800 MHz (or 144.390, 145.175,
  ...), Doppler tracking off, every station on the map. Handy for testing on the ground.
- **SSTV** (Robot 36, PD120) for ISS events: the picture builds up in a panel and can be saved.
  Clean to -132 dBm, recognisable to -136 dBm; decodes an RS18S picture SatNOGS lost.
- **World map** (offline, Natural Earth): your station, the satellite's footprint and ground track,
  the APRS stations heard with their distance. From the Satellites tab (Map) or a tap on the APRS
  panel.
- **Decoder plugins** (Luau): iss-aprs and a generic aprs-map plugin turn frames into readable lines
  and map positions; switch in Settings.
- **AMOLED screen saver**: after 0/1/2/5/10 minutes without a touch the screen dims to a small
  drifting summary (frequency, satellite, signal, last decode); a tap wakes it. The screen is kept
  on only while the app is in front.
- **Updates**: on Android 12+ the app can update itself without the Install dialog; where the
  system refuses (MIUI) it falls back to the normal dialog and remembers that. "Allow reopening"
  in Settings brings the app back after an update.
- **Receiver fixes**: RTL-SDR (R820T) tuning error removed (PLL fraction in Hz, the rest corrected
  in the RTL IF); Doppler tracking glides between updates instead of stepping; AM audio bandwidth
  and the NFM deviation reference fixed.

## New in beta 9

First satellite heard and decoded with it: ITUPSAT 1 on 70 cm CW (see docs/MEASUREMENTS.md).

- **Weak signals show up**: the spectrum now averages every FFT between two frames (before, one
  FFT per frame was taken and ~97 % of the samples were skipped). FFT 8192 by default, 16384
  selectable. A beacon 10 dB weaker than before is visible.
- **No more stutter**: the CW demodulator used almost a whole phone CPU core, blocks were dropped
  silently (choppy audio, a jumpy waterfall). CW is now 10x lighter, SSB / FM 3x. If blocks are
  still lost the status line says so.
- **Span / decimation** (/2, /4, /8) right above the mode buttons: a narrower span around the VFO
  with finer FFT bins and less CPU. /8 gives 300 kHz with 37 Hz bins.
- **Satellite labels on the waterfall**: every active downlink of the satellites above the horizon
  that falls in the span, at its Doppler-shifted frequency (name, mode, elevation; transponders
  with their passband). Tap next to a label to tune exactly onto it.
- **IQ recorder**: the red dot next to play records what the receiver gets as an SDR++
  compatible WAV into Downloads/SatHunter, with the receiver settings and satellite inside.
- **CW**: 2 kHz filter by default (a beacon a few hundred Hz off is still heard); the VFO line is
  faint on the waterfall, so a tracked beacon is not hidden under it.
- **RTL-SDR frequency correction (ppm)** in Settings; automatic gain stops at 40 dB (an LNA in
  front needs no more); a retune made while the RTL-SDR was opening is no longer lost (it could
  leave the receiver on the wrong frequency while the display showed the right one).
- Satellites tab works in landscape (list beside the details).

## New in beta 8

- Hungarian satellites are no longer pinned to the top of the list (search for one and star it
  if you want it there); only favourites are.

## New in beta 7

- **Nixie-tube frequency display**, full width: tap the upper half of a tube to go up, the lower
  half to go down, drag it to spin, long-press to type a frequency.
- **Volume slider** next to the speaker button (0–200 %; the speaker button mutes).
- **Clearer satellite list**: labelled groups (Favourites · Overhead now · Next 2
  hours · Later today), the pass in plain words ("In 12 min · 18:42–18:53", "Overhead now · 5 min
  left" with a progress bar), maximum elevation coloured by how good the pass is.

## New in beta 6

- **Bias tee** for the RTL-SDR (Settings → Receiver): 4.5 V on the antenna input to power an LNA
  or active antenna. Remembered; the status line says "bias tee ON" while it is on.

## New in beta 5

- **"Best heard" order** on the satellite list: favourites first, then the satellites the SatNOGS
  ground stations receive most reliably (share of good observations weighted by how many there
  are). Every row shows ♥ success rate · number of good observations. Press ⟳ once to download
  the statistics.
- Spectrum / waterfall divider is clearer and has a **handle**: drag it up or down to share the
  height (remembered).
- Full screen: the floating bar is slimmer; leaving full screen is a big separate button in the
  corner, so it is not hit by accident.

## New in beta 4

- **Seamless dragging**: every waterfall row remembers the frequency it was received at, so
  while you drag, the whole history slides with your finger and new rows fill in from the side
  (no jumping when the receiver retunes).
- **Center tuning** (Settings → Receiver): the VFO stays in the middle of the screen and tuning
  moves the whole spectrum, like SDR++.
- **New automatic gain for the RTL-SDR**: it watches the ADC level and steps the gain down fast
  when the signal clips, up slowly when it is weak (the tuner's own AGC overloaded on FM
  broadcast). The status line shows the gain it chose.

## New in beta 3

- Fixed release signature, updates install in place.

## New in beta 2

- **RTL-SDR Blog V4**: the V4 is recognised from its USB product string (Android hands the driver
  only a file descriptor, so the old detection could miss it and set the R828D up with the wrong
  crystal, which made it nearly deaf). The status line under the frequency now says
  "(RTL-SDR Blog V4)" when it was recognised.
- **Tuning digits**: drag a digit of the frequency up or down, or tap its upper / lower half, to
  change it. Long-press a digit or press the keyboard button to type a frequency in MHz.
- **Dragging the spectrum sweeps the frequency axis** (like a map) instead of moving the marker.
  Zoomed in, the view slides first; past the edge the receiver retunes and follows the finger.
  Tap still tunes to the tapped frequency.

## New in beta 1

- **Full-screen mode** (the ⛶ button on the receiver): the waterfall fills the screen, the
  frequency, play/stop and mode buttons float over it and fade away after 4 s; a touch brings them
  back. Swipe from the screen edge for the system bars.
- **RTL-SDR** over USB OTG (RTL2832U + R820T/R828D; 250 kS/s – 2.4 MS/s, gain steps or auto).
- **ESP32-S3 ESP-SDR** over its native USB port: 2204–2804 MHz, 250 / 125 / 62.5 kS/s, gain
  index 0–82, smooth in-stream tuning with firmware that supports it, firmware version shown.
- Plug and play: plugging an SDR in switches to it (Android asks for permission once), unplugging
  goes back to the demo source. Each source remembers its own frequency.

## Since 0.1

- Satellites from SatNOGS DB and CelesTrak, pass list with favourites and Hungarian satellites
  first, Doppler tracking, sky radar with compass and aim mode, simulated passes.
- Demo source: works without hardware.

## Known limits

- ESP-SDR: no wideband spectrum (SPEC) mode and no firmware updater yet; use a board with ESP-SDR
  firmware already on it.
- Decoder plugins: format and catalog only, the runtime comes next.
- Beta: please send feedback with the device model and what you were doing.
