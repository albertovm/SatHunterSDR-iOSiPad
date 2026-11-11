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
    @Published private(set) var heading: Double = 0
    @Published var volume: Float = 1
    @Published private(set) var waterfall: [[Float]] = []
    @Published private(set) var sstvImage: UIImage?
    @Published private(set) var pluginPins: [[String: Any]] = []
    lazy var location = LocationProvider()
    lazy var audio = AudioOutput()
    @Published var lastError: String?
    private var timer: Timer?
    private var initialized = false
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
        location.onLocation = { [weak self] point in _ = self?.command(["cmd":"gps", "lat":point.coordinate.latitude, "lon":point.coordinate.longitude, "alt":point.altitude]) }
        if let source = UserDefaults.standard.string(forKey: "source") { _ = command(["cmd":"source", "id":source]) }
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
    func bootstrap() { ensureInitialized() }
    @discardableResult func command(_ object: [String: Any]) -> [String: Any] {
        guard let data = try? JSONSerialization.data(withJSONObject: object), let json = String(data: data, encoding: .utf8), let pointer = json.withCString({ sh_apple_command($0) }) else { return ["ok": false, "error": "comando inválido"] }
        defer { sh_apple_string_free(pointer) }
        guard let data = String(cString: pointer).data(using: .utf8), let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return ["ok": false, "error": "resposta inválida"] }
        if value["ok"] as? Bool == false { lastError = value["error"] as? String }; return value
    }
    func refresh() { guard initialized else { return }; status = command(["cmd":"status"]); if let plugins = status["plugins"] as? [String: Any] { pluginPins = plugins["pins"] as? [[String: Any]] ?? [] }; let l = command(["cmd":"sat_list"]); satelliteRows = l["rows"] as? [[String: Any]] ?? []; detail = command(["cmd":"sat_detail"]); if (status["sstv"] as? [String: Any])?["on"] as? Bool == true { loadSSTVImage() }; var values = [Float](repeating: 0, count: 1024); var metadata = [Double](repeating: 0, count: 2); let packed = sh_apple_spectrum_rows(&values, values.count, &metadata, metadata.count); let rows = Int(packed >> 16); if rows > 0 { spectrum = Array(values.prefix(min(values.count, rows * 16))); waterfall.insert(spectrum, at: 0); if waterfall.count > 80 { waterfall.removeLast() } }; if timer == nil { timer = Timer.scheduledTimer(withTimeInterval: 0.75, repeats: true) { [weak self] _ in Task { @MainActor in self?.refresh() } } } }
    private func loadSSTVImage() { let value = command(["cmd": "sstv_image", "current": true]); guard let width = value["width"] as? Int, let height = value["height"] as? Int, let encoded = value["rgb"] as? String, let rgb = Data(base64Encoded: encoded), width > 0, height > 0, rgb.count >= width * height * 3 else { return }; let provider = CGDataProvider(data: rgb as CFData); let image = CGImage(width: width, height: height, bitsPerComponent: 8, bitsPerPixel: 24, bytesPerRow: width * 3, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.none.rawValue), provider: provider!, decode: nil, shouldInterpolate: false, intent: .defaultIntent); if let image { sstvImage = UIImage(cgImage: image) } }
    func setting(_ cmd: String, _ values: [String:Any] = [:]) { var object = values; object["cmd"] = cmd; _ = command(object); refresh() }
    func setDecimation(_ value: Int) { setting("decimation", ["factor": value]) }
    func recording(_ on: Bool) { let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].path; _ = command(["cmd": on ? "record_start" : "record_stop", "dir": dir]); refresh() }
    func decoder(_ name: String, on: Bool) { _ = command(["cmd": name, "on": on]); refresh() }
    func groundAprs(_ on: Bool, hz: Double? = nil) { var values: [String: Any] = ["on": on]; if let hz { values["hz"] = hz }; setting("ground_aprs", values) }
    func tune(_ hz: Double) { _ = command(["cmd":"tune", "hz": hz]); refresh() }
    func changeVolume(_ delta: Float) { volume = max(0, min(1, volume + delta)); audio.setVolume(volume) }
    func start() { ensureInitialized(); _ = command(["cmd":"start"]); audio.start(); audio.setVolume(volume); refresh() }; func stop() { ensureInitialized(); _ = command(["cmd":"stop"]); audio.stop(); refresh() }; func updateSatellites() { ensureInitialized(); _ = command(["cmd":"sat_update"]); refresh() }
    func favourite(_ norad: Int, on: Bool) { _ = command(["cmd":"favourite", "norad": norad, "on": on]); refresh() }
    func select(_ norad: Int) { UserDefaults.standard.set(norad, forKey: "selectedNorad"); _ = command(["cmd":"sat_select","norad":norad]); refresh() }; func track(_ on: Bool) { _ = command(["cmd":"sat_track","on":on]); refresh() }; func setMode(_ mode: String) { UserDefaults.standard.set(mode, forKey: "mode"); _ = command(["cmd":"mode","mode":mode]); refresh() }; func setSource(_ id: String) { UserDefaults.standard.set(id, forKey: "source"); _ = command(["cmd":"source","id":id]); refresh() }
}
