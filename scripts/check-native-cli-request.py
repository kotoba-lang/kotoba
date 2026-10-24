#!/usr/bin/env python3
"""Stage immutable bytes; Kotoba fixtures decide request-parser correctness.

No host EDN parser, compiler, namespace resolver, language runtime or oracle.
The adopted compiler resolves the pinned multi-module graph itself.
"""
import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pin(path):
    data = Path(path).read_bytes()
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main(amu, contract, compiler, out):
    assert platform.system() == "Linux" and platform.machine() in ("aarch64", "arm64"), "native ARM Linux required"
    inputs = json.loads((ROOT / "scripts/native-ci-inputs.json").read_text())
    for name, identity in inputs["amu"]["files"].items():
        assert pin(amu / name) == identity, ("Amu source drift", name)
    assert pin(contract) == inputs["contract"]["identity"], "contract drift"
    assert pin(compiler) == inputs["amu"]["files"]["seed/bootstrap/aarch64-linux-static-root.elf"], "unqualified compiler generation"
    out.mkdir(parents=True, exist_ok=False)
    calls = []
    # All .kotoba sources retain their namespaces. No host concatenation or
    # rewriting substitutes for the compiler's project loader/checker.
    entry = ROOT / "test/kotoba/native_cli_request.kotoba"
    sources = [entry, ROOT / "src/kotoba/cli.kotoba", ROOT / "src/kotoba/cli_exec.kotoba",
               ROOT / "lib/kotoba.ioMultiformats/src/multiformats/cid.kotoba",
               ROOT / "lib/kotoba.ioMultiformats/src/multiformats/sha256.kotoba",
               *[amu / "src/kotoba" / name for name in
               ("form.kotoba", "compiler/kotoba_reader.kotoba", "compiler/decimal_bits.kotoba",
                "compiler/module_lock.kotoba")]]
    roots = [ROOT / "src", ROOT / "lib/kotoba.ioMultiformats/src", amu / "src"]
    lock = out / "request.ksl"
    lock.write_text("KSL1\nentry " + str(entry) + "\n" + "".join("root " + str(p) + "\n" for p in roots)
                    + "".join("file " + pin(p)["sha256"] + " " + str(p) + "\n" for p in sorted(sources)))
    env = dict(PATH="/nonexistent", KEXE_ALLOW="35,37,38,39", KEXE_STACK_BYTES="8388608",
               KEXE_CAP_RESOURCES_35=":".join(map(str, [ROOT, amu, out])))

    def run(name, args, custom=None, expected=0):
        p = subprocess.run(list(map(str, args)), cwd=out, env=custom or env, capture_output=True, timeout=900)
        (out / (name + ".stdout")).write_bytes(p.stdout)
        (out / (name + ".stderr")).write_bytes(p.stderr)
        calls.append(dict(name=name, exit=p.returncode))
        (out / "calls.json").write_text(json.dumps(calls, indent=2) + "\n")
        if expected == 0:
            assert p.returncode == 0 and not p.stderr, (name, p.returncode, p.stderr[-1200:])
        else:
            assert p.returncode != 0, (name, "negative control accepted")
        return p

    run("compile", [compiler, "compile", entry, "--target", "aarch64-macos", "--output", out / "request.kseed",
                    *[part for p in roots for part in ("--source-path", p)], "--source-lock", lock,
                    "--source-lock-sha256", pin(lock)["sha256"]])
    run("pack", [compiler, "compile", amu / "seed/x86_64-kx64-runner.kotoba", "--target", "aarch64-linux",
                 "--output", out / "request.elf", "--format", "packed", "--payload", out / "request.kseed"])
    (out / "request.elf").chmod(0o755)
    # The contract is opaque argv data. Its Kotoba reader and all assertions
    # execute inside the native fixture; Python never interprets the EDN.
    data = contract.read_text()
    valid_lock = out / "valid-module-lock.edn"
    valid_lock.write_text('{:schema :kotoba.module-lock/v1 :root main :modules {util "bafkreicnabst32iqvrylj36cgn2cm2xfywgxyyoielxnejmqywmcaswmbi" main "bafkreibqtanjq6cttjjq6eywse4a3ryai5txbtswhimcuodgbwnvqx6u3a"}}\n')
    invalid_lock = out / "invalid-module-lock.edn"
    invalid_lock.write_text('{:schema :kotoba.module-lock/v1 :root main :modules {main "bad-pin"}}\n')
    missing_lock = out / "missing-module-lock.edn"
    guest = dict(PATH="/nonexistent", KEXE_ALLOW="35,37,38", KEXE_STACK_BYTES="8388608",
                 KEXE_CAP_RESOURCES_35=str(out))
    positive = run("all12-request", [out / "request.elf", data, valid_lock, invalid_lock], guest)
    assert positive.stdout == b"PASS_NATIVE_ALL12_CLI_REQUEST_AND_CONTRACT_AND_LOCK_CHECK_EXECUTION\n"
    missing = run("missing-lock-negative-control", [out / "request.elf", "FS_MISSING", data, missing_lock],
                  guest, expected=1)
    assert b":fs2/refused" in missing.stderr, "missing lock was not refused by FS2"
    assert ":values [:kotoba]" in data
    changed = data.replace(":values [:kotoba]", ":values [:nbb]", 1)
    run("contract-negative-control", [out / "request.elf", changed, valid_lock, invalid_lock], guest, expected=1)
    run("grant-negative-control", [out / "request.elf", data, valid_lock, invalid_lock],
        dict(PATH="/nonexistent", KEXE_ALLOW="-"), expected=1)
    denied = run("fs-grant-negative-control", [out / "request.elf", data, valid_lock, invalid_lock],
                 dict(PATH="/nonexistent", KEXE_ALLOW="37,38", KEXE_STACK_BYTES="8388608"), expected=1)
    assert b":not-granted" in denied.stderr, "FS denial lacks named refusal"
    scoped = run("fs-scope-negative-control", [out / "request.elf", data, valid_lock, invalid_lock],
                 dict(PATH="/nonexistent", KEXE_ALLOW="35,37,38", KEXE_STACK_BYTES="8388608",
                      KEXE_CAP_RESOURCES_35=str(ROOT / "src")), expected=1)
    assert b":module-lock/reader" in scoped.stdout, "FS scope denial reached an accepted lock"
    assert not any(p.name.startswith("kotoba-output-") for p in out.iterdir()), "stage leaked"
    report = dict(status="PASS_NATIVE_ALL12_CLI_REQUEST", inputs=inputs, compiler=pin(compiler),
                  sources={str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else "amu/" + str(p.relative_to(amu)): pin(p) for p in sources},
                  contract=pin(contract), lock=pin(lock), image=pin(out / "request.elf"),
                  lockFixtures=dict(valid=pin(valid_lock), invalid=pin(invalid_lock), missing=not missing_lock.exists()),
                  calls=calls,
                  nativeGuestOwnsAssertions=True, contractCheckExecutionQualified=True,
                  lockCheckExecutionQualified=True,
                  commandExecutionQualified=False, publicEntryReplaced=False,
                  wholeCLIQualified=False, legacyRuntimeFallback=False, cCompilerOrLoader=False, emulation=False)
    (out / "native-cli-request.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--amu", type=Path, required=True)
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--compiler", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    main(a.amu.resolve(), a.contract.resolve(), a.compiler.resolve(), a.output.resolve())
