//! Lab link: the receiver as a measuring instrument on the LAN. Debug mode in the app starts it;
//! a script on a PC (tools/lab/lab.py) drives a signal generator, tells the phone which phase
//! it is in, and reads the measurements back. Off by default; every request needs the PIN the
//! phone shows.
//!
//! HTTP on port 8765 (JSON unless noted):
//!   GET  /                       short help page (no PIN needed)
//!   GET  /status                 the engine status
//!   POST /cmd                    any engine command (the app's JSON API)
//!   GET  /measure?hz=&bw=&secs=  channel at `hz`: peak level, noise floor, SNR, frequency offset
//!   GET  /cw?secs=               CW decode of the last `secs` of demodulated audio
//!   GET  /iq?secs=               `secs` of IQ as an SDR++ style WAV (binary)
//!   POST /phase                  {"phase","step","total","detail"}: shown on the phone's console
//!   POST /log                    {"line"}: a line on the phone's console
//!   GET  /log                    the console lines
//! PIN: `?pin=123456` or the header `X-Lab-Pin`.

use super::*;
use std::io::Read;
use std::sync::atomic::AtomicBool;
use std::time::Instant;

pub const PORT: u16 = 8765;
const LOG_MAX: usize = 200;

/// What the DSP hands the lab link while it is on.
#[derive(Default)]
pub(crate) struct Tap {
    /// (centre Hz, rate, spectrum row dBFS)
    pub rows: VecDeque<(f64, f64, Vec<f32>)>,
    /// demodulated audio, 48 kHz
    pub audio: VecDeque<f32>,
}

pub(crate) struct Lab {
    pub port: u16,
    pub pin: String,
    pub phase: Value,
    pub log: VecDeque<String>,
    pub client: String,
    pub requests: u64,
    stop: Arc<AtomicBool>,
    thread: Option<JoinHandle<()>>,
}

const TAP_ROWS: usize = 30 * 60; // ~60 s of rows at 30 fps
const TAP_AUDIO: usize = 48_000 * 60;

fn clock() -> String {
    let t = now_unix() as i64;
    format!("{:02}:{:02}:{:02}", t.rem_euclid(86_400) / 3600, t.rem_euclid(3600) / 60, t.rem_euclid(60))
}

pub(crate) fn log(i: &Inner, line: impl Into<String>) {
    if let Some(l) = lock(&i.lab).as_mut() {
        l.log.push_back(format!("{} {}", clock(), line.into()));
        while l.log.len() > LOG_MAX {
            l.log.pop_front();
        }
    }
}

/// The address the phone is reached at on the LAN (the interface of the default route; the
/// app also lists every interface itself).
fn lan_ips() -> Vec<String> {
    let mut v = Vec::new();
    for probe in ["192.0.2.1:9", "10.255.255.255:9", "172.31.255.255:9"] {
        if let Ok(s) = std::net::UdpSocket::bind("0.0.0.0:0") {
            if s.connect(probe).is_ok() {
                if let Ok(a) = s.local_addr() {
                    let ip = a.ip().to_string();
                    if !a.ip().is_loopback() && !a.ip().is_unspecified() && !v.contains(&ip) {
                        v.push(ip);
                    }
                }
            }
        }
    }
    v
}

pub(crate) fn valid_pin(p: &str) -> bool {
    (4..=8).contains(&p.len()) && p.bytes().all(|b| b.is_ascii_digit())
}

/// A new PIN for the running lab link (the setting is saved by the caller)
pub(crate) fn set_pin(i: &Inner, pin: &str) {
    if let Some(l) = lock(&i.lab).as_mut() {
        l.pin = if valid_pin(pin) { pin.to_string() } else { new_pin() };
    }
}

fn new_pin() -> String {
    let n = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_nanos()).unwrap_or(0);
    let mut x = (n as u64) ^ 0x9E37_79B9_7F4A_7C15;
    x ^= x >> 33;
    x = x.wrapping_mul(0xff51_afd7_ed55_8ccd);
    x ^= x >> 33;
    format!("{:06}", x % 1_000_000)
}

pub(crate) fn status(i: &Inner) -> Value {
    match lock(&i.lab).as_ref() {
        None => json!({ "on": false }),
        Some(l) => json!({
            "on": true,
            "port": l.port,
            "pin": l.pin,
            "ips": lan_ips(),
            "phase": l.phase,
            "client": l.client,
            "requests": l.requests,
            "log": l.log.iter().rev().take(14).rev().cloned().collect::<Vec<_>>(),
        }),
    }
}

pub(crate) fn start(i: &Arc<Inner>, port: Option<u16>) -> Result<Value, String> {
    if lock(&i.lab).is_some() {
        return Ok(status(i));
    }
    let port = port.unwrap_or(PORT);
    let server = tiny_http::Server::http(("0.0.0.0", port)).map_err(|e| format!("lab link: port {port}: {e}"))?;
    let stop = Arc::new(AtomicBool::new(false));
    let fixed = lock(&i.cfg).lab_pin.trim().to_string();
    let pin = if valid_pin(&fixed) { fixed } else { new_pin() };
    *lock(&i.lab) = Some(Lab {
        port,
        pin: pin.clone(),
        phase: Value::Null,
        log: VecDeque::new(),
        client: String::new(),
        requests: 0,
        stop: stop.clone(),
        thread: None,
    });
    *lock(&i.tap) = Tap::default();
    i.lab_on.store(true, Ordering::SeqCst);
    let ii = i.clone();
    let t = std::thread::Builder::new()
        .name("lab-link".into())
        .spawn(move || {
            while !stop.load(Ordering::SeqCst) {
                match server.recv_timeout(Duration::from_millis(200)) {
                    Ok(Some(rq)) => handle(&ii, rq),
                    Ok(None) => {}
                    Err(_) => break,
                }
            }
        })
        .map_err(|e| e.to_string())?;
    if let Some(l) = lock(&i.lab).as_mut() {
        l.thread = Some(t);
    }
    let ips = lan_ips();
    log(i, format!("lab link on, port {port}, PIN {pin}"));
    if ips.is_empty() {
        log(i, "no LAN address yet: connect Wi-Fi or USB Ethernet");
    }
    for ip in &ips {
        log(i, format!("on the PC: python lab.py --phone {ip} --pin {pin}"));
    }
    Ok(status(i))
}

pub(crate) fn stop(i: &Inner) {
    i.lab_on.store(false, Ordering::SeqCst);
    let l = lock(&i.lab).take();
    if let Some(mut l) = l {
        l.stop.store(true, Ordering::SeqCst);
        if let Some(t) = l.thread.take() {
            let _ = t.join();
        }
    }
    *lock(&i.tap) = Tap::default();
}

/// Called by the DSP thread for every block while the lab link is on.
pub(crate) fn feed(i: &Inner, center: f64, rate: f64, rows: &[Vec<f32>], audio: &[f32]) {
    let mut t = lock(&i.tap);
    for r in rows {
        t.rows.push_back((center, rate, r.clone()));
    }
    while t.rows.len() > TAP_ROWS {
        t.rows.pop_front();
    }
    t.audio.extend(audio.iter());
    while t.audio.len() > TAP_AUDIO {
        t.audio.pop_front();
    }
}

fn query(url: &str) -> std::collections::HashMap<String, String> {
    url.split_once('?')
        .map(|(_, q)| q.split('&').filter_map(|kv| kv.split_once('=')).map(|(k, v)| (k.to_string(), v.replace("%20", " "))).collect())
        .unwrap_or_default()
}

fn reply(rq: tiny_http::Request, code: u16, v: &Value) {
    let h = tiny_http::Header::from_bytes(&b"Content-Type"[..], &b"application/json"[..]).unwrap();
    let _ = rq.respond(tiny_http::Response::from_string(v.to_string()).with_status_code(code).with_header(h));
}

const HELP: &str = "<!doctype html><meta charset=utf-8><title>SatHunterSDR lab link</title>\
<body style='font-family:monospace;background:#0a0f16;color:#5ae08c;padding:16px'>\
<h3>SatHunterSDR lab link</h3><p>The phone shows its address and PIN on the lab console.</p>\
<p>On the PC: <b>python tools/lab/lab.py --phone &lt;address&gt; --pin &lt;PIN&gt;</b></p>\
<p>JSON API (PIN as ?pin= or X-Lab-Pin): /status, POST /cmd, /measure?hz=&amp;bw=&amp;secs=, /cw?secs=, /iq?secs=, POST /phase, POST /log, /log</p></body>";

fn handle(i: &Arc<Inner>, mut rq: tiny_http::Request) {
    let url = rq.url().to_string();
    let path = url.split('?').next().unwrap_or("").to_string();
    let q = query(&url);
    let who = rq.remote_addr().map(|a| a.ip().to_string()).unwrap_or_default();
    if path == "/" {
        let h = tiny_http::Header::from_bytes(&b"Content-Type"[..], &b"text/html; charset=utf-8"[..]).unwrap();
        let _ = rq.respond(tiny_http::Response::from_string(HELP).with_header(h));
        return;
    }
    let pin_hdr = rq.headers().iter().find(|h| h.field.equiv("X-Lab-Pin")).map(|h| h.value.as_str().to_string());
    let pin = lock(&i.lab).as_ref().map(|l| l.pin.clone()).unwrap_or_default();
    if pin.is_empty() || (q.get("pin") != Some(&pin) && pin_hdr.as_deref() != Some(pin.as_str())) {
        log(i, format!("{who}: wrong PIN for {path}"));
        return reply(rq, 403, &json!({ "ok": false, "error": "wrong or missing PIN" }));
    }
    let first = {
        let mut g = lock(&i.lab);
        match g.as_mut() {
            Some(l) => {
                l.requests += 1;
                let f = l.client != who;
                l.client = who.clone();
                f
            }
            None => false,
        }
    };
    if first {
        log(i, format!("PC connected: {who}"));
    }
    let mut body = String::new();
    let _ = rq.as_reader().take(1 << 20).read_to_string(&mut body);
    let num = |k: &str, d: f64| q.get(k).and_then(|v| v.parse::<f64>().ok()).unwrap_or(d);
    let r: Result<Value, String> = match (rq.method().as_str(), path.as_str()) {
        ("GET", "/status") => Ok(super::status(i)),
        ("POST", "/cmd") => match serde_json::from_str::<Cmd>(&body) {
            Ok(Cmd::LabStart { .. }) | Ok(Cmd::LabStop) => Err("not over the lab link".into()),
            Ok(c) => {
                let short: String = body.chars().take(60).collect();
                log(i, format!("cmd {short}"));
                run_cmd(i, c)
            }
            Err(e) => Err(format!("bad command: {e}")),
        },
        ("GET", "/measure") => measure(i, num("hz", f64::NAN), num("bw", 2000.0), num("secs", 2.0).clamp(0.2, 30.0)),
        ("GET", "/cw") => cw(i, num("secs", 20.0).clamp(2.0, 60.0)),
        ("GET", "/iq") => return iq(i, rq, num("secs", 2.0).clamp(0.1, 30.0)),
        ("POST", "/phase") => {
            let v: Value = serde_json::from_str(&body).unwrap_or(Value::Null);
            let p = v["phase"].as_str().unwrap_or("").to_string();
            let step = match (v["step"].as_u64(), v["total"].as_u64()) {
                (Some(a), Some(b)) => format!("[{a}/{b}] "),
                _ => String::new(),
            };
            log(i, format!("PHASE {step}{p} {}", v["detail"].as_str().unwrap_or("")));
            if let Some(l) = lock(&i.lab).as_mut() {
                l.phase = v;
            }
            Ok(json!({}))
        }
        ("POST", "/log") => {
            let v: Value = serde_json::from_str(&body).unwrap_or(Value::Null);
            log(i, format!("PC: {}", v["line"].as_str().unwrap_or(&body)));
            Ok(json!({}))
        }
        ("GET", "/log") => Ok(json!({ "log": lock(&i.lab).as_ref().map(|l| l.log.iter().cloned().collect::<Vec<_>>()).unwrap_or_default() })),
        _ => Err(format!("unknown {} {}", rq.method(), path)),
    };
    match r {
        Ok(mut v) => {
            if v.is_object() {
                v["ok"] = json!(true);
            }
            reply(rq, 200, &v)
        }
        Err(e) => {
            log(i, format!("error: {e}"));
            reply(rq, 400, &json!({ "ok": false, "error": e }))
        }
    }
}

/// Average the spectrum over `secs` (fresh rows only) and measure the channel at `hz`.
fn measure(i: &Inner, hz: f64, bw: f64, secs: f64) -> Result<Value, String> {
    if !i.running.load(Ordering::SeqCst) {
        return Err("the receiver is not running".into());
    }
    lock(&i.tap).rows.clear();
    let t0 = Instant::now();
    std::thread::sleep(Duration::from_secs_f64(secs));
    let rows: Vec<(f64, f64, Vec<f32>)> = lock(&i.tap).rows.iter().cloned().collect();
    let Some((c, rate, first)) = rows.last().cloned() else { return Err("no spectrum rows (receiver stalled?)".into()) };
    let n = first.len();
    let same: Vec<&Vec<f32>> = rows.iter().filter(|r| (r.0 - c).abs() < 0.5 && r.1 == rate && r.2.len() == n).map(|r| &r.2).collect();
    let mut avg = vec![0.0f64; n];
    for r in &same {
        for (a, v) in avg.iter_mut().zip(r.iter()) {
            *a += 10f64.powf(*v as f64 / 10.0);
        }
    }
    for a in avg.iter_mut() {
        *a /= same.len() as f64;
    }
    let bin_hz = rate / n as f64;
    let f_of = |k: usize| c + (k as f64 - n as f64 / 2.0) * bin_hz;
    let hz = if hz.is_finite() { hz } else { lock(&i.cfg).vfo_hz };
    // noise: median bin away from the channel, DC and the band edges
    let mut noise: Vec<f64> = (0..n)
        .filter(|&k| (f_of(k) - hz).abs() > bw.max(4.0 * bin_hz) && (k as i64 - n as i64 / 2).abs() > 3 && k > n / 16 && k < n * 15 / 16)
        .map(|k| avg[k])
        .collect();
    noise.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let floor = noise.get(noise.len() / 2).copied().unwrap_or(1e-30).max(1e-30);
    let in_ch: Vec<usize> = (0..n).filter(|&k| (f_of(k) - hz).abs() <= bw / 2.0).collect();
    if in_ch.is_empty() {
        return Err(format!("{hz:.0} Hz is not in the span {:.0}..{:.0}", c - rate / 2.0, c + rate / 2.0));
    }
    let kp = *in_ch.iter().max_by(|a, b| avg[**a].partial_cmp(&avg[**b]).unwrap()).unwrap();
    // parabolic interpolation of the peak frequency
    let frac = if kp > 0 && kp + 1 < n {
        let (a, b, d) = (avg[kp - 1].ln(), avg[kp].ln(), avg[kp + 1].ln());
        let den = a - 2.0 * b + d;
        if den.abs() > 1e-12 { 0.5 * (a - d) / den } else { 0.0 }
    } else {
        0.0
    };
    let peak_hz = f_of(kp) + frac * bin_hz;
    let ch_power: f64 = in_ch.iter().map(|&k| avg[k]).sum();
    let ch_noise = floor * in_ch.len() as f64;
    let db = |x: f64| 10.0 * x.max(1e-30).log10();
    let v = json!({
        "hz": hz,
        "bw": bw,
        "secs": t0.elapsed().as_secs_f64(),
        "rows": same.len(),
        "bin_hz": bin_hz,
        "center_hz": c,
        "rate": rate,
        "peak_dbfs": db(avg[kp]),
        "noise_dbfs_per_bin": db(floor),
        "peak_snr_db": db(avg[kp] / floor),
        "channel_snr_db": db((ch_power - ch_noise).max(1e-30) / ch_noise),
        "peak_hz": peak_hz,
        "offset_hz": peak_hz - hz,
        "offset_ppm": (peak_hz - hz) / hz * 1e6,
        "cn0_dbhz": db(avg[kp] / floor) + 10.0 * (bin_hz * 2.0).log10(), // BH4 window: ~2 bins noise bandwidth
    });
    log(i, format!("measure {:.4} MHz: peak {:+.1} dB over noise, offset {:+.0} Hz", hz / 1e6, db(avg[kp] / floor), peak_hz - hz));
    Ok(v)
}

/// CW decode of the last `secs` of audio.
fn cw(i: &Inner, secs: f64) -> Result<Value, String> {
    let n = (secs * sh_dsp::demod::AUDIO_RATE) as usize;
    let a: Vec<f32> = {
        let t = lock(&i.tap);
        let skip = t.audio.len().saturating_sub(n);
        t.audio.iter().skip(skip).copied().collect()
    };
    if a.len() < 48_000 {
        return Err("less than 1 s of audio yet".into());
    }
    let r = sh_dsp::cw::decode(&a, sh_dsp::demod::AUDIO_RATE, (200.0, 3500.0));
    log(i, format!("cw: \"{}\" {:.0} WPM C/N0 {:.0} dB-Hz", r.text, r.wpm, r.cn0_dbhz));
    Ok(json!({
        "text": r.text, "wpm": r.wpm, "snr_db": r.snr_db, "cn0_dbhz": r.cn0_dbhz, "drift_hz_s": r.drift_hz_s,
        "tone_hz": r.tone.first().map(|t| t.1), "secs": a.len() as f64 / sh_dsp::demod::AUDIO_RATE,
    }))
}

/// `secs` of IQ as a WAV, through the recorder into a scratch file.
fn iq(i: &Arc<Inner>, rq: tiny_http::Request, secs: f64) {
    if lock(&i.recorder).is_some() {
        return reply(rq, 409, &json!({ "ok": false, "error": "a recording is running on the phone" }));
    }
    let dir = i.dir.join("lab");
    let _ = std::fs::remove_dir_all(&dir);
    let r = record_start(i, Some(dir.display().to_string()), None, Some("lab_iq.wav".into()));
    if let Err(e) = r {
        return reply(rq, 400, &json!({ "ok": false, "error": e }));
    }
    std::thread::sleep(Duration::from_secs_f64(secs));
    let _ = record_stop(i, "lab link");
    match std::fs::read(dir.join("lab_iq.wav")) {
        Ok(b) => {
            log(i, format!("iq: {:.1} s, {} kB sent", secs, b.len() / 1000));
            let h = tiny_http::Header::from_bytes(&b"Content-Type"[..], &b"audio/wav"[..]).unwrap();
            let _ = rq.respond(tiny_http::Response::from_data(b).with_header(h));
        }
        Err(e) => reply(rq, 500, &json!({ "ok": false, "error": e.to_string() })),
    }
}
