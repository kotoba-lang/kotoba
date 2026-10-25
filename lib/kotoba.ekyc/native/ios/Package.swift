// swift-tools-version: 5.9
// CoreNFC is a platform host only. Identity policy and verification stay in Kotoba.
import PackageDescription
let package = Package(
    name: "KotobaPassportReader",
    platforms: [.iOS(.v15)],
    products: [.library(name: "KotobaPassportReader", targets: ["KotobaPassportReader"])],
    dependencies: [.package(url: "https://github.com/AndyQ/NFCPassportReader.git", revision: "6e37f1ab249fef82771da46d32707f2b94ed090f")],
    targets: [.target(name: "KotobaPassportReader", dependencies: [.product(name: "NFCPassportReader", package: "NFCPassportReader")])]
)
