#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
fetch="$repo/os/aiueos/scripts/fetch-qwen38-model-bundle.sh"
work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-ranged-model.XXXXXX")
server_pid=
cleanup() {
  [ -z "$server_pid" ] || kill "$server_pid" 2>/dev/null || true
  rm -rf "$work"
}
trap cleanup EXIT HUP INT TERM
mkdir -p "$work/volume/EFI/AIUEOS"

python3 - "$work/model.bin" <<'PY'
from pathlib import Path
import sys
Path(sys.argv[1]).write_bytes(bytes((index * 29 + 7) % 256 for index in range(8193)))
PY
fixture_sha=$(shasum -a 256 "$work/model.bin" | awk '{print $1}')
head -c 137 "$work/model.bin" > "$work/volume/EFI/AIUEOS/Q38P0.BIN.partial"

python3 - "$work/model.bin" "$work/port" "$work/ranges.log" <<'PY' &
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

payload = Path(sys.argv[1]).read_bytes()
port_file, log_file = Path(sys.argv[2]), Path(sys.argv[3])

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        header = self.headers.get("Range", "")
        if not header.startswith("bytes=") or "," in header:
            self.send_response(416); self.end_headers(); return
        first, last = header[6:].split("-", 1)
        first, last = int(first), int(last)
        if first < 0 or last < first or last >= len(payload):
            self.send_response(416); self.end_headers(); return
        body = payload[first:last + 1]
        with log_file.open("a", encoding="ascii") as stream:
            stream.write(f"{first}-{last}\n")
        self.send_response(206)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Range", f"bytes {first}-{last}/{len(payload)}")
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *_):
        pass

server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
port_file.write_text(str(server.server_port), encoding="ascii")
server.serve_forever()
PY
server_pid=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do
  [ -s "$work/port" ] && break
  sleep 1
done
[ -s "$work/port" ] || { echo "error: range fixture server did not start" >&2; exit 1; }
port=$(cat "$work/port")

AIUEOS_MODEL_TEST_FIXTURE=1 \
AIUEOS_MODEL_ARTIFACT=model.bin \
AIUEOS_MODEL_TOTAL_BYTES=8193 \
AIUEOS_MODEL_SHA256="$fixture_sha" \
AIUEOS_MODEL_REVISION=test \
AIUEOS_MODEL_PART0_BYTES=3000 \
AIUEOS_MODEL_PART1_BYTES=3000 \
AIUEOS_MODEL_PART2_BYTES=2193 \
AIUEOS_MODEL_CHUNK_BYTES=997 \
AIUEOS_MODEL_URL="http://127.0.0.1:$port/model.bin" \
  "$fetch" "$work/volume" > "$work/fetch.log"

cat "$work/volume/EFI/AIUEOS/Q38P0.BIN" \
    "$work/volume/EFI/AIUEOS/Q38P1.BIN" \
    "$work/volume/EFI/AIUEOS/Q38P2.BIN" > "$work/reconstructed.bin"
cmp "$work/model.bin" "$work/reconstructed.bin"
grep -F "137-1133" "$work/ranges.log" >/dev/null
grep -F "AIUEOS_QWEN38_BUNDLE_OK" "$work/fetch.log" >/dev/null
python3 - "$work/volume/EFI/AIUEOS/model-bundle-v1.json" "$fixture_sha" <<'PY'
import json, sys
value = json.load(open(sys.argv[1]))
assert value["schema"] == "aiueos.qwen38-model-bundle.v1"
assert value["artifact"]["bytes"] == 8193
assert value["artifact"]["sha256"] == sys.argv[2]
assert len(value["parts"]) == 3
PY

echo "AIUEOS_QWEN38_RANGED_BUNDLE_OK resume=prefix ranges=exact fat32-parts=3 sha256=reconstructed"
