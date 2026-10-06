#!/bin/zsh
set -eu
cd "${0:A:h}"
PULSE_OUTPUT="${1:-dist}"
mkdir -p .build "$PULSE_OUTPUT/Agent Pulse.app/Contents/MacOS" "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources"
xcrun swiftc -parse-as-library Sources/AgentPulse.swift -O -o "$PULSE_OUTPUT/Agent Pulse.app/Contents/MacOS/AgentPulse" -framework AppKit -framework SwiftUI -framework Charts -target "$(uname -m)-apple-macosx14.0"
cp collector.py providers.py platform_support.py journal.py analytics.py journal_cli.py instrumentation.py mcp_server.py "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources/"
mkdir -p "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources/scripts"
cp scripts/hook_bridge.py "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources/scripts/"
if [[ -f .build/pulse-collector ]]; then
  cp .build/pulse-collector "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources/"
else
  rm -f "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources/pulse-collector"
fi
cat > "$PULSE_OUTPUT/Agent Pulse.app/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>AgentPulse</string>
<key>CFBundleIdentifier</key><string>app.agentpulse.desktop</string>
<key>CFBundleName</key><string>Agent Pulse</string>
<key>CFBundleDisplayName</key><string>Agent Pulse</string>
<key>CFBundleVersion</key><string>6</string>
<key>CFBundleShortVersionString</key><string>0.3.1</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>LSUIElement</key><true/>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
if [[ -n "${AGENT_PULSE_BUNDLE_ID:-}" ]]; then
  /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier $AGENT_PULSE_BUNDLE_ID" "$PULSE_OUTPUT/Agent Pulse.app/Contents/Info.plist"
fi
codesign --force --sign - "$PULSE_OUTPUT/Agent Pulse.app"
