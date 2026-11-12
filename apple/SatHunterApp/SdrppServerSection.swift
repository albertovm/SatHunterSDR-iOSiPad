import SwiftUI

struct SdrppServerSection: View {
    @EnvironmentObject private var engine: SatHunterEngine
    @AppStorage("sdrppHost") private var host = "127.0.0.1"
    @AppStorage("sdrppPort") private var port = 5259

    var body: some View {
        Section("Servidor SDR++") {
            TextField("Endereço/IP", text: $host)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
            Stepper("Porta: \(port)", value: $port, in: 1...65535)
            Button("Conectar ao SDR++") { engine.configureSdrpp(host: host, port: port) }
            Text("Execute sdrpp --server no computador ligado ao SDR. Porta padrão: 5259/TCP.")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }
}
