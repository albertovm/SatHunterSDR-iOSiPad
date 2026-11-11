import Foundation
import SatHunterCore

@MainActor
final class SatHunterEngine: ObservableObject {
    @Published private(set) var statusText = "Inicializando…"
    @Published private(set) var running = false

    init() {
        let directory = FileManager.default.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        )[0].appendingPathComponent("SatHunterSDR", isDirectory: true)

        do {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            let initialized = directory.path.withCString { sh_apple_init($0) }
            statusText = initialized ? "Núcleo pronto" : "Falha ao iniciar o núcleo"
        } catch {
            statusText = error.localizedDescription
        }
    }

    func command(_ object: [String: Any]) -> [String: Any] {
        guard JSONSerialization.isValidJSONObject(object),
              let data = try? JSONSerialization.data(withJSONObject: object),
              let json = String(data: data, encoding: .utf8) else {
            return ["ok": false, "error": "comando inválido"]
        }

        guard let pointer = json.withCString({ sh_apple_command($0) }) else {
            return ["ok": false, "error": "sem resposta"]
        }
        defer { sh_apple_string_free(pointer) }

        let response = String(cString: pointer)
        guard let responseData = response.data(using: .utf8),
              let value = try? JSONSerialization.jsonObject(with: responseData) as? [String: Any] else {
            return ["ok": false, "error": "resposta inválida"]
        }
        return value
    }

    func toggleDemo() {
        if running {
            _ = command(["cmd": "stop"])
            running = false
            statusText = "Receptor parado"
        } else {
            _ = command(["cmd": "source", "id": "demo"])
            let response = command(["cmd": "start"])
            running = response["ok"] as? Bool ?? false
            statusText = running ? "Demonstração ativa" : (response["error"] as? String ?? "Falha ao iniciar")
        }
    }
}
