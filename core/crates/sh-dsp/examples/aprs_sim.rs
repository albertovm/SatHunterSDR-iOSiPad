//! Packet success of the APRS chain vs C/N0, simulated (FM-modulated AFSK 1200 + white noise ->
//! NFM demodulator -> AfskDecoder), to compare decoder variants offline:
//!     cargo run --release --example aprs_sim -- [deviation Hz] [channel Hz] [variant]
use sh_dsp::afsk::{afsk_audio, hdlc_nrzi_bits, AfskDecoder, Ax25Frame};
use sh_dsp::demod::{Demodulator, Mode, AUDIO_RATE};
use sh_dsp::Complex32;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let dev: f64 = a.get(1).map(|s| s.parse().unwrap()).unwrap_or(3000.0);
    let chan: f64 = a.get(2).map(|s| s.parse().unwrap()).unwrap_or(12_500.0);
    let variant = a.get(3).cloned().unwrap_or("disc".into());
    let wn_hz: f64 = a.get(4).map(|s| s.parse().unwrap()).unwrap_or(3000.0);
    let fs: f64 = std::env::var("FS").ok().and_then(|v| v.parse().ok()).unwrap_or(64_000.0);
    let foff: f64 = std::env::var("FOFF").ok().and_then(|v| v.parse().ok()).unwrap_or(0.0); // signal offset from the VFO
    let vfo: f64 = std::env::var("VFO").ok().and_then(|v| v.parse().ok()).unwrap_or(0.0); // VFO offset from the centre
    let env = |k: &str, d: f64| std::env::var(k).ok().and_then(|v| v.parse().ok()).unwrap_or(d);
    let def = sh_dsp::afsk::AfskParams::default();
    let prm = sh_dsp::afsk::AfskParams {
        lp_cut: env("LP", def.lp_cut), lp_trans: env("LPT", def.lp_trans), smooth: env("SM", def.smooth),
        pll_gain: env("PG", def.pll_gain), deemph_hz: env("DE", def.deemph_hz), fix_bits: env("FIX", 0.0) > 0.0,
    };
    eprintln!("{prm:?}");
    let n_pk = std::env::var("NP").ok().and_then(|v| v.parse().ok()).unwrap_or(40usize);
    // packets: audio at fs, FM to IQ
    let mut audio = Vec::new();
    for k in 0..n_pk {
        let raw = Ax25Frame::ui("HG0LAB-1", "APRS", &["WIDE1-1"], format!("!4729.87N/01902.41E>SatHunter lab packet {k:02}").as_bytes());
        audio.extend(afsk_audio(&hdlc_nrzi_bits(&raw, 40, 3), fs));
        audio.extend(vec![0.0f32; (0.2 * fs) as usize]);
    }
    let peak = audio.iter().fold(0.0f32, |m, v| m.max(v.abs()));
    let mut ph = 0.0f64;
    let sig: Vec<Complex32> = audio
        .iter()
        .map(|&x| {
            ph += 2.0 * std::f64::consts::PI * (dev * (x / peak) as f64 + vfo + foff) / fs;
            Complex32::new(ph.cos() as f32, ph.sin() as f32)
        })
        .collect();
    let mut seed = 0x9e3779b97f4a7c15u64;
    let mut gauss = || {
        let mut u = || {
            seed ^= seed << 13;
            seed ^= seed >> 7;
            seed ^= seed << 17;
            ((seed >> 11) as f64 + 0.5) / (1u64 << 53) as f64
        };
        let (u1, u2) = (u(), u());
        let r = (-2.0 * u1.ln()).sqrt();
        (r * (2.0 * std::f64::consts::PI * u2).cos(), r * (2.0 * std::f64::consts::PI * u2).sin())
    };
    println!("dev {dev} Hz, channel {chan} Hz, {variant} {wn_hz}");
    for cn0 in [47.0, 48.0, 49.0, 50.0, 51.0] {
        // carrier power 1; N0 = 1/10^(cn0/10) per Hz; per complex sample noise power N0*fs
        let n0 = 10f64.powf(-cn0 / 10.0);
        let sigma = (n0 * fs / 2.0).sqrt();
        let x: Vec<Complex32> = sig.iter().map(|s| { let (a, b) = gauss(); *s + Complex32::new((a * sigma) as f32, (b * sigma) as f32) }).collect();
        let mut au = Vec::new();
        let mut d;
        if variant == "pll" {
            // channel filter, then a 2nd-order PLL FM demodulator (threshold extension)
            let mut ch = sh_dsp::channel::Channel::new(fs, 0.0, chan, 40_000.0);
            let fc = ch.rate();
            let (mut tmp, mut bb) = (Vec::new(), Vec::new());
            let t = 1.0 / fc;
            let wn = 2.0 * std::f64::consts::PI * wn_hz;
            let (kp, ki) = (2.0 * 0.707 * wn * t, (wn * t).powi(2));
            let (mut th, mut w) = (0.0f64, 0.0f64);
            for c in x.chunks(4096) {
                bb.clear();
                ch.process(c, &mut tmp, &mut bb);
                for z in &bb {
                    let r = Complex32::new(th.cos() as f32, -(th.sin() as f32));
                    let e = (*z * r).arg() as f64;
                    w += ki * e;
                    th += w + kp * e;
                    if th > std::f64::consts::PI { th -= 2.0 * std::f64::consts::PI; } else if th < -std::f64::consts::PI { th += 2.0 * std::f64::consts::PI; }
                    au.push((w + kp * e) as f32);
                }
            }
            d = AfskDecoder::with_params(fc, prm);
        } else {
            let mut dm = Demodulator::new(Mode::Nfm, fs, vfo, chan);
            for c in x.chunks(4096) {
                dm.process(c, &mut au);
            }
            d = AfskDecoder::with_params(AUDIO_RATE, prm);
        }
        d.process(&au);
        let junk = d.frames.iter().filter(|f| !f.tnc2().starts_with("HG0LAB-1>APRS,WIDE1-1:!4729.87N/01902.41E>SatHunter lab packet")).count();
        if junk > 0 { eprintln!("C/N0 {cn0}: {junk} wrong frames"); }
        let mut got: Vec<String> = d.frames.iter().map(|f| f.tnc2()).filter(|t| t.starts_with("HG0LAB-1>APRS,WIDE1-1:!4729.87N/01902.41E>SatHunter lab packet")).collect();
        got.sort();
        got.dedup();
        println!("C/N0 {cn0:4.1} dB-Hz: {:3.0} % ({} of {n_pk}, bad CRC {})", 100.0 * got.len() as f64 / n_pk as f64, got.len(), d.bad_crc);
    }
}
