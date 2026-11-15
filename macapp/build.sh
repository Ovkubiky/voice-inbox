#!/bin/bash
# Builds macapp/build/VoiceInbox.app (menu-bar only, ad-hoc signed so macOS can ask for microphone access).
# Run: ./macapp/build.sh && open macapp/build/VoiceInbox.app
set -euo pipefail
cd "$(dirname "$0")"

swift build -c release
APP=build/VoiceInbox.app
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp .build/release/VoiceInbox "$APP/Contents/MacOS/VoiceInbox"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>VoiceInbox</string>
  <key>CFBundleDisplayName</key><string>Голосовий інбокс</string>
  <key>CFBundleIdentifier</key><string>ua.ucu.voiceinbox</string>
  <key>CFBundleExecutable</key><string>VoiceInbox</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>LSUIElement</key><true/>
  <key>NSMicrophoneUsageDescription</key><string>Записувати голосові нотатки для інбоксу.</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict>
</plist>
PLIST

codesign --force --sign - "$APP"
echo "Built $APP"
