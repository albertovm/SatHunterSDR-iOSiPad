//! Minimal SDR++ Server client (TCP 5259).
//! It negotiates signed 16-bit IQ and forwards baseband packets to the engine.
use crate::{Block, Complex32, Sink, Source, SourceError, SourceInfo};
use std::io::{Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::sync::{Arc, Mutex, atomic::{AtomicBool, AtomicU64, Ordering}};
use std::thread::{self, JoinHandle};

const COMMAND_START: u32 = 2;
const COMMAND_STOP: u32 = 3;
const COMMAND_SET_FREQUENCY: u32 = 4;
const COMMAND_SET_SAMPLE_TYPE: u32 = 6;
const COMMAND_SET_COMPRESSION: u32 = 7;
const PACKET_COMMAND: u32 = 0;
const PACKET_BASEBAND: u32 = 2;
const COMMAND_SET_SAMPLERATE: u32 = 0x80;

pub struct SdrppSource {
    host: String, port: u16, freq: f64, rate: f64, running: bool,
    stop: Arc<AtomicBool>, thread: Option<JoinHandle<()>>, status: Arc<Mutex<String>>, control: Option<TcpStream>, rate_bits: Arc<AtomicU64>, center_bits: Arc<AtomicU64>,
}

impl SdrppSource {
    pub fn new(host: impl Into<String>, port: u16) -> Self { Self { host: host.into(), port, freq: 100e6, rate: 1e6, running: false, stop: Arc::new(AtomicBool::new(false)), thread: None, status: Arc::new(Mutex::new(String::new())), control: None, rate_bits: Arc::new(AtomicU64::new(1e6f64.to_bits())), center_bits: Arc::new(AtomicU64::new(100e6f64.to_bits())) } }
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
        self.control = Some(stream.try_clone().map_err(|e| SourceError::Device(e.to_string()))?);
        self.stop.store(false, Ordering::SeqCst); let stop = self.stop.clone(); let status = self.status.clone(); let rate_bits = self.rate_bits.clone(); let center_bits = self.center_bits.clone();
        *self.status.lock().unwrap() = format!("TCP conectado a {}:{}; aguardando IQ", self.host, self.port);
        self.thread = Some(thread::Builder::new().name("sdrpp-server".into()).spawn(move || {
            let mut h = [0u8; 8];
            while !stop.load(Ordering::Relaxed) {
                if let Err(error) = stream.read_exact(&mut h) { if !stop.load(Ordering::Relaxed) { *status.lock().unwrap() = format!("Sem fluxo IQ: {error}"); } break }
                let typ = u32::from_le_bytes(h[0..4].try_into().unwrap()); let size = u32::from_le_bytes(h[4..8].try_into().unwrap()) as usize;
                if size < 8 || size > 16 * 1024 * 1024 { *status.lock().unwrap() = "Pacote SDR++ inválido".into(); break }
                let mut p = vec![0u8; size - 8]; if let Err(error) = stream.read_exact(&mut p) { *status.lock().unwrap() = format!("IQ interrompido: {error}"); break }
                if typ == PACKET_COMMAND && p.len() >= 12 && u32::from_le_bytes(p[0..4].try_into().unwrap()) == COMMAND_SET_SAMPLERATE {
                    let rate = f64::from_le_bytes(p[4..12].try_into().unwrap());
                    if rate.is_finite() && rate > 0.0 { rate_bits.store(rate.to_bits(), Ordering::Relaxed); }
                    continue;
                }
                if typ != PACKET_BASEBAND { continue }
                if p.len() < 8 { *status.lock().unwrap() = "Pacote IQ sem cabeçalho PCM".into(); break }
                let sample_type = u16::from_le_bytes([p[2], p[3]]);
                if sample_type != 1 { *status.lock().unwrap() = format!("Formato PCM SDR++ inesperado: {sample_type}"); break }
                let scale = f32::from_le_bytes([p[4], p[5], p[6], p[7]]);
                if !scale.is_finite() { *status.lock().unwrap() = "Escala IQ inválida".into(); break }
                let mut samples = Vec::with_capacity((p.len() - 8) / 4);
                for c in p[8..].chunks_exact(4) { let i = i16::from_le_bytes([c[0],c[1]]) as f32 * scale / 32768.0; let q = i16::from_le_bytes([c[2],c[3]]) as f32 * scale / 32768.0; samples.push(Complex32::new(i,q)); }
                let rate = f64::from_bits(rate_bits.load(Ordering::Relaxed));
                let center = f64::from_bits(center_bits.load(Ordering::Relaxed));
                *status.lock().unwrap() = format!("Recebendo IQ: {} amostras/pacote, {:.0} kS/s", samples.len(), rate / 1000.0);
                if !sink.push(Block { center_hz: center, rate, samples }) { *status.lock().unwrap() = "Fluxo IQ interrompido".into(); break; }
            }
        }).map_err(|e| SourceError::Device(e.to_string()))?); self.running = true; Ok(())
    }
    fn stop(&mut self) { self.stop.store(true, Ordering::SeqCst); if let Some(mut control) = self.control.take() { let _ = Self::command(&mut control, COMMAND_STOP, &[]); let _ = control.shutdown(std::net::Shutdown::Both); } if let Some(t) = self.thread.take() { let _ = t.join(); } self.running = false; }
    fn running(&self) -> bool { self.running }
    fn set_frequency(&mut self, hz: f64) -> Result<f64, SourceError> { if let Some(control) = self.control.as_mut() { Self::command(control, COMMAND_SET_FREQUENCY, &hz.to_le_bytes()).map_err(|e| SourceError::Device(format!("SDR++ sintonia: {e}")))?; } self.freq = hz; self.center_bits.store(hz.to_bits(), Ordering::Relaxed); Ok(hz) }
    fn frequency(&self) -> f64 { self.freq }
    fn set_sample_rate(&mut self, fs: f64) -> Result<(), SourceError> { self.rate = fs; Ok(()) }
    fn sample_rate(&self) -> f64 { f64::from_bits(self.rate_bits.load(Ordering::Relaxed)) }
    fn set_gain(&mut self, _db: Option<f32>) -> Result<(), SourceError> { Ok(()) }
    fn status(&self) -> String { self.status.lock().map(|s| s.clone()).unwrap_or_else(|_| "Estado SDR++ indisponível".into()) }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;
    use std::time::Duration;

    #[test]
    fn sends_tuning_and_receives_server_rate_and_iq() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let server = thread::spawn(move || {
            let (mut socket, _) = listener.accept().unwrap();
            socket.set_read_timeout(Some(Duration::from_secs(3))).unwrap();
            let mut commands = Vec::new();
            while commands.len() < 4 {
                let mut header = [0u8; 8]; socket.read_exact(&mut header).unwrap();
                let size = u32::from_le_bytes(header[4..8].try_into().unwrap()) as usize;
                let mut body = vec![0; size - 8]; socket.read_exact(&mut body).unwrap();
                commands.push(u32::from_le_bytes(body[..4].try_into().unwrap()));
            }
            assert_eq!(commands, [COMMAND_SET_SAMPLE_TYPE, COMMAND_SET_COMPRESSION, COMMAND_SET_FREQUENCY, COMMAND_START]);
            let mut rate = Vec::new();
            rate.extend_from_slice(&PACKET_COMMAND.to_le_bytes());
            rate.extend_from_slice(&20u32.to_le_bytes());
            rate.extend_from_slice(&COMMAND_SET_SAMPLERATE.to_le_bytes());
            rate.extend_from_slice(&1_000_000f64.to_le_bytes());
            socket.write_all(&rate).unwrap();
            let mut iq = Vec::new();
            iq.extend_from_slice(&PACKET_BASEBAND.to_le_bytes());
            iq.extend_from_slice(&20u32.to_le_bytes());
            iq.extend_from_slice(&0u16.to_le_bytes());
            iq.extend_from_slice(&1u16.to_le_bytes());
            iq.extend_from_slice(&1f32.to_le_bytes());
            iq.extend_from_slice(&16384i16.to_le_bytes());
            iq.extend_from_slice(&(-8192i16).to_le_bytes());
            socket.write_all(&iq).unwrap();
            let mut header = [0u8; 8]; socket.read_exact(&mut header).unwrap();
            let mut body = vec![0; u32::from_le_bytes(header[4..8].try_into().unwrap()) as usize - 8];
            socket.read_exact(&mut body).unwrap();
            assert_eq!(u32::from_le_bytes(body[..4].try_into().unwrap()), COMMAND_SET_FREQUENCY);
            assert_eq!(f64::from_le_bytes(body[4..12].try_into().unwrap()), 99_700_000.0);
        });
        let mut source = SdrppSource::new("127.0.0.1", port);
        let (sink, rx, _) = Sink::new(8);
        source.start(sink).unwrap();
        let block = rx.recv_timeout(Duration::from_secs(3)).unwrap();
        assert_eq!(block.rate, 1_000_000.0);
        assert!((block.samples[0].re - 0.5).abs() < 0.001);
        source.set_frequency(99_700_000.0).unwrap();
        server.join().unwrap();
        source.stop();
    }
}
