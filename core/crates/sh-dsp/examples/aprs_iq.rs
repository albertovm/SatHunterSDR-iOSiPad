//! Decode APRS / AX.25 from raw complex float32 IQ (cf32, as the lab writes for the VSG60):
//!     cargo run --release --example aprs_iq -- file.cf32 <sample rate> [offset Hz]
use sh_dsp::afsk::AfskDecoder;
use sh_dsp::demod::{Demodulator, Mode, AUDIO_RATE};
use sh_dsp::Complex32;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let b = std::fs::read(&a[1]).expect("file");
    let fs: f64 = a[2].parse().unwrap();
    let off: f64 = a.get(3).map(|s| s.parse().unwrap()).unwrap_or(0.0);
    let iq: Vec<Complex32> = b.chunks(8).map(|c| Complex32::new(f32::from_le_bytes([c[0], c[1], c[2], c[3]]), f32::from_le_bytes([c[4], c[5], c[6], c[7]]))).collect();
    let mut dm = Demodulator::new(Mode::Nfm, fs, off, 12_500.0);
    let mut audio = Vec::new();
    for c in iq.chunks(4096) {
        dm.process(c, &mut audio);
    }
    let mut d = AfskDecoder::new(AUDIO_RATE);
    d.process(&audio);
    for f in &d.frames {
        println!("{}", f.tnc2());
    }
    eprintln!("{} frames, {} bad CRC", d.frames.len(), d.bad_crc);
}
