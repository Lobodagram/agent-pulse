#!/bin/zsh
set -eu
cd "${0:A:h}"
PULSE_OUTPUT="${1:-dist}"
PULSE_VERSION="$(python3 -c 'from pulse_version import __version__; print(__version__)')"
mkdir -p .build "$PULSE_OUTPUT/Agent Pulse.app/Contents/MacOS" "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources"
xcrun swiftc -parse-as-library Sources/AgentPulse.swift Sources/LaunchAtLogin.swift Sources/PulseBrand.swift -O -o "$PULSE_OUTPUT/Agent Pulse.app/Contents/MacOS/AgentPulse" -framework AppKit -framework SwiftUI -framework ServiceManagement -target "$(uname -m)-apple-macosx14.0"
cp brand/AgentPulse.icns brand/logo-128.png "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources/"
cp check_receipts.py collection_health.py efficiency.py agent_control.py provider_secrets.py glm_quota.py sanitizers.py pulse_version.py hook_bridge.py capability_detection.py finding_review.py review_pack.py session_view.py model_evidence.py command_profile.py result_metadata.py capability_report.py evidence_pack.py compact_summary.py collector.py providers.py platform_support.py journal.py analytics.py journal_cli.py instrumentation.py mcp_server.py "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources/"
mkdir -p "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources/scripts"
cp scripts/hook_bridge.py "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources/scripts/"
rm -rf "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources/pulse-runtime"
PULSE_COLLECTOR="${AGENT_PULSE_COLLECTOR_DIR:-.build/pulse-collector}"
if [[ -d "$PULSE_COLLECTOR" ]]; then
  cp -R "$PULSE_COLLECTOR"/. "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources/"
elif [[ -f "$PULSE_COLLECTOR" ]]; then
  cp "$PULSE_COLLECTOR" "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources/"
else
  rm -f "$PULSE_OUTPUT/Agent Pulse.app/Contents/Resources/pulse-collector"
fi
cat > "$PULSE_OUTPUT/Agent Pulse.app/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>AgentPulse</string>
<key>CFBundleIdentifier</key><string>app.agentpulse.desktop</string>
<key>CFBundleName</key><string>Agent Pulse</string>
<key>CFBundleDisplayName</key><string>Agent Pulse</string>
<key>CFBundleVersion</key><string>37</string>
<key>CFBundleIconFile</key><string>AgentPulse.icns</string>
<key>CFBundleShortVersionString</key><string>${PULSE_VERSION}</string>
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
