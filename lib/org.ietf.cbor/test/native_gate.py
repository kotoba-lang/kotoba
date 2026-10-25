#!/usr/bin/env python3
"""Stage exact locks and native processes; Kotoba fixtures own all checks."""
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
    amu, multiformats = args.amu.resolve(), args.multiformats.resolve()
    compiler, out = args.compiler.resolve(), args.output.resolve()
    assert pin(compiler)["sha256"] == args.compiler_sha256
    out.mkdir(parents=True, exist_ok=False)
    runner = amu / "seed/x86_64-kx64-runner.kotoba"
    env = dict(PATH="/nonexistent", KEXE_ALLOW="35,37,38,39", KEXE_STACK_BYTES="8388608",
               KEXE_CAP_RESOURCES_35=":".join(map(str, [out, repo, amu, multiformats])))
    calls, inputs = [], {}

    def run(name, argv):
        result = subprocess.run(list(map(str, argv)), cwd=out, env=env, capture_output=True, timeout=900)
        (out / (name + ".stdout")).write_bytes(result.stdout)
        (out / (name + ".stderr")).write_bytes(result.stderr)
        calls.append(dict(name=name, exit=result.returncode))
        (out / "calls.json").write_text(json.dumps(calls, indent=2) + "\n")
        assert result.returncode == 0 and not result.stderr, (name, result.returncode, result.stderr[-1200:])

    for name in ["codec", "form", "golden_roundtrip", "golden_encode"]:
        entry = repo / ("test/cbor/native_" + name + ".kotoba")
        files = [entry, *[repo / "src/cbor" / p for p in ["codec.kotoba", "fragment.kotoba", "value.kotoba"]]]
        roots = [repo / "src"]
        if name == "codec":
            files += [repo / "src/cbor/core.kotoba"]
        else:
            roots += [amu / "src"]
            files += [amu / "src/kotoba/form.kotoba"]
        if name == "form":
            files += [repo / "src/cbor/form.kotoba"]
        if name.startswith("golden"):
            files += [amu / "src/kotoba/compiler/kotoba_reader.kotoba", amu / "src/kotoba/compiler/decimal_bits.kotoba",
                      multiformats / "src/multiformats/cid.kotoba"]
            roots += [multiformats / "src"]
        if name == "golden_encode":
            files += [repo / "test/cbor/native_golden_values.kotoba"]
            roots += [repo / "test"]
        lock, payload, image = [out / (name + suffix) for suffix in [".ksl", ".kseed", ".elf"]]
        source_pins = {}
        for path in files:
            owner = repo if path.is_relative_to(repo) else amu if path.is_relative_to(amu) else multiformats
            owner_name = "cbor" if owner == repo else "amu" if owner == amu else "multiformats"
            source_pins[owner_name + "/" + str(path.relative_to(owner))] = pin(path)
        inputs[name] = source_pins
        lock.write_text("KSL1\nentry " + str(entry) + "\n" + "".join("root " + str(root) + "\n" for root in roots) +
                        "".join("file " + pin(path)["sha256"] + " " + str(path) + "\n" for path in sorted(files)))
        run(name + "-compile", [compiler, "compile", entry, "--target", "aarch64-macos",
                                *[arg for root in roots for arg in ["--source-path", root]],
                                "--source-lock", lock, "--source-lock-sha256", pin(lock)["sha256"], "--output", payload])
        run(name + "-pack", [compiler, "compile", runner, "--target", "aarch64-linux", "--output", image,
                             "--format", "packed", "--payload", payload])
        image.chmod(0o755)
        run(name + "-execute", [image, *([repo / "test/cbor/golden.edn"] if name.startswith("golden") else [])])
    report = dict(status="PASS_NATIVE_CBOR_FULL_CORPUS", host=[platform.system(), platform.machine(), platform.release()],
                  compiler=pin(compiler), runner=pin(runner), inputs=inputs, calls=calls,
                  golden=pin(repo / "test/cbor/golden.edn"), goldenValues=2367, randomValues=2000,
                  explicitNativeRepresentationChanges=[13, 26, 27, 295, 297, 302, 314, 363],
                  classifiedFrozenNoncanonical=[360, 363], legacyHostExecuted=False, x86Executed=False,
                  allDownstreamCallersQualified=False)
    (out / "native-gate.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--compiler-sha256", required=True)
    parser.add_argument("--amu", type=Path, required=True)
    parser.add_argument("--multiformats", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
