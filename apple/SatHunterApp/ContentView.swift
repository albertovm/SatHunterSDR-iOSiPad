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
    var body: some View { TabView() { ReceiverView().tabItem { Label("Receiver", systemImage: "radio") }; SatellitesView().tabItem { Label("Satellites", systemImage: "dot.radiowaves.left.and.right") }; SettingsView().tabItem { Label("Settings", systemImage: "gearshape.fill") } }.tint(Color(red: 0.32, green: 0.70, blue: 1.0)).preferredColorScheme(.dark).task { engine.bootstrap() } }
}
private struct ReceiverView: View {
    @EnvironmentObject private var engine: SatHunterEngine
    var running: Bool { engine.status["running"] as? Bool ?? false }; var source: String { engine.status["source"] as? String ?? "desconhecida" }; var mode: String { engine.status["mode"] as? String ?? "WFM" }; var hz: Double { engine.status["vfo_hz"] as? Double ?? 0 }
    var body: some View { NavigationStack { ScrollView { VStack(alignment: .leading, spacing: 10) { HStack { SatHunterLogo().frame(width: 42, height: 42); FrequencyDisplay(hz: hz); Spacer(); Circle().fill(running ? .green : .red).frame(width: 10) }; Text("\(mode)  •  \(source)").foregroundStyle(.secondary).font(.caption); HStack { Button("−") { engine.tune(hz - 12500) }.buttonStyle(.bordered); Button(running ? "■" : "▶") { running ? engine.stop() : engine.start() }.buttonStyle(.borderedProminent); Button("+") { engine.tune(hz + 12500) }.buttonStyle(.bordered) }.frame(maxWidth: .infinity); SpectrumView(values: engine.spectrum, centerHz: hz) { engine.tune($0) }.frame(height: 150)
                WaterfallView(rows: engine.waterfall).frame(height: 180).background(Color.black).clipShape(RoundedRectangle(cornerRadius: 12)); RadarView(azimuth: engine.detail["az"] as? Double ?? 0, elevation: engine.detail["el"] as? Double ?? 0).frame(height: 220).background(Color.black).clipShape(RoundedRectangle(cornerRadius: 12)); HStack { Button(running ? "Parar" : "Iniciar") { running ? engine.stop() : engine.start() }.buttonStyle(.borderedProminent); Button("Usar demonstração") { engine.setSource("demo") }.buttonStyle(.bordered) }; HStack(spacing: 4) { ForEach(["NFM","WFM","AM","USB","LSB","CW"], id: \.self) { item in Button(item) { engine.setMode(item) }.buttonStyle(.borderedProminent).tint(mode == item ? .blue : .gray) } }.lineLimit(1); HStack { Button("Volume −") { engine.changeVolume(-0.1) }; Text("Vol \(Int(engine.volume * 100))%"); Button("Volume +") { engine.changeVolume(0.1) } }; HStack { RecordButton(engine: engine, active: engine.status["recording"] != nil); HStack { DecoderButton(title: "APRS", key: "aprs", status: engine.status["aprs"] as? [String:Any] ?? [:], engine: engine); DecoderButton(title: "SSTV", key: "sstv", status: engine.status["sstv"] as? [String:Any] ?? [:], engine: engine); DecoderButton(title: "FSK 9k6", key: "fsk9k6", status: engine.status["fsk9k6"] as? [String:Any] ?? [:], engine: engine) }; }; Text("APRS: \((engine.status["aprs"] as? [String:Any])?["count"] as? Int ?? 0) frames • SSTV: \((engine.status["sstv"] as? [String:Any])?["rows"] as? Int ?? 0) linhas • FSK: \((engine.status["fsk9k6"] as? [String:Any])?["count"] as? Int ?? 0) frames").font(.caption).foregroundStyle(.secondary); Text(((engine.status["plugins"] as? [String]) ?? []).suffix(3).joined(separator: "\n")).font(.caption2).foregroundStyle(.secondary); Text("Estado do núcleo").font(.headline); Text(engine.status["source_status"] as? String ?? (running ? "Executando" : "Parado")).frame(maxWidth: .infinity, alignment: .leading).padding().background(.thinMaterial).clipShape(RoundedRectangle(cornerRadius: 12)); if let err = engine.lastError { Text(err).foregroundStyle(.red) } }.padding() }.navigationTitle("SatHunter SDR") } }
}
private struct SatellitesView: View { @EnvironmentObject private var engine: SatHunterEngine; @State private var search = ""; @State private var favouritesOnly = false; @State private var band = "Todas"; var filtered: [Int] { engine.satelliteRows.indices.filter { (search.isEmpty || (engine.satelliteRows[$0]["name"] as? String ?? "").localizedCaseInsensitiveContains(search)) && (!favouritesOnly || (engine.satelliteRows[$0]["fav"] as? Bool ?? false)) && (band == "Todas" || (engine.satelliteRows[$0]["bands"] as? String ?? "").localizedCaseInsensitiveContains(band)) } }; var body: some View { NavigationSplitView { List { TextField("Buscar satélite", text: $search); Button("Atualizar dados dos satélites") { engine.updateSatellites() }; Toggle("Somente favoritos", isOn: $favouritesOnly); Picker("Banda", selection: $band) { ForEach(["Todas", "TwoM", "SeventyCm", "SBand", "ThirteenCm"], id: \.self) { Text($0).tag($0) } }; ForEach(filtered, id: \.self) { i in let row = engine.satelliteRows[i]; let name = row["name"] as? String ?? "Satélite"; let norad = row["norad"] as? Int ?? 0; HStack { Button { engine.select(norad) } label: { VStack(alignment: .leading) { Text(name); Text("NORAD \(norad)").font(.caption).foregroundStyle(.secondary) } }; Spacer(); Button { engine.favourite(norad, on: !(row["fav"] as? Bool ?? false)) } label: { Image(systemName: (row["fav"] as? Bool ?? false) ? "star.fill" : "star").foregroundStyle(.yellow) }.buttonStyle(.plain) } } }.navigationTitle("Satélites") } detail: { SatelliteDetailView() } } }
private struct SatelliteDetailView: View { @EnvironmentObject private var engine: SatHunterEngine
    var look: [String: Any] { engine.detail["look"] as? [String: Any] ?? [:] }
    var body: some View { VStack(alignment: .leading, spacing: 12) { Text(engine.detail["name"] as? String ?? "Selecione um satélite").font(.title2.bold()); Text("Azimute: \(String(format: "%.1f°", look["az"] as? Double ?? 0)) • Elevação: \(String(format: "%.1f°", look["el"] as? Double ?? 0))"); RadarView(azimuth: look["az"] as? Double ?? 0, elevation: look["el"] as? Double ?? 0).frame(height: 220).background(Color.black).clipShape(RoundedRectangle(cornerRadius: 12)); if let sub = engine.detail["sub"] as? [String: Any] { MapOverview(latitude: sub["lat"] as? Double ?? 0, longitude: sub["lon"] as? Double ?? 0).frame(height: 180).clipShape(RoundedRectangle(cornerRadius: 12)) }; let tracking = engine.detail["tracking"] as? Bool ?? false; Button(tracking ? "Parar rastreio" : "Começar rastreio") { engine.track(!tracking) }.buttonStyle(.borderedProminent); Spacer() }.padding() } }
private struct SettingsView: View { @EnvironmentObject private var engine: SatHunterEngine; var body: some View { NavigationStack { Form { Section("Fonte") { Button("Demonstração") { engine.setSource("demo") }; Button("Ativar localização") { engine.location.request(); engine.location.start() }; Button((engine.status["follow_gps"] as? Bool ?? false) ? "Parar seguir GPS" : "Seguir GPS") { engine.setting("follow_gps", ["on": !(engine.status["follow_gps"] as? Bool ?? false)]) }; Button("Sintonia central") { engine.setting("center_tuning", ["on": true]) }; Button("Plugins") { engine.setting("plugins", ["on": true]) }; Button("Bias-tee") { engine.setting("bias_tee", ["on": true]) }.disabled(!(engine.status["has_bias_tee"] as? Bool ?? false)); Text("USB direto no iPad exige uma camada DriverKit ou fonte de rede.").font(.footnote).foregroundStyle(.secondary) }; Section("Diagnóstico") { Text("Satélites carregados: \(engine.satelliteRows.count)"); Text("Núcleo: \(engine.status.isEmpty ? "não inicializado" : "pronto")"); Text("Taxa: \(String(format: "%.1f MS/s", (engine.status["rate"] as? Double ?? 0) / 1e6))"); Text("Nível: \(String(format: "%.1f dB", engine.status["level_db"] as? Double ?? -120))"); Text("Bússola: \(String(format: "%.0f°", engine.heading))"); HStack { Button("Ganho −") { let g = engine.status["gain"] as? Double ?? 0; engine.setting("gain", ["db": g - 1]) }; Text("Ganho: \(String(format: "%.1f dB", engine.status["gain"] as? Double ?? 0))"); Button("Ganho +") { let g = engine.status["gain"] as? Double ?? 0; engine.setting("gain", ["db": g + 1]) } }; HStack { Button("PPM −") { let p = engine.status["ppm"] as? Double ?? 0; engine.setting("ppm", ["ppm": p - 1]) }; Text("PPM: \(String(format: "%.0f", engine.status["ppm"] as? Double ?? 0))"); Button("PPM +") { let p = engine.status["ppm"] as? Double ?? 0; engine.setting("ppm", ["ppm": p + 1]) } } } } }.navigationTitle("Configurações") } } 

private struct SpectrumView: View { let values: [Float]; let centerHz: Double; let onTune: (Double) -> Void; @State private var dragHz: Double?; @State private var zoom: CGFloat = 1; @State private var baseZoom: CGFloat = 1; var body: some View { GeometryReader { geo in Path { path in guard values.count > 1 else { return }; let lo = values.min() ?? -120; let hi = max(values.max() ?? 0, lo + 1); for i in values.indices { let rawX = CGFloat(i) / CGFloat(values.count - 1); let x = geo.size.width * (0.5 + (rawX - 0.5) / zoom); let y = geo.size.height * CGFloat(1 - (values[i] - lo) / (hi - lo)); if i == values.startIndex { path.move(to: CGPoint(x:x,y:y)) } else { path.addLine(to: CGPoint(x:x,y:y)) } } }.stroke(.green, lineWidth: 1.5).contentShape(Rectangle()).gesture(DragGesture(minimumDistance: 0).onChanged { value in let delta = Double(value.translation.width / max(1, geo.size.width)) * 2_000_000 / Double(zoom); dragHz = centerHz - delta }.onEnded { _ in if let f = dragHz { onTune(f) }; dragHz = nil }).simultaneousGesture(MagnificationGesture().onChanged { value in zoom = min(16, max(1, baseZoom * value)) }.onEnded { _ in baseZoom = zoom }) } } }

private struct RadarView: View {
    let azimuth: Double
    let elevation: Double
    var body: some View {
        Canvas { context, size in
            let center = CGPoint(x: size.width / 2, y: size.height / 2)
            let radius = min(size.width, size.height) * 0.42
            for factor in [1.0, 0.66, 0.33] {
                context.stroke(Path(ellipseIn: CGRect(x: center.x - radius * factor, y: center.y - radius * factor, width: radius * 2 * factor, height: radius * 2 * factor)), with: .color(.green.opacity(0.45)), lineWidth: 1)
            }
            var cross = Path(); cross.move(to: CGPoint(x: center.x - radius, y: center.y)); cross.addLine(to: CGPoint(x: center.x + radius, y: center.y)); cross.move(to: CGPoint(x: center.x, y: center.y - radius)); cross.addLine(to: CGPoint(x: center.x, y: center.y + radius)); context.stroke(cross, with: .color(.green.opacity(0.35)))
            let angle = (azimuth - 90) * .pi / 180
            let distance = radius * max(0, min(1, elevation / 90))
            let point = CGPoint(x: center.x + CGFloat(cos(angle) * distance), y: center.y + CGFloat(sin(angle) * distance))
            context.fill(Path(ellipseIn: CGRect(x: point.x - 6, y: point.y - 6, width: 12, height: 12)), with: .color(.yellow))
        }
        .overlay(alignment: .topLeading) { Text("Radar • Az \(String(format: "%.0f", azimuth))°  El \(String(format: "%.0f", elevation))°").font(.caption).foregroundStyle(.green).padding(8) }
    }
}

private struct WaterfallView: View {
    let rows: [[Float]]
    var body: some View { Canvas { context, size in
        guard !rows.isEmpty else { return }
        let rowHeight = size.height / CGFloat(rows.count)
        for (y, row) in rows.enumerated() { guard let lo = row.min(), let hi0 = row.max() else { continue }; let hi = max(hi0, lo + 1); let width = size.width / CGFloat(max(row.count, 1)); for (x, value) in row.enumerated() { let n = CGFloat((value - lo) / (hi - lo)); let color = Color(hue: Double(0.66 - n * 0.66), saturation: 0.95, brightness: 0.25 + Double(n) * 0.75); context.fill(Path(CGRect(x: CGFloat(x) * width, y: CGFloat(y) * rowHeight, width: width + 1, height: rowHeight + 1)), with: .color(color)) } }
    }.overlay(alignment: .topLeading) { Text("Waterfall").font(.caption).foregroundStyle(.white).padding(8) } }
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
    var body: some View { Map(initialPosition: .region(MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: latitude, longitude: longitude), span: MKCoordinateSpan(latitudeDelta: 20, longitudeDelta: 20)))) { Marker("Observador", coordinate: CLLocationCoordinate2D(latitude: latitude, longitude: longitude)).tint(.blue) } }
}
