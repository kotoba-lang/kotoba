import Foundation
import Testing
@testable import KotobaFileProvider
#if canImport(FileProvider)
import FileProvider
#endif

@Test func wireShapeRoundTrips() throws {
    let item = DriveItem(id: .init(rawValue: "item-1"),
                         parentID: .init(rawValue: "root"),
                         name: "暗号化.txt", directory: false, size: 42,
                         contentVersion: "cipher-cid", metadataVersion: "v1",
                         schedule: .manual, residency: .pinned)
    let data = try JSONEncoder().encode(item)
    let decoded = try JSONDecoder().decode(DriveItem.self, from: data)
    #expect(decoded == item)
    #expect(String(decoding: data, as: UTF8.self).contains("online-only") == false)
}

@Test func onlyLocalBridgeEndpointsAreAccepted() {
    let localhost = URL(string: "http://127.0.0.1:1338/")!
    _ = HTTPDriveBridge(baseURL: localhost, bearer: "ephemeral")
}

#if canImport(FileProvider)
@Test func residencyMapsToFinderContentPolicy() {
    func item(_ residency: Residency) -> ProviderItem {
        ProviderItem(DriveItem(id: .init(rawValue: "item"),
                               parentID: .init(rawValue: "root"), name: "file",
                               directory: false, size: 0,
                               contentVersion: "c", metadataVersion: "m",
                               schedule: .continuous, residency: residency))
    }
    #expect(item(.onlineOnly).contentPolicy == .downloadLazily)
    #expect(item(.automatic).contentPolicy == .inherited)
    #expect(item(.pinned).contentPolicy == .downloadEagerlyAndKeepDownloaded)
}
#endif
