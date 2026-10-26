#!/usr/bin/env python3
"""Stage exact native sources; observe Kotoba assertions and process/fs faults.

No admission, cryptography, source resolution or storage decisions live here.
Test keys are public fixtures; this does not enroll or contact real members.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import signal
import subprocess
import time
from pathlib import Path

LIB = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--compiler-sha256", required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", choices=["all", "authority", "store"], default="all")
    args = parser.parse_args()
    if (platform.system(), platform.machine()) != ("Linux", "x86_64"):
        raise SystemExit("native Linux x86_64 required; no fallback")
    compiler, runner = args.compiler.resolve(), args.runner.resolve()
    if sha(compiler.read_bytes()) != args.compiler_sha256:
        raise SystemExit("compiler digest mismatch")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    sources = {
        **{f"hata/{name}.kotoba": LIB / f"src/hata/{name}.kotoba"
           for name in ["admission", "codec", "authority", "store", "store_io"]},
        "hata/admission_native_test.kotoba": LIB / "test/admission_native.kotoba",
        "hata/authority_fixture.kotoba": LIB / "test/authority_fixture.kotoba",
        "hata/authority_native_test.kotoba": LIB / "test/authority_native.kotoba",
        "hata/store_native_test.kotoba": LIB / "test/store_native.kotoba",
        "ed25519/selfhost.kotoba": LIB.parent / "org.ietf.ed25519/kotoba/ed25519/selfhost.kotoba",
        "sha2/core.kotoba": LIB.parent / "gov.nist.sha2/kotoba/sha2/core.kotoba",
    }
    original = {name: path.read_bytes() for name, path in sources.items()}
    env = {"PATH": "/nonexistent", "KEXE_ALLOW": "35,37,38,39",
           "KEXE_CAP_RESOURCES_35": str(out), "KEXE_STACK_BYTES": "8388608"}
    observations, artifacts = [], {}

    def call(label, argv, custom=env, expected=0, timeout=600):
        started = time.monotonic()
        result = subprocess.run(list(map(str, argv)), cwd=out, env=custom,
                                capture_output=True, timeout=timeout)
        (out / (label + ".stdout")).write_bytes(result.stdout)
        (out / (label + ".stderr")).write_bytes(result.stderr)
        observations.append({"name": label, "exit": result.returncode,
                             "seconds": round(time.monotonic() - started, 3)})
        print(label, "exit", result.returncode, flush=True)
        if result.returncode != expected:
            raise RuntimeError((label, result.returncode, result.stdout[-500:], result.stderr[-1500:]))
        return result

    def build(label, entry_name, files):
        root = out / label / "src"
        for name, data in files.items():
            dest = root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        entry = root / entry_name
        lock = out / (label + ".ksl")
        lock.write_text(f"KSL1\nentry {entry}\nroot {root}\n" + "".join(
            f"file {sha(data)} {root / name}\n" for name, data in sorted(files.items())))
        flags = ["--source-path", root, "--source-lock", lock, "--source-lock-sha256", sha(lock.read_bytes())]
        call(label + "-check", [compiler, "check", entry, *flags])
        container = out / (label + ".kx64")
        call(label + "-compile", [compiler, "compile", entry, "--target", "x86_64-linux",
                                  "--output", container, "--format", "kx64-v1", *flags])
        header, payload = container.read_bytes().split(b"\n\n", 1)
        matched = re.fullmatch(rb"KX64V1 x86_64-linux sysv-ctx-v11 ([0-9]+) 0", header)
        assert matched and len(payload) == int(matched[1]) and payload[0] == 0xe9
        binary = out / (label + ".bin")
        binary.write_bytes(payload)
        artifacts[label] = {"artifactSHA256": sha(container.read_bytes()), "payloadSHA256": sha(payload),
                            "lockSHA256": sha(lock.read_bytes()),
                            "sources": {name: sha(data) for name, data in files.items()}}
        return binary

    def runtime(allow="-", scope=out):
        return {"PATH": "/nonexistent", "KEXE_ALLOW": allow, "KEXE_CAP_RESOURCES_35": str(scope),
                "KEXE_FUEL": "100000000000", "KEXE_STRUCTURED_REPORT": "1", "KEXE_STACK_BYTES": "8388608"}

    def observed(label, binary, expected, mode=None, base=None, allow="-", scope=out):
        command = [runner, binary, "0", "0", "x86_64", allow]
        if mode is not None:
            command += ["--", mode, base]
        result = call(label, command, runtime(allow, scope))
        value = re.search(rb":result (-?[0-9]+)\b", result.stdout)
        assert value and int(value[1]) == expected and not result.stderr, (label, result.stdout, result.stderr)
        return int(value[1])

    authority_files = {name: data for name, data in original.items()
                       if name not in {"hata/store.kotoba", "hata/store_io.kotoba", "hata/store_native_test.kotoba"}}
    store_files = {name: data for name, data in original.items()
                   if name not in {"hata/admission_native_test.kotoba", "hata/authority_native_test.kotoba"}}
    if args.case != "store":
        gate = build("authority", "hata/authority_native_test.kotoba", authority_files)
        observed("authority-vectors", gate, 0)
        needle = b"(not (ed/verify? pk (request-message r id) (c/slice auth 229 64)))"
        assert original["hata/authority.kotoba"].count(needle) == 1
        mutant = dict(authority_files)
        mutant["hata/authority.kotoba"] = mutant["hata/authority.kotoba"].replace(needle, b"false")
        broken = build("signature-bypass", "hata/authority_native_test.kotoba", mutant)
        observed("signature-bypass-detected", broken, 1016)
    if args.case == "authority":
        report = {"schema": "hata.authority.native-evidence.v1", "status": "PASS_NATIVE_AUTHORITY_ONLY",
                  "compilerSHA256": sha(compiler.read_bytes()), "runnerSHA256": sha(runner.read_bytes()),
                  "artifacts": artifacts, "observations": observations, "persistenceQualified": False}
        (out / "evidence.json").write_text(json.dumps(report, indent=2) + "\n")
        print(report["status"], flush=True)
        return
    store = build("store", "hata/store_native_test.kotoba", store_files)

    def run(mode, base, expected=1, binary=store, label=None):
        return observed(label or f"{base.name}-{mode}", binary, expected, mode, base, "35,38")

    normal = out / "normal"
    normal.mkdir()
    for mode in ["create", "create-again", "state-empty", "denied", "save-token", "submit",
                 "state-reserved", "duplicate", "conflict", "stale", "complete", "state-complete"]:
        run(mode, normal)
    unknown = out / "unknown"
    unknown.mkdir()
    for mode in ["create", "submit", "recover", "state-unknown", "old-writer", "request-after-recovery", "state-unknown"]:
        run(mode, unknown)
    small = out / "small"
    small.mkdir()
    for mode in ["create-small", "submit", "capacity", "state-reserved"]:
        run(mode, small)
    run("codec-max", normal)
    run("unsafe-path", normal)
    snapshot = normal / "awai-admission.state"
    good = snapshot.read_bytes()
    snapshot.write_bytes(good[:-1] + (b"0" if good[-1:] != b"0" else b"1"))
    run("corrupt", normal)
    snapshot.write_bytes(good)
    run("state-complete", normal, label="normal-restored-signature")

    race = out / "race"
    race.mkdir()
    run("create", race)
    run("save-token", race)
    argv = list(map(str, [runner, store, "0", "0", "x86_64", "35,38", "--", "race", race]))
    children = [subprocess.Popen(argv, env=runtime("35,38"), cwd=out,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
    values = []
    for index, child in enumerate(children):
        stdout, stderr = child.communicate(timeout=600)
        (out / f"race-{index}.stdout").write_bytes(stdout)
        (out / f"race-{index}.stderr").write_bytes(stderr)
        match = re.search(rb":result (-?[0-9]+)\b", stdout)
        assert child.returncode == 0 and not stderr and match, (child.returncode, stdout, stderr)
        values.append(int(match[1]))
    assert values.count(11) == 1 and all(value in (11, 12, 13) for value in values), values
    run("state-reserved", race)
    # Fault-only adapter wraps the original I/O responses. Production store,
    # cryptography, signed candidate and transition code remain unchanged.
    faulty = dict(store_files)
    adapter = faulty["hata/store_io.kotoba"].replace(
        b"(:capabilities [:fs/app-data])", b"(:capabilities [:fs/app-data :cli/args])")
    helper = b"""
(defn- fault-after [stage :string value :bool] :bool
  (if (and value (= (typed-cap-call :cli/args :string :string "2") stage))
    (let [base (typed-cap-call :cli/args :string :string "1")
          ready (typed-cap-call :fs/app-data :string :string
                  (string-concat base "/readyWRITE_SEPready"))]
      (if (not= ready "ready") false
        (loop [i 0] (if (= i 9223372036854775807) false (recur (+ i 1)))))) value))
"""
    adapter += helper
    write_original = b"""(defn write [path :string data :string] :bool
  (= (typed-cap-call :fs/app-data :string :string (string-concat path (string-concat "WRITE_SEP" data))) data))"""
    write_fault = b"""(defn write [path :string data :string] :bool
  (let [partial (= (typed-cap-call :cli/args :string :string "2") "partial")
        actual (if partial "partial" data)]
    (fault-after (if partial "partial" "written")
      (= (typed-cap-call :fs/app-data :string :string
           (string-concat path (string-concat "WRITE_SEP" actual))) actual))))"""
    sync_original = b"""(defn sync [path :string] :bool
  (= (typed-cap-call :fs/app-data :string :string (string-concat path "FSYNC_SEP")) "1"))"""
    sync_fault = b"""(defn sync [path :string] :bool
  (fault-after (if (= path (typed-cap-call :cli/args :string :string "1")) "durable" "synced")
    (= (typed-cap-call :fs/app-data :string :string (string-concat path "FSYNC_SEP")) "1")))"""
    rename_original = b"""(defn rename [from :string to :string] :bool
  (= (typed-cap-call :fs/app-data :string :string (string-concat from (string-concat "RENAME_SEP" to))) "1"))"""
    rename_fault = b"""(defn rename [from :string to :string] :bool
  (fault-after "renamed"
    (= (typed-cap-call :fs/app-data :string :string (string-concat from (string-concat "RENAME_SEP" to))) "1")))"""
    for old, new in [(write_original, write_fault), (sync_original, sync_fault), (rename_original, rename_fault)]:
        assert adapter.count(old) == 1
        adapter = adapter.replace(old, new)
    faulty["hata/store_io.kotoba"] = adapter
    fault_image = build("crash-control", "hata/store_native_test.kotoba", faulty)
    crashes = []
    for stage in ["partial", "written", "synced", "renamed", "durable"]:
        base = out / ("crash-" + stage)
        base.mkdir()
        run("create", base)
        argv = list(map(str, [runner, fault_image, 0, 0, "x86_64", "35,38", "--", "submit", base, stage]))
        child = subprocess.Popen(argv, env=runtime("35,38"), cwd=out,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 60
            while not (base / "ready").exists():
                assert child.poll() is None, (stage, child.communicate())
                assert time.monotonic() < deadline, (stage, "fault hook deadline")
                time.sleep(0.01)
            # The original binary must observe the still-live writer's flock.
            run("busy", base)
        finally:
            if child.poll() is None:
                child.kill()
            stdout, stderr = child.communicate(timeout=10)
            (out / ("crash-" + stage + ".stdout")).write_bytes(stdout)
            (out / ("crash-" + stage + ".stderr")).write_bytes(stderr)
        assert child.returncode == -signal.SIGKILL and not stdout and not stderr
        published = stage in ("renamed", "durable")
        run("state-reserved" if published else "state-empty", base)
        # Reopen after process death: the kernel released the unchanged lock.
        if published:
            run("duplicate", base)
        else:
            run("submit", base)
        run("state-reserved", base, label="crash-" + stage + "-exactly-one-reservation")
        run("recover", base)
        run("state-unknown", base)
        crashes.append(dict(stage=stage, signal="SIGKILL", visible="reserved" if published else "empty",
                            lockReleased=True, exactlyOneReservation=True, recovered="UNKNOWN"))

    # Test real host resource scope and an ungranted wire, independently of
    # lexical base validation. No state file may appear outside the grant.
    outside = out / "outside"
    outside.mkdir()
    observed("host-scope-refusal", store, 1, "busy", outside, "35,38", normal)
    assert not list(outside.iterdir())
    command = [runner, store, 0, 0, "x86_64", "38", "--", "create", outside]
    refusal = call("host-ungranted-fs", command, runtime("38"), expected=120)
    assert b"KEXE_CAP {:wire 35 :refused :not-granted}" in refusal.stderr and not list(outside.iterdir())
    report = {"schema": "hata.authority-store.native-evidence.v1", "status": "PASS_NATIVE_AUTHORITY_STORE" if args.case == "all" else "PASS_NATIVE_STORE_ONLY",
              "compilerSHA256": sha(compiler.read_bytes()), "runnerSHA256": sha(runner.read_bytes()),
              "observerSHA256": sha(Path(__file__).read_bytes()), "artifacts": artifacts,
              "signatureBypassDetected": 1016 if args.case == "all" else None, "raceResults": values,
              "processCrashBoundaries": crashes, "powerLossQualified": False,
              "scope": "C0 signed authority; trusted-host single-filesystem checkpoint and flock, no dispatch/quorum",
              "observations": observations, "legacyRuntimeFallback": False}
    (out / "evidence.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], flush=True)


if __name__ == "__main__":
    main()
