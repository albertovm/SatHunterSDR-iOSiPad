#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
CORE="$ROOT/core"
OUT="$ROOT/apple/Frameworks"
CARGO="${CARGO:-$HOME/.cargo/bin/cargo}"

cd "$CORE"
export IPHONEOS_DEPLOYMENT_TARGET="${IPHONEOS_DEPLOYMENT_TARGET:-18.0}"
"$CARGO" build --release -p sh-apple --target aarch64-apple-ios
"$CARGO" build --release -p sh-apple --target aarch64-apple-ios-sim

mkdir -p "$OUT"
rm -rf "$OUT/SatHunterCore.xcframework"
xcodebuild -create-xcframework \
  -library "$CORE/target/aarch64-apple-ios/release/libsathunter_apple.a" \
  -headers "$CORE/crates/sh-apple/include" \
  -library "$CORE/target/aarch64-apple-ios-sim/release/libsathunter_apple.a" \
  -headers "$CORE/crates/sh-apple/include" \
  -output "$OUT/SatHunterCore.xcframework"

echo "Created $OUT/SatHunterCore.xcframework"
