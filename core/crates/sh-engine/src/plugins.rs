//! Decoder plugins inside the engine: the built-in Luau plugins get the frames the native chains
//! decode (APRS for now) and their output (text, values, map pins) goes to a list the UI and the
//! lab link read. Loaded on first use; a plugin that fails to load or errors is reported, never
//! fatal.

use serde_json::{json, Value};
use sh_plugin::runtime::{Frame, Output, Plugin};
use sh_plugin::{Chain, Manifest};
use std::collections::VecDeque;

/// Built-in plugins (the repository's plugins/ folder, compiled in).
const BUILTIN: &[(&str, &str, &str)] = &[
    ("plugins/iss-aprs", include_str!("../../../../plugins/iss-aprs/plugin.toml"), include_str!("../../../../plugins/iss-aprs/decoder.lua")),
    ("plugins/aprs-map", include_str!("../../../../plugins/aprs-map/plugin.toml"), include_str!("../../../../plugins/aprs-map/decoder.lua")),
];

const KEEP: usize = 300;

pub struct Host {
    plugins: Vec<Plugin>,
    pub errors: Vec<String>,
    /// (number of the last output, the last outputs)
    pub out: (u64, VecDeque<Value>),
    /// Map pins, the latest per label (station), oldest first
    pub pins: VecDeque<Value>,
}

const KEEP_PINS: usize = 200;

impl Host {
    pub fn load() -> Host {
        let mut plugins = Vec::new();
        let mut errors = Vec::new();
        for (origin, toml, lua) in BUILTIN {
            match Manifest::parse(toml, origin).and_then(|m| Plugin::new(m, lua)) {
                Ok(p) => plugins.push(p),
                Err(e) => errors.push(e.to_string()),
            }
        }
        Host { plugins, errors, out: (0, VecDeque::new()), pins: VecDeque::new() }
    }

    pub fn ids(&self) -> Vec<String> {
        self.plugins.iter().map(|p| p.manifest.id.clone()).collect()
    }

    /// The plugins for a chain and the selected satellite: the ones made for that satellite if
    /// any, otherwise the generic ones (no NORAD list).
    fn pick(&self, chain: Chain, norad: Option<u64>, mode: &str) -> Vec<usize> {
        let of_chain: Vec<usize> = (0..self.plugins.len()).filter(|&k| self.plugins[k].manifest.chain == chain).collect();
        let specific: Vec<usize> = of_chain
            .iter()
            .copied()
            .filter(|&k| {
                let m = &self.plugins[k].manifest;
                norad.is_some_and(|n| !m.norad.is_empty() && m.applies(n, mode))
            })
            .collect();
        if !specific.is_empty() {
            return specific;
        }
        of_chain.into_iter().filter(|&k| self.plugins[k].manifest.norad.is_empty() && self.plugins[k].manifest.applies(0, mode)).collect()
    }

    /// A decoded AX.25 frame from the AFSK1200 chain.
    pub fn ax25(&mut self, f: &sh_dsp::afsk::Ax25Frame, norad: Option<u64>, freq_hz: f64, time: f64) {
        let frame = Frame {
            src: f.src.clone(),
            dst: f.dst.clone(),
            path: f.path.clone(),
            info: String::from_utf8_lossy(&f.info).into_owned(),
            bytes: f.info.clone(),
            time,
            ..Default::default()
        };
        for k in self.pick(Chain::Afsk1200, norad, "AFSK") {
            let id = self.plugins[k].manifest.id.clone();
            match self.plugins[k].on_frame(&frame) {
                Ok(outs) => {
                    for o in outs {
                        self.push(&id, time, freq_hz, o);
                    }
                }
                Err(e) => {
                    self.errors.push(format!("{id}: {e}"));
                    if self.errors.len() > 20 {
                        self.errors.remove(0);
                    }
                }
            }
        }
    }

    fn push(&mut self, id: &str, time: f64, freq_hz: f64, o: Output) {
        self.out.0 += 1;
        let n = self.out.0;
        let mut v = json!({ "n": n, "time": time, "freq_hz": freq_hz, "plugin": id, "line": o.line() });
        match o {
            Output::Text(s) => {
                v["kind"] = "text".into();
                v["text"] = s.into();
            }
            Output::Value { name, value, unit } => {
                v["kind"] = "value".into();
                v["name"] = name.into();
                v["value"] = value.into();
                v["unit"] = unit.into();
            }
            Output::Map { lat, lon, label } => {
                v["kind"] = "map".into();
                v["lat"] = lat.into();
                v["lon"] = lon.into();
                v["label"] = label.into();
            }
            Output::Image { width, height, .. } => {
                v["kind"] = "image".into();
                v["width"] = width.into();
                v["height"] = height.into();
            }
        }
        if v["kind"] == "map" {
            self.pins.retain(|p| p["label"] != v["label"]);
            self.pins.push_back(json!({ "lat": v["lat"], "lon": v["lon"], "label": v["label"], "time": time, "plugin": id }));
            while self.pins.len() > KEEP_PINS {
                self.pins.pop_front();
            }
        }
        self.out.1.push_back(v);
        while self.out.1.len() > KEEP {
            self.out.1.pop_front();
        }
    }

    pub fn since(&self, since: u64) -> Value {
        json!({
            "plugins": self.ids(), "errors": self.errors, "count": self.out.0, "pins": self.pins,
            "out": self.out.1.iter().filter(|v| v["n"].as_u64().unwrap_or(0) > since).cloned().collect::<Vec<_>>(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn frame(tnc2: &str) -> sh_dsp::afsk::Ax25Frame {
        let f = Frame::from_tnc2(tnc2).unwrap();
        sh_dsp::afsk::Ax25Frame { dst: f.dst, src: f.src, path: f.path, control: 3, pid: Some(0xf0), info: f.bytes, raw: vec![] }
    }

    #[test]
    fn builtins_load_and_pick_by_satellite() {
        let mut h = Host::load();
        assert!(h.errors.is_empty(), "{:?}", h.errors);
        assert_eq!(h.ids(), vec!["iss-aprs", "aprs-map"]);
        let f = frame("HA5ABC-7>APRS,RS0ISS*:!4729.87N/01902.41E>Hello");
        // ISS selected: only iss-aprs
        h.ax25(&f, Some(25544), 145.825e6, 1.0);
        let v = h.since(0);
        assert!(v["out"].as_array().unwrap().iter().all(|o| o["plugin"] == "iss-aprs"));
        assert_eq!(v["out"].as_array().unwrap().len(), 2);
        // nothing (or another satellite) selected: the generic one
        h.ax25(&f, None, 145.825e6, 2.0);
        h.ax25(&f, Some(31130), 435.245e6, 3.0);
        let v = h.since(2);
        let outs = v["out"].as_array().unwrap();
        assert_eq!(outs.len(), 4);
        assert!(outs.iter().all(|o| o["plugin"] == "aprs-map"));
        let pin = outs.iter().find(|o| o["kind"] == "map").unwrap();
        assert!((pin["lat"].as_f64().unwrap() - 47.497833).abs() < 1e-5);
        // one pin per station, the latest
        let pins = h.since(0)["pins"].as_array().unwrap().clone();
        assert_eq!(pins.len(), 1);
        assert_eq!(pins[0]["label"], "HA5ABC-7");
        assert_eq!(pins[0]["time"], 3.0);
    }
}
