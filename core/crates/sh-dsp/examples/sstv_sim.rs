//! SSTV through the whole receive chain, simulated: picture -> SSTV audio -> FM (3 kHz deviation)
//! + white noise at a C/N0 -> NFM demodulator -> SstvDecoder; writes the decoded picture as PPM.
//!     cargo run --release --example sstv_sim -- [robot36|pd120] [C/N0 dB-Hz] [out.ppm]
use sh_dsp::demod::{Demodulator, Mode};
use sh_dsp::sstv::{sstv_audio, SstvDecoder, SstvMode};
use sh_dsp::Complex32;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let mode = if a.get(1).map(|s| s.as_str()) == Some("pd120") { SstvMode::Pd120 } else { SstvMode::Robot36 };
    let cn0: f64 = a.get(2).map(|s| s.parse().unwrap()).unwrap_or(60.0);
    let out = a.get(3).cloned().unwrap_or("sstv.ppm".into());
    let (w, h) = mode.size();
    let bars = [[255u8, 255, 255], [255, 255, 0], [0, 255, 255], [0, 255, 0], [255, 0, 255], [255, 0, 0], [0, 0, 255], [0, 0, 0]];
    let mut img = Vec::new();
    for y in 0..h {
        for x in 0..w {
            let p = if y < h / 2 { bars[x * 8 / w] } else if ((x / 20) + (y / 20)) % 2 == 0 { [230, 230, 230] } else { [20, 20, 120] };
            img.extend_from_slice(&p);
        }
    }
    let fs = 48_000.0;
    let audio = sstv_audio(mode, &img, fs);
    let mut ph = 0.0f64;
    let mut seed = 0x2545F4914F6CDD1Du64;
    let mut u = || {
        seed ^= seed << 13;
        seed ^= seed >> 7;
        seed ^= seed << 17;
        ((seed >> 11) as f64 + 0.5) / (1u64 << 53) as f64
    };
    let sigma = (10f64.powf(-cn0 / 10.0) * fs / 2.0).sqrt();
    let iq: Vec<Complex32> = audio
        .iter()
        .map(|&x| {
            ph += 2.0 * std::f64::consts::PI * 3000.0 * (x as f64 / 0.7) / fs;
            let (u1, u2) = (u(), u());
            let r = (-2.0 * u1.ln()).sqrt() * sigma;
            let t = 2.0 * std::f64::consts::PI * u2;
            Complex32::new((ph.cos() + r * t.cos()) as f32, (ph.sin() + r * t.sin()) as f32)
        })
        .collect();
    let mut dm = Demodulator::new(Mode::Nfm, fs, 0.0, 12_500.0);
    let mut au = Vec::new();
    for c in iq.chunks(4096) {
        dm.process(c, &mut au);
    }
    let mut d = SstvDecoder::new(sh_dsp::demod::AUDIO_RATE);
    d.process(&au);
    let Some(got) = d.done.pop_front().or_else(|| d.current().cloned()) else {
        println!("C/N0 {cn0}: no picture (VIS not found)");
        return;
    };
    let err: f64 = img.iter().zip(&got.rgb).map(|(a, b)| (*a as f64 - *b as f64).abs()).sum::<f64>() / img.len() as f64;
    println!("{} C/N0 {cn0} dB-Hz: {} rows, syncs {}/{}, mean error {err:.1} (0-255)", mode.name(), got.rows, got.syncs_found, got.rows);
    let mut f = format!("P6\n{w} {h}\n255\n").into_bytes();
    f.extend_from_slice(&got.rgb);
    std::fs::write(&out, f).unwrap();
}
