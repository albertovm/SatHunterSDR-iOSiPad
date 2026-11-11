import Foundation
import SwiftUI
import SatHunterCore

@MainActor
final class SatHunterEngine: ObservableObject {
    @Published private(set) var status: [String: Any] = [:]
    @Published private(set) var satelliteRows: [[String: Any]] = []
    @Published private(set) var detail: [String: Any] = [:]
    @Published private(set) var spectrum: [Float] = []
    @Published private(set) var heading: Double = 0
    @Published private(set) var waterfall: [[Float]] = []
    let location = LocationProvider()
    let audio = AudioOutput()
    @Published var lastError: String?
    private var timer: Timer?
    init() {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("SatHunterSDR", isDirectory: true)
        do { try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true); _ = dir.path.withCString { sh_apple_init($0) }; if let source = UserDefaults.standard.string(forKey: "source") { _ = command(["cmd":"source", "id":source]) }; if let mode = UserDefaults.standard.string(forKey: "mode") { _ = command(["cmd":"mode", "mode":mode]) }; location.onHeading = { [weak self] value in self?.heading = value.trueHeading >= 0 ? value.trueHeading : value.magneticHeading }; location.onLocation = { [weak self] point in _ = self?.command(["cmd":"gps", "lat":point.coordinate.latitude, "lon":point.coordinate.longitude, "alt":point.altitude]) }; refresh() } catch { lastError = error.localizedDescription }
    }
    @discardableResult func command(_ object: [String: Any]) -> [String: Any] {
        guard let data = try? JSONSerialization.data(withJSONObject: object), let json = String(data: data, encoding: .utf8), let pointer = json.withCString({ sh_apple_command($0) }) else { return ["ok": false, "error": "comando inválido"] }
        defer { sh_apple_string_free(pointer) }
        guard let data = String(cString: pointer).data(using: .utf8), let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return ["ok": false, "error": "resposta inválida"] }
        if value["ok"] as? Bool == false { lastError = value["error"] as? String }; return value
    }
    func refresh() { status = command(["cmd":"status"]); let l = command(["cmd":"sat_list"]); satelliteRows = l["rows"] as? [[String: Any]] ?? []; detail = command(["cmd":"sat_detail"]); var values = [Float](repeating: 0, count: 1024); var metadata = [Double](repeating: 0, count: 2); let packed = sh_apple_spectrum_rows(&values, values.count, &metadata, metadata.count); let rows = Int(packed >> 16); if rows > 0 { spectrum = Array(values.prefix(min(values.count, rows * 16))); waterfall.insert(spectrum, at: 0); if waterfall.count > 80 { waterfall.removeLast() } }; if timer == nil { timer = Timer.scheduledTimer(withTimeInterval: 0.75, repeats: true) { [weak self] _ in self?.refresh() } } }
    func setting(_ cmd: String, _ values: [String:Any] = [:]) { var object = values; object["cmd"] = cmd; _ = command(object); refresh() }
    func recording(_ on: Bool) { let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].path; _ = command(["cmd": on ? "record_start" : "record_stop", "dir": dir]); refresh() }
    func decoder(_ name: String, on: Bool) { _ = command(["cmd": name, "on": on]); refresh() }
    func tune(_ hz: Double) { _ = command(["cmd":"tune", "hz": hz]); refresh() }
    func start() { _ = command(["cmd":"start"]); audio.start(); refresh() }; func stop() { _ = command(["cmd":"stop"]); audio.stop(); refresh() }; func updateSatellites() { _ = command(["cmd":"sat_update"]); refresh() }
    func favourite(_ norad: Int, on: Bool) { _ = command(["cmd":"favourite", "norad": norad, "on": on]); refresh() }
    func select(_ norad: Int) { UserDefaults.standard.set(norad, forKey: "selectedNorad"); _ = command(["cmd":"sat_select","norad":norad]); refresh() }; func track(_ on: Bool) { _ = command(["cmd":"sat_track","on":on]); refresh() }; func setMode(_ mode: String) { UserDefaults.standard.set(mode, forKey: "mode"); _ = command(["cmd":"mode","mode":mode]); refresh() }; func setSource(_ id: String) { UserDefaults.standard.set(id, forKey: "source"); _ = command(["cmd":"source","id":id]); refresh() }
}
