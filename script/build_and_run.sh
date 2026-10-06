#!/bin/zsh
set -eu
cd "${0:A:h:h}"
PULSE_MODE="${1:-run}"
if (( $# )); then shift; fi
PULSE_ARGS=()
while (( $# )); do
  if [[ "$1" == '--fixture' || "$1" == '--snapshot' ]]; then
    PULSE_FLAG="$1"; shift
    (( $# )) || exit 2
    PULSE_VALUE="$1"; [[ "$PULSE_VALUE" == /* ]] || PULSE_VALUE="$PWD/$PULSE_VALUE"
    PULSE_ARGS+=("$PULSE_FLAG" "$PULSE_VALUE")
  else PULSE_ARGS+=("$1"); fi
  shift
done
PULSE_LAUNCH_ENV=()
if [[ -n "${AGENT_PULSE_PYTHON:-}" ]]; then PULSE_LAUNCH_ENV+=(--env "AGENT_PULSE_PYTHON=$AGENT_PULSE_PYTHON"); fi
PULSE_ROOT="$PWD/.build/local-run"
PULSE_BINARY="$PULSE_ROOT/Agent Pulse.app/Contents/MacOS/AgentPulse"
# Stop only this script's bundle, preserving installed app and other fixtures.
while read -r PULSE_PID PULSE_COMM; do
  if [[ "$PULSE_COMM" == "$PULSE_BINARY" ]]; then kill -TERM "$PULSE_PID" 2>/dev/null || true; fi
done < <(ps -axo pid=,comm=)
AGENT_PULSE_BUNDLE_ID=app.agentpulse.localrun ./build.sh "$PULSE_ROOT"
case "$PULSE_MODE" in
  run|--verify) open -n "${PULSE_LAUNCH_ENV[@]}" "$PULSE_ROOT/Agent Pulse.app" --args "${PULSE_ARGS[@]}" ;;
  --debug) lldb -- "$PULSE_BINARY" "${PULSE_ARGS[@]}" ;;
  --logs|--telemetry)
    open -n "${PULSE_LAUNCH_ENV[@]}" "$PULSE_ROOT/Agent Pulse.app" --args "${PULSE_ARGS[@]}"
    /usr/bin/log stream --info --style compact --predicate 'process == "AgentPulse"' ;;
  *) print -u2 'Usage: script/build_and_run.sh [run|--verify|--debug|--logs|--telemetry] [app arguments]'; exit 2 ;;
esac
if [[ "$PULSE_MODE" == '--verify' ]]; then
  sleep 1
  ps -axo comm= | /usr/bin/grep -F -x "$PULSE_BINARY" >/dev/null
fi
