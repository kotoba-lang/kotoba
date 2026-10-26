#!/usr/bin/env python3
"""Stage/hash exact Kotoba sources and observe pinned native project execution.

All admission decisions and assertions execute in Kotoba. No hosted compiler,
language runtime or C loader fallback exists. The supplied runner must be built
by the same qualified Amu native toolchain (CI's native project gate does this).
"""
import argparse
import hashlib
import json
import platform
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--compiler-sha256", required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (platform.system(), platform.machine()) != ("Linux", "x86_64"):
        raise SystemExit("requires native Linux x86_64; no fallback")
    compiler = args.compiler.resolve(strict=True)
    runner = args.runner.resolve(strict=True)
    compiler_bytes = compiler.read_bytes()
    runner_bytes = runner.read_bytes()
    if digest(compiler_bytes) != args.compiler_sha256:
        raise SystemExit("compiler digest mismatch")
    if not all(b.startswith(b"\x7fELF\x02\x01") for b in (compiler_bytes, runner_bytes)):
        raise SystemExit("compiler and native runner must be ELF64 images")
    output = args.output.resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    module = (ROOT / "src/hata/admission.kotoba").read_bytes()
    tests = (ROOT / "test/admission_native.kotoba").read_bytes()
    compiler_env = {
        "PATH": "/nonexistent", "KEXE_ALLOW": "35,37,38,39",
        "KEXE_CAP_RESOURCES_35": str(output), "KEXE_STACK_BYTES": "8388608",
    }
    runtime_env = {
        "PATH": "/nonexistent", "KEXE_ALLOW": "-",
        "KEXE_FUEL": "100000000", "KEXE_STRUCTURED_REPORT": "1",
        "KEXE_STACK_BYTES": "8388608",
    }
    observations = []

    def invoke(label, command, env, expected_exit=0):
        result = subprocess.run(list(map(str, command)), env=env, cwd=output,
                                capture_output=True, timeout=120)
        (output / (label + ".stdout")).write_bytes(result.stdout)
        (output / (label + ".stderr")).write_bytes(result.stderr)
        if result.returncode != expected_exit:
            raise RuntimeError((label, result.returncode, result.stderr[-1500:].decode(errors="replace")))
        observations.append({"label": label, "argv": list(map(str, command)),
                             "exit": result.returncode,
                             "stdoutSHA256": digest(result.stdout),
                             "stderrSHA256": digest(result.stderr)})
        return result

    def build_run(label, module_bytes, expected_result):
        source_root = output / label / "src"
        source_root.joinpath("hata").mkdir(parents=True)
        implementation = source_root / "hata/admission.kotoba"
        implementation.write_bytes(module_bytes)
        entry = source_root / "hata/admission_native_test.kotoba"
        entry.write_bytes(tests)
        lock = output / (label + ".ksl")
        paths = sorted([implementation, entry])
        lock.write_text(f"KSL1\nentry {entry}\nroot {source_root}\n" + "".join(
            f"file {digest(p.read_bytes())} {p}\n" for p in paths))
        pinned = ["--source-path", source_root, "--source-lock", lock,
                  "--source-lock-sha256", digest(lock.read_bytes())]
        invoke(label + "-check", [compiler, "check", entry, *pinned], compiler_env)
        container = output / (label + ".kx64")
        invoke(label + "-compile", [compiler, "compile", entry, "--target", "x86_64-linux",
                                    "--output", container, "--format", "kx64-v1", *pinned], compiler_env)
        if implementation.read_bytes() != module_bytes or entry.read_bytes() != tests:
            raise RuntimeError("staged source changed")
        header, payload = container.read_bytes().split(b"\n\n", 1)
        match = re.fullmatch(rb"KX64V1 x86_64-linux sysv-ctx-v11 ([0-9]+) 0", header)
        if not match or len(payload) != int(match[1]) or not payload.startswith(b"\xe9"):
            raise RuntimeError("invalid native project container")
        image = output / (label + ".bin")
        image.write_bytes(payload)
        result = invoke(label + "-run", [runner, image, "0", "0", "x86_64", "-"], runtime_env)
        found = re.search(rb":result (-?\d+)\b", result.stdout)
        if not found or int(found[1]) != expected_result or result.stderr:
            raise RuntimeError((label, "native assertion failure", result.stdout[-1500:], result.stderr[-1500:]))
        return {"moduleSHA256": digest(module_bytes), "testsSHA256": digest(tests),
                "lockSHA256": digest(lock.read_bytes()),
                "artifactSHA256": digest(container.read_bytes()),
                "payloadSHA256": digest(payload), "result": int(found[1])}, entry, pinned

    positive, entry, pinned = build_run("admission", module, 0)
    needle = b"(not (ad-budget? s r)) (ad-decision s 18 -1)"
    if module.count(needle) != 1:
        raise RuntimeError("budget-bypass control no longer matches")
    negative, _, _ = build_run("budget-bypass-control", module.replace(
        needle, b"false (ad-decision s 18 -1)"), 320)
    refused = output / "wrong-lock.kx64"
    bad_lock = [*pinned[:-1], "0" * 64]
    result = subprocess.run(list(map(str, [compiler, "compile", entry, "--target", "x86_64-linux",
        "--output", refused, "--format", "kx64-v1", *bad_lock])), env=compiler_env,
        cwd=output, capture_output=True, timeout=120)
    (output / "wrong-lock.stderr").write_bytes(result.stderr)
    if result.returncode != 1 or b"E6015" not in result.stderr or refused.exists():
        raise RuntimeError("compiler accepted a mismatched source lock")
    report = {
        "schema": "hata.admission.native-evidence.v1",
        "status": "PASS_NATIVE_ADMISSION_STATE_MACHINE",
        "compilerSHA256": digest(compiler_bytes), "runnerSHA256": digest(runner_bytes),
        "sourceSHA256": digest(module), "testsSHA256": digest(tests),
        "observerSHA256": digest(Path(__file__).read_bytes()),
        "target": "x86_64-linux-kx64-v1/native-static-runner",
        "publicExportsExercised": 7, "assertionPredicates": 276,
        "positive": positive, "budgetBypassControl": negative,
        "wrongSourceLockControl": {"exit": result.returncode, "diagnostic": "E6015", "noArtifact": True},
        "runtimeCapabilities": [], "legacyRuntimeFallback": False,
        "packaging": "unchanged canonical module plus importing native test module",
        "frontendSourceLock": True, "nativeEmitterSourceLockQualified": True,
        "scope": "post-verification state machine; no wire authentication, persistence or dispatch",
        "observations": observations,
    }
    (output / "evidence.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], "276 predicates; budget bypass and wrong-lock refused; 7 exports linked/exercised")


if __name__ == "__main__":
    main()
