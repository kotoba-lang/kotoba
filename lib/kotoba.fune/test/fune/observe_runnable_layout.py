#!/usr/bin/env python3
"""Observe native runnable-stream and private worker, without an OCI parser."""
import argparse
import os
import select
import struct
import subprocess
from pathlib import Path


def run(guest, worker, layout, digest, reason=None, preflight=False):
    env = {"PATH": "/nonexistent", "KEXE_ALLOW": "35,37,38,39", "KEXE_COMMAND": "1",
           "KEXE_FUEL": "100000000000", "KEXE_STACK_BYTES": "8388608", "KEXE_CAP_RESOURCES_35": str(layout)}
    w = subprocess.Popen([str(worker)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         env={"PATH": "/nonexistent"})
    try:
        ready, _, _ = select.select([w.stdout], [], [], 20)
        assert ready and w.stdout.readline() == b"fune-private-root-ready\n"
        g = subprocess.run([str(guest), str(layout), digest], env=env, stdin=subprocess.DEVNULL,
                           capture_output=True, timeout=60)
        if reason is not None:
            assert g.returncode != 0 and reason.encode() in g.stderr, (g.returncode, g.stderr)
            if preflight:
                assert not g.stdout
            if g.stdout:
                w.stdin.write(g.stdout)
                w.stdin.flush()
            w.stdin.close()
            w.stdin = None
            out, err = w.communicate(timeout=20)
            assert w.returncode == 2 and b"D" not in out and b"FREFUSE:" in err, (w.returncode, out, err)
            return {"case": layout.name, "guestExit": g.returncode, "workerExit": w.returncode,
                    "bytesBeforeFailure": len(g.stdout)}
        assert g.returncode == 0 and not g.stderr, (g.returncode, g.stderr)
        w.stdin.write(g.stdout)
        w.stdin.flush()
        assert w.stdout.read(5) == b"KKKKD"
        path = b"bin/run"
        request = b"V" + struct.pack(">HI", len(path), 0) + path
        w.stdin.write(request.hex().encode())
        w.stdin.flush()
        assert w.stdout.read(3) == b"K\x01\xed"  # 0755
        out, err = w.communicate(b"58", timeout=20)
        assert w.returncode == 0 and not out and not err
        return {"case": layout.name, "guestExit": 0, "workerExit": 0, "mode": "0755"}
    finally:
        if w.poll() is None:
            w.kill()
            w.communicate(timeout=20)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--guest", type=Path, required=True)
    p.add_argument("--worker", type=Path, required=True)
    p.add_argument("--layouts", type=Path, required=True)
    p.add_argument("--digests", type=Path, required=True)
    a = p.parse_args()
    import json
    digests = json.loads(a.digests.read_text())
    for name, reason, preflight in (("good", None, False), ("noexec", "fune/process-executable-mode", False),
                                    ("missing", "fune/process-executable-missing", False),
                                    ("badcwd", "fune/process-working-dir-missing", False),
                                    ("replaced", "fune/process-executable-mode", False),
                                    ("corrupt", "fune/blob-digest", True)):
        print(run(a.guest.resolve(), a.worker.resolve(), (a.layouts / name).resolve(), digests[name], reason, preflight))
    print("PASS_FUNE_RUNNABLE_STREAM_OBSERVATION")
