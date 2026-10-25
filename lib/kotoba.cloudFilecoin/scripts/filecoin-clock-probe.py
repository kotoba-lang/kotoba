#!/usr/bin/env python3
"""filecoin-clock-probe -- one endpoint-health-shaped probe for the
filecoin.cloud guest clock.

Fetch a REAL calibration block header over read-only RPC, run the native
guest (kototama executor, signed artifact, measured runtime) against the
chain's own claimed height, and report drift + verdict.

Verdict vocabulary matches verify-endpoint-health:
  ok | answered-badly | unanswered   (+ skipped when the amu/runtime
  measurement is missing on this machine -- a machine without the setup is
  NOT a red probe)

Read-only: no keys, no signing, no spend. RPC calls: 1 (eth_getBlockByNumber).

Prereqs (all under /tmp; vanish on reboot -> probe reports skipped):
  /tmp/fc-runtime.edn + /tmp/fc-loader   from: amu measure-runtime
  /tmp/fc-cp.txt                         from: kbb -Spath -M:native-run (amu)
  /tmp/fc_live_probe.clj                 copied from host/ by this script

Exit: 0 ok/skipped, 1 answered-badly/unanswered (cron failure signal).
"""

import json
import re
import subprocess
import sys
import urllib.request

HOME = "/Users/junkawasaki"
AMU_DIR = HOME + "/github/com-junkawasaki/orgs/kotoba-lang/amu"
GUEST_REPO = HOME + "/github/com-junkawasaki/orgs/kotoba-lang/cloud-filecoin"
RPC_URL = "https://api.calibration.node.glif.io/rpc/v1"
GENESIS_CALIBRATION = 1667326380
EPOCH_SECONDS = 30
BASE = 1000000000000


def sh(cmd):
    return subprocess.run(
        ["bash", "-c", cmd], capture_output=True, text=True, timeout=180
    )


def fetch_block():
    req = urllib.request.Request(
        RPC_URL,
        data=json.dumps({
            "jsonrpc": "2.0", "id": 1,
            "method": "eth_getBlockByNumber",
            "params": ["latest", False],
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        block = json.load(resp)["result"]
    return int(block["number"], 16), int(block["timestamp"], 16)


def prereqs_ok():
    import os
    return all(os.path.exists(p) for p in (
        "/tmp/fc-runtime.edn", "/tmp/fc-loader", "/tmp/fc-cp.txt"))


def guest_verdict(claimed_height, block_ts):
    cp = subprocess.run(
        ["cp", "/tmp/fc-probe/host/live_probe.cljk", "/tmp/fc_live_probe.clj"],
        capture_output=True, text=True)
    if cp.returncode != 0:
        raise RuntimeError("cannot copy guest driver: " + cp.stderr)
    r = sh(
        "cd '%s' && java -cp \"/tmp:$(cat /tmp/fc-cp.txt)\" clojure.main -e "
        "\"(require 'fc-live-probe) (fc-live-probe/-main \\\"%d\\\" \\\"%d\\\")\""
        % (AMU_DIR, claimed_height, block_ts)
    )
    out = r.stdout
    m_status = re.search(r":status :([a-z-]+)", out)
    m_word = re.search(r":verdict-word (\d+)", out)
    if not m_status or not m_word:
        raise RuntimeError("guest output unreadable: " + (r.stderr or out)[-300:])
    word = int(m_word.group(1))
    abs_delta = (word - BASE) // 1048576
    drift_ok = (word - BASE) % 1048576
    return m_status.group(1), abs_delta, drift_ok


def main():
    if not prereqs_ok():
        print("probe-id: filecoin/calibration-clock")
        print("note: runtime measurement or loader missing; "
              "run amu measure-runtime first")
        print("verdict: skipped")
        return 0
    try:
        height, ts = fetch_block()
    except Exception as e:  # noqa: BLE001 -- probe must report, not crash
        print("probe-id: filecoin/calibration-clock")
        print("error: fetch failed: %s" % e)
        print("verdict: unanswered")
        return 1

    drift = ts - (GENESIS_CALIBRATION + height * EPOCH_SECONDS)
    try:
        status, abs_delta, drift_ok = guest_verdict(height, ts)
    except Exception as e:  # noqa: BLE001
        print("probe-id: filecoin/calibration-clock")
        print("height: %d" % height)
        print("error: guest run failed: %s" % e)
        print("verdict: unanswered")
        return 1

    verdict = "answered-badly"
    if status == "ok" and drift_ok == 1 and abs_delta <= 2 and -300 <= drift <= 300:
        verdict = "ok"

    print("probe-id: filecoin/calibration-clock")
    print("height: %d" % height)
    print("block-timestamp: %d" % ts)
    print("drift-seconds: %d" % drift)
    print("guest-abs-delta: %d" % abs_delta)
    print("verdict: %s" % verdict)
    return 0 if verdict == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
