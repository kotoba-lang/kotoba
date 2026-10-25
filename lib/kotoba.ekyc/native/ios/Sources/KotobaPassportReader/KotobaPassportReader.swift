import Foundation
import NFCPassportReader

/// Capture transport only. Neither a successful chip read nor local library
/// authentication flags constitute a Kotoba identity approval.
@MainActor
public final class KotobaPassportReader {
    public struct Challenge: Sendable {
        public let applicationID: String
        public let nonce: String
        public let audience: String
        public let expiresAt: Date
        public init(applicationID: String, nonce: String, audience: String, expiresAt: Date) {
            self.applicationID = applicationID
            self.nonce = nonce
            self.audience = audience
            self.expiresAt = expiresAt
        }
    }
    public struct Evidence: Sendable {
        public let applicationID: String
        public let nonce: String
        public let sod: Data
        public let dg1: Data
        public let dg2: Data
    }
    public enum CaptureError: Error {
        case invalidMRZKey, invalidChallenge, expiredChallenge, captureInProgress, missingData, dataTooLarge
    }
    private var capturing = false
    public init() {}

    /// mrzKey is derived locally. This host writes no files, logs, network
    /// requests or verification state; raw evidence is returned in memory.
    public func read(mrzKey: String, challenge: Challenge) async throws -> Evidence {
        guard mrzKey.utf8.count == 24,
              mrzKey.utf8.allSatisfy({ $0 == 60 || (48...57).contains($0) || (65...90).contains($0) }) else {
            throw CaptureError.invalidMRZKey
        }
        guard !capturing else { throw CaptureError.captureInProgress }
        guard challenge.audience == "https://kotoba.cloud",
              !challenge.applicationID.isEmpty, challenge.applicationID.count <= 128,
              (32...256).contains(challenge.nonce.count) else {
            throw CaptureError.invalidChallenge
        }
        guard challenge.expiresAt > Date(), challenge.expiresAt.timeIntervalSinceNow <= 900 else {
            throw CaptureError.expiredChallenge
        }
        capturing = true
        defer { capturing = false }
        let reader = PassportReader()
        let passport = try await reader.readPassport(
            mrzKey: mrzKey, tags: [.SOD, .DG1, .DG2], skipSecureElements: true,
            skipCA: false, skipPACE: false
        )
        guard challenge.expiresAt > Date() else { throw CaptureError.expiredChallenge }
        guard let sod = passport.dataGroupsRead[.SOD]?.data,
              let dg1 = passport.dataGroupsRead[.DG1]?.data,
              let dg2 = passport.dataGroupsRead[.DG2]?.data,
              !sod.isEmpty, !dg1.isEmpty, !dg2.isEmpty else { throw CaptureError.missingData }
        guard sod.count <= 131_072, dg1.count <= 256, dg2.count <= 2_097_152 else {
            throw CaptureError.dataTooLarge
        }
        return Evidence(applicationID: challenge.applicationID, nonce: challenge.nonce,
                        sod: Data(sod), dg1: Data(dg1), dg2: Data(dg2))
    }
}
