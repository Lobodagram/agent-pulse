#!/bin/zsh
set -eu
cd "${0:A:h}"
mkdir -p .build 'dist/Agent Pulse.app/Contents/MacOS' 'dist/Agent Pulse.app/Contents/Resources'
xcrun swiftc -parse-as-library Sources/AgentPulse.swift -O -o 'dist/Agent Pulse.app/Contents/MacOS/AgentPulse' -framework AppKit -framework SwiftUI -framework Charts -target "$(uname -m)-apple-macosx14.0"
cp collector.py providers.py platform_support.py 'dist/Agent Pulse.app/Contents/Resources/'
if [[ -f .build/pulse-collector ]]; then cp .build/pulse-collector 'dist/Agent Pulse.app/Contents/Resources/'; fi
cat > 'dist/Agent Pulse.app/Contents/Info.plist' <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>AgentPulse</string>
<key>CFBundleIdentifier</key><string>app.agentpulse.desktop</string>
<key>CFBundleName</key><string>Agent Pulse</string>
<key>CFBundleDisplayName</key><string>Agent Pulse</string>
<key>CFBundleVersion</key><string>3</string>
<key>CFBundleShortVersionString</key><string>0.2.1</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>LSUIElement</key><true/>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
codesign --force --sign - 'dist/Agent Pulse.app'
