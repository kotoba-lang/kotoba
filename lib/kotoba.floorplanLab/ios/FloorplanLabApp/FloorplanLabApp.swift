import SwiftUI

/// App entry point for the FloorplanLab native shim. This target exists
/// solely to exercise `SensingBridge` against real device hardware -- it
/// deliberately has no design polish, no navigation, and no persistence.
/// See `ios/../README.md` "ios/" section and `SensingBridge.swift`'s
/// doc comment for the judgment-free-shim boundary this app respects.
@main
struct FloorplanLabApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
