//! Decode SSTV from recorded audio (16-bit WAV, e.g. the lab link's /audio), several files back to back:
//!     cargo run --release --example sstv_wav -- out.ppm a.wav b.wav ...
use sh_dsp::sstv::SstvDecoder;

fn wav(path: &str) -> (f64, Vec<f32>) {
    let b = std::fs::read(path).unwrap();
    let rate = u32::from_le_bytes([b[24], b[25], b[26], b[27]]) as f64;
    let mut k = 12;
    while &b[k..k + 4] != b"data" {
        k += 8 + u32::from_le_bytes([b[k + 4], b[k + 5], b[k + 6], b[k + 7]]) as usize;
    }
    let d = &b[k + 8..];
    (rate, d.chunks_exact(2).map(|c| i16::from_le_bytes([c[0], c[1]]) as f32 / 32768.0).collect())
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let mut dec: Option<SstvDecoder> = None;
    for p in &a[2..] {
        let (fs, s) = wav(p);
        dec.get_or_insert_with(|| SstvDecoder::new(fs)).process(&s);
    }
    let mut d = dec.unwrap();
    let img = d.done.pop_front().or_else(|| d.current().cloned());
    match img {
        Some(i) => {
            println!("{}: {} rows, syncs {}", i.mode.name(), i.rows, i.syncs_found);
            let mut f = format!("P6\n{} {}\n255\n", i.width, i.height).into_bytes();
            f.extend_from_slice(&i.rgb);
            std::fs::write(&a[1], f).unwrap();
        }
        None => println!("no picture"),
    }
}
