import AppKit
import FileProvider

@main
final class KotobaDriveApp: NSObject, NSApplicationDelegate {
    private let domain = NSFileProviderDomain(identifier: .init("org.kotoba.drive"),
                                               displayName: "Cloud Itonami Drive")

    static func main() {
        let app = NSApplication.shared
        let delegate = KotobaDriveApp()
        app.delegate = delegate
        app.setActivationPolicy(.accessory)
        app.run()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let environment = ProcessInfo.processInfo.environment
        let defaults = UserDefaults(suiteName: "group.org.kotoba.drive")
        defaults?.set(environment["CLOUD_ITONAMI_FILE_PROVIDER_URL"] ?? "http://127.0.0.1:1338/",
                      forKey: "bridgeBaseURL")
        if let bearer = environment["CLOUD_ITONAMI_FILE_PROVIDER_BEARER"] {
            defaults?.set(bearer, forKey: "bridgeBearer")
        }
        NSFileProviderManager.add(domain) { error in
            if let error { NSLog("Cloud Itonami File Provider registration failed: %@", String(describing: error)) }
            else { NSLog("Cloud Itonami File Provider domain registered") }
        }
    }
}
