//! Minimal SDR++ Server client (TCP 5259).
//! It negotiates signed 16-bit IQ and forwards baseband packets to the engine.
use crate::{Block, Complex32, Sink, Source, SourceError, SourceInfo};
use std::io::{Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::sync::{Arc, atomic::{AtomicBool, Ordering}};
use std::thread::{self, JoinHandle};

const COMMAND_START: u32 = 2;
const COMMAND_STOP: u32 = 3;
const COMMAND_SET_FREQUENCY: u32 = 4;
const COMMAND_SET_SAMPLE_TYPE: u32 = 6;
const COMMAND_SET_COMPRESSION: u32 = 7;
const PACKET_COMMAND: u32 = 0;
const PACKET_BASEBAND: u32 = 2;

pub struct SdrppSource {
    host: String, port: u16, freq: f64, rate: f64, running: bool,
    stop: Arc<AtomicBool>, thread: Option<JoinHandle<()>>, status: String,
}

impl SdrppSource {
    pub fn new(host: impl Into<String>, port: u16) -> Self { Self { host: host.into(), port, freq: 100e6, rate: 1e6, running: false, stop: Arc::new(AtomicBool::new(false)), thread: None, status: String::new() } }
    fn command(stream: &mut TcpStream, cmd: u32, data: &[u8]) -> std::io::Result<()> {
        let size = (8 + 4 + data.len()) as u32;
        stream.write_all(&0u32.to_le_bytes())?; stream.write_all(&size.to_le_bytes())?;
        stream.write_all(&cmd.to_le_bytes())?; stream.write_all(data)
    }
}

impl Source for SdrppSource {
    fn info(&self) -> SourceInfo { SourceInfo { id: "sdrpp", name: format!("SDR++ Server ({}:{})", self.host, self.port), min_hz: 1.0, max_hz: 6e9, sample_rates: vec![250e3, 500e3, 1e6, 2e6], gains: vec![] } }
    fn start(&mut self, sink: Sink) -> Result<(), SourceError> {
        let addr = (self.host.as_str(), self.port).to_socket_addrs().map_err(|e| SourceError::Device(e.to_string()))?.next().ok_or_else(|| SourceError::Device("SDR++ address not found".into()))?;
        let mut stream = TcpStream::connect_timeout(&addr, std::time::Duration::from_secs(5)).map_err(|e| SourceError::Device(format!("SDR++ connect: {e}")))?;
        stream.set_read_timeout(Some(std::time::Duration::from_secs(5))).ok();
        Self::command(&mut stream, COMMAND_SET_SAMPLE_TYPE, &[1]).map_err(|e| SourceError::Device(e.to_string()))?; // signed int16
        Self::command(&mut stream, COMMAND_SET_COMPRESSION, &[0]).map_err(|e| SourceError::Device(e.to_string()))?;
        Self::command(&mut stream, COMMAND_SET_FREQUENCY, &self.freq.to_le_bytes()).map_err(|e| SourceError::Device(e.to_string()))?;
        Self::command(&mut stream, COMMAND_START, &[]).map_err(|e| SourceError::Device(e.to_string()))?;
        self.stop.store(false, Ordering::SeqCst); let stop = self.stop.clone(); let rate = self.rate; let center = self.freq;
        self.thread = Some(thread::Builder::new().name("sdrpp-server".into()).spawn(move || {
            let mut h = [0u8; 8];
            while !stop.load(Ordering::Relaxed) {
                if stream.read_exact(&mut h).is_err() { break }
                let typ = u32::from_le_bytes(h[0..4].try_into().unwrap()); let size = u32::from_le_bytes(h[4..8].try_into().unwrap()) as usize;
                if size < 8 || size > 16 * 1024 * 1024 { break }
                let mut p = vec![0u8; size - 8]; if stream.read_exact(&mut p).is_err() { break }
                if typ != PACKET_BASEBAND { continue }
                let mut samples = Vec::with_capacity(p.len() / 4);
                for c in p.chunks_exact(4) { let i = i16::from_le_bytes([c[0],c[1]]) as f32 / 32768.0; let q = i16::from_le_bytes([c[2],c[3]]) as f32 / 32768.0; samples.push(Complex32::new(i,q)); }
                if !sink.push(Block { center_hz: center, rate, samples }) { break; }
            }
        }).map_err(|e| SourceError::Device(e.to_string()))?); self.running = true; self.status = format!("Conectado a SDR++ em {}:{}", self.host, self.port); Ok(())
    }
    fn stop(&mut self) { self.stop.store(true, Ordering::SeqCst); if let Some(t) = self.thread.take() { let _ = t.join(); } self.running = false; }
    fn running(&self) -> bool { self.running }
    fn set_frequency(&mut self, hz: f64) -> Result<f64, SourceError> { self.freq = hz; Ok(hz) }
    fn frequency(&self) -> f64 { self.freq }
    fn set_sample_rate(&mut self, fs: f64) -> Result<(), SourceError> { self.rate = fs; Ok(()) }
    fn sample_rate(&self) -> f64 { self.rate }
    fn set_gain(&mut self, _db: Option<f32>) -> Result<(), SourceError> { Ok(()) }
    fn status(&self) -> String { self.status.clone() }
}
