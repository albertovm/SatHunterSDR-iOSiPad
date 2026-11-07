//! Decode 9600 bd G3RUH from a WAV of FM-discriminator audio (SatNOGS observation audio):
//!     cargo run --release --example g3ruh_wav -- file.wav   (DUMP=1 prints the frames as hex on stderr)
use sh_dsp::fsk9600::G3ruhDecoder;

fn main() {
    let path = std::env::args().nth(1).expect("wav file");
    let b = std::fs::read(&path).unwrap();
    // minimal PCM16 mono parser
    let mut i = 12;
    let (mut fs, mut data) = (48_000u32, &b[0..0]);
    while i + 8 <= b.len() {
        let id = &b[i..i + 4];
        let n = u32::from_le_bytes(b[i + 4..i + 8].try_into().unwrap()) as usize;
        if id == b"fmt " {
            fs = u32::from_le_bytes(b[i + 12..i + 16].try_into().unwrap());
        } else if id == b"data" {
            data = &b[i + 8..(i + 8 + n).min(b.len())];
        }
        i += 8 + n + (n & 1);
    }
    let x: Vec<f32> = data.chunks_exact(2).map(|c| i16::from_le_bytes([c[0], c[1]]) as f32 / 32768.0).collect();
    let env = |k: &str, v: f64| std::env::var(k).ok().and_then(|s| s.parse().ok()).unwrap_or(v);
    let mut d = G3ruhDecoder::with_params(fs as f64, env("BAUD", 9600.0), env("LP", 0.6), env("PG", 0.25));
    let mut all = Vec::new();
    for c in x.chunks(960) {
        d.process(c);
        all.extend(d.frames.drain(..));
    }
    if std::env::var("DUMP").is_ok() {
        for f in &all {
            eprintln!("{}", f.data.iter().map(|b| format!("{b:02x}")).collect::<String>());
        }
    }
    let ax = all.iter().filter(|f| f.ax25.is_some()).count();
    println!("fs {fs}, {:.0} s: {} frames ({} AX.25), bad CRC {}", x.len() as f64 / fs as f64, all.len(), ax, d.bad_crc);
}
