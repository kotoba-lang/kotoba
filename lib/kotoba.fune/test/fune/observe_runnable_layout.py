#!/usr/bin/env python3
"""Observe native runnable-stream and private worker, without an OCI parser."""
import argparse
import os
import select
import struct
import subprocess
from pathlib import Path


def run(guest, worker, layout, digest, reason=None, preflight=False, expected_spec=None):
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
        if expected_spec is not None:
            w.stdin.write(b"51")  # Q in hex transport
            w.stdin.flush()
            assert w.stdout.read(5) == b"K" + struct.pack(">I", len(expected_spec))
            assert w.stdout.read(len(expected_spec)) == expected_spec
        else:
            path = b"bin/run"
            request = b"V" + struct.pack(">HI", len(path), 0) + path
            w.stdin.write(request.hex().encode())
            w.stdin.flush()
            assert w.stdout.read(3) == b"K\x01\xed"  # 0755
        out, err = w.communicate(b"58", timeout=20)
        assert w.returncode == 0 and not out and not err
        return {"case": layout.name, "guestExit": 0, "workerExit": 0,
                "mode": "0755" if expected_spec is None else None,
                "specBytes": len(expected_spec) if expected_spec is not None else 0}
    finally:
        if w.poll() is None:
            w.kill()
            w.communicate(timeout=20)


def bad_spec(guest, worker, layout, digest):
    env = {"PATH": "/nonexistent", "KEXE_ALLOW": "35,37,38,39", "KEXE_COMMAND": "1",
           "KEXE_FUEL": "100000000000", "KEXE_STACK_BYTES": "8388608", "KEXE_CAP_RESOURCES_35": str(layout)}
    g = subprocess.run([str(guest), str(layout), digest], env=env, stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=60)
    assert g.returncode == 0 and not g.stderr
    w = subprocess.Popen([str(worker)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         env={"PATH": "/nonexistent"})
    try:
        ready, _, _ = select.select([w.stdout], [], [], 20)
        assert ready and w.stdout.readline() == b"fune-private-root-ready\n"
        out, err = w.communicate(g.stdout, timeout=20)
        assert w.returncode == 2 and b"D" not in out and b"FREFUSE:20" in err, (w.returncode, out, err)
        print({"case": "bad-process-spec", "guestExit": 0, "workerExit": w.returncode})
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
    p.add_argument("--bad-spec-guest", type=Path, help="test-only producer emitting an invalid FPS magic")
    a = p.parse_args()
    import json
    digests = json.loads(a.digests.read_text())
    for name, reason, preflight in (("good", None, False), ("noexec", "fune/process-executable-mode", False),
                                    ("missing", "fune/process-executable-missing", False),
                                    ("badcwd", "fune/process-working-dir-missing", False),
                                    ("replaced", "fune/process-executable-mode", False),
                                    ("corrupt", "fune/blob-digest", True)):
        print(run(a.guest.resolve(), a.worker.resolve(), (a.layouts / name).resolve(), digests[name], reason, preflight))
    if "args" in digests:
        values = [b"/bin/run", b"--x", b"", b"y", b"A=1", "Z=雪".encode()]
        expected = b"FPS\x01" + struct.pack(">HHH", 4, 2, 4) + b"/bin"
        for value in values:
            expected += struct.pack(">I", len(value)) + value
        print(run(a.guest.resolve(), a.worker.resolve(), (a.layouts / "args").resolve(), digests["args"],
                  expected_spec=expected))
    if "args-big" in digests:
        values = [b"/bin/run", b"x" * 9000]
        expected = b"FPS\x01" + struct.pack(">HHH", 2, 0, 1) + b"/"
        for value in values:
            expected += struct.pack(">I", len(value)) + value
        print(run(a.guest.resolve(), a.worker.resolve(), (a.layouts / "args-big").resolve(), digests["args-big"],
                  expected_spec=expected))
    if a.bad_spec_guest:
        bad_spec(a.bad_spec_guest.resolve(), a.worker.resolve(), (a.layouts / "good").resolve(), digests["good"])
    print("PASS_FUNE_RUNNABLE_STREAM_OBSERVATION")
