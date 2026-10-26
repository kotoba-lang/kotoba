#!/bin/sh
set -eu

[ "$(uname -s)" = Darwin ] || {
  echo "error: the K16 PXE relay installer is for macOS" >&2
  exit 2
}

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
state_home=${AIUEOS_STATE_HOME:-"$HOME/.gftd"}
source_boot=${AIUEOS_PXE_BOOT:-"$repo/build/aiueos-physical-job-pxe/aiueos-k16-native-pxe.efi"}
receipt=${AIUEOS_PXE_RECEIPT:-"${source_boot%.efi}-receipt.json"}
support="$HOME/Library/Application Support/AIUEOS/K16 PXE"
logs="$HOME/Library/Logs/AIUEOS"
agents="$HOME/Library/LaunchAgents"
label=cloud.murakumo.aiueos-k16-pxe
plist="$agents/$label.plist"
did_file="$state_home/aiueos-k16-node-did"
token_file="$state_home/aiueos-k16-murakumo-service-token"

[ -r "$source_boot" ] && [ -r "$receipt" ] || {
  echo "error: missing clean K16 PXE image or receipt" >&2
  exit 2
}
[ -r "$did_file" ] && [ -r "$token_file" ] || {
  echo "error: missing owner-only K16 DID or service-token file" >&2
  exit 2
}

python3 - "$source_boot" "$receipt" <<'PY'
import hashlib, json, pathlib, sys
boot, receipt_path = map(pathlib.Path, sys.argv[1:])
receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
digest = hashlib.sha256(boot.read_bytes()).hexdigest()
if receipt.get("source", {}).get("dirty") is not False:
    raise SystemExit("error: refusing a dirty qualification image")
if receipt.get("artifact", {}).get("sha256") != digest:
    raise SystemExit("error: qualification receipt does not match the EFI image")
PY

AIUEOS_PXE_BOOT="$source_boot" \
AIUEOS_MURAKUMO_NODE_DID_FILE="$did_file" \
AIUEOS_MURAKUMO_SERVICE_TOKEN_FILE="$token_file" \
AIUEOS_MURAKUMO_JOB_QUALIFICATION=1 \
  python3 "$repo/os/aiueos/tools/k16-pxe-server.py" --preflight >/dev/null

mkdir -p "$support" "$logs" "$agents"
install -m 755 "$repo/os/aiueos/tools/k16-pxe-server.py" "$support/k16-pxe-server.py"
install -m 644 "$source_boot" "$support/bootx64.efi"
install -m 644 "$receipt" "$support/bootx64-receipt.json"

runner="$support/run-k16-pxe.sh"
cat > "$runner" <<EOF
#!/bin/sh
set -eu
AIUEOS_PXE_BOOT='$support/bootx64.efi' \\
AIUEOS_MURAKUMO_NODE_DID_FILE='$did_file' \\
AIUEOS_MURAKUMO_SERVICE_TOKEN_FILE='$token_file' \\
AIUEOS_MURAKUMO_JOB_QUALIFICATION=1 \\
  exec /usr/bin/python3 '$support/k16-pxe-server.py' "\$@"
EOF
chmod 755 "$runner"

cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array><string>$runner</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>5</integer>
  <key>StandardOutPath</key><string>$logs/k16-pxe.stdout.log</string>
  <key>StandardErrorPath</key><string>$logs/k16-pxe.stderr.log</string>
</dict>
</plist>
EOF
chmod 600 "$plist"
plutil -lint "$plist" >/dev/null

if [ "${AIUEOS_PXE_INSTALL_NO_LOAD:-0}" = 1 ]; then
  printf 'AIUEOS_MACOS_K16_PXE_PREPARED plist=%s boot=%s\n' "$plist" "$support/bootx64.efi"
  exit 0
fi

domain="gui/$(id -u)"
launchctl bootout "$domain" "$plist" >/dev/null 2>&1 || true
launchctl bootstrap "$domain" "$plist"
launchctl kickstart -k "$domain/$label"
printf 'AIUEOS_MACOS_K16_PXE_OK label=%s log=%s\n' "$label" "$logs/k16-pxe.stdout.log"
