// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "KotobaFileProvider",
    platforms: [.macOS(.v13)],
    products: [
        .library(name: "KotobaFileProvider", targets: ["KotobaFileProvider"])
    ],
    targets: [
        .target(name: "KotobaFileProvider"),
        .testTarget(name: "KotobaFileProviderTests", dependencies: ["KotobaFileProvider"])
    ],
    swiftLanguageModes: [.v5]
)
