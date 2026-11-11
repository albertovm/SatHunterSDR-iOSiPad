import MapKit
import SwiftUI

private struct FrequencyDisplay: View {
    let hz: Double
    var body: some View {
        HStack(spacing: 2) {
            ForEach(Array(String(format: "%09.0f", max(0, hz)).enumerated()), id: \.offset) { _, c in
                Text(String(c)).font(.system(size: 24, weight: .medium, design: .monospaced)).foregroundStyle(.orange).padding(.horizontal, 2).background(Color.black.opacity(0.7)).clipShape(RoundedRectangle(cornerRadius: 4))
            }
        }
    }
}

struct ContentView: View {
    @EnvironmentObject private var engine: SatHunterEngine
    var body: some View { TabView() { ReceiverScreenView().tabItem { Label("Receiver", systemImage: "radio") }; SatellitesView().tabItem { Label("Satellites", systemImage: "dot.radiowaves.left.and.right") }; SettingsView().tabItem { Label("Settings", systemImage: "gearshape.fill") } }.tint(Color(red: 0.32, green: 0.70, blue: 1.0)).preferredColorScheme(.dark).task { engine.bootstrap() } }
}
private struct ReceiverView: View {
    @EnvironmentObject private var engine: SatHunterEngine
    var running: Bool { engine.status["running"] as? Bool ?? false }; var source: String { engine.status["source"] as? String ?? "desconhecida" }; var mode: String { engine.status["mode"] as? String ?? "WFM" }; var hz: Double { engine.status["vfo_hz"] as? Double ?? 0 }
    var body: some View { NavigationStack { ScrollView { VStack(alignment: .leading, spacing: 10) { HStack { SatHunterLogo().frame(width: 42, height: 42); FrequencyDisplay(hz: hz); Spacer(); Circle().fill(running ? .green : .red).frame(width: 10) }; Text("\(mode)  •  \(source)").foregroundStyle(.secondary).font(.caption); HStack { Button("−") { engine.tune(hz - 12500) }.buttonStyle(.bordered); Button(running ? "■" : "▶") { running ? engine.stop() : engine.start() }.buttonStyle(.borderedProminent); Button("+") { engine.tune(hz + 12500) }.buttonStyle(.bordered) }.frame(maxWidth: .infinity); ZStack { SpectrumView(values: engine.spectrum, centerHz: hz) { engine.tune($0) }; FrequencyScaleOverlay(centerHz: hz, mode: mode); SatelliteMarkerOverlay(rows: engine.satelliteRows, centerHz: hz) { row in if let n = row["norad"] as? Int { engine.select(n) }; if let f = row["freq"] as? Double { engine.tune(f) } } }.frame(height: 150)
                WaterfallView(rows: engine.waterfall, centerHz: hz) { engine.tune($0) }.frame(height: 180).background(Color.black).clipShape(RoundedRectangle(cornerRadius: 12)).overlay { SatelliteMarkerOverlay(rows: engine.satelliteRows, centerHz: hz) { row in if let n = row["norad"] as? Int { engine.select(n) }; if let f = row["freq"] as? Double { engine.tune(f) } } }; RadarView(azimuth: engine.detail["az"] as? Double ?? 0, elevation: engine.detail["el"] as? Double ?? 0).frame(height: 220).background(Color.black).clipShape(RoundedRectangle(cornerRadius: 12)); HStack { Button(running ? "Parar" : "Iniciar") { running ? engine.stop() : engine.start() }.buttonStyle(.borderedProminent); Button("Usar demonstração") { engine.setSource("demo") }.buttonStyle(.bordered) }; HStack(spacing: 4) { ForEach(["NFM","WFM","AM","USB","LSB","CW"], id: \.self) { item in Button(item) { engine.setMode(item) }.buttonStyle(.borderedProminent).tint(mode == item ? .blue : .gray) } }.lineLimit(1); HStack { Button("Volume −") { engine.changeVolume(-0.1) }; Text("Vol \(Int(engine.volume * 100))%"); Button("Volume +") { engine.changeVolume(0.1) } }; HStack { RecordButton(engine: engine, active: engine.status["recording"] != nil); HStack { DecoderButton(title: "APRS", key: "aprs", status: engine.status["aprs"] as? [String:Any] ?? [:], engine: engine); DecoderButton(title: "SSTV", key: "sstv", status: engine.status["sstv"] as? [String:Any] ?? [:], engine: engine); DecoderButton(title: "FSK 9k6", key: "fsk9k6", status: engine.status["fsk9k6"] as? [String:Any] ?? [:], engine: engine) }; }; Text("APRS: \((engine.status["aprs"] as? [String:Any])?["count"] as? Int ?? 0) frames • SSTV: \((engine.status["sstv"] as? [String:Any])?["rows"] as? Int ?? 0) linhas • FSK: \((engine.status["fsk9k6"] as? [String:Any])?["count"] as? Int ?? 0) frames").font(.caption).foregroundStyle(.secondary); Text(((engine.status["plugins"] as? [String]) ?? []).suffix(3).joined(separator: "\n")).font(.caption2).foregroundStyle(.secondary); Text("Estado do núcleo").font(.headline); Text(engine.status["source_status"] as? String ?? (running ? "Executando" : "Parado")).frame(maxWidth: .infinity, alignment: .leading).padding().background(.thinMaterial).clipShape(RoundedRectangle(cornerRadius: 12)); if let err = engine.lastError { Text(err).foregroundStyle(.red) } }.padding() }.navigationTitle("SatHunter SDR") } }
}
private struct SatellitesView: View { @EnvironmentObject private var engine: SatHunterEngine; @State private var search = ""; @State private var favouritesOnly = false; @State private var band = "Todas"; @State private var selectedNorad: Int?; var filtered: [Int] { engine.satelliteRows.indices.filter { (search.isEmpty || (engine.satelliteRows[$0]["name"] as? String ?? "").localizedCaseInsensitiveContains(search)) && (!favouritesOnly || (engine.satelliteRows[$0]["fav"] as? Bool ?? false)) && (band == "Todas" || (engine.satelliteRows[$0]["bands"] as? String ?? "").localizedCaseInsensitiveContains(band)) } }; var body: some View { NavigationSplitView { List(selection: $selectedNorad) { TextField("Buscar satélite", text: $search); Button("Atualizar dados dos satélites") { engine.updateSatellites() }; Toggle("Somente favoritos", isOn: $favouritesOnly); Picker("Banda", selection: $band) { ForEach(["Todas", "TwoM", "SeventyCm", "SBand", "ThirteenCm"], id: \.self) { Text($0).tag($0) } }; ForEach(filtered, id: \.self) { i in let row = engine.satelliteRows[i]; let name = row["name"] as? String ?? "Satélite"; let norad = row["norad"] as? Int ?? 0; HStack { Button { selectedNorad = norad; engine.select(norad) } label: { VStack(alignment: .leading) { Text(name); Text("NORAD \(norad)").font(.caption).foregroundStyle(.secondary) } }.buttonStyle(.plain); Spacer(); Button { engine.favourite(norad, on: !(row["fav"] as? Bool ?? false)) } label: { Image(systemName: (row["fav"] as? Bool ?? false) ? "star.fill" : "star").foregroundStyle(.yellow) }.buttonStyle(.plain) }.tag(norad) } }.navigationTitle("Satélites") } detail: { SatelliteDetailView() }.onChange(of: selectedNorad) { _, value in if let value { engine.select(value) } } } }
 private struct SatelliteDetailView: View { @EnvironmentObject private var engine: SatHunterEngine
    var look: [String: Any] { engine.detail["look"] as? [String: Any] ?? [:] }
    var body: some View { ScrollView { VStack(alignment: .leading, spacing: 12) { Text(engine.detail["name"] as? String ?? "Selecione um satélite").font(.title2.bold()); Text("Azimute: \(String(format: "%.1f°", look["az"] as? Double ?? 0)) • Elevação: \(String(format: "%.1f°", look["el"] as? Double ?? 0))"); if let txs = engine.detail["tx"] as? [[String: Any]], !txs.isEmpty { Text("Downlinks").font(.headline); ForEach(Array(txs.enumerated()), id: \.offset) { _, tx in let uuid = tx["uuid"] as? String ?? ""; let freq = tx["freq"] as? Double ?? tx["low"] as? Double ?? 0; Button { if let norad = engine.detail["selected"] as? Int { engine.select(norad, tx: uuid) } } label: { HStack { VStack(alignment: .leading) { Text(tx["description"] as? String ?? tx["mode"] as? String ?? "Transmissor"); Text(String(format: "%.3f MHz • %@", freq / 1e6, tx["mode"] as? String ?? "")).font(.caption).foregroundStyle(.secondary) }; Spacer(); Image(systemName: (tx["matches"] as? Bool ?? false) ? "checkmark.circle.fill" : "circle") } }.buttonStyle(.plain) } }; RadarView(azimuth: look["az"] as? Double ?? 0, elevation: look["el"] as? Double ?? 0, heading: engine.heading).frame(height: 220).background(Color.black).clipShape(RoundedRectangle(cornerRadius: 12)); if let sub = engine.detail["sub"] as? [String: Any] { let ground = (engine.detail["ground"] as? [[Any]] ?? []).compactMap { p -> [Double]? in guard p.count >= 2, let lat = p[0] as? Double, let lon = p[1] as? Double else { return nil }; return [lat, lon] }; MapOverview(latitude: sub["lat"] as? Double ?? 0, longitude: sub["lon"] as? Double ?? 0, ground: ground, pins: engine.pluginPins).frame(height: 180).clipShape(RoundedRectangle(cornerRadius: 12)) }; let tracking = engine.detail["tracking"] as? Bool ?? false; Button(tracking ? "Parar rastreio" : "Começar rastreio") { engine.track(!tracking) }.buttonStyle(.borderedProminent) }.padding() } }
}
private struct SettingsView: View { @EnvironmentObject private var engine: SatHunterEngine; var body: some View { NavigationStack { Form { Section("Fonte") { Button("Demonstração") { engine.setSource("demo") }; Button("Ativar localização") { engine.location.request(); engine.location.start() }; Button((engine.status["follow_gps"] as? Bool ?? false) ? "Parar seguir GPS" : "Seguir GPS") { engine.setting("follow_gps", ["on": !(engine.status["follow_gps"] as? Bool ?? false)]) }; Button("Sintonia central") { engine.setting("center_tuning", ["on": true]) }; Toggle("Plugins de decodificação", isOn: Binding(get: { engine.status["plugins"] as? Bool ?? true }, set: { engine.plugins($0) })); Button("Bias-tee") { engine.setting("bias_tee", ["on": true]) }.disabled(!(engine.status["has_bias_tee"] as? Bool ?? false)); Text("USB direto no iPad exige uma camada DriverKit ou fonte de rede.").font(.footnote).foregroundStyle(.secondary) }; GroundAprsSection(engine: engine); DebugLabSection(engine: engine); AdvancedDSPSection(engine: engine); Section("Espectro") { HStack { ForEach([1, 2, 4, 8], id: \.self) { value in Button("\(value)×") { engine.setDecimation(value) }.buttonStyle(.borderedProminent).tint((engine.status["decimation"] as? Int ?? 1) == value ? .blue : .gray) } }; Text("Decimação reduz a largura processada e destaca sinais fracos.").font(.footnote).foregroundStyle(.secondary) }; Section("Diagnóstico") { Text("Satélites carregados: \(engine.satelliteRows.count)"); Text("Núcleo: \(engine.status.isEmpty ? "não inicializado" : "pronto")"); Text("Taxa: \(String(format: "%.1f MS/s", (engine.status["rate"] as? Double ?? 0) / 1e6))"); Text("Nível: \(String(format: "%.1f dB", engine.status["level_db"] as? Double ?? -120))"); Text("Bússola: \(String(format: "%.0f°", engine.heading))"); HStack { Button("Ganho −") { let g = engine.status["gain"] as? Double ?? 0; engine.setting("gain", ["db": g - 1]) }; Text("Ganho: \(String(format: "%.1f dB", engine.status["gain"] as? Double ?? 0))"); Button("Ganho +") { let g = engine.status["gain"] as? Double ?? 0; engine.setting("gain", ["db": g + 1]) } }; HStack { Button("PPM −") { let p = engine.status["ppm"] as? Double ?? 0; engine.setting("ppm", ["ppm": p - 1]) }; Text("PPM: \(String(format: "%.0f", engine.status["ppm"] as? Double ?? 0))"); Button("PPM +") { let p = engine.status["ppm"] as? Double ?? 0; engine.setting("ppm", ["ppm": p + 1]) } } } } }.navigationTitle("Configurações") } } 

private struct GroundAprsSection: View { let engine: SatHunterEngine; var active: Bool { (engine.status["ground_aprs"] as? [String: Any])?["on"] as? Bool ?? false }; var hz: Double { (engine.status["ground_aprs"] as? [String: Any])?["hz"] as? Double ?? 144.8e6; }; var body: some View { Section("APRS terrestre") { Toggle("Escutar APRS sem rastrear satélite", isOn: Binding(get: { active }, set: { engine.groundAprs($0, hz: hz) })); HStack { ForEach([144.39e6, 144.8e6, 145.825e6], id: \.self) { value in Button(String(format: "%.3f MHz", value / 1e6)) { engine.groundAprs(true, hz: value) }.buttonStyle(.borderedProminent).tint(abs(hz - value) < 1 ? .blue : .gray) } }.disabled(!active); Text("Modo fixo NFM/AFSK 1200; iniciar o rastreio de um satélite encerra este modo.").font(.footnote).foregroundStyle(.secondary) } } }

private struct DebugLabSection: View { let engine: SatHunterEngine; @State private var pin = ""; var debug: Bool { engine.status["debug_mode"] as? Bool ?? false }; var body: some View { Section("Diagnóstico e laboratório") { Toggle("Modo debug / console LAN", isOn: Binding(get: { debug }, set: { engine.debugMode($0) })); HStack { TextField("PIN (4–8 dígitos)", text: $pin).keyboardType(.numberPad); Button("Definir") { engine.labPin(pin) } }; if let lab = engine.status["lab"] as? [String: Any], let address = lab["address"] as? String { Text("Console: \(address)").font(.footnote).foregroundStyle(.secondary) }; Text("GPS: \(engine.gpsText)").font(.footnote).foregroundStyle(.secondary); Text("O console permite medições e testes do receptor pela rede local.").font(.footnote).foregroundStyle(.secondary) } } }

private struct AdvancedDSPSection: View { let engine: SatHunterEngine; var body: some View { Section("DSP avançado") { Text("Largura de banda"); HStack { ForEach([12500.0, 25000.0, 200000.0], id: \.self) { value in Button(String(format: "%.1f kHz", value / 1000)) { engine.bandwidth(value) }.buttonStyle(.borderedProminent) } }; Text("Taxa de amostragem"); HStack { ForEach([1.0e6, 2.0e6, 2.4e6], id: \.self) { value in Button(String(format: "%.1f MS/s", value / 1e6)) { engine.sampleRate(value) }.buttonStyle(.bordered) } }; HStack { Button("Simular passagem") { engine.simulatePass() }; Button("Tempo real") { engine.realTime() } }; Button("Resetar offset Doppler") { engine.resetDopplerOffset() } } } }

private struct SatelliteMarkerOverlay: View { let rows: [[String: Any]]; let centerHz: Double; let onSelect: ([String: Any]) -> Void; var body: some View { GeometryReader { geo in ForEach(Array(rows.prefix(24).enumerated()), id: \.offset) { _, row in if let f = row["freq"] as? Double, f > 0 { let x = geo.size.width * (0.5 + CGFloat((f - centerHz) / 2_000_000)); if x >= 0 && x <= geo.size.width { VStack(spacing: 2) { Rectangle().fill(.yellow.opacity(0.7)).frame(width: 1); Text(row["name"] as? String ?? "SAT").font(.system(size: 8, weight: .semibold)).foregroundStyle(.yellow).lineLimit(1).frame(maxWidth: 72) }.position(x: x, y: geo.size.height / 2).contentShape(Rectangle()).onTapGesture { onSelect(row) } } } } } } }

private struct FrequencyScaleOverlay: View {
    let centerHz: Double
    let mode: String
    var body: some View {
        GeometryReader { geo in
            ZStack {
                let width: CGFloat = mode == "WFM" ? 0.42 : (mode == "AM" ? 0.12 : (mode == "USB" || mode == "LSB" ? 0.16 : 0.08))
                Rectangle().fill(.blue.opacity(0.14)).frame(width: geo.size.width * width, height: geo.size.height).position(x: geo.size.width / 2, y: geo.size.height / 2)
                Rectangle().fill(.red).frame(width: 2).position(x: geo.size.width / 2, y: geo.size.height / 2)
                HStack {
                    ForEach(-2...2, id: \.self) { tick in
                        VStack(spacing: 2) {
                            Rectangle().fill(.white.opacity(0.5)).frame(width: 1, height: 7)
                            Text(String(format: "%.3f", (centerHz + Double(tick) * 500_000) / 1e6)).font(.system(size: 8, design: .monospaced)).foregroundStyle(.white.opacity(0.75))
                        }.frame(maxWidth: .infinity)
                    }
                }.frame(maxHeight: .infinity, alignment: .bottom)
                Text(mode).font(.caption2.bold()).foregroundStyle(.white).padding(4).background(.black.opacity(0.55)).clipShape(Capsule()).position(x: 26, y: 14)
            }
        }
    }
}

private struct SpectrumView: View { let values: [Float]; let centerHz: Double; let onTune: (Double) -> Void; @State private var dragHz: Double?; @State private var zoom: CGFloat = 1; @State private var baseZoom: CGFloat = 1; var body: some View { GeometryReader { geo in Path { path in guard values.count > 1 else { return }; let lo = values.min() ?? -120; let hi = max(values.max() ?? 0, lo + 1); for i in values.indices { let rawX = CGFloat(i) / CGFloat(values.count - 1); let x = geo.size.width * (0.5 + (rawX - 0.5) / zoom); let y = geo.size.height * CGFloat(1 - (values[i] - lo) / (hi - lo)); if i == values.startIndex { path.move(to: CGPoint(x:x,y:y)) } else { path.addLine(to: CGPoint(x:x,y:y)) } } }.stroke(.green, lineWidth: 1.5).contentShape(Rectangle()).gesture(DragGesture(minimumDistance: 0).onChanged { value in let delta = Double(value.translation.width / max(1, geo.size.width)) * 2_000_000 / Double(zoom); dragHz = centerHz - delta }.onEnded { _ in if let f = dragHz { onTune(f) }; dragHz = nil }).simultaneousGesture(MagnificationGesture().onChanged { value in zoom = min(16, max(1, baseZoom * value)) }.onEnded { _ in baseZoom = zoom }) } } }

private struct RadarView: View {
    let azimuth: Double
    let elevation: Double
    var heading: Double = 0
    var body: some View {
        Canvas { context, size in
            let center = CGPoint(x: size.width / 2, y: size.height / 2)
            let radius = min(size.width, size.height) * 0.42
            for factor in [1.0, 0.66, 0.33] {
                context.stroke(Path(ellipseIn: CGRect(x: center.x - radius * factor, y: center.y - radius * factor, width: radius * 2 * factor, height: radius * 2 * factor)), with: .color(.green.opacity(0.45)), lineWidth: 1)
            }
            var cross = Path(); cross.move(to: CGPoint(x: center.x - radius, y: center.y)); cross.addLine(to: CGPoint(x: center.x + radius, y: center.y)); cross.move(to: CGPoint(x: center.x, y: center.y - radius)); cross.addLine(to: CGPoint(x: center.x, y: center.y + radius)); context.stroke(cross, with: .color(.green.opacity(0.35)))
            let angle = (azimuth - heading - 90) * .pi / 180
            let distance = radius * max(0, min(1, elevation / 90))
            let point = CGPoint(x: center.x + CGFloat(cos(angle) * distance), y: center.y + CGFloat(sin(angle) * distance))
            context.fill(Path(ellipseIn: CGRect(x: point.x - 6, y: point.y - 6, width: 12, height: 12)), with: .color(.yellow))
        }
        .overlay(alignment: .topLeading) { Text("Radar • Az \(String(format: "%.0f", azimuth))°  El \(String(format: "%.0f", elevation))°  Hdg \(String(format: "%.0f", heading))°").font(.caption).foregroundStyle(.green).padding(8) }
    }
}

private struct WaterfallView: View {
    let rows: [[Float]]; let centerHz: Double; let onTune: (Double) -> Void
    @State private var dragHz: Double?; @State private var zoom: CGFloat = 1; @State private var baseZoom: CGFloat = 1
    var body: some View { Canvas { context, size in
        guard !rows.isEmpty else { return }
        let rowHeight = size.height / CGFloat(rows.count)
        for (y, row) in rows.enumerated() { guard let lo = row.min(), let hi0 = row.max() else { continue }; let hi = max(hi0, lo + 1); let width = size.width / CGFloat(max(row.count, 1)); for (x, value) in row.enumerated() { let n = CGFloat((value - lo) / (hi - lo)); let shifted = (CGFloat(x) / CGFloat(max(row.count, 1)) - 0.5) * zoom + 0.5; let color = Color(hue: Double(0.66 - n * 0.66), saturation: 0.95, brightness: 0.25 + Double(n) * 0.75); context.fill(Path(CGRect(x: shifted * size.width, y: CGFloat(y) * rowHeight, width: width * zoom + 1, height: rowHeight + 1)), with: .color(color)) } }
    }.overlay(alignment: .topLeading) { Text("Waterfall").font(.caption).foregroundStyle(.white).padding(8) }.contentShape(Rectangle()).gesture(DragGesture(minimumDistance: 0).onChanged { value in let delta = Double(value.translation.width / 300) * 2_000_000 / Double(zoom); dragHz = centerHz - delta }.onEnded { _ in if let f = dragHz { onTune(f) }; dragHz = nil }).simultaneousGesture(MagnificationGesture().onChanged { value in zoom = min(16, max(1, baseZoom * value)) }.onEnded { _ in baseZoom = zoom }) }
}

private struct GroundTrackView: View {
    let points: [[Double]]
    var body: some View { Canvas { context, size in
        context.fill(Path(CGRect(origin: .zero, size: size)), with: .color(Color.blue.opacity(0.28)))
        var grid = Path(); for x in stride(from: 0.0, through: 1.0, by: 0.25) { grid.move(to: CGPoint(x: size.width * x, y: 0)); grid.addLine(to: CGPoint(x: size.width * x, y: size.height)) }; for y in stride(from: 0.0, through: 1.0, by: 0.25) { grid.move(to: CGPoint(x: 0, y: size.height * y)); grid.addLine(to: CGPoint(x: size.width, y: size.height * y)) }; context.stroke(grid, with: .color(.white.opacity(0.2)))
        guard points.count > 1 else { return }; var track = Path(); for (i, point) in points.enumerated() where point.count >= 2 { let x = size.width * CGFloat((point[1] + 180) / 360); let y = size.height * CGFloat((90 - point[0]) / 180); if i == 0 { track.move(to: CGPoint(x:x,y:y)) } else { track.addLine(to: CGPoint(x:x,y:y)) } }; context.stroke(track, with: .color(.yellow), lineWidth: 2)
    }.overlay(alignment: .topLeading) { Text("Trajetória terrestre").font(.caption).foregroundStyle(.white).padding(8) } }
}

private struct DecoderButton: View { let title: String; let key: String; let status: [String:Any]; let engine: SatHunterEngine; var active: Bool { status["on"] as? Bool ?? false }; var body: some View { Button { engine.decoder(key, on: !active) } label: { Label(title, systemImage: active ? "stop.circle.fill" : "play.circle").font(.caption) }.buttonStyle(.bordered).tint(active ? .green : .secondary) } }

private struct RecordButton: View { let engine: SatHunterEngine; let active: Bool; var body: some View { Button { engine.recording(!active) } label: { Label(active ? "Parar gravação" : "Gravar IQ", systemImage: active ? "stop.circle.fill" : "record.circle") }.buttonStyle(.bordered).tint(active ? .red : .secondary) } }

private struct MapOverview: View {
    let latitude: Double
    let longitude: Double
    var ground: [[Double]] = []
    var pins: [[String: Any]] = []
    var body: some View { Map(initialPosition: .region(MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: latitude, longitude: longitude), span: MKCoordinateSpan(latitudeDelta: 20, longitudeDelta: 20)))) { Marker("Observador", coordinate: CLLocationCoordinate2D(latitude: latitude, longitude: longitude)).tint(.blue); if !ground.isEmpty { MapPolyline(coordinates: ground.map { CLLocationCoordinate2D(latitude: $0[0], longitude: $0[1]) }).stroke(.yellow, lineWidth: 2) }; ForEach(Array(pins.enumerated()), id: \.offset) { _, pin in if let lat = pin["lat"] as? Double, let lon = pin["lon"] as? Double { Marker(pin["label"] as? String ?? "APRS", coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon)).tint(.orange) } } } }
}

private struct ReceiverScreenView: View {
    @EnvironmentObject private var engine: SatHunterEngine
    @Environment(\.dismiss) private var dismiss
    @State private var fullscreen = false
    private var mode: String { engine.status["mode"] as? String ?? "WFM" }
    private var hz: Double { engine.status["vfo_hz"] as? Double ?? 0 }
    private var running: Bool { engine.status["running"] as? Bool ?? false }
    private var look: [String: Any] { engine.detail["look"] as? [String: Any] ?? [:] }
    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()
                VStack(spacing: 6) {
                    HStack { FrequencyDisplay(hz: hz); Spacer(); Circle().fill(running ? .green : .red).frame(width: 10) }
                    Text("\(mode)  •  \(engine.status["source"] as? String ?? "demo")").font(.caption).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading)
                    Text("Heading \(String(format: "%.0f°", engine.heading))").font(.caption2.monospacedDigit()).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading)
                    ZStack { SpectrumView(values: engine.spectrum, centerHz: hz) { engine.tune($0) }; FrequencyScaleOverlay(centerHz: hz, mode: mode) }.frame(height: fullscreen ? 220 : 150)
                    WaterfallView(rows: engine.waterfall, centerHz: hz) { engine.tune($0) }.frame(maxHeight: .infinity).overlay { SatelliteMarkerOverlay(rows: engine.satelliteRows, centerHz: hz) { row in if let n = row["norad"] as? Int { engine.select(n) } } }
                    if !fullscreen {
                        RadarView(azimuth: look["az"] as? Double ?? 0, elevation: look["el"] as? Double ?? 0, heading: engine.heading).frame(height: 150).background(Color.black).clipShape(RoundedRectangle(cornerRadius: 10))
                        HStack { Button("−") { engine.tune(hz - 12500) }; Button(running ? "Parar" : "Iniciar") { running ? engine.stop() : engine.start() }.buttonStyle(.borderedProminent); Button("+") { engine.tune(hz + 12500) } }
                        HStack(spacing: 4) { ForEach(["NFM","WFM","AM","USB","LSB","CW"], id: \.self) { item in Button(item) { engine.setMode(item) }.buttonStyle(.borderedProminent).tint(item == mode ? .blue : .gray) } }.lineLimit(1)
                    }
                    HStack { Button("Vol −") { engine.changeVolume(-0.1) }; Text("Vol \(Int(engine.volume * 100))%").font(.caption.monospacedDigit()); Button("Vol +") { engine.changeVolume(0.1) }; RecordButton(engine: engine, active: engine.status["recording"] != nil) }
                    HStack { DecoderButton(title: "APRS", key: "aprs", status: engine.status["aprs"] as? [String: Any] ?? [:], engine: engine); DecoderButton(title: "SSTV", key: "sstv", status: engine.status["sstv"] as? [String: Any] ?? [:], engine: engine); DecoderButton(title: "FSK 9k6", key: "fsk9k6", status: engine.status["fsk9k6"] as? [String: Any] ?? [:], engine: engine) }
                    DecoderSummaryPanel(status: engine.status, engine: engine)
                }.padding(8)
            }.toolbar { ToolbarItem(placement: .topBarTrailing) { Button { fullscreen.toggle() } label: { Image(systemName: fullscreen ? "arrow.down.right.and.arrow.up.left" : "arrow.up.left.and.arrow.down.right") } } }.navigationTitle(fullscreen ? "" : "SatHunter SDR").navigationBarTitleDisplayMode(.inline)
        }
    }
}

private struct DecoderSummaryPanel: View {
    let status: [String: Any]
    let engine: SatHunterEngine
    private func decoder(_ key: String) -> [String: Any] { status[key] as? [String: Any] ?? [:] }
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            let aprs = decoder("aprs"); let sstv = decoder("sstv"); let fsk = decoder("fsk9k6")
            Text("APRS \(aprs["count"] as? Int ?? 0) frames  •  SSTV \(sstv["rows"] as? Int ?? 0) linhas  •  FSK \(fsk["count"] as? Int ?? 0) frames").font(.caption).foregroundStyle(.secondary)
            if let frames = aprs["frames"] as? [[String: Any]], let last = frames.last { Text("APRS: \(last["src"] as? String ?? "") → \(last["dst"] as? String ?? "")").font(.caption2).foregroundStyle(.yellow) }
            if let image = engine.sstvImage { Image(uiImage: image).resizable().scaledToFit().frame(maxHeight: 180).clipShape(RoundedRectangle(cornerRadius: 6)) }
            if let plugins = status["plugins"] as? [String], !plugins.isEmpty { Text(plugins.suffix(3).joined(separator: "\n")).font(.caption2.monospaced()).foregroundStyle(.green) }
        }.frame(maxWidth: .infinity, alignment: .leading).padding(8).background(Color.white.opacity(0.06)).clipShape(RoundedRectangle(cornerRadius: 8))
    }
}
