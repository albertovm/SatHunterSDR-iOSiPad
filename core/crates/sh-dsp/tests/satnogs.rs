//! Real satellite recordings from the SatNOGS network (testdata/satnogs, see its README):
//! the AFSK1200 / AX.25 and SSTV chains must keep decoding what they decode today.
//! Run in release (`cargo test --release`); a debug build is slow on minutes of audio.

use lewton::inside_ogg::OggStreamReader;
use sh_dsp::afsk::{AfskDecoder, AfskParams};
use sh_dsp::sstv::SstvDecoder;
use std::path::PathBuf;

fn ogg(name: &str) -> (f64, Vec<f32>) {
    let p = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("testdata/satnogs").join(name);
    let mut r = OggStreamReader::new(std::fs::File::open(&p).unwrap()).unwrap();
    let fs = r.ident_hdr.audio_sample_rate as f64;
    let ch = r.ident_hdr.audio_channels as usize;
    let mut out = Vec::new();
    while let Some(pk) = r.read_dec_packet_itl().unwrap() {
        out.extend(pk.chunks(ch).map(|c| c[0] as f32 / 32768.0));
    }
    (fs, out)
}

fn afsk(name: &str, multi: bool) -> Vec<sh_dsp::afsk::Ax25Frame> {
    let (fs, x) = ogg(name);
    let mut d = AfskDecoder::with_params(fs, AfskParams { multi, ..AfskParams::default() });
    for c in x.chunks(960) {
        d.process(c);
    }
    d.frames.into_iter().collect()
}

#[test]
fn iss_aprs_beacon() {
    // SatNOGS 15339570 (DB0RBX), ISS 437.825 MHz: the station's own decoder got this beacon twice
    // in the pass; the discriminator alone misses it, the merged detectors get it
    let f = afsk("satnogs_15339570_iss_afsk1200.ogg", true);
    assert_eq!(f.len(), 1, "{:?}", f.iter().map(|f| f.tnc2()).collect::<Vec<_>>());
    assert_eq!(f[0].src, "RS0ISS");
    assert!(String::from_utf8_lossy(&f[0].info).contains("ARISS-International Space Station"), "{}", f[0].tnc2());
}

#[test]
fn telemetry_68795() {
    // SatNOGS 15372907 (JA1HCB-pi3), 437.505 MHz, 66 s with 8 frames in the station's decode
    let all = afsk("satnogs_15372907_68795_afsk1200.ogg", true);
    let one = afsk("satnogs_15372907_68795_afsk1200.ogg", false);
    assert!(all.len() >= 7, "{} frames", all.len());
    assert!(all.len() > one.len(), "merged {} vs discriminator {}", all.len(), one.len());
}

#[test]
fn pcsat_aprs() {
    // SatNOGS 15370705 (KI5YNG), PCSAT 144.39 MHz
    let f = afsk("satnogs_15370705_pcsat_afsk1200.ogg", true);
    assert!(f.len() >= 2, "{} frames", f.len());
}

#[test]
fn rs18s_robot36_picture() {
    // SatNOGS 15332613 (PE0SAT-21), 437.35 MHz: a Robot 36 picture the station's own SSTV
    // decoder lost (its PNG is noise); this chain gets the whole picture
    let (fs, x) = ogg("satnogs_15332613_rs18s_robot36.ogg");
    let mut d = SstvDecoder::new(fs);
    for c in x.chunks(960) {
        d.process(c);
    }
    let img = d.done.front().cloned().or_else(|| d.current().cloned()).expect("no picture");
    assert_eq!(img.mode.name(), "Robot 36");
    assert_eq!(img.rows, img.height);
    assert!(img.syncs_found >= 150, "{} syncs", img.syncs_found);
}
