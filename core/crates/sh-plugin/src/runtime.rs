//! Luau runtime for decoder plugins: the script gets decoded frames and says what to show.
//!
//! Sandboxed: no files, no network, no `os` / `io`; globals are read-only (Luau sandbox mode);
//! each call may run for at most 50 ms and the script may use at most 16 MB, so a child's
//! endless loop cannot hang the receiver.
//!
//! Script API (see docs/PLUGINS.md):
//!   on_start(info), on_frame(frame), on_end()
//!   show.text(s), show.value(name, number, unit), show.map(lat, lon, label),
//!   show.image(width, height, pixels)
//!   bytes.u8 / u16le / u16be / s16le / s16be / u32le / u32be (b, i)   -- 1-based index
//!   aprs.position(info) -> lat, lon (or nil)

use crate::{Manifest, PluginError};
use mlua::{Function, Lua, LuaOptions, StdLib, Table, Value, VmState};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

const CALL_LIMIT: Duration = Duration::from_millis(50);
const MEMORY_LIMIT: usize = 16 << 20;

/// What a plugin asked to show.
#[derive(Debug, Clone, PartialEq)]
pub enum Output {
    Text(String),
    Value { name: String, value: f64, unit: String },
    Map { lat: f64, lon: f64, label: String },
    Image { width: u32, height: u32, pixels: Vec<u8> },
}

impl Output {
    /// One line, the format of the plugin tests' expected.txt.
    pub fn line(&self) -> String {
        match self {
            Output::Text(s) => format!("text {s}"),
            Output::Value { name, value, unit } => format!("value {name} {} {unit}", trim_num(*value)).trim_end().to_string(),
            Output::Map { lat, lon, label } => format!("map {lat:.6} {lon:.6} {label}"),
            Output::Image { width, height, pixels } => format!("image {width}x{height} {} bytes", pixels.len()),
        }
    }
}

fn trim_num(v: f64) -> String {
    let s = format!("{v:.6}");
    let s = s.trim_end_matches('0').trim_end_matches('.');
    if s.is_empty() { "0".into() } else { s.to_string() }
}

/// A decoded frame as the script sees it. AX.25 chains fill src / dst / path / info / bytes;
/// the CW chain fills text (and info, the same) plus the measured speed and signal.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct Frame {
    pub src: String,
    pub dst: String,
    pub path: Vec<String>,
    pub info: String,
    pub bytes: Vec<u8>,
    pub text: Option<String>,
    pub wpm: Option<f64>,
    pub snr_db: Option<f64>,
    /// Receive time, unix seconds
    pub time: f64,
}

impl Frame {
    /// TNC2 text, e.g. `HA5ABC-7>APRS,RS0ISS*:!4729.87N/01902.41E>Hello` (plugin tests).
    pub fn from_tnc2(line: &str) -> Option<Frame> {
        let (head, info) = line.split_once(':')?;
        let (src, rest) = head.split_once('>')?;
        let mut parts = rest.split(',');
        let dst = parts.next()?.to_string();
        Some(Frame {
            src: src.to_string(),
            dst,
            path: parts.map(|p| p.to_string()).collect(),
            info: info.to_string(),
            bytes: info.as_bytes().to_vec(),
            ..Default::default()
        })
    }
}

/// Latitude, longitude from an APRS position report (uncompressed: `!` `=` or `/` `@` with a
/// timestamp), None when the info field has no position.
pub fn aprs_position(info: &str) -> Option<(f64, f64)> {
    let b = info.as_bytes();
    let start = match b.first()? {
        b'!' | b'=' => 1,
        b'/' | b'@' => 8, // 7-character timestamp
        _ => return None,
    };
    let s = info.get(start..start + 19)?;
    let (lat_s, rest) = (s.get(0..8)?, s.get(9..18)?);
    let deg = |t: &str, d: usize| -> Option<f64> {
        let v: f64 = t.get(0..d)?.parse().ok()?;
        let m: f64 = t.get(d..d + 5)?.replace(' ', "0").parse().ok()?;
        Some(v + m / 60.0)
    };
    let mut lat = deg(lat_s, 2)?;
    match lat_s.as_bytes()[7] {
        b'N' => {}
        b'S' => lat = -lat,
        _ => return None,
    }
    let mut lon = deg(rest, 3)?;
    match rest.as_bytes()[8] {
        b'E' => {}
        b'W' => lon = -lon,
        _ => return None,
    }
    ((-90.0..=90.0).contains(&lat) && (-180.0..=180.0).contains(&lon)).then_some((lat, lon))
}

pub struct Plugin {
    pub manifest: Manifest,
    lua: Lua,
    out: Arc<Mutex<Vec<Output>>>,
    deadline: Arc<Mutex<Instant>>,
}

fn err(m: &Manifest, e: impl std::fmt::Display) -> PluginError {
    PluginError::Invalid(m.id.clone(), e.to_string())
}

impl Plugin {
    /// Load a plugin from its manifest and script source.
    pub fn new(manifest: Manifest, source: &str) -> Result<Plugin, PluginError> {
        let lua = Lua::new_with(StdLib::STRING | StdLib::TABLE | StdLib::MATH | StdLib::UTF8 | StdLib::BIT, LuaOptions::default())
            .map_err(|e| err(&manifest, e))?;
        lua.set_memory_limit(MEMORY_LIMIT).map_err(|e| err(&manifest, e))?;
        let deadline = Arc::new(Mutex::new(Instant::now() + CALL_LIMIT));
        let dl = deadline.clone();
        lua.set_interrupt(move |_| {
            if Instant::now() > *dl.lock().unwrap_or_else(|e| e.into_inner()) {
                return Err(mlua::Error::runtime("the script ran too long (50 ms per call)"));
            }
            Ok(VmState::Continue)
        });
        let out = Arc::new(Mutex::new(Vec::new()));
        Self::install_api(&lua, out.clone()).map_err(|e| err(&manifest, e))?;
        lua.sandbox(true).map_err(|e| err(&manifest, e))?;
        let p = Plugin { manifest, lua, out, deadline };
        p.arm();
        p.lua.load(source).set_name(p.manifest.entry.as_str()).exec().map_err(|e| err(&p.manifest, e))?;
        Ok(p)
    }

    /// Load from a plugin folder.
    pub fn load_dir(dir: &std::path::Path) -> Result<Plugin, PluginError> {
        let m = crate::load_dir(dir)?;
        let src = std::fs::read_to_string(dir.join(&m.entry)).map_err(|e| PluginError::Io(m.id.clone(), e.to_string()))?;
        Plugin::new(m, &src)
    }

    fn arm(&self) {
        *self.deadline.lock().unwrap_or_else(|e| e.into_inner()) = Instant::now() + CALL_LIMIT;
    }

    fn install_api(lua: &Lua, out: Arc<Mutex<Vec<Output>>>) -> mlua::Result<()> {
        let g = lua.globals();
        let show = lua.create_table()?;
        let o = out.clone();
        show.set("text", lua.create_function(move |_, s: Value| {
            let s = match s {
                Value::String(s) => s.to_string_lossy().to_string(),
                Value::Number(n) => trim_num(n),
                Value::Integer(i) => i.to_string(),
                Value::Boolean(b) => b.to_string(),
                _ => String::new(),
            };
            o.lock().unwrap_or_else(|e| e.into_inner()).push(Output::Text(s));
            Ok(())
        })?)?;
        let o = out.clone();
        show.set("value", lua.create_function(move |_, (name, value, unit): (String, f64, Option<String>)| {
            o.lock().unwrap_or_else(|e| e.into_inner()).push(Output::Value { name, value, unit: unit.unwrap_or_default() });
            Ok(())
        })?)?;
        let o = out.clone();
        show.set("map", lua.create_function(move |_, (lat, lon, label): (f64, f64, Option<String>)| {
            o.lock().unwrap_or_else(|e| e.into_inner()).push(Output::Map { lat, lon, label: label.unwrap_or_default() });
            Ok(())
        })?)?;
        let o = out;
        show.set("image", lua.create_function(move |_, (w, h, px): (u32, u32, Table)| {
            let n = (w as usize).saturating_mul(h as usize).min(4 << 20);
            let mut pixels = Vec::with_capacity(n);
            for v in px.sequence_values::<f64>().take(n) {
                pixels.push(v?.clamp(0.0, 255.0) as u8);
            }
            o.lock().unwrap_or_else(|e| e.into_inner()).push(Output::Image { width: w, height: h, pixels });
            Ok(())
        })?)?;
        g.set("show", show)?;

        let bytes = lua.create_table()?;
        fn get(b: &mlua::String, i: i64, n: usize) -> mlua::Result<Vec<u8>> {
            let b = b.as_bytes();
            let s = (i - 1).max(0) as usize;
            b.get(s..s + n).map(|v| v.to_vec()).ok_or_else(|| mlua::Error::runtime(format!("bytes: index {i} past the end ({} bytes)", b.len())))
        }
        bytes.set("u8", lua.create_function(|_, (b, i): (mlua::String, i64)| Ok(get(&b, i, 1)?[0] as i64))?)?;
        bytes.set("u16le", lua.create_function(|_, (b, i): (mlua::String, i64)| { let v = get(&b, i, 2)?; Ok(u16::from_le_bytes([v[0], v[1]]) as i64) })?)?;
        bytes.set("u16be", lua.create_function(|_, (b, i): (mlua::String, i64)| { let v = get(&b, i, 2)?; Ok(u16::from_be_bytes([v[0], v[1]]) as i64) })?)?;
        bytes.set("s16le", lua.create_function(|_, (b, i): (mlua::String, i64)| { let v = get(&b, i, 2)?; Ok(i16::from_le_bytes([v[0], v[1]]) as i64) })?)?;
        bytes.set("s16be", lua.create_function(|_, (b, i): (mlua::String, i64)| { let v = get(&b, i, 2)?; Ok(i16::from_be_bytes([v[0], v[1]]) as i64) })?)?;
        bytes.set("u32le", lua.create_function(|_, (b, i): (mlua::String, i64)| { let v = get(&b, i, 4)?; Ok(u32::from_le_bytes([v[0], v[1], v[2], v[3]]) as i64) })?)?;
        bytes.set("u32be", lua.create_function(|_, (b, i): (mlua::String, i64)| { let v = get(&b, i, 4)?; Ok(u32::from_be_bytes([v[0], v[1], v[2], v[3]]) as i64) })?)?;
        g.set("bytes", bytes)?;

        let aprs = lua.create_table()?;
        aprs.set("position", lua.create_function(|_, info: String| Ok(match aprs_position(&info) {
            Some((a, b)) => (Some(a), Some(b)),
            None => (None, None),
        }))?)?;
        g.set("aprs", aprs)?;
        Ok(())
    }

    fn call(&self, name: &str, arg: impl mlua::IntoLuaMulti) -> Result<Vec<Output>, PluginError> {
        let f: Option<Function> = self.lua.globals().get(name).map_err(|e| err(&self.manifest, e))?;
        if let Some(f) = f {
            self.arm();
            f.call::<()>(arg).map_err(|e| err(&self.manifest, e))?;
        }
        Ok(std::mem::take(&mut *self.out.lock().unwrap_or_else(|e| e.into_inner())))
    }

    pub fn on_start(&self, satellite: &str, norad: u64) -> Result<Vec<Output>, PluginError> {
        let t = self.lua.create_table().map_err(|e| err(&self.manifest, e))?;
        let _ = t.set("satellite", satellite);
        let _ = t.set("norad", norad);
        self.call("on_start", t)
    }

    pub fn on_frame(&self, f: &Frame) -> Result<Vec<Output>, PluginError> {
        let l = &self.lua;
        let t = l.create_table().map_err(|e| err(&self.manifest, e))?;
        let set = || -> mlua::Result<()> {
            t.set("src", f.src.as_str())?;
            t.set("dst", f.dst.as_str())?;
            t.set("path", l.create_sequence_from(f.path.iter().map(|s| s.as_str()))?)?;
            t.set("info", f.info.as_str())?;
            t.set("bytes", l.create_string(&f.bytes)?)?;
            if let Some(x) = &f.text {
                t.set("text", x.as_str())?;
            }
            if let Some(x) = f.wpm {
                t.set("wpm", x)?;
            }
            if let Some(x) = f.snr_db {
                t.set("snr", x)?;
            }
            t.set("time", f.time)?;
            Ok(())
        };
        set().map_err(|e| err(&self.manifest, e))?;
        self.call("on_frame", t)
    }

    pub fn on_end(&self) -> Result<Vec<Output>, PluginError> {
        self.call("on_end", ())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn manifest(chain: &str) -> Manifest {
        Manifest::parse(&format!("id = \"t\"\nname = \"T\"\nversion = \"0.1\"\nauthor = \"x\"\nchain = \"{chain}\""), "t").unwrap()
    }

    #[test]
    fn aprs_positions() {
        assert_eq!(aprs_position("!4729.87N/01902.41E>Hello").map(|(a, b)| ((a * 1e6).round(), (b * 1e6).round())), Some((47497833.0, 19040167.0)));
        assert!(aprs_position("@092345z3345.67S/07012.34W_").map(|(a, b)| a < 0.0 && b < 0.0).unwrap());
        assert_eq!(aprs_position(":HA5XYZ   :hello"), None);
        assert_eq!(aprs_position("!99"), None);
    }

    #[test]
    fn script_shows_text_values_and_bytes() {
        let p = Plugin::new(manifest("afsk1200"), r#"
            function on_frame(f)
              show.text(f.src .. ": " .. f.info)
              show.value("first", bytes.u8(f.bytes, 1))
              show.value("word", bytes.u16le(f.bytes, 1), "raw")
            end"#).unwrap();
        let out = p.on_frame(&Frame { src: "A".into(), info: "AB".into(), bytes: vec![0x41, 0x42], ..Default::default() }).unwrap();
        let lines: Vec<String> = out.iter().map(|o| o.line()).collect();
        assert_eq!(lines, vec!["text A: AB", "value first 65", "value word 16961 raw"]);
    }

    #[test]
    fn sandbox_blocks_files_and_endless_loops() {
        // no io / os library, globals read-only
        let p = Plugin::new(manifest("cw"), "function on_frame(f) local x = io.open('/etc/passwd') end").unwrap();
        assert!(p.on_frame(&Frame::default()).is_err());
        let p = Plugin::new(manifest("cw"), "function on_frame(f) while true do end end").unwrap();
        let t = Instant::now();
        let e = p.on_frame(&Frame::default()).unwrap_err().to_string();
        assert!(e.contains("too long"), "{e}");
        assert!(t.elapsed() < Duration::from_millis(500));
        // it still works afterwards
        let p2 = Plugin::new(manifest("cw"), "function on_frame(f) show.text('ok') end").unwrap();
        assert_eq!(p2.on_frame(&Frame::default()).unwrap(), vec![Output::Text("ok".into())]);
        // memory
        let p = Plugin::new(manifest("cw"), "function on_frame(f) local t = {} for i = 1, 1e8 do t[i] = string.rep('x', 1000) end end").unwrap();
        assert!(p.on_frame(&Frame::default()).is_err());
    }

    #[test]
    fn tnc2_lines() {
        let f = Frame::from_tnc2("HA5ABC-7>APRS,RS0ISS*:!4729.87N/01902.41E>Hi").unwrap();
        assert_eq!((f.src.as_str(), f.dst.as_str(), f.path.clone(), f.info.as_str()), ("HA5ABC-7", "APRS", vec!["RS0ISS*".to_string()], "!4729.87N/01902.41E>Hi"));
    }
}
