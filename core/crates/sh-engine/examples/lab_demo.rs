//! The engine with the demo source and the lab link on, as on a phone in debug mode: try
//! tools/lab/lab.py without a phone.
//! `cargo run --release -p sh-engine --example lab_demo -- [port]`
use sh_engine::config::Config;
use sh_engine::Engine;

fn main() {
    let port: u16 = std::env::args().nth(1).and_then(|s| s.parse().ok()).unwrap_or(8765);
    let dir = std::env::temp_dir().join("sathunter-lab-demo");
    std::fs::create_dir_all(dir.join("sat")).unwrap();
    Config { update_days: 0.0, fft_size: 8192, ..Config::default() }.save(&dir.join("config.json"));
    let e = Engine::new(&dir);
    e.command(r#"{"cmd":"source","id":"demo"}"#);
    let st: serde_json::Value = serde_json::from_str(&e.command(&format!(r#"{{"cmd":"lab_start","port":{port}}}"#))).unwrap();
    println!("lab link on port {port}, PIN {}  (addresses {})", st["pin"], st["ips"]);
    println!("try: python tools/lab/lab.py --phone 127.0.0.1 --port {port} --pin {} --gen demo", st["pin"].as_str().unwrap_or(""));
    let mut shown = 0;
    loop {
        std::thread::sleep(std::time::Duration::from_millis(500));
        let s: serde_json::Value = serde_json::from_str(&e.command(r#"{"cmd":"status"}"#)).unwrap();
        if let Some(log) = s["lab"]["log"].as_array() {
            // print new console lines (the phone shows the same)
            let n = s["lab"]["requests"].as_u64().unwrap_or(0) as usize;
            if n != shown {
                shown = n;
                if let Some(l) = log.last() {
                    println!("console | {}", l.as_str().unwrap_or(""));
                }
            }
        }
    }
}
