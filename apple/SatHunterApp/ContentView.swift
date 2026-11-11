import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var engine: SatHunterEngine

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                Image(systemName: "antenna.radiowaves.left.and.right")
                    .font(.system(size: 72))
                    .foregroundStyle(.tint)

                Text("SatHunter SDR")
                    .font(.largeTitle.bold())

                Text(engine.statusText)
                    .foregroundStyle(.secondary)

                Button(engine.running ? "Parar demonstração" : "Iniciar demonstração") {
                    engine.toggleDemo()
                }
                .buttonStyle(.borderedProminent)
            }
            .padding()
            .navigationTitle("Receptor")
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(SatHunterEngine())
}
