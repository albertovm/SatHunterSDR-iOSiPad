//! SSTV (slow-scan television) decoder for the demodulated audio: Robot 36 and PD120, the modes
//! the ISS uses for its SSTV events (145.800 MHz FM). Streaming: VIS code -> mode, then line by
//! line, each line re-aligned on its 1200 Hz sync pulse (the sound card / radio clock never
//! matches exactly). Also a generator for tests and the lab (`sstv_audio`).
//!
//! Frequency to brightness: 1500 Hz black ... 2300 Hz white; sync 1200 Hz.

use crate::Complex32;
use std::collections::VecDeque;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SstvMode {
    Robot36,
    Pd120,
}

impl SstvMode {
    pub fn from_vis(code: u8) -> Option<SstvMode> {
        match code {
            8 => Some(SstvMode::Robot36),
            95 => Some(SstvMode::Pd120),
            _ => None,
        }
    }
    pub fn vis(self) -> u8 {
        match self {
            SstvMode::Robot36 => 8,
            SstvMode::Pd120 => 95,
        }
    }
    pub fn name(self) -> &'static str {
        match self {
            SstvMode::Robot36 => "Robot 36",
            SstvMode::Pd120 => "PD120",
        }
    }
    pub fn size(self) -> (usize, usize) {
        match self {
            SstvMode::Robot36 => (320, 240),
            SstvMode::Pd120 => (640, 496),
        }
    }
    /// One scan period (one line for Robot 36, a line pair for PD120), seconds
    fn period(self) -> f64 {
        match self {
            SstvMode::Robot36 => 0.150,
            SstvMode::Pd120 => 0.508_48,
        }
    }
    fn periods(self) -> usize {
        match self {
            SstvMode::Robot36 => 240,
            SstvMode::Pd120 => 248,
        }
    }
    fn sync(self) -> f64 {
        match self {
            SstvMode::Robot36 => 0.009,
            SstvMode::Pd120 => 0.020,
        }
    }
}

const BLACK: f64 = 1500.0;
const WHITE: f64 = 2300.0;
const SYNC: f64 = 1200.0;

/// Segments of one scan period after the sync pulse: (start, length) in seconds from the start of
/// the sync, and what they carry.
#[derive(Debug, Clone, Copy, PartialEq)]
enum Seg {
    Y,
    Y2,
    Cr,
    Cb,
    /// Robot 36: the chroma of this line (R-Y on even lines, B-Y on odd ones)
    Chroma,
}

fn layout(m: SstvMode) -> Vec<(f64, f64, Seg)> {
    match m {
        // sync 9, porch 3, Y 88, separator 4.5, porch 1.5, chroma 44 ms
        SstvMode::Robot36 => vec![(0.012, 0.088, Seg::Y), (0.106, 0.044, Seg::Chroma)],
        // sync 20, porch 2.08, then Y0, R-Y, B-Y, Y1 of 121.6 ms each
        SstvMode::Pd120 => {
            let s = 0.022_08;
            let l = 0.1216;
            vec![(s, l, Seg::Y), (s + l, l, Seg::Cr), (s + 2.0 * l, l, Seg::Cb), (s + 3.0 * l, l, Seg::Y2)]
        }
    }
}

fn level(f: f64) -> u8 {
    (((f - BLACK) / (WHITE - BLACK)) * 255.0).round().clamp(0.0, 255.0) as u8
}

fn ycc_rgb(y: u8, cr: u8, cb: u8) -> [u8; 3] {
    let (y, cr, cb) = (y as f64, cr as f64 - 128.0, cb as f64 - 128.0);
    let c = |v: f64| v.round().clamp(0.0, 255.0) as u8;
    [c(y + 1.402 * cr), c(y - 0.344_136 * cb - 0.714_136 * cr), c(y + 1.772 * cb)]
}

fn rgb_ycc(p: [u8; 3]) -> (u8, u8, u8) {
    let (r, g, b) = (p[0] as f64, p[1] as f64, p[2] as f64);
    let y = 0.299 * r + 0.587 * g + 0.114 * b;
    let c = |v: f64| v.round().clamp(0.0, 255.0) as u8;
    (c(y), c(128.0 + 0.713 * (r - y)), c(128.0 + 0.564 * (b - y)))
}

/// A picture, finished or in progress.
#[derive(Debug, Clone)]
pub struct SstvImage {
    pub mode: SstvMode,
    pub width: usize,
    pub height: usize,
    /// RGB, row by row
    pub rgb: Vec<u8>,
    /// Rows received so far
    pub rows: usize,
    /// Sync pulses found where expected (out of the periods so far)
    pub syncs_found: usize,
}

/// FM audio for an image (VIS header included), phase-continuous, at `fs`.
pub fn sstv_audio(mode: SstvMode, rgb: &[u8], fs: f64) -> Vec<f32> {
    let (w, h) = mode.size();
    assert_eq!(rgb.len(), w * h * 3);
    let mut out = Vec::new();
    let mut ph = 0.0f64;
    let mut t_acc = 0.0f64; // exact time, so the rounding does not pile up
    let mut tone = |f: f64, secs: f64, out: &mut Vec<f32>| {
        let n_end = ((t_acc + secs) * fs).round() as usize;
        let n0 = (t_acc * fs).round() as usize;
        for _ in n0..n_end {
            ph += 2.0 * std::f64::consts::PI * f / fs;
            out.push((ph.sin() * 0.7) as f32);
        }
        t_acc += secs;
    };
    tone(0.0, 0.1, &mut out);
    // VIS: leader, break, leader, start bit, 7 data bits LSB first, even parity, stop bit
    tone(1900.0, 0.3, &mut out);
    tone(1200.0, 0.01, &mut out);
    tone(1900.0, 0.3, &mut out);
    tone(1200.0, 0.03, &mut out);
    let code = mode.vis();
    let mut ones = 0;
    for b in 0..7 {
        let one = (code >> b) & 1 == 1;
        ones += one as u32;
        tone(if one { 1100.0 } else { 1300.0 }, 0.03, &mut out);
    }
    tone(if ones % 2 == 1 { 1100.0 } else { 1300.0 }, 0.03, &mut out);
    tone(1200.0, 0.03, &mut out);
    let px = |x: usize, y: usize| [rgb[(y * w + x) * 3], rgb[(y * w + x) * 3 + 1], rgb[(y * w + x) * 3 + 2]];
    let scan = |vals: &mut dyn Iterator<Item = u8>, secs: f64, n: usize, tone: &mut dyn FnMut(f64, f64)| {
        for v in vals {
            tone(BLACK + (WHITE - BLACK) * v as f64 / 255.0, secs / n as f64);
        }
    };
    let mut tone_fn = |f: f64, s: f64| tone(f, s, &mut out);
    match mode {
        SstvMode::Robot36 => {
            for y in 0..h {
                tone_fn(SYNC, 0.009);
                tone_fn(BLACK, 0.003);
                let ys: Vec<u8> = (0..w).map(|x| rgb_ycc(px(x, y)).0).collect();
                scan(&mut ys.into_iter(), 0.088, w, &mut tone_fn);
                // even line: R-Y (separator 1500 Hz), odd: B-Y (2300 Hz); chroma averaged over the pair
                let even = y % 2 == 0;
                tone_fn(if even { BLACK } else { WHITE }, 0.0045);
                tone_fn(1900.0, 0.0015);
                let pair = y - y % 2;
                let ch: Vec<u8> = (0..w / 2)
                    .map(|x2| {
                        let mut acc = 0.0;
                        for yy in pair..(pair + 2).min(h) {
                            for xx in [2 * x2, 2 * x2 + 1] {
                                let (_, cr, cb) = rgb_ycc(px(xx, yy));
                                acc += if even { cr } else { cb } as f64;
                            }
                        }
                        (acc / 4.0).round() as u8
                    })
                    .collect();
                scan(&mut ch.into_iter(), 0.044, w / 2, &mut tone_fn);
            }
        }
        SstvMode::Pd120 => {
            for p in 0..h / 2 {
                let (y0, y1) = (2 * p, 2 * p + 1);
                tone_fn(SYNC, 0.020);
                tone_fn(BLACK, 0.002_08);
                let l = 0.1216;
                let a: Vec<u8> = (0..w).map(|x| rgb_ycc(px(x, y0)).0).collect();
                scan(&mut a.into_iter(), l, w, &mut tone_fn);
                let cr: Vec<u8> = (0..w).map(|x| ((rgb_ycc(px(x, y0)).1 as u16 + rgb_ycc(px(x, y1)).1 as u16) / 2) as u8).collect();
                scan(&mut cr.into_iter(), l, w, &mut tone_fn);
                let cb: Vec<u8> = (0..w).map(|x| ((rgb_ycc(px(x, y0)).2 as u16 + rgb_ycc(px(x, y1)).2 as u16) / 2) as u8).collect();
                scan(&mut cb.into_iter(), l, w, &mut tone_fn);
                let b: Vec<u8> = (0..w).map(|x| rgb_ycc(px(x, y1)).0).collect();
                scan(&mut b.into_iter(), l, w, &mut tone_fn);
            }
        }
    }
    tone_fn(0.0, 0.2);
    out
}

/// Streaming SSTV decoder.
pub struct SstvDecoder {
    fs: f64,
    // frequency estimate: mix down by 1900 Hz, low-pass, phase difference
    nco: crate::Nco,
    lp: Vec<f32>,
    hist: VecDeque<Complex32>,
    last: Complex32,
    /// Instantaneous frequency, Hz, from sample `base` on
    freq: VecDeque<f32>,
    base: u64,
    n: u64,
    // VIS detector on 1 ms means
    ms_acc: f64,
    ms_n: usize,
    ms: VecDeque<f32>,
    // picture in progress
    mode: Option<SstvMode>,
    /// Sample where the next scan period's sync is expected
    next_sync: f64,
    period_samples: f64,
    period: usize,
    cur: Option<SstvImage>,
    /// Robot 36: the previous line's luminance and chroma (R-Y)
    y_prev: Vec<u8>,
    chroma_prev: Vec<u8>,
    /// Finished pictures, oldest first
    pub done: VecDeque<SstvImage>,
}

impl SstvDecoder {
    pub fn new(fs: f64) -> SstvDecoder {
        let lp = crate::filter::lowpass(900.0, 600.0, fs);
        SstvDecoder {
            fs,
            nco: crate::Nco::new(1900.0, fs),
            hist: VecDeque::from(vec![Complex32::new(0.0, 0.0); lp.len()]),
            lp,
            last: Complex32::new(1.0, 0.0),
            freq: VecDeque::new(),
            base: 0,
            n: 0,
            ms_acc: 0.0,
            ms_n: 0,
            ms: VecDeque::new(),
            mode: None,
            next_sync: 0.0,
            period_samples: 0.0,
            period: 0,
            cur: None,
            y_prev: Vec::new(),
            chroma_prev: Vec::new(),
            done: VecDeque::new(),
        }
    }

    /// The picture being received (rows so far), if any.
    pub fn current(&self) -> Option<&SstvImage> {
        self.cur.as_ref()
    }

    pub fn process(&mut self, audio: &[f32]) {
        for &a in audio {
            let z0 = self.nco.next() * a;
            self.hist.pop_front();
            self.hist.push_back(z0);
            let mut z = Complex32::new(0.0, 0.0);
            for (h, t) in self.hist.iter().zip(self.lp.iter()) {
                z += h * *t;
            }
            let f = 1900.0 + (z * self.last.conj()).arg() as f64 * self.fs / (2.0 * std::f64::consts::PI);
            self.last = z;
            self.freq.push_back(f as f32);
            self.n += 1;
            self.ms_acc += f;
            self.ms_n += 1;
            if self.ms_n as f64 >= self.fs / 1000.0 {
                self.ms.push_back((self.ms_acc / self.ms_n as f64) as f32);
                self.ms_acc = 0.0;
                self.ms_n = 0;
                if self.ms.len() > 700 {
                    self.ms.pop_front();
                }
                if let Some(m) = self.vis() {
                    self.start(m);
                }
            }
            if self.mode.is_some() {
                self.scan();
            }
            // keep a bit more than one scan period of frequency history
            let keep = (self.fs * 1.2) as usize;
            while self.freq.len() > keep {
                self.freq.pop_front();
                self.base += 1;
            }
        }
    }

    /// VIS header ending now? (on the 1 ms means: leader 1900, start bit 1200, 8 bits, stop 1200)
    fn vis(&mut self) -> Option<SstvMode> {
        let need = 200 + 30 + 240 + 30;
        if self.ms.len() < need {
            return None;
        }
        let k0 = self.ms.len() - need;
        let mean = |a: usize, n: usize| -> f64 { (a + 3..a + n - 3).map(|k| self.ms[k] as f64).sum::<f64>() / (n - 6) as f64 };
        let near = |v: f64, f: f64| (v - f).abs() < 70.0;
        if !near(mean(k0, 200), 1900.0) || !near(mean(k0 + 200, 30), 1200.0) || !near(mean(k0 + 470, 30), 1200.0) {
            return None;
        }
        let mut code = 0u8;
        let mut ones = 0;
        for b in 0..8 {
            let v = mean(k0 + 230 + 30 * b, 30);
            let one = if near(v, 1100.0) {
                true
            } else if near(v, 1300.0) {
                false
            } else {
                return None;
            };
            if b < 7 {
                code |= (one as u8) << b;
            }
            ones += one as u32;
        }
        if ones % 2 != 0 {
            return None; // parity (even, over the 7 data bits and the parity bit)
        }
        let m = SstvMode::from_vis(code)?;
        self.ms.clear();
        Some(m)
    }

    fn start(&mut self, m: SstvMode) {
        // a new VIS while a picture is coming in: keep the old one if it got far enough
        if let Some(old) = self.cur.take() {
            if old.rows * 2 >= old.height {
                self.done.push_back(old);
            }
        }
        let (w, h) = m.size();
        self.mode = Some(m);
        self.period = 0;
        self.period_samples = m.period() * self.fs;
        // the VIS stop bit ended about now (1 ms resolution)
        self.next_sync = self.n as f64;
        self.chroma_prev = vec![128; w];
        self.y_prev = vec![0; w];
        self.cur = Some(SstvImage { mode: m, width: w, height: h, rgb: vec![0; w * h * 3], rows: 0, syncs_found: 0 });
    }

    fn f_at(&self, sample: f64) -> Option<f64> {
        let k = sample.round() as i64 - self.base as i64;
        (k >= 0 && (k as usize) < self.freq.len()).then(|| self.freq[k as usize] as f64)
    }

    /// Mean frequency over [t0, t0 + len) samples.
    fn mean(&self, t0: f64, len: f64) -> Option<f64> {
        let (a, b) = (t0.round() as i64, (t0 + len).round() as i64);
        let mut s = 0.0;
        for k in a..b.max(a + 1) {
            s += self.f_at(k as f64)?;
        }
        Some(s / (b.max(a + 1) - a) as f64)
    }

    /// Decode a scan period once its samples are all in.
    fn scan(&mut self) {
        let Some(m) = self.mode else { return };
        let end = self.next_sync + self.period_samples + 0.01 * self.fs;
        if (self.n as f64) < end {
            return;
        }
        // re-align on the sync pulse: within +-8 ms of the prediction, the start of the
        // window of sync length whose mean frequency is lowest
        let sync_len = m.sync() * self.fs;
        let step = (self.fs / 4000.0).max(1.0);
        let mut best = (f64::MAX, self.next_sync);
        let mut t = self.next_sync - 0.008 * self.fs;
        while t <= self.next_sync + 0.008 * self.fs {
            if let Some(v) = self.mean(t, sync_len) {
                if v < best.0 {
                    best = (v, t);
                }
            }
            t += step;
        }
        let found = (best.0 - SYNC).abs() < 120.0;
        // a 2nd-order loop on the sync times: fast for the first periods, then it trusts its
        // prediction (and learns the sender's clock) so one noisy sync cannot shift a line
        let err = best.1 - self.next_sync;
        let t0 = if found {
            if self.period < 4 {
                self.next_sync + 0.7 * err
            } else {
                self.period_samples += 0.01 * err;
                self.next_sync + 0.1 * err
            }
        } else {
            self.next_sync
        };
        let w = m.size().0;
        let mut rows: Vec<(usize, Vec<u8>, Vec<u8>, Vec<u8>)> = Vec::new();
        let seg_px = |s: f64, len: f64, n: usize| -> Vec<u8> {
            (0..n).map(|x| self.mean(t0 + (s + len * x as f64 / n as f64) * self.fs, len / n as f64 * self.fs).map(level).unwrap_or(0)).collect()
        };
        match m {
            SstvMode::Robot36 => {
                let y = self.period;
                let mut ys = Vec::new();
                let mut ch = Vec::new();
                for (s, len, seg) in layout(m) {
                    match seg {
                        Seg::Y => ys = seg_px(s, len, w),
                        _ => ch = seg_px(s, len, w / 2),
                    }
                }
                // the separator before the chroma says which one it is: 1500 Hz R-Y, 2300 Hz B-Y
                let sep = self.mean(t0 + 0.1 * self.fs, 0.004 * self.fs).unwrap_or(BLACK);
                // ... when it is clearly one or the other; otherwise the line number decides (even: R-Y)
                let is_cb = if (sep - 1900.0).abs() > 250.0 { sep > 1900.0 } else { y % 2 == 1 };
                let ch_full: Vec<u8> = (0..w).map(|x| ch[(x / 2).min(ch.len() - 1)]).collect();
                if is_cb {
                    // B-Y line: completes the R-Y line before it, both get the pair's chroma
                    if y > 0 {
                        rows.push((y - 1, self.y_prev.clone(), self.chroma_prev.clone(), ch_full.clone()));
                    }
                    rows.push((y, ys, self.chroma_prev.clone(), ch_full));
                } else {
                    // R-Y line: shown with neutral blue until its B-Y partner arrives
                    self.y_prev = ys.clone();
                    self.chroma_prev = ch_full.clone();
                    rows.push((y, ys, ch_full, vec![128; w]));
                }
            }
            SstvMode::Pd120 => {
                let l = layout(m);
                let y0 = seg_px(l[0].0, l[0].1, w);
                let cr = seg_px(l[1].0, l[1].1, w);
                let cb = seg_px(l[2].0, l[2].1, w);
                let y1 = seg_px(l[3].0, l[3].1, w);
                rows.push((2 * self.period, y0, cr.clone(), cb.clone()));
                rows.push((2 * self.period + 1, y1, cr, cb));
            }
        }
        if let Some(img) = self.cur.as_mut() {
            for (y, ys, cr, cb) in rows {
                if y >= img.height {
                    continue;
                }
                for x in 0..w {
                    let p = ycc_rgb(ys[x], cr[x], cb[x]);
                    img.rgb[(y * w + x) * 3..(y * w + x) * 3 + 3].copy_from_slice(&p);
                }
                img.rows = img.rows.max(y + 1);
            }
            img.syncs_found += found as usize;
        }
        self.period += 1;
        self.next_sync = t0 + self.period_samples;
        if self.period >= m.periods() {
            if let Some(img) = self.cur.take() {
                self.done.push_back(img);
            }
            self.mode = None;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_image(w: usize, h: usize) -> Vec<u8> {
        // colour bars over a grey ramp
        let bars = [[255, 255, 255], [255, 255, 0], [0, 255, 255], [0, 255, 0], [255, 0, 255], [255, 0, 0], [0, 0, 255], [0, 0, 0]];
        let mut v = Vec::with_capacity(w * h * 3);
        for y in 0..h {
            for x in 0..w {
                let p: [u8; 3] = if y < h * 2 / 3 { bars[x * 8 / w] } else { let g = (x * 255 / w) as u8; [g, g, g] };
                v.extend_from_slice(&p);
            }
        }
        v
    }

    fn mean_err(a: &[u8], b: &[u8]) -> f64 {
        a.iter().zip(b).map(|(x, y)| (*x as f64 - *y as f64).abs()).sum::<f64>() / a.len() as f64
    }

    fn roundtrip(mode: SstvMode, clock_ppm: f64) -> f64 {
        let (w, h) = mode.size();
        let img = test_image(w, h);
        let fs = 48_000.0;
        // the transmitter's clock off by `clock_ppm`: generate at a slightly different rate
        let audio = sstv_audio(mode, &img, fs * (1.0 + clock_ppm * 1e-6));
        let mut d = SstvDecoder::new(fs);
        for c in audio.chunks(4800) {
            d.process(c);
        }
        let got = d.done.pop_front().expect("no picture");
        assert_eq!(got.mode, mode);
        assert_eq!(got.rows, h);
        // compare away from the edges (the filter smears the first and last pixels)
        let mut a = Vec::new();
        let mut b = Vec::new();
        for y in 2..h - 2 {
            for x in 4..w - 4 {
                let k = (y * w + x) * 3;
                a.extend_from_slice(&img[k..k + 3]);
                b.extend_from_slice(&got.rgb[k..k + 3]);
            }
        }
        mean_err(&a, &b)
    }

    #[test]
    fn robot36_roundtrip() {
        let e = roundtrip(SstvMode::Robot36, 0.0);
        assert!(e < 20.0, "mean error {e}");
    }

    #[test]
    fn pd120_roundtrip_with_clock_error() {
        let e = roundtrip(SstvMode::Pd120, 300.0);
        assert!(e < 20.0, "mean error {e}");
    }
}
