// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "VoiceInbox",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "VoiceInbox", path: "Sources/VoiceInbox")
    ]
)
