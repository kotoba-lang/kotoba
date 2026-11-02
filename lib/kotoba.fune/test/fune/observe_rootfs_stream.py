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


def check_final_frames(wire):
    assert wire[:1] == b"H"
    data = bytes.fromhex(wire[1:].decode("ascii"))
    off = 0
    operations = []
    while off < len(data):
        op = data[off:off + 1]
        off += 1
        if op == b"C":
            assert data[off:] == b"\x00\x05" and len(operations) == 5
            assert operations[-2:] == [(b"P", b"bin/hello", 0o644), (b"P", b"bin", 0o755)]
            return
        n, size = struct.unpack_from(">HI", data, off)
        off += 6
        path = data[off:off + n]
        off += n
        if op in (b"F", b"U"):
            off += size
        operations.append((op, path, size))
    raise AssertionError("missing terminal frame")


def run_case(guest, worker, root, good, digest=DIGEST, expected=None,
             expected_error=b"fune/blob-digest", preflight=False, finalize=False, mode_check=False):
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
        wire = bytearray()
        while True:
            part = source.stdout.read1(4096)
            if not part:
                break
            sink.stdin.write(part)
            sink.stdin.flush()
            transferred += len(part)
            if finalize:
                wire.extend(part)
        source.stdout.close()
        diagnostics = source.stderr.read()
        source_code = source.wait(timeout=60)
        if not good:
            assert source_code != 0 and expected_error in diagnostics, (source_code, diagnostics)
            sink.stdin.close()
            sink.stdin = None
            out, err = sink.communicate(timeout=20)
            assert sink.returncode == 2 and b"FREFUSE:" in err, (sink.returncode, out, err)
            if preflight:
                assert transferred == 0 and not out, (transferred, out)
            return {"case": root.name, "producerExit": source_code, "workerExit": sink.returncode,
                    "streamBytes": transferred}
        assert source_code == 0 and not diagnostics, (source_code, diagnostics)
        if finalize:
            check_final_frames(wire)
        acknowledgments = 5 if finalize else 3
        assert sink.stdout.read(acknowledgments + 1) == b"K" * acknowledgments + b"D", "worker acknowledgments and checked terminal count"
        path = b"bin/hello"
        if expected is None:
            expected = bytes(range(256)) * 65 + b"end"
        command = (b"V" if mode_check else b"R") + struct.pack(">HI", len(path), 0 if mode_check else len(expected)) + path
        sink.stdin.write(command.hex().encode("ascii"))
        sink.stdin.flush()
        assert sink.stdout.read(1) == b"K"
        received = sink.stdout.read(2 if mode_check else len(expected))
        assert received == (struct.pack(">H", 0o644) if mode_check else expected), "private root file or mode differs from verified fixture"
        out, err = sink.communicate(b"58", timeout=20)
        assert sink.returncode == 0 and not out and not err, (sink.returncode, out, err)
        return {"case": "good-mode" if mode_check else "good", "producerExit": source_code,
                "workerExit": sink.returncode, "verifiedMode": oct(0o644) if mode_check else None,
                "verifiedBytes": 0 if mode_check else len(received), "streamBytes": transferred}
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
    parser.add_argument("--full-layout", action="store_true", help="check layout metadata before any stream")
    parser.add_argument("--bad-arch-digest", help="manifest digest of the unsupported architecture fixture")
    parser.add_argument("--repeat-dir-digest", help="also check a repeated-directory fixture")
    parser.add_argument("--finalize", action="store_true", help="expect final mode commands and check actual file mode")
    args = parser.parse_args()
    print(run_case(args.guest.resolve(), args.worker.resolve(), (args.layouts / "plan-binary").resolve(), True, finalize=args.finalize))
    if args.finalize:
        print(run_case(args.guest.resolve(), args.worker.resolve(), (args.layouts / "plan-binary").resolve(), True, finalize=True, mode_check=True))
    print(run_case(args.guest.resolve(), args.worker.resolve(), (args.layouts / "plan-binary-third-tampered").resolve(), False,
                   preflight=args.full_layout))
    if args.full_layout:
        for name, reason in (("plan-binary-bad-marker", b"fune/layout-marker"),
                             ("plan-binary-bad-index", b"fune/layout-index"),
                             ("plan-binary-bad-config", b"fune/blob-digest")):
            print(run_case(args.guest.resolve(), args.worker.resolve(), (args.layouts / name).resolve(), False,
                           expected_error=reason, preflight=True))
        assert args.bad_arch_digest
        print(run_case(args.guest.resolve(), args.worker.resolve(), (args.layouts / "plan-binary-bad-arch").resolve(), False,
                       digest=args.bad_arch_digest, expected_error=b"fune/config-platform", preflight=True))
    if args.large_digest:
        print(run_case(args.guest.resolve(), args.worker.resolve(), (args.layouts / "plan-binary-max").resolve(),
                       True, digest=args.large_digest, expected=bytes(range(256)) * 4096, finalize=args.finalize))
    if args.repeat_dir_digest:
        print(run_case(args.guest.resolve(), args.worker.resolve(), (args.layouts / "plan-binary-repeat-dir").resolve(),
                       True, digest=args.repeat_dir_digest, finalize=args.finalize))
    print("PASS_FUNE_NATIVE_STREAM_OBSERVATION")
