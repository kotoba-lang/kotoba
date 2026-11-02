#!/usr/bin/env python3
"""Observe native verifier-to-worker streaming for task-owned fixtures.

The observer forwards the bytes unchanged, checks child statuses, and reads the
worker's diagnostic result. It does not parse OCI or generate worker writes.
The worker and test guest are candidates; this is not a production supervisor.
"""
import argparse
import os
import select
import struct
import subprocess
from pathlib import Path

DIGEST = "sha256:abeeb5676fc9f826390bebd952b0a8336beda3230f1dab60b8cfde84f160aebf"


def run_case(guest, worker, root, good, digest=DIGEST, expected=None):
    env = {"PATH": "/nonexistent", "KEXE_ALLOW": "35,37,38,39", "KEXE_COMMAND": "1",
           "KEXE_FUEL": "100000000000", "KEXE_STACK_BYTES": "8388608",
           "KEXE_CAP_RESOURCES_35": str(root)}
    sink = subprocess.Popen([str(worker)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={"PATH": "/nonexistent"})
    source = None
    try:
        ready, _, _ = select.select([sink.stdout], [], [], 20)
        assert ready and sink.stdout.readline() == b"fune-private-root-ready\n"
        source = subprocess.Popen([str(guest), str(root), digest], stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        transferred = 0
        while True:
            part = source.stdout.read1(4096)
            if not part:
                break
            sink.stdin.write(part)
            sink.stdin.flush()
            transferred += len(part)
        source.stdout.close()
        diagnostics = source.stderr.read()
        source_code = source.wait(timeout=60)
        if not good:
            assert source_code != 0 and b"fune/blob-digest" in diagnostics, (source_code, diagnostics)
            sink.stdin.close()
            sink.stdin = None
            out, err = sink.communicate(timeout=20)
            assert sink.returncode == 2 and b"FREFUSE:" in err, (sink.returncode, out, err)
            return {"case": "tampered", "producerExit": source_code, "workerExit": sink.returncode,
                    "streamBytes": transferred}
        assert source_code == 0 and not diagnostics, (source_code, diagnostics)
        assert sink.stdout.read(3) == b"KKK", "directory, create and replacement acknowledgments"
        path = b"bin/hello"
        if expected is None:
            expected = bytes(range(256)) * 65 + b"end"
        command = b"R" + struct.pack(">HI", len(path), len(expected)) + path
        sink.stdin.write(command.hex().encode("ascii"))
        sink.stdin.flush()
        assert sink.stdout.read(1) == b"K"
        received = sink.stdout.read(len(expected))
        assert received == expected, "private root file differs from verified fixture"
        out, err = sink.communicate(b"58", timeout=20)
        assert sink.returncode == 0 and not out and not err, (sink.returncode, out, err)
        return {"case": "good", "producerExit": source_code, "workerExit": sink.returncode,
                "verifiedBytes": len(received), "streamBytes": transferred}
    finally:
        for p in (source, sink):
            if p is not None and p.poll() is None:
                p.kill()
                p.communicate(timeout=20)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--guest", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--layouts", type=Path, required=True)
    parser.add_argument("--large-digest", help="also check the independently staged 1 MiB fixture")
    args = parser.parse_args()
    print(run_case(args.guest.resolve(), args.worker.resolve(), (args.layouts / "plan-binary").resolve(), True))
    print(run_case(args.guest.resolve(), args.worker.resolve(), (args.layouts / "plan-binary-third-tampered").resolve(), False))
    if args.large_digest:
        print(run_case(args.guest.resolve(), args.worker.resolve(), (args.layouts / "plan-binary-max").resolve(),
                       True, digest=args.large_digest, expected=bytes(range(256)) * 4096))
    print("PASS_FUNE_NATIVE_STREAM_OBSERVATION")
