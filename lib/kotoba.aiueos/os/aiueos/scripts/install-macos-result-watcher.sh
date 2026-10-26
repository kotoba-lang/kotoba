#!/bin/sh
set -eu

[ "$(uname -s)" = Darwin ] || {
  echo "error: the result watcher is for macOS" >&2
  exit 2
}

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
support="$HOME/Library/Application Support/AIUEOS"
logs="$HOME/Library/Logs/AIUEOS"
agents="$HOME/Library/LaunchAgents"
label=cloud.murakumo.aiueos-k16-result
plist="$agents/$label.plist"

mkdir -p "$support" "$logs" "$agents"
cp "$script_dir/check-physical-qualification-result.sh" "$support/check-result.sh"
chmod 755 "$support/check-result.sh"

runner="$support/watch-result.sh"
cat > "$runner" <<EOF
#!/bin/sh
set -u
checker='$support/check-result.sh'
logs='$logs'
tmp="\$logs/.latest-result.\$\$.tmp"
if "\$checker" >"\$tmp" 2>&1; then
  mv -f "\$tmp" "\$logs/latest-result.txt"
  date -u '+%Y-%m-%dT%H:%M:%SZ' >"\$logs/latest-result-time.txt"
  exit 0
else
  check_rc=\$?
  if [ "\$check_rc" -ne 2 ]; then
    mv -f "\$tmp" "\$logs/latest-result.txt"
    date -u '+%Y-%m-%dT%H:%M:%SZ' >"\$logs/latest-result-time.txt"
  else
    rm -f "\$tmp"
  fi
fi
exit 0
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
  <key>WatchPaths</key>
  <array><string>/Volumes</string></array>
  <key>ThrottleInterval</key><integer>2</integer>
  <key>StandardOutPath</key><string>$logs/watcher.stdout.log</string>
  <key>StandardErrorPath</key><string>$logs/watcher.stderr.log</string>
</dict>
</plist>
EOF
plutil -lint "$plist" >/dev/null

if [ "${AIUEOS_WATCHER_INSTALL_DRY_RUN:-0}" = 1 ]; then
  printf 'AIUEOS_MACOS_RESULT_WATCHER_DRY_RUN_OK plist=%s\n' "$plist"
  exit 0
fi

domain="gui/$(id -u)"
launchctl bootout "$domain" "$plist" >/dev/null 2>&1 || true
launchctl bootstrap "$domain" "$plist"
launchctl kickstart -k "$domain/$label"
printf 'AIUEOS_MACOS_RESULT_WATCHER_OK result=%s\n' "$logs/latest-result.txt"
