//! Settings kept between runs (JSON in the app's data folder).

use serde::{Deserialize, Serialize};
use sh_sat::{Filter, Station};
use std::collections::BTreeSet;
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    pub source: String,
    pub center_hz: f64,
    pub vfo_hz: f64,
    pub mode: String,
    pub bw: f64,
    pub rate: f64,
    pub gain: Option<f32>,
    pub fft_size: usize,
    pub fps: f64,
    pub squelch: Option<f32>,
    pub station: Station,
    pub follow_gps: bool,
    pub filter: Filter,
    pub favourites: BTreeSet<u64>,
    /// Refresh the satellite data when older than this (days, 0 = never)
    pub update_days: f64,
    pub step_hz: f64,
    pub auto_demod: bool,
    pub selected: Option<u64>,
    pub selected_tx: Option<String>,
    /// Start in the demo source when no SDR is plugged in
    pub demo_when_no_device: bool,
    /// Switch to an SDR when one is plugged in
    pub usb_autostart: bool,
    /// VFO stays in the middle of the span, tuning moves the hardware
    pub center_tuning: bool,
    /// Power an LNA / active antenna through the RTL-SDR input (4.5 V)
    pub bias_tee: bool,
    /// Receiver crystal error, ppm (RTL-SDR); read it off a known signal, e.g. a beacon
    pub ppm: f64,
    /// Decimation of the receiver stream: 1 (off), 2, 4, 8
    pub decimation: usize,
    /// Debug mode: the lab link (measurements over the LAN) is on
    pub debug_mode: bool,
    /// Lab link PIN (4-8 digits); empty = a new random PIN every time
    pub lab_pin: String,
    /// APRS / AX.25 decoder (AFSK 1200) on the demodulated audio
    pub aprs: bool,
    /// Decoder plugins (Luau) get the decoded frames
    pub plugins: bool,
    /// SSTV decoder (Robot 36, PD120) on the demodulated audio
    pub sstv: bool,
    /// 9600 bd G3RUH FSK decoder on the FM discriminator (needs NFM 15-25 kHz)
    pub fsk9k6: bool,
    /// Terrestrial APRS mode: fixed frequency, no Doppler tracking, the generic APRS plugins
    /// (for testing the decoder and the map on the local APRS network)
    pub ground_aprs: bool,
    /// Its frequency: 144.800 MHz (Europe), 144.390 (North America), 145.175 (Australia) ...
    pub ground_aprs_hz: f64,
    /// Last VFO frequency per source ("demo", "rtl", "esp")
    pub freqs: std::collections::BTreeMap<String, f64>,
    pub sdrpp_host: String,
    pub sdrpp_port: u16,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            source: if cfg!(target_os = "ios") { "sdrpp".into() } else { "demo".into() },
            center_hz: 100.0e6,
            vfo_hz: 100.0e6,
            mode: "WFM".into(),
            bw: 180_000.0,
            rate: 2_400_000.0,
            gain: None,
            fft_size: 8192,
            fps: 30.0,
            squelch: None,
            station: Station::default(),
            follow_gps: true,
            filter: Filter::default(),
            favourites: BTreeSet::new(),
            update_days: 3.0,
            step_hz: 10.0,
            auto_demod: true,
            selected: None,
            selected_tx: None,
            demo_when_no_device: true,
            usb_autostart: true,
            center_tuning: false,
            bias_tee: false,
            ppm: 0.0,
            decimation: 1,
            debug_mode: false,
            lab_pin: "1027".into(),
            aprs: false,
            plugins: true,
            sstv: false,
            fsk9k6: false,
            ground_aprs: false,
            ground_aprs_hz: 144.800e6,
            freqs: Default::default(),
            sdrpp_host: "127.0.0.1".into(),
            sdrpp_port: 5259,
        }
    }
}

impl Config {
    pub fn load(path: &Path) -> Config {
        std::fs::read_to_string(path).ok().and_then(|t| serde_json::from_str(&t).ok()).unwrap_or_default()
    }

    pub fn save(&self, path: &Path) {
        if let Ok(t) = serde_json::to_string_pretty(self) {
            let tmp = path.with_extension("json.part");
            if std::fs::write(&tmp, t).is_ok() {
                let _ = std::fs::rename(&tmp, path);
            }
        }
    }
}
