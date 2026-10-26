#!/usr/bin/env python3
"""Exact input staging and process observation for native identity fixtures."""
import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path


def pin(path):
    return dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main(args):
    assert platform.system() == "Linux" and platform.machine() == "aarch64", "native ARM Linux required"
    repo = Path(__file__).resolve().parents[1]
    compiler, out = args.compiler.resolve(), args.output.resolve()
    amu, cbor, multiformats = args.amu.resolve(), args.cbor.resolve(), args.multiformats.resolve()
    assert pin(compiler)["sha256"] == args.compiler_sha256
    out.mkdir(parents=True, exist_ok=False)
    entry = repo / "test/kotoba/kir/native_definition_identity.kotoba"
    files = [entry, repo / "src/kotoba/kir/definition_identity.kotoba", repo / "src/kotoba/kir/alpha_normalization.kotoba",
             *[amu / "src/kotoba" / p for p in ["form.kotoba", "compiler/kotoba_reader.kotoba", "compiler/decimal_bits.kotoba"]],
             *[cbor / "src/cbor" / p for p in ["form.kotoba", "codec.kotoba", "fragment.kotoba", "value.kotoba"]],
             multiformats / "src/multiformats/cid.kotoba", multiformats / "src/multiformats/sha256.kotoba"]
    owners = {"osaho": repo, "amu": amu, "cbor": cbor, "multiformats": multiformats}
    inputs = {}
    for path in files:
        owner, root = next((name, root) for name, root in owners.items() if path.is_relative_to(root))
        inputs[owner + "/" + str(path.relative_to(root))] = pin(path)
    roots = [root / "src" for root in owners.values()]
    lock = out / "identity.ksl"
    lock.write_text("KSL1\nentry " + str(entry) + "\n" + "".join("root " + str(root) + "\n" for root in roots) +
                    "".join("file " + pin(path)["sha256"] + " " + str(path) + "\n" for path in sorted(files)))
    env = dict(PATH="/nonexistent", KEXE_ALLOW="35,37,38,39", KEXE_STACK_BYTES="8388608",
               KEXE_CAP_RESOURCES_35=":".join(map(str, [out, *owners.values()])))
    calls = []

    def run(name, argv):
        result = subprocess.run(list(map(str, argv)), cwd=out, env=env, capture_output=True, timeout=900)
        (out / (name + ".stdout")).write_bytes(result.stdout)
        (out / (name + ".stderr")).write_bytes(result.stderr)
        calls.append(dict(name=name, exit=result.returncode))
        (out / "calls.json").write_text(json.dumps(calls, indent=2) + "\n")
        assert result.returncode == 0 and not result.stderr, (name, result.returncode, result.stderr[-1200:])

    payload, image = out / "identity.kseed", out / "identity.elf"
    run("compile", [compiler, "compile", entry, "--target", "aarch64-macos",
                    *[arg for root in roots for arg in ["--source-path", root]], "--source-lock", lock,
                    "--source-lock-sha256", pin(lock)["sha256"], "--output", payload])
    runner = amu / "seed/x86_64-kx64-runner.kotoba"
    run("pack", [compiler, "compile", runner, "--target", "aarch64-linux", "--output", image,
                 "--format", "packed", "--payload", payload])
    image.chmod(0o755)
    vectors = repo / "test/kotoba/kir/fixtures/code-identity-vectors.edn"
    run("execute", [image, vectors])
    report = dict(status="PASS_NATIVE_IDENTITY_FROZEN10_ALPHA_BRIDGE_LOCK", compiler=pin(compiler), runner=pin(runner),
                  host=[platform.system(), platform.machine(), platform.release()], inputs=inputs,
                  sourceLock=pin(lock), frozenVectors=pin(vectors), cases=calls,
                  legacyHostExecuted=False, compilerGraphWiringQualified=False, x86Executed=False)
    (out / "native-gate.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--compiler-sha256", required=True)
    parser.add_argument("--amu", type=Path, required=True)
    parser.add_argument("--cbor", type=Path, required=True)
    parser.add_argument("--multiformats", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
