import Foundation
import SwiftUI
import UIKit
import SatHunterCore

@MainActor
final class SatHunterEngine: ObservableObject {
    @Published private(set) var status: [String: Any] = [:]
    @Published private(set) var satelliteRows: [[String: Any]] = []
    @Published private(set) var detail: [String: Any] = [:]
    @Published private(set) var spectrum: [Float] = []
    @Published private(set) var spectrumCenterHz: Double = 100_000_000
    @Published private(set) var spectrumRateHz: Double = 1_000_000
    @Published private(set) var heading: Double = 0
    @Published private(set) var gpsText: String = "Localização não disponível"
    @Published var volume: Float = 1
    @Published private(set) var waterfall: [[Float]] = []
    @Published private(set) var sstvImage: UIImage?
    @Published private(set) var pluginPins: [[String: Any]] = []
    lazy var location = LocationProvider()
    lazy var audio = AudioOutput()
    @Published var lastError: String?
    @Published private(set) var sdrppConnecting = false
    private var wantsSdrpp = false
    var sdrppRequested: Bool { wantsSdrpp }
    private var reconnectTask: Task<Void, Never>?
    private var timer: Timer?
    private var initialized = false
    #if DEBUG
    private var didRunDebugAutoconnect = false
    #endif
    init() {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("SatHunterSDR", isDirectory: true)
        do { try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true) } catch { lastError = error.localizedDescription }
    }
    private func ensureInitialized() {
        guard !initialized else { return }
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("SatHunterSDR", isDirectory: true)
        seedSatelliteCache(at: dir)
        _ = dir.path.withCString { sh_apple_init($0) }
        initialized = true
        location.onHeading = { [weak self] value in self?.heading = value.trueHeading >= 0 ? value.trueHeading : value.magneticHeading }
        location.onLocation = { [weak self] point in self?.gpsText = String(format: "%.5f, %.5f • %.0f m", point.coordinate.latitude, point.coordinate.longitude, point.altitude); _ = self?.command(["cmd":"gps", "lat":point.coordinate.latitude, "lon":point.coordinate.longitude, "alt":point.altitude]) }
        _ = command(["cmd":"stop"])
        if let mode = UserDefaults.standard.string(forKey: "mode") { _ = command(["cmd":"mode", "mode":mode]) }
        if let norad = UserDefaults.standard.object(forKey: "selectedNorad") as? Int { _ = command(["cmd":"sat_select", "norad":norad]) }
        refresh()
        if satelliteRows.isEmpty { _ = command(["cmd":"sat_update"]); refresh() }
    }
    /// Keep the first launch useful when the network is unavailable. The Rust worker will
    /// replace these records with the current SatNOGS/Celestrak cache when an update succeeds.
    private func seedSatelliteCache(at dir: URL) {
        let satDir = dir.appendingPathComponent("sat", isDirectory: true)
        let fm = FileManager.default
        guard !fm.fileExists(atPath: satDir.appendingPathComponent("transmitters.json").path) else { return }
        do {
            try fm.createDirectory(at: satDir, withIntermediateDirectories: true)
            try #"[{"uuid":"iss-aprs","description":"ISS APRS 1200","alive":true,"type":"Transceiver","downlink_low":145825000,"downlink_drifted":145825000,"mode":"AFSK","baud":1200,"norad_cat_id":25544,"status":"active","service":"Amateur"}]"#.write(to: satDir.appendingPathComponent("transmitters.json"), atomically: true, encoding: .utf8)
            try #"[{"tle0":"0 ISS (ZARYA)","tle1":"1 25544U 98067A   26282.95044904  .00006711  00000-0  13074-3 0  9998","tle2":"2 25544  51.6315  92.1575 0006672 244.0714 115.9587 15.48795780589546","norad_cat_id":25544}]"#.write(to: satDir.appendingPathComponent("tle_satnogs.json"), atomically: true, encoding: .utf8)
            try #"[{"name":"ISS","norad_cat_id":25544,"status":"in orbit","countries":"RU,US"}]"#.write(to: satDir.appendingPathComponent("satellites.json"), atomically: true, encoding: .utf8)
        } catch { lastError = "Não foi possível preparar a lista inicial de satélites: \(error.localizedDescription)" }
    }
    func bootstrap() {
        ensureInitialized()
        #if DEBUG
        if !didRunDebugAutoconnect && ProcessInfo.processInfo.arguments.contains("-SDRPPTestConnect") {
            didRunDebugAutoconnect = true
            let args = ProcessInfo.processInfo.arguments
            let testPort = args.firstIndex(of: "-SDRPPTestPort").flatMap { args.indices.contains($0 + 1) ? Int(args[$0 + 1]) : nil }
            configureSdrpp(host: "127.0.0.1", port: testPort ?? 5259)
            if let index = args.firstIndex(of: "-SDRPPTestTune"), args.indices.contains(index + 1), let frequency = Double(args[index + 1]) {
                Task { @MainActor in
                    try? await Task.sleep(for: .seconds(2))
                    tune(frequency)
                }
            }
        }
        #endif
    }
    @discardableResult func command(_ object: [String: Any]) -> [String: Any] {
        guard let data = try? JSONSerialization.data(withJSONObject: object), let json = String(data: data, encoding: .utf8), let pointer = json.withCString({ sh_apple_command($0) }) else { return ["ok": false, "error": "comando inválido"] }
        defer { sh_apple_string_free(pointer) }
        guard let data = String(cString: pointer).data(using: .utf8), let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return ["ok": false, "error": "resposta inválida"] }
        if value["ok"] as? Bool == false { lastError = value["error"] as? String }; return value
    }
    func refresh() {
        guard initialized else { return }
        status = command(["cmd":"status"])
        if status["running"] as? Bool != true {
            spectrum.removeAll()
            waterfall.removeAll()
            if timer == nil { timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in Task { @MainActor in self?.refresh() } } }
            return
        }
        if let plugins = status["plugins"] as? [String: Any] { pluginPins = plugins["pins"] as? [[String: Any]] ?? [] }
        let satellites = command(["cmd":"sat_list"])
        satelliteRows = satellites["rows"] as? [[String: Any]] ?? []
        detail = command(["cmd":"sat_detail"])
        if (status["sstv"] as? [String: Any])?["on"] as? Bool == true { loadSSTVImage() }
        var values = [Float](repeating: 0, count: 16384)
        var metadata = [Double](repeating: 0, count: 2)
        var newest: [Float]?
        var added = 0
        for _ in 0..<16 {
            let packed = sh_apple_spectrum_rows(&values, values.count, &metadata, metadata.count)
            let rows = Int(packed >> 16)
            let bins = Int(packed & 0xffff) * 16
            guard rows > 0 && bins > 0 && bins <= values.count else { break }
            let step = max(1, bins / 512)
            let row = stride(from: 0, to: bins, by: step).map { start in
                let end = min(start + step, bins)
                return values[start..<end].reduce(0, +) / Float(end - start)
            }
            if (metadata[0] - spectrumCenterHz).magnitude > 1 || (metadata[1] - spectrumRateHz).magnitude > 1 { waterfall.removeAll() }
            newest = row
            waterfall.insert(row, at: 0)
            if metadata[0].isFinite { spectrumCenterHz = metadata[0] }
            if metadata[1].isFinite && metadata[1] > 0 { spectrumRateHz = metadata[1] }
            added += 1
        }
        if let newest { spectrum = newest }
        if added > 0 && waterfall.count > 80 { waterfall.removeLast(waterfall.count - 80) }
        if timer == nil { timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in Task { @MainActor in self?.refresh() } } }
    }
    private func loadSSTVImage() { let value = command(["cmd": "sstv_image", "current": true]); guard let width = value["width"] as? Int, let height = value["height"] as? Int, let encoded = value["rgb"] as? String, let rgb = Data(base64Encoded: encoded), width > 0, height > 0, rgb.count >= width * height * 3 else { return }; let provider = CGDataProvider(data: rgb as CFData); let image = CGImage(width: width, height: height, bitsPerComponent: 8, bitsPerPixel: 24, bytesPerRow: width * 3, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.none.rawValue), provider: provider!, decode: nil, shouldInterpolate: false, intent: .defaultIntent); if let image { sstvImage = UIImage(cgImage: image) } }
    func setting(_ cmd: String, _ values: [String:Any] = [:]) { var object = values; object["cmd"] = cmd; _ = command(object); refresh() }
    func setDecimation(_ value: Int) { setting("decimation", ["factor": value]) }
    func recording(_ on: Bool) { let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].path; _ = command(["cmd": on ? "record_start" : "record_stop", "dir": dir]); refresh() }
    func decoder(_ name: String, on: Bool) { _ = command(["cmd": name, "on": on]); refresh() }
    func clearAPRS() { _ = command(["cmd": "aprs_clear"]); refresh() }
    func groundAprs(_ on: Bool, hz: Double? = nil) { var values: [String: Any] = ["on": on]; if let hz { values["hz"] = hz }; setting("ground_aprs", values) }
    func debugMode(_ on: Bool) { setting("debug_mode", ["on": on]) }
    func labPin(_ pin: String) { setting("lab_pin", ["pin": pin]) }
    func plugins(_ on: Bool) { setting("plugins", ["on": on]) }
    func bandwidth(_ hz: Double) { setting("bandwidth", ["hz": hz]) }
    func sampleRate(_ hz: Double) { setting("rate", ["hz": hz]) }
    func simulatePass() { _ = command(["cmd": "simulate"]); refresh() }
    func realTime() { _ = command(["cmd": "real_time"]); refresh() }
    func resetDopplerOffset() { _ = command(["cmd": "sat_reset_offset"]); refresh() }
    func tune(_ hz: Double) {
        ensureInitialized()
        // The broadcast FM band needs the wide FM demodulator and its 150 kHz filter.
        if (87_500_000...108_000_000).contains(hz), status["mode"] as? String != "WFM" {
            _ = command(["cmd":"mode", "mode":"WFM"])
            UserDefaults.standard.set("WFM", forKey: "mode")
        }
        _ = command(["cmd":"tune", "hz": hz])
        refresh()
    }
    func changeVolume(_ delta: Float) { volume = max(0, min(1, volume + delta)); audio.setVolume(volume) }
    func start() { ensureInitialized(); _ = command(["cmd":"start"]); audio.start(); audio.setVolume(volume); refresh() }; func stop() { wantsSdrpp = false; reconnectTask?.cancel(); reconnectTask = nil; sdrppConnecting = false; ensureInitialized(); _ = command(["cmd":"stop"]); audio.stop(); spectrum.removeAll(); waterfall.removeAll(); refresh() }; func updateSatellites() { ensureInitialized(); _ = command(["cmd":"sat_update"]); refresh() }
    func configureSdrpp(host: String, port: Int) {
        ensureInitialized()
        guard !wantsSdrpp else { return }
        wantsSdrpp = true
        sdrppConnecting = true
        lastError = nil
        UserDefaults.standard.set(host, forKey: "sdrppHost")
        UserDefaults.standard.set(port, forKey: "sdrppPort")
        connectSdrppAttempt(host: host, port: port)
        refresh()
        sdrppConnecting = false
        reconnectTask = Task { @MainActor in
            var waitingSince = Date()
            while wantsSdrpp && !Task.isCancelled {
                try? await Task.sleep(for: .seconds(3))
                guard wantsSdrpp && !Task.isCancelled else { break }
                refresh()
                let sourceStatus = status["source_status"] as? String ?? ""
                if sourceStatus.hasPrefix("Recebendo IQ") {
                    waitingSince = Date()
                    if !audio.isRunning { audio.start() }
                } else if sourceStatus.hasPrefix("Sem fluxo IQ") || sourceStatus.hasPrefix("IQ interrompido") || sourceStatus.hasPrefix("Fluxo IQ interrompido") || Date().timeIntervalSince(waitingSince) > 15 {
                    sdrppConnecting = true
                    connectSdrppAttempt(host: host, port: port)
                    refresh()
                    sdrppConnecting = false
                    waitingSince = Date()
                }
            }
        }
    }
    private func connectSdrppAttempt(host: String, port: Int) {
        let response = command(["cmd":"sdrpp_config", "host": host, "port": port])
        if response["ok"] as? Bool == false { lastError = response["error"] as? String ?? "Não foi possível configurar o SDR++"; return }
        let started = command(["cmd":"start"])
        if started["ok"] as? Bool == false { lastError = started["error"] as? String ?? "Não foi possível iniciar o fluxo IQ do SDR++"; return }
        lastError = nil
        audio.start()
        audio.setVolume(volume)
    }
    func disconnectSdrpp() {
        stop()
        lastError = nil
    }
    func favourite(_ norad: Int, on: Bool) { _ = command(["cmd":"favourite", "norad": norad, "on": on]); refresh() }
    func select(_ norad: Int, tx: String? = nil) { UserDefaults.standard.set(norad, forKey: "selectedNorad"); var object: [String: Any] = ["cmd":"sat_select", "norad":norad]; if let tx { object["tx"] = tx }; _ = command(object); refresh() }; func track(_ on: Bool) { _ = command(["cmd":"sat_track","on":on]); refresh() }; func setMode(_ mode: String) { UserDefaults.standard.set(mode, forKey: "mode"); _ = command(["cmd":"mode","mode":mode]); refresh() }; func setSource(_ id: String) { UserDefaults.standard.set(id, forKey: "source"); _ = command(["cmd":"source","id":id]); refresh() }
}
