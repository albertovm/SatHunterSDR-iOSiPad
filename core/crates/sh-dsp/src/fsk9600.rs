//! 9600 bd G3RUH FSK (the usual "FSK 9k6 AX.25" of cubesats and the 9k6 packet network).
//!
//! On air: AX.25 / HDLC frames, NRZI-coded, scrambled with 1 + x^12 + x^17 (G3RUH), sent as
//! filtered NRZ that frequency-modulates the carrier (about +-3 kHz). Here: the FM
//! discriminator's output (not the audio: its low-pass is too narrow) -> low-pass at about 0.6 x
//! the bit rate -> slow DC tracking (the carrier offset) -> bit clock from the zero crossings ->
//! slicer -> descrambler -> NRZI -> HDLC -> CRC-16 -> AX.25 parse. Frames whose CRC is right but
//! that are not AX.25 (AX.100, CSP over HDLC) are kept raw.

use crate::afsk::{crc16, Ax25Frame};
use crate::filter::{lowpass, Fir};
use std::collections::VecDeque;

pub const BAUD: f64 = 9600.0;

/// One received HDLC frame with a good CRC.
#[derive(Debug, Clone, PartialEq)]
pub struct RawFrame {
    pub data: Vec<u8>,
    /// Parsed when it is AX.25
    pub ax25: Option<Ax25Frame>,
}

pub struct G3ruhDecoder {
    fs: f64,
    lp: Fir,
    buf: Vec<f32>,
    dc: f32,
    dc_k: f32,
    // bit clock
    pll: f64,
    step: f64,
    pll_gain: f64,
    prev: f32,
    // descrambler, NRZI
    sreg: u32,
    last: u8,
    // HDLC
    ones: u32,
    shift: u8,
    nbits: u32,
    frame: Vec<u8>,
    in_frame: bool,
    pub frames: VecDeque<RawFrame>,
    pub count: u64,
    pub bad_crc: u64,
}

impl G3ruhDecoder {
    /// `fs`: rate of the discriminator samples (at least 4 per bit, 48 kHz is fine).
    pub fn new(fs: f64) -> Self {
        Self::with_rate(fs, BAUD)
    }

    pub fn with_rate(fs: f64, baud: f64) -> Self {
        G3ruhDecoder {
            fs,
            lp: Fir::new(lowpass(0.6 * baud, 0.4 * baud, fs)),
            buf: Vec::new(),
            dc: 0.0,
            // carrier offset: tracked over about 200 ms (the scrambled stream has no DC)
            dc_k: (1.0 / (0.2 * fs)) as f32,
            pll: 0.0,
            step: baud / fs,
            pll_gain: 0.25,
            prev: 0.0,
            sreg: 0,
            last: 0,
            ones: 0,
            shift: 0,
            nbits: 0,
            frame: Vec::new(),
            in_frame: false,
            frames: VecDeque::new(),
            count: 0,
            bad_crc: 0,
        }
    }

    pub fn rate(&self) -> f64 {
        self.fs
    }

    /// Discriminator samples (any scale: the sign decides).
    pub fn process(&mut self, disc: &[f32]) {
        self.buf.clear();
        self.lp.process(disc, &mut self.buf);
        let buf = std::mem::take(&mut self.buf);
        for &v in &buf {
            self.dc += (v - self.dc) * self.dc_k;
            let y = v - self.dc;
            // zero crossing: pull the clock so the decision falls in the middle of the bit
            if (y > 0.0) != (self.prev > 0.0) {
                // where the crossing was, as a fraction of a sample back
                let frac = (y / (y - self.prev)).clamp(0.0, 1.0) as f64;
                let ph = self.pll - frac * self.step; // clock phase at the crossing
                let err = if ph > 0.5 { ph - 1.0 } else { ph };
                self.pll -= self.pll_gain * err;
            }
            self.prev = y;
            self.pll += self.step;
            if self.pll >= 0.5 && self.pll - self.step < 0.5 {
                self.bit((y > 0.0) as u8);
            }
            if self.pll >= 1.0 {
                self.pll -= 1.0;
            }
        }
        self.buf = buf;
    }

    fn bit(&mut self, line: u8) {
        // descramble: d = s ^ s[-12] ^ s[-17]
        let d = line ^ ((self.sreg >> 11) & 1) as u8 ^ ((self.sreg >> 16) & 1) as u8;
        self.sreg = (self.sreg << 1) | line as u32;
        // NRZI: no change = 1
        let b = (d == self.last) as u8;
        self.last = d;
        self.hdlc(b);
    }

    fn hdlc(&mut self, b: u8) {
        if b == 1 {
            self.ones += 1;
            if self.ones > 6 {
                self.in_frame = false;
                self.frame.clear();
                return;
            }
            self.push(1);
        } else {
            if self.ones == 6 {
                self.flag();
                self.ones = 0;
                return;
            }
            if self.ones == 5 {
                self.ones = 0; // stuffed
                return;
            }
            self.ones = 0;
            self.push(0);
        }
    }

    fn push(&mut self, b: u8) {
        if !self.in_frame {
            return;
        }
        self.shift = (self.shift >> 1) | (b << 7);
        self.nbits += 1;
        if self.nbits == 8 {
            self.frame.push(self.shift);
            self.nbits = 0;
            if self.frame.len() > 1200 {
                self.in_frame = false;
                self.frame.clear();
            }
        }
    }

    fn flag(&mut self) {
        if self.in_frame && self.frame.len() >= 4 {
            let n = self.frame.len();
            let got = self.frame[n - 2] as u16 | (self.frame[n - 1] as u16) << 8;
            let body = &self.frame[..n - 2];
            if crc16(body) == got {
                self.count += 1;
                self.frames.push_back(RawFrame { data: body.to_vec(), ax25: Ax25Frame::parse(body) });
                while self.frames.len() > 100 {
                    self.frames.pop_front();
                }
            } else if n >= 17 {
                self.bad_crc += 1;
            }
        }
        self.in_frame = true;
        self.frame.clear();
        self.nbits = 0;
        self.shift = 0;
    }
}

/// G3RUH line bits of a transmission (HDLC + NRZI from `afsk::hdlc_nrzi_bits`, then scrambled).
/// For tests and the lab's generator.
pub fn g3ruh_bits(frame: &[u8], pre_flags: usize, post_flags: usize) -> Vec<u8> {
    let nrzi = crate::afsk::hdlc_nrzi_bits(frame, pre_flags, post_flags);
    let mut reg: u32 = 0;
    nrzi.iter()
        .map(|&d| {
            let s = d ^ ((reg >> 11) & 1) as u8 ^ ((reg >> 16) & 1) as u8;
            reg = (reg << 1) | s as u32;
            s
        })
        .collect()
}

/// Baseband for line bits at `fs`: NRZ +-1, raised-cosine shaped (roll-off 0.5, as the G3RUH
/// modem's transmit filter), ready to frequency-modulate.
pub fn g3ruh_baseband(bits: &[u8], fs: f64, baud: f64) -> Vec<f32> {
    let sps = fs / baud;
    let n = (bits.len() as f64 * sps).ceil() as usize;
    let span = 4.0; // bits each side
    let beta = 0.5;
    let mut out = vec![0.0f32; n];
    for (k, &b) in bits.iter().enumerate() {
        let a = if b == 1 { 1.0 } else { -1.0 };
        let c = (k as f64 + 0.5) * sps;
        let lo = ((c - span * sps).floor().max(0.0)) as usize;
        let hi = ((c + span * sps).ceil() as usize).min(n);
        for (i, o) in out.iter_mut().enumerate().take(hi).skip(lo) {
            let t = (i as f64 - c) / sps;
            let sinc = if t.abs() < 1e-9 { 1.0 } else { (std::f64::consts::PI * t).sin() / (std::f64::consts::PI * t) };
            let den = 1.0 - (2.0 * beta * t).powi(2);
            let rc = if den.abs() < 1e-6 { std::f64::consts::PI / 4.0 } else { (std::f64::consts::PI * beta * t).cos() / den };
            *o += (a * sinc * rc) as f32;
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Complex32;

    fn fm_disc(bb: &[f32], fs: f64, dev: f64, cn0: f64, foff: f64, seed: u64) -> Vec<f32> {
        let mut s = seed;
        let mut u = || {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            ((s >> 11) as f64 + 0.5) / (1u64 << 53) as f64
        };
        let sigma = (10f64.powf(-cn0 / 10.0) * fs / 2.0).sqrt();
        let mut ph = 0.0f64;
        let mut last = Complex32::new(1.0, 0.0);
        bb.iter()
            .map(|&x| {
                ph += 2.0 * std::f64::consts::PI * (dev * x as f64 + foff) / fs;
                let (u1, u2) = (u(), u());
                let r = (-2.0 * u1.ln()).sqrt() * sigma;
                let v = Complex32::new((ph.cos() + r * (2.0 * std::f64::consts::PI * u2).cos()) as f32, (ph.sin() + r * (2.0 * std::f64::consts::PI * u2).sin()) as f32);
                let d = (v * last.conj()).arg();
                last = v;
                d
            })
            .collect()
    }

    fn packets(n: usize) -> (Vec<Vec<u8>>, Vec<u8>) {
        let mut bits = Vec::new();
        let mut frames = Vec::new();
        for k in 0..n {
            let f = Ax25Frame::ui("HG0SAT", "CQ", &[], format!("telemetry {k:03} {}", "x".repeat(60)).as_bytes());
            bits.extend(g3ruh_bits(&f, 30, 4));
            frames.push(f);
        }
        (frames, bits)
    }

    #[test]
    fn clean_frames_come_back() {
        let fs = 48_000.0;
        let (frames, bits) = packets(5);
        let d = fm_disc(&g3ruh_baseband(&bits, fs, BAUD), fs, 3000.0, 80.0, 0.0, 1);
        let mut dec = G3ruhDecoder::new(fs);
        for c in d.chunks(960) {
            dec.process(c);
        }
        let got: Vec<Vec<u8>> = dec.frames.iter().map(|f| f.data.clone()).collect();
        assert_eq!(got, frames);
        assert!(dec.frames[0].ax25.as_ref().unwrap().src == "HG0SAT");
    }

    #[test]
    fn noise_offset_and_inversion() {
        let fs = 48_000.0;
        let (frames, bits) = packets(10);
        let bb = g3ruh_baseband(&bits, fs, BAUD);
        // 1.5 kHz carrier offset, inverted deviation (some radios), C/N0 62 dB-Hz
        let d = fm_disc(&bb, fs, -3000.0, 62.0, 1500.0, 7);
        let mut dec = G3ruhDecoder::new(fs);
        for c in d.chunks(777) {
            dec.process(c);
        }
        assert!(dec.frames.len() >= 9, "{} of {} frames", dec.frames.len(), frames.len());
    }
}
