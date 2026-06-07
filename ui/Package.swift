// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Devbench",
    platforms: [
        .macOS(.v14)
    ],
    targets: [
        .executableTarget(
            name: "Devbench",
            dependencies: [],
            path: "Sources",
            resources: [
                .process("Resources")
            ]
        )
    ]
)