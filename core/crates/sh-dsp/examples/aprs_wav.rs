//! Decode APRS from a 16-bit mono audio WAV (the lab's /audio capture):
//!     cargo run --release --example aprs_wav -- file.wav
use sh_dsp::afsk::{AfskDecoder, AfskParams};
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let b = std::fs::read(&a[1]).unwrap();
    let fs = u32::from_le_bytes([b[24], b[25], b[26], b[27]]) as f64;
    let x: Vec<f32> = b[44..].chunks(2).map(|c| i16::from_le_bytes([c[0], c[1]]) as f32 / 32768.0).collect();
    let env = |k: &str, d: f64| std::env::var(k).ok().and_then(|v| v.parse().ok()).unwrap_or(d);
    let def = AfskParams::default();
    let prm = AfskParams { lp_cut: env("LP", def.lp_cut), lp_trans: env("LPT", def.lp_trans), fix_bits: env("FIX", 1.0) > 0.0, ..def };
    let mut d = AfskDecoder::with_params(fs, prm);
    for c in x.chunks(960) {
        d.process(c);
    }
    let rms = (x.iter().map(|v| v * v).sum::<f32>() / x.len() as f32).sqrt();
    println!("fs {fs}, {} s, rms {rms:.3}, {} frames, {} bad CRC, {} fixed", x.len() as f64 / fs, d.frames.len(), d.bad_crc, d.fixed);
}
