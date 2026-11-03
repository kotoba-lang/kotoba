#!/usr/bin/env python3
"""Observe two Linux FS2 boundaries for a native layout snapshot fixture.

Only the observer's child is traced. The race case changes a disposable marker
after the real F fstat and before the child resumes. The oversize case records
whether the child issues read/pread on a disposable oversized index. Native
Kotoba still produces the validation result; this script observes kernel calls.
"""
import argparse
import ctypes
import json
import os
import platform
import signal
import time
from pathlib import Path


def main(image, layout, digest, output, case):
    machine = platform.machine()
    assert platform.system() == "Linux" and machine in ("aarch64", "arm64", "x86_64")
    arm = machine in ("aarch64", "arm64")
    reg_count, number, result, args = (34, 8, 0, [0, 1, 2, 3, 4, 5]) if arm else (27, 15, 10, [14, 13, 12, 7, 9, 8])
    ids = {"fstat": 80, "read": 63, "pread": 67} if arm else {"fstat": 5, "read": 0, "pread": 17}
    target = layout / ("oci-layout" if case == "race" else "index.json")
    assert target.is_file() and not target.is_symlink()
    if case == "race":
        assert target.stat().st_size <= 1024
    else:
        assert target.stat().st_size > 1048576
    output.mkdir(parents=True, exist_ok=False)
    lib = ctypes.CDLL(None, use_errno=True)
    lib.ptrace.restype = ctypes.c_long

    class IOV(ctypes.Structure):
        _fields_ = [("base", ctypes.c_void_p), ("length", ctypes.c_size_t)]

    def trace(request, pid, address=0, data=0):
        ctypes.set_errno(0)
        value = lib.ptrace(ctypes.c_uint(request), ctypes.c_uint(pid), ctypes.c_void_p(address), ctypes.c_void_p(data))
        if value == -1:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        return value

    def registers(pid):
        values = (ctypes.c_uint64 * reg_count)()
        io = IOV(ctypes.addressof(values), ctypes.sizeof(values))
        trace(0x4204, pid, 1, ctypes.addressof(io))
        assert io.length == ctypes.sizeof(values)
        return values

    def fd_path(pid, fd):
        try:
            return os.readlink(f"/proc/{pid}/fd/{fd}")
        except FileNotFoundError:
            return "<closed>"

    pid = os.fork()
    if pid == 0:
        stdout = os.open(output / "guest.stdout", os.O_CREAT | os.O_WRONLY, 0o600)
        stderr = os.open(output / "guest.stderr", os.O_CREAT | os.O_WRONLY, 0o600)
        os.dup2(stdout, 1)
        os.dup2(stderr, 2)
        os.close(stdout)
        os.close(stderr)
        trace(0, 0)
        os.execve(image, [str(image), str(layout), digest],
                  {"PATH": "/nonexistent", "KEXE_ALLOW": "35,37,38,39", "KEXE_COMMAND": "1",
                   "KEXE_CAP_RESOURCES_35": str(layout), "KEXE_STACK_BYTES": "8388608"})
    _, status = os.waitpid(pid, 0)
    assert os.WIFSTOPPED(status) and os.WSTOPSIG(status) == signal.SIGTRAP
    trace(0x4200, pid, 0, 0x100001)
    entering, pending, changed, deliver = True, False, False, 0
    target_fstats, target_reads = 0, []
    start = time.monotonic()
    try:
        while True:
            assert time.monotonic() - start < 30
            trace(24, pid, 0, deliver)
            deliver = 0
            _, status = os.waitpid(pid, 0)
            if os.WIFEXITED(status):
                code = os.WEXITSTATUS(status)
                break
            if os.WIFSIGNALED(status):
                code = -os.WTERMSIG(status)
                break
            sig = os.WSTOPSIG(status)
            if sig == (signal.SIGTRAP | 0x80):
                r = registers(pid)
                if entering:
                    pending = False
                    name = fd_path(pid, r[args[0]]) if r[number] in ids.values() else ""
                    if name == str(target):
                        if r[number] == ids["fstat"]:
                            target_fstats += 1
                            pending = case == "race" and not changed
                        elif r[number] in (ids["read"], ids["pread"]):
                            target_reads.append(int(r[args[2]]))
                elif pending and not changed:
                    assert r[result] == 0, "F metadata must have completed successfully"
                    with target.open("r+b") as f:
                        f.truncate(1025)
                    changed = True
                    pending = False
                entering = not entering
            elif sig != signal.SIGTRAP:
                deliver = sig
    except BaseException:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
        raise
    stdout = (output / "guest.stdout").read_bytes()
    stderr = (output / "guest.stderr").read_bytes()
    assert target_fstats >= 1, "target metadata syscall was not observed"
    if case == "race":
        assert changed and code == 126 and b":stage 15}" in stderr, (changed, code, stdout, stderr)
    else:
        assert code == 1 and stdout.strip() == b"fune/layout-index", (code, stdout, stderr)
        assert not target_reads, ("oversized index was read before refusal", target_reads)
    report = {"case": case, "exit": code, "metadataSyscalls": target_fstats,
              "targetReadRequests": target_reads, "sourceChangedAfterFstat": changed,
              "nativeGuestUnmodified": True, "compilerOrReleaseQualified": False}
    (output / "observation.json").write_text(json.dumps(report, indent=2) + "\n")
    print("PASS_LAYOUT_METADATA_BOUNDARY", case)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--layout", type=Path, required=True)
    p.add_argument("--digest", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--case", choices=("race", "oversize"), required=True)
    a = p.parse_args()
    main(a.image.resolve(), a.layout.resolve(), a.digest, a.output.resolve(), a.case)
