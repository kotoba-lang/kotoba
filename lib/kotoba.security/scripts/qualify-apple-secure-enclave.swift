#!/usr/bin/env swift
import Foundation
import Security

func emit(_ values: [String: String]) {
    let body = values.keys.sorted().map { key in
        let value = values[key]!
        return ":\(key) \(value)"
    }.joined(separator: " ")
    print("{\(body)}")
}

guard #available(macOS 10.12.2, *) else {
    emit(["apple/qualified?": "false", "apple/error": "\"secure-enclave-unavailable\""])
    exit(2)
}

var accessError: Unmanaged<CFError>?
guard let access = SecAccessControlCreateWithFlags(
    kCFAllocatorDefault,
    kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
    [.privateKeyUsage],
    &accessError
) else {
    emit(["apple/qualified?": "false", "apple/error": "\"access-control\""])
    exit(3)
}

let attributes: [String: Any] = [
    kSecAttrKeyType as String: kSecAttrKeyTypeECSECPrimeRandom,
    kSecAttrKeySizeInBits as String: 256,
    kSecAttrTokenID as String: kSecAttrTokenIDSecureEnclave,
    kSecPrivateKeyAttrs as String: [
        kSecAttrIsPermanent as String: false,
        kSecAttrAccessControl as String: access
    ]
]

var createError: Unmanaged<CFError>?
guard let privateKey = SecKeyCreateRandomKey(attributes as CFDictionary, &createError),
      let publicKey = SecKeyCopyPublicKey(privateKey) else {
    let message = createError?.takeRetainedValue().localizedDescription ?? "key-generation"
    emit(["apple/qualified?": "false", "apple/error": "\"\(message)\""])
    exit(4)
}

var exportError: Unmanaged<CFError>?
let exported = SecKeyCopyExternalRepresentation(privateKey, &exportError)
let nonExportable = exported == nil

let message = Data("kotoba-secure-enclave-qualification".utf8)
let algorithm = SecKeyAlgorithm.ecdsaSignatureMessageX962SHA256
var signError: Unmanaged<CFError>?
guard SecKeyIsAlgorithmSupported(privateKey, .sign, algorithm),
      let signature = SecKeyCreateSignature(privateKey, algorithm, message as CFData, &signError) else {
    emit(["apple/qualified?": "false",
          "apple/non-exportable?": nonExportable ? "true" : "false",
          "apple/error": "\"sign\""])
    exit(5)
}

var verifyError: Unmanaged<CFError>?
let verified = SecKeyVerifySignature(publicKey, algorithm, message as CFData,
                                     signature, &verifyError)
let qualified = nonExportable && verified
emit([
    "apple/provider-id": ":apple-secure-enclave",
    "apple/hardware-backed?": "true",
    "apple/non-exportable?": nonExportable ? "true" : "false",
    "apple/sign-verified?": verified ? "true" : "false",
    "apple/kem-verified?": "false",
    "apple/qualified?": qualified ? "true" : "false",
    "apple/non-claim": "\"Secure Enclave EC signing does not provide ML-KEM or general-purpose HSM qualification\""
])
exit(qualified ? 0 : 6)
