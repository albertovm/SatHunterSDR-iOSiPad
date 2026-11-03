//! AFSK 1200 Bd (Bell 202: mark 1200 Hz, space 2200 Hz) -> NRZI -> HDLC -> AX.25 frames, the
//! packet radio / APRS chain (ISS digipeater, APRS-capable CubeSats).
//!
//! Input is the FM-demodulated audio (48 kHz in the app). The tone is told apart by its
//! frequency, not its level: the audio is mixed down around 1700 Hz and the sign of the
//! instantaneous frequency is the bit, so pre-/de-emphasis twist between the two tones does not
//! matter. A digital PLL recovers the bit clock (a fixed sampling phase loses long frames, as the
//! CUBEBUG-2 recording showed), HDLC removes the bit stuffing, the CRC-16 (X.25) checks the frame.

use crate::Complex32;
use std::collections::VecDeque;

const MARK: f64 = 1200.0;
const SPACE: f64 = 2200.0;
const BAUD: f64 = 1200.0;

/// One AX.25 frame with a good CRC.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Ax25Frame {
    pub dst: String,
    pub src: String,
    /// Digipeaters; a `*` marks one that has repeated the frame
    pub path: Vec<String>,
    pub control: u8,
    pub pid: Option<u8>,
    /// Information field (APRS text), raw bytes
    pub info: Vec<u8>,
    /// The whole frame without the CRC
    pub raw: Vec<u8>,
}

impl Ax25Frame {
    /// Parse the bytes between two flags (CRC already removed).
    pub fn parse(raw: &[u8]) -> Option<Ax25Frame> {
        let mut addrs = Vec::new();
        let mut k = 0;
        loop {
            if raw.len() < k + 7 {
                return None;
            }
            let a = &raw[k..k + 7];
            let call: String = a[..6].iter().map(|b| (b >> 1) as char).collect::<String>().trim_end().to_string();
            if call.is_empty() || !call.chars().all(|c| c.is_ascii_alphanumeric()) {
                return None;
            }
            let ssid = (a[6] >> 1) & 0x0f;
            let h = a[6] & 0x80 != 0;
            addrs.push((if ssid > 0 { format!("{call}-{ssid}") } else { call }, h));
            k += 7;
            if a[6] & 1 == 1 {
                break;
            }
            if addrs.len() > 10 {
                return None;
            }
        }
        if addrs.len() < 2 || raw.len() < k + 1 {
            return None;
        }
        let control = raw[k];
        k += 1;
        // UI and I frames carry a PID
        let pid = if control & 0x01 == 0 || control & 0xef == 0x03 {
            let p = *raw.get(k)?;
            k += 1;
            Some(p)
        } else {
            None
        };
        Some(Ax25Frame {
            dst: addrs[0].0.clone(),
            src: addrs[1].0.clone(),
            path: addrs[2..].iter().map(|(c, h)| if *h { format!("{c}*") } else { c.clone() }).collect(),
            control,
            pid,
            info: raw[k..].to_vec(),
            raw: raw.to_vec(),
        })
    }

    /// TNC2 text, e.g. `HA5ABC-7>APRS,RS0ISS*:!4729.87N/01902.41E>Hello`
    pub fn tnc2(&self) -> String {
        let mut s = format!("{}>{}", self.src, self.dst);
        for p in &self.path {
            s.push(',');
            s.push_str(p);
        }
        s.push(':');
        s.push_str(&String::from_utf8_lossy(&self.info));
        s
    }

    /// Build a UI frame (for tests and the lab's generator), without the CRC.
    pub fn ui(src: &str, dst: &str, path: &[&str], info: &[u8]) -> Vec<u8> {
        fn addr(c: &str, last: bool, out: &mut Vec<u8>) {
            let (call, ssid) = match c.trim_end_matches('*').split_once('-') {
                Some((a, b)) => (a.to_string(), b.parse::<u8>().unwrap_or(0)),
                None => (c.trim_end_matches('*').to_string(), 0),
            };
            let mut b: Vec<u8> = call.bytes().take(6).collect();
            b.resize(6, b' ');
            out.extend(b.iter().map(|x| x << 1));
            out.push(0x60 | (ssid << 1) | if c.ends_with('*') { 0x80 } else { 0 } | last as u8);
        }
        let mut out = Vec::new();
        addr(dst, false, &mut out);
        addr(src, path.is_empty(), &mut out);
        for (n, p) in path.iter().enumerate() {
            addr(p, n + 1 == path.len(), &mut out);
        }
        out.push(0x03);
        out.push(0xf0);
        out.extend_from_slice(info);
        out
    }
}

/// CRC-16/X.25 (the AX.25 FCS), sent low byte first.
pub fn crc16(data: &[u8]) -> u16 {
    let mut c: u16 = 0xffff;
    for &b in data {
        c ^= b as u16;
        for _ in 0..8 {
            c = if c & 1 != 0 { (c >> 1) ^ 0x8408 } else { c >> 1 };
        }
    }
    !c
}

/// Bits of a whole transmission: flags, the stuffed frame with its CRC, flags; NRZI-coded
/// (a 0 is a tone change). For tests and the lab's generator.
pub fn hdlc_nrzi_bits(frame: &[u8], pre_flags: usize, post_flags: usize) -> Vec<u8> {
    let mut data = frame.to_vec();
    let c = crc16(frame);
    data.push((c & 0xff) as u8);
    data.push((c >> 8) as u8);
    let mut bits = Vec::new();
    let flag = |bits: &mut Vec<u8>| bits.extend((0..8).map(|k| (0x7e >> k) & 1));
    for _ in 0..pre_flags {
        flag(&mut bits);
    }
    let mut ones = 0;
    for b in data {
        for k in 0..8 {
            let bit = (b >> k) & 1;
            bits.push(bit);
            if bit == 1 {
                ones += 1;
                if ones == 5 {
                    bits.push(0);
                    ones = 0;
                }
            } else {
                ones = 0;
            }
        }
    }
    for _ in 0..post_flags {
        flag(&mut bits);
    }
    // NRZI: 0 = change, 1 = no change; 1 = mark at the start
    let mut level = 1u8;
    bits.iter()
        .map(|&b| {
            if b == 0 {
                level ^= 1;
            }
            level
        })
        .collect()
}

/// AFSK audio for NRZI levels (1 = mark 1200 Hz, 0 = space 2200 Hz), phase continuous.
pub fn afsk_audio(levels: &[u8], fs: f64) -> Vec<f32> {
    let spb = fs / BAUD;
    let mut ph = 0.0f64;
    let mut out = Vec::new();
    let n = (levels.len() as f64 * spb) as usize;
    for i in 0..n {
        let l = levels[((i as f64) / spb) as usize];
        ph += 2.0 * std::f64::consts::PI * if l == 1 { MARK } else { SPACE } / fs;
        out.push(ph.sin() as f32 * 0.5);
    }
    out
}

/// Latitude, longitude from an APRS position report (uncompressed: `!` `=` or `/` `@` with a
/// timestamp), None when the info field has no position.
pub fn aprs_position(info: &str) -> Option<(f64, f64)> {
    let b = info.as_bytes();
    let start = match b.first()? {
        b'!' | b'=' => 1,
        b'/' | b'@' => 8, // 7-character timestamp
        _ => return None,
    };
    let s = info.get(start..start + 19)?;
    let (lat_s, rest) = (s.get(0..8)?, s.get(9..18)?);
    let deg = |t: &str, d: usize| -> Option<f64> {
        let v: f64 = t.get(0..d)?.parse().ok()?;
        let m: f64 = t.get(d..d + 5)?.replace(' ', "0").parse().ok()?;
        Some(v + m / 60.0)
    };
    let mut lat = deg(lat_s, 2)?;
    match lat_s.as_bytes()[7] {
        b'N' => {}
        b'S' => lat = -lat,
        _ => return None,
    }
    let mut lon = deg(rest, 3)?;
    match rest.as_bytes()[8] {
        b'E' => {}
        b'W' => lon = -lon,
        _ => return None,
    }
    ((-90.0..=90.0).contains(&lat) && (-180.0..=180.0).contains(&lon)).then_some((lat, lon))
}

/// Streaming AFSK1200 / AX.25 decoder.
pub struct AfskDecoder {
    fs: f64,
    // FM discriminator around 1700 Hz
    nco_ph: f64,
    nco_step: f64,
    lp: Vec<f32>,
    hist: VecDeque<Complex32>,
    last: Complex32,
    // bit smoothing (half a bit)
    dsum: f32,
    dwin: VecDeque<f32>,
    dwin_n: usize,
    // clock recovery
    pll: f64,
    pll_step: f64,
    prev_sign: bool,
    // NRZI / HDLC
    last_level: bool,
    ones: u32,
    shift: u8,
    nbits: u32,
    buf: Vec<u8>,
    in_frame: bool,
    /// Frames with a good CRC, oldest first
    pub frames: VecDeque<Ax25Frame>,
    /// Frames with a bad CRC (for statistics)
    pub bad_crc: u64,
}

impl AfskDecoder {
    pub fn new(fs: f64) -> Self {
        // Low-pass of the mixed-down audio: the tones are at -500 / +500 Hz, the keying adds
        // sidebands up to ~1.2 kHz; the image at -3400 Hz must go
        let taps = crate::filter::lowpass(1_100.0, 800.0, fs);
        AfskDecoder {
            fs,
            nco_ph: 0.0,
            nco_step: 2.0 * std::f64::consts::PI * (MARK + SPACE) / 2.0 / fs,
            hist: VecDeque::from(vec![Complex32::new(0.0, 0.0); taps.len()]),
            lp: taps,
            last: Complex32::new(1.0, 0.0),
            dsum: 0.0,
            dwin_n: ((fs / BAUD) / 2.0).round().max(1.0) as usize,
            dwin: VecDeque::new(),
            pll: 0.0,
            pll_step: BAUD / fs,
            prev_sign: false,
            last_level: false,
            ones: 0,
            shift: 0,
            nbits: 0,
            buf: Vec::new(),
            in_frame: false,
            frames: VecDeque::new(),
            bad_crc: 0,
        }
    }

    pub fn rate(&self) -> f64 {
        self.fs
    }

    /// Feed audio samples; decoded frames collect in `frames`.
    pub fn process(&mut self, audio: &[f32]) {
        for &a in audio {
            // mix down by 1700 Hz and low-pass
            let (s, c) = self.nco_ph.sin_cos();
            self.nco_ph += self.nco_step;
            if self.nco_ph > std::f64::consts::PI {
                self.nco_ph -= 2.0 * std::f64::consts::PI;
            }
            self.hist.pop_front();
            self.hist.push_back(Complex32::new(a * c as f32, -a * s as f32));
            let mut z = Complex32::new(0.0, 0.0);
            for (h, t) in self.hist.iter().zip(self.lp.iter()) {
                z += h * *t;
            }
            // instantaneous frequency: > 0 = space (2200 Hz), < 0 = mark (1200 Hz)
            let d = (z * self.last.conj()).arg();
            self.last = z;
            self.dwin.push_back(d);
            self.dsum += d;
            if self.dwin.len() > self.dwin_n {
                self.dsum -= self.dwin.pop_front().unwrap();
            }
            let mark = self.dsum < 0.0;
            // DPLL: sample when the phase wraps; a transition pulls the phase towards 0.5
            if mark != self.prev_sign {
                self.prev_sign = mark;
                self.pll += (0.5 - self.pll) * 0.3;
            }
            self.pll += self.pll_step;
            if self.pll >= 1.0 {
                self.pll -= 1.0;
                self.bit(mark);
            }
        }
    }

    fn bit(&mut self, level: bool) {
        // NRZI: no change = 1
        let b = level == self.last_level;
        self.last_level = level;
        if b {
            self.ones += 1;
            if self.ones > 6 {
                // abort / idle
                self.in_frame = false;
                self.buf.clear();
                return;
            }
            self.push(1);
        } else {
            if self.ones == 6 {
                // flag 01111110: close the frame before it, open a new one
                self.flag();
                self.ones = 0;
                return;
            }
            if self.ones == 5 {
                // stuffed 0
                self.ones = 0;
                return;
            }
            self.ones = 0;
            self.push(0);
        }
    }

    fn push(&mut self, bit: u8) {
        if !self.in_frame {
            return;
        }
        self.shift = (self.shift >> 1) | (bit << 7);
        self.nbits += 1;
        if self.nbits == 8 {
            self.buf.push(self.shift);
            self.nbits = 0;
            if self.buf.len() > 400 {
                self.in_frame = false;
                self.buf.clear();
            }
        }
    }

    fn flag(&mut self) {
        // The 6 ones of the flag already went in as bits: drop them (they are less than a byte,
        // so only the partial byte is lost)
        if self.in_frame && self.buf.len() >= 17 {
            let n = self.buf.len();
            let (body, fcs) = self.buf.split_at(n - 2);
            let got = fcs[0] as u16 | (fcs[1] as u16) << 8;
            if crc16(body) == got {
                if let Some(f) = Ax25Frame::parse(body) {
                    self.frames.push_back(f);
                    while self.frames.len() > 100 {
                        self.frames.pop_front();
                    }
                }
            } else {
                self.bad_crc += 1;
            }
        }
        self.in_frame = true;
        self.buf.clear();
        self.nbits = 0;
        self.shift = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn noise(n: usize, seed: &mut u64) -> Vec<f32> {
        (0..n)
            .map(|_| {
                // sum of uniforms ~ Gaussian
                let mut s = 0.0f32;
                for _ in 0..6 {
                    *seed ^= *seed << 13;
                    *seed ^= *seed >> 7;
                    *seed ^= *seed << 17;
                    s += (*seed >> 40) as f32 / (1u64 << 24) as f32 - 0.5;
                }
                s
            })
            .collect()
    }

    #[test]
    fn crc_of_the_check_string() {
        assert_eq!(crc16(b"123456789"), 0x906e);
    }

    #[test]
    fn frame_round_trip_in_noise_and_twist() {
        let fs = 48_000.0;
        let raw = Ax25Frame::ui("HA5ABC-7", "APRS", &["RS0ISS*"], b"!4729.87N/01902.41E>Hello from Budapest");
        let lv = hdlc_nrzi_bits(&raw, 40, 4);
        let mut a = vec![0.0f32; 4800];
        a.extend(afsk_audio(&lv, fs));
        a.extend(vec![0.0f32; 4800]);
        // 6 dB twist (space weaker), noise, a level that is not 1
        let mut b = Vec::with_capacity(a.len());
        let mut prev = 0.0f32;
        for &x in &a {
            b.push(0.6 * x + 0.4 * prev); // a crude low-pass: the 2200 Hz tone comes out weaker
            prev = x;
        }
        let mut seed = 0x1234_5678u64;
        let n = noise(b.len(), &mut seed);
        let b: Vec<f32> = b.iter().zip(&n).map(|(x, w)| 0.3 * x + 0.05 * w).collect();
        let mut d = AfskDecoder::new(fs);
        for c in b.chunks(1000) {
            d.process(c);
        }
        assert_eq!(d.frames.len(), 1, "bad CRC {}", d.bad_crc);
        assert_eq!(d.frames[0].tnc2(), "HA5ABC-7>APRS,RS0ISS*:!4729.87N/01902.41E>Hello from Budapest");
    }

    #[test]
    fn cubebug2_from_the_field_recording() {
        // 64 kS/s IQ of a CUBEBUG-2 burst (2026-11-01): NFM demodulation, then this decoder
        let b = std::fs::read(concat!(env!("CARGO_MANIFEST_DIR"), "/testdata/cubebug2_afsk1200_64k.wav")).unwrap();
        let data = &b[44..44 + 614_400];
        let iq: Vec<Complex32> = data
            .chunks(4)
            .map(|c| Complex32::new(i16::from_le_bytes([c[0], c[1]]) as f32 / 32768.0, i16::from_le_bytes([c[2], c[3]]) as f32 / 32768.0))
            .collect();
        let mut dm = crate::demod::Demodulator::new(crate::demod::Mode::Nfm, 64_000.0, 0.0, 12_500.0);
        let mut audio = Vec::new();
        dm.process(&iq, &mut audio);
        let mut d = AfskDecoder::new(crate::demod::AUDIO_RATE);
        d.process(&audio);
        let got: Vec<String> = d.frames.iter().map(|f| f.tnc2()).collect();
        assert!(
            got.iter().any(|t| t.starts_with("CUBEB2-6>CQ:") && t.contains("Manolito ad astra! 73 to LU1VZ, LU7AA, and all my HAM friends!")),
            "decoded {got:?}, bad CRC {}",
            d.bad_crc
        );
    }
}
