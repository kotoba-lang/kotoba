import Foundation

public enum SyncSchedule: String, Codable, Sendable {
    case continuous, manual, paused
}

public enum Residency: String, Codable, Sendable {
    case onlineOnly = "online-only"
    case automatic, pinned
}

public struct ItemID: RawRepresentable, Codable, Hashable, Sendable {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }
}

public struct DriveItem: Codable, Equatable, Sendable {
    public let id: ItemID
    public let parentID: ItemID
    public let name: String
    public let directory: Bool
    public let size: Int64
    public let contentVersion: String
    public let metadataVersion: String
    public let schedule: SyncSchedule
    public let residency: Residency

    public init(id: ItemID, parentID: ItemID, name: String, directory: Bool,
                size: Int64, contentVersion: String, metadataVersion: String,
                schedule: SyncSchedule, residency: Residency) {
        self.id = id
        self.parentID = parentID
        self.name = name
        self.directory = directory
        self.size = size
        self.contentVersion = contentVersion
        self.metadataVersion = metadataVersion
        self.schedule = schedule
        self.residency = residency
    }
}

public struct Page: Codable, Equatable, Sendable {
    public let items: [DriveItem]
    public let nextPage: String?
    public init(items: [DriveItem], nextPage: String? = nil) {
        self.items = items
        self.nextPage = nextPage
    }
}

public protocol DriveBridge: Sendable {
    func item(_ id: ItemID) async throws -> DriveItem
    func children(of id: ItemID, page: String?) async throws -> Page
    func materialize(_ id: ItemID, to destination: URL) async throws -> DriveItem
    func create(parentID: ItemID, name: String, directory: Bool) async throws -> DriveItem
    func modify(_ id: ItemID, parentID: ItemID, name: String) async throws -> DriveItem
    func upload(_ id: ItemID, from source: URL) async throws -> DriveItem
    func delete(_ id: ItemID) async throws
}

public enum BridgeError: Error, Equatable {
    case invalidResponse
    case server(status: Int, message: String)
}

/// Localhost-only adapter. Authentication is a short-lived bearer injected by
/// the host app; the extension never discovers credentials or decides policy.
public struct HTTPDriveBridge: DriveBridge {
    public let baseURL: URL
    private let bearer: String
    private let session: URLSession

    public init(baseURL: URL, bearer: String, session: URLSession = .shared) {
        precondition(baseURL.host == "127.0.0.1" || baseURL.host == "localhost")
        self.baseURL = baseURL
        self.bearer = bearer
        self.session = session
    }

    private func request(_ path: String, method: String = "GET",
                         body: Data? = nil) async throws -> (Data, HTTPURLResponse) {
        var request = URLRequest(url: baseURL.appending(path: path))
        request.httpMethod = method
        request.httpBody = body
        request.setValue("Bearer \(bearer)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if body != nil { request.setValue("application/octet-stream", forHTTPHeaderField: "Content-Type") }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw BridgeError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else {
            throw BridgeError.server(status: http.statusCode,
                                     message: String(decoding: data, as: UTF8.self))
        }
        return (data, http)
    }

    public func item(_ id: ItemID) async throws -> DriveItem {
        let (data, _) = try await request("v1/file-provider/items/\(id.rawValue.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed)!)")
        return try JSONDecoder().decode(DriveItem.self, from: data)
    }

    public func children(of id: ItemID, page: String?) async throws -> Page {
        var path = "v1/file-provider/items/\(id.rawValue.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed)!)/children"
        if let page { path += "?page=\(page.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed)!)" }
        let (data, _) = try await request(path)
        return try JSONDecoder().decode(Page.self, from: data)
    }

    public func materialize(_ id: ItemID, to destination: URL) async throws -> DriveItem {
        let (data, response) = try await request("v1/file-provider/items/\(id.rawValue)/content")
        try data.write(to: destination, options: .atomic)
        guard let encoded = response.value(forHTTPHeaderField: "X-Kotoba-Item"),
              let metadata = Data(base64Encoded: encoded) else { throw BridgeError.invalidResponse }
        return try JSONDecoder().decode(DriveItem.self, from: metadata)
    }

    public func create(parentID: ItemID, name: String, directory: Bool) async throws -> DriveItem {
        let payload: [String: Any] = ["parentID": parentID.rawValue,
                                      "name": name,
                                      "directory": directory]
        let body = try JSONSerialization.data(withJSONObject: payload)
        let (data, _) = try await request("v1/file-provider/items", method: "POST", body: body)
        return try JSONDecoder().decode(DriveItem.self, from: data)
    }

    public func modify(_ id: ItemID, parentID: ItemID, name: String) async throws -> DriveItem {
        let payload: [String: Any] = ["parentID": parentID.rawValue, "name": name]
        let body = try JSONSerialization.data(withJSONObject: payload)
        let (data, _) = try await request("v1/file-provider/items/\(id.rawValue)",
                                          method: "PATCH", body: body)
        return try JSONDecoder().decode(DriveItem.self, from: data)
    }

    public func upload(_ id: ItemID, from source: URL) async throws -> DriveItem {
        let body = try Data(contentsOf: source, options: .mappedIfSafe)
        let (data, _) = try await request("v1/file-provider/items/\(id.rawValue)/content",
                                          method: "PUT", body: body)
        return try JSONDecoder().decode(DriveItem.self, from: data)
    }

    public func delete(_ id: ItemID) async throws {
        _ = try await request("v1/file-provider/items/\(id.rawValue)", method: "DELETE")
    }
}
