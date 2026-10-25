#if canImport(FileProvider)
import FileProvider
import Foundation
import UniformTypeIdentifiers

public final class ProviderItem: NSObject, NSFileProviderItem {
    public let value: DriveItem
    public init(_ value: DriveItem) { self.value = value }

    public var itemIdentifier: NSFileProviderItemIdentifier { .init(value.id.rawValue) }
    public var parentItemIdentifier: NSFileProviderItemIdentifier { .init(value.parentID.rawValue) }
    public var filename: String { value.name }
    public var contentType: UTType {
        value.directory ? .folder : (UTType(filenameExtension: (value.name as NSString).pathExtension) ?? .data)
    }
    public var documentSize: NSNumber? { value.directory ? nil : NSNumber(value: value.size) }
    public var contentPolicy: NSFileProviderContentPolicy {
        switch value.residency {
        case .onlineOnly: .downloadLazily
        case .automatic: .inherited
        case .pinned: .downloadEagerlyAndKeepDownloaded
        }
    }
    public var capabilities: NSFileProviderItemCapabilities {
        value.directory ? [.allowsReading, .allowsContentEnumerating, .allowsRenaming,
                           .allowsReparenting, .allowsDeleting, .allowsAddingSubItems]
                        : [.allowsReading, .allowsWriting, .allowsRenaming,
                           .allowsReparenting, .allowsDeleting]
    }
    public var itemVersion: NSFileProviderItemVersion {
        .init(contentVersion: Data(value.contentVersion.utf8),
              metadataVersion: Data(value.metadataVersion.utf8))
    }
}

public final class ProviderEnumerator: NSObject, NSFileProviderEnumerator {
    private let bridge: any DriveBridge
    private let container: ItemID

    public init(bridge: any DriveBridge, container: ItemID) {
        self.bridge = bridge
        self.container = container
    }

    public func invalidate() {}

    public func enumerateItems(for observer: NSFileProviderEnumerationObserver,
                               startingAt page: NSFileProviderPage) {
        let initial = page.rawValue == (NSFileProviderPage.initialPageSortedByName as Data)
        let pageString = initial ? nil : String(decoding: page.rawValue, as: UTF8.self)
        Task {
            do {
                let result = try await bridge.children(of: container, page: pageString)
                observer.didEnumerate(result.items.map(ProviderItem.init))
                observer.finishEnumerating(upTo: result.nextPage.map {
                    NSFileProviderPage(rawValue: Data($0.utf8))
                })
            } catch {
                observer.finishEnumeratingWithError(error)
            }
        }
    }
}

/// The only native boundary. It translates File Provider callbacks to the
/// localhost bridge; scheduling, residency, conflicts and crypto stay in the
/// portable libraries and Cloud Itonami.
open class KotobaReplicatedExtension: NSObject, NSFileProviderReplicatedExtension {
    public typealias BridgeLoader = @Sendable (NSFileProviderDomain) throws -> any DriveBridge
    nonisolated(unsafe) public static var bridgeLoader: BridgeLoader = { domain in
        let defaults = UserDefaults(suiteName: "group.org.kotoba.drive")
        guard let base = defaults?.string(forKey: "bridgeBaseURL").flatMap(URL.init(string:)),
              let token = defaults?.string(forKey: "bridgeBearer") else {
            throw NSFileProviderError(.notAuthenticated)
        }
        return HTTPDriveBridge(baseURL: base, bearer: token)
    }

    private let bridge: any DriveBridge

    required public init(domain: NSFileProviderDomain) {
        do { bridge = try Self.bridgeLoader(domain) }
        catch { bridge = UnavailableBridge(error: error) }
        super.init()
    }

    open func invalidate() {}

    open func item(for identifier: NSFileProviderItemIdentifier,
                            request: NSFileProviderRequest,
                            completionHandler: @escaping (NSFileProviderItem?, Error?) -> Void) -> Progress {
        let progress = Progress(totalUnitCount: 1)
        Task {
            do {
                let item = try await bridge.item(.init(rawValue: identifier.rawValue))
                completionHandler(ProviderItem(item), nil)
            } catch { completionHandler(nil, error) }
            progress.completedUnitCount = 1
        }
        return progress
    }

    open func fetchContents(for itemIdentifier: NSFileProviderItemIdentifier,
                                     version requestedVersion: NSFileProviderItemVersion?,
                                     request: NSFileProviderRequest,
                                     completionHandler: @escaping (URL?, NSFileProviderItem?, Error?) -> Void) -> Progress {
        let progress = Progress(totalUnitCount: 1)
        let destination = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        Task {
            do {
                let item = try await bridge.materialize(.init(rawValue: itemIdentifier.rawValue), to: destination)
                completionHandler(destination, ProviderItem(item), nil)
            } catch { completionHandler(nil, nil, error) }
            progress.completedUnitCount = 1
        }
        return progress
    }

    open func createItem(basedOn itemTemplate: NSFileProviderItem,
                                  fields: NSFileProviderItemFields,
                                  contents: URL?,
                                  options: NSFileProviderCreateItemOptions,
                                  request: NSFileProviderRequest,
                                  completionHandler: @escaping (NSFileProviderItem?, NSFileProviderItemFields, Bool, Error?) -> Void) -> Progress {
        let progress = Progress(totalUnitCount: contents == nil ? 1 : 2)
        Task {
            do {
                var created = try await bridge.create(parentID: .init(rawValue: itemTemplate.parentItemIdentifier.rawValue),
                                                      name: itemTemplate.filename,
                                                      directory: itemTemplate.contentType == .folder)
                progress.completedUnitCount = 1
                if let contents { created = try await bridge.upload(created.id, from: contents) }
                completionHandler(ProviderItem(created), [], false, nil)
            } catch { completionHandler(nil, fields, false, error) }
            progress.completedUnitCount = progress.totalUnitCount
        }
        return progress
    }

    open func modifyItem(_ item: NSFileProviderItem,
                                  baseVersion version: NSFileProviderItemVersion,
                                  changedFields: NSFileProviderItemFields,
                                  contents newContents: URL?,
                                  options: NSFileProviderModifyItemOptions,
                                  request: NSFileProviderRequest,
                                  completionHandler: @escaping (NSFileProviderItem?, NSFileProviderItemFields, Bool, Error?) -> Void) -> Progress {
        let progress = Progress(totalUnitCount: newContents == nil ? 1 : 2)
        Task {
            do {
                var modified = try await bridge.modify(.init(rawValue: item.itemIdentifier.rawValue),
                                                       parentID: .init(rawValue: item.parentItemIdentifier.rawValue),
                                                       name: item.filename)
                progress.completedUnitCount = 1
                if let newContents { modified = try await bridge.upload(modified.id, from: newContents) }
                completionHandler(ProviderItem(modified), [], false, nil)
            } catch { completionHandler(nil, changedFields, false, error) }
            progress.completedUnitCount = progress.totalUnitCount
        }
        return progress
    }

    open func deleteItem(identifier: NSFileProviderItemIdentifier,
                                  baseVersion version: NSFileProviderItemVersion,
                                  options: NSFileProviderDeleteItemOptions,
                                  request: NSFileProviderRequest,
                                  completionHandler: @escaping (Error?) -> Void) -> Progress {
        let progress = Progress(totalUnitCount: 1)
        Task {
            do { try await bridge.delete(.init(rawValue: identifier.rawValue)); completionHandler(nil) }
            catch { completionHandler(error) }
            progress.completedUnitCount = 1
        }
        return progress
    }

    open func enumerator(for containerItemIdentifier: NSFileProviderItemIdentifier,
                                  request: NSFileProviderRequest) throws -> NSFileProviderEnumerator {
        ProviderEnumerator(bridge: bridge, container: .init(rawValue: containerItemIdentifier.rawValue))
    }
}

private struct UnavailableBridge: DriveBridge {
    let error: Error
    func item(_ id: ItemID) async throws -> DriveItem { throw error }
    func children(of id: ItemID, page: String?) async throws -> Page { throw error }
    func materialize(_ id: ItemID, to destination: URL) async throws -> DriveItem { throw error }
    func create(parentID: ItemID, name: String, directory: Bool) async throws -> DriveItem { throw error }
    func modify(_ id: ItemID, parentID: ItemID, name: String) async throws -> DriveItem { throw error }
    func upload(_ id: ItemID, from source: URL) async throws -> DriveItem { throw error }
    func delete(_ id: ItemID) async throws { throw error }
}
#endif
