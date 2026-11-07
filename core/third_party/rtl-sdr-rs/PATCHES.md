# Local changes (SatHunterSDR)

Vendored from rtl-sdr-rs 0.4.2 (https://github.com/ccostes/rtl-sdr-rs), MPL-2.0 (see LICENSE).

- `src/lib.rs`, `src/device/device_handle.rs`: no `nusb::list_devices()` on Android (nusb has no
  enumeration there); Android opens devices with `DeviceId::Fd` only.
- `src/lib.rs`, `src/rtlsdr.rs`: `set_blog_v4_hint()` — the app can say the device is an RTL-SDR
  Blog V4 (Android knows the USB product strings even when reading them over the fd fails);
  `is_blog_v4()` reports what was chosen; the USB strings are logged.

- `AsyncReadConfigChange::BiasTee(bool)` and `AsyncReadControlHandle::set_bias_tee()`: switch the
  bias tee while the async reader owns the device.
- `bias_forced()`: reports the EEPROM's force-bias-tee bit, which makes the library keep the bias
  tee on whatever the application asks (the app shows it instead of a misleading "off").
- EEPROM force bits are honoured only when the EEPROM header is valid (0x28 0x32): a failed or
  blank read returned zeros, which read as "force bias tee" and kept the bias tee on.
  `eeprom_byte7()` reports the byte for diagnostics.
