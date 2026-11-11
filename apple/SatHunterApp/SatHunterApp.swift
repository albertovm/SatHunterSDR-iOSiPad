import SwiftUI

@main
struct SatHunterApp: App {
    @StateObject private var engine = SatHunterEngine()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(engine)
        }
    }
}
