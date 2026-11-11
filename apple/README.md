# SatHunter SDR for iOS and iPadOS

This directory contains the native SwiftUI front end and the Rust bridge shared with Android.

`project.yml` is the canonical XcodeGen project definition. After installing XcodeGen, run
`xcodegen generate --spec apple/project.yml --project apple` from the repository root, or use the
convenience script below.

## Build the Rust XCFramework

```sh
./apple/build-rust.sh
```

Generate the Xcode project:

```sh
./apple/generate-xcodeproj.sh
```

The script creates `apple/Frameworks/SatHunterCore.xcframework` for physical arm64 devices and
Apple Silicon simulators. Add that XCFramework to an iOS App target named `SatHunterApp`, then add
the Swift files from `apple/SatHunterApp` to the target.

The initial Apple build supports the simulated receiver. Direct RTL-SDR and ESP-SDR USB sources
are compiled out on iOS because `nusb` has no iOS backend. Network receivers will be added as the
portable hardware path; DriverKit remains a separate iPad-only investigation.
