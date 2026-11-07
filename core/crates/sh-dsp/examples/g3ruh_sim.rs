//! Packet success of the 9600 bd G3RUH chain vs C/N0, simulated (FM +-3 kHz, white noise,
//! discriminator at 48 kHz -> G3ruhDecoder):  cargo run --release --example g3ruh_sim -- [dev Hz]
use sh_dsp::afsk::Ax25Frame;
use sh_dsp::fsk9600::{g3ruh_baseband, g3ruh_bits, G3ruhDecoder, BAUD};
use sh_dsp::Complex32;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let dev: f64 = a.get(1).map(|s| s.parse().unwrap()).unwrap_or(3000.0);
    let chan: f64 = a.get(2).map(|s| s.parse().unwrap()).unwrap_or(20_000.0);
    let fs = 48_000.0;
    let n_pk = 50;
    let mut bits = Vec::new();
    for k in 0..n_pk {
        let f = Ax25Frame::ui("HG0SAT", "CQ", &[], format!("telemetry frame {k:03} {}", "abcdefgh".repeat(10)).as_bytes());
        bits.extend(g3ruh_bits(&f, 20, 4));
    }
    let bb = g3ruh_baseband(&bits, fs, BAUD);
    // channel filter (the receiver's IF): simple FIR low-pass on I and Q at +-chan/2
    let taps = sh_dsp::filter::lowpass(chan / 2.0, 3000.0, fs);
    let mut seed = 0x2545f4914f6cdd1du64;
    let mut u = move || {
        seed ^= seed << 13;
        seed ^= seed >> 7;
        seed ^= seed << 17;
        ((seed >> 11) as f64 + 0.5) / (1u64 << 53) as f64
    };
    println!("G3RUH 9600 bd, deviation {dev} Hz, channel {chan} Hz, {n_pk} frames of {} bytes", 18 + 80 + 2);
    for cn0 in [46.0, 48.0, 50.0, 52.0, 54.0, 56.0] {
        let sigma = (10f64.powf(-cn0 / 10.0) * fs / 2.0).sqrt();
        let mut ph = 0.0f64;
        let x: Vec<Complex32> = bb
            .iter()
            .map(|&v| {
                ph += 2.0 * std::f64::consts::PI * dev * v as f64 / fs;
                let (u1, u2) = (u(), u());
                let r = (-2.0 * u1.ln()).sqrt() * sigma;
                Complex32::new((ph.cos() + r * (2.0 * std::f64::consts::PI * u2).cos()) as f32, (ph.sin() + r * (2.0 * std::f64::consts::PI * u2).sin()) as f32)
            })
            .collect();
        // IF filter
        let n = taps.len();
        let y: Vec<Complex32> = (0..x.len()).map(|i| {
            let mut acc = Complex32::new(0.0, 0.0);
            for k in 0..n.min(i + 1) {
                acc += x[i - k] * taps[k];
            }
            acc
        }).collect();
        let mut last = Complex32::new(1.0, 0.0);
        let d: Vec<f32> = y.iter().map(|v| { let a = (*v * last.conj()).arg(); last = *v; a }).collect();
        let mut dec = G3ruhDecoder::new(fs);
        for c in d.chunks(960) {
            dec.process(c);
        }
        println!("C/N0 {cn0:4.1} dB-Hz: {:3}/{n_pk} frames ({:5.1} %), bad CRC {}", dec.count, 100.0 * dec.count as f64 / n_pk as f64, dec.bad_crc);
    }
}
