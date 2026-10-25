#!/usr/bin/env python3
"""Stage exact inputs; Amu and the native Kotoba fixtures own all verdicts."""
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
    compiler, amu, out = args.compiler.resolve(), args.amu.resolve(), args.output.resolve()
    assert pin(compiler)["sha256"] == args.compiler_sha256
    out.mkdir(parents=True, exist_ok=False)
    runner = amu / "seed/x86_64-kx64-runner.kotoba"
    env = dict(PATH="/nonexistent", KEXE_ALLOW="35,37,38,39",
               KEXE_CAP_RESOURCES_35=":".join(map(str, [repo, amu, out])), KEXE_STACK_BYTES="8388608")
    calls, inputs = [], {}

    def run(name, argv):
        result = subprocess.run(list(map(str, argv)), cwd=out, env=env, capture_output=True, timeout=900)
        (out / (name + ".stdout")).write_bytes(result.stdout)
        (out / (name + ".stderr")).write_bytes(result.stderr)
        calls.append(dict(name=name, exit=result.returncode))
        (out / "calls.json").write_text(json.dumps(calls, indent=2) + "\n")
        assert result.returncode == 0 and not result.stderr, (name, result.returncode, result.stderr[-1200:])

    for name in ["cid", "sha256"]:
        entry = repo / ("test/multiformats/native_" + name + ".kotoba")
        files = [entry, repo / "src/multiformats/cid.kotoba"]
        if name == "sha256":
            files += [repo / "src/multiformats/sha256.kotoba", repo / "src/multiformats/cid_hash.kotoba"]
        lock, payload, image = [out / (name + suffix) for suffix in [".ksl", ".kseed", ".elf"]]
        inputs[name] = {str(path.relative_to(repo)): pin(path) for path in files}
        lock.write_text("KSL1\nentry " + str(entry) + "\nroot " + str(repo / "src") + "\n" +
                        "".join("file " + pin(path)["sha256"] + " " + str(path) + "\n" for path in sorted(files)))
        run(name + "-compile", [compiler, "compile", entry, "--target", "aarch64-macos", "--source-path", repo / "src",
                                "--source-lock", lock, "--source-lock-sha256", pin(lock)["sha256"], "--output", payload])
        run(name + "-pack", [compiler, "compile", runner, "--target", "aarch64-linux", "--output", image,
                             "--format", "packed", "--payload", payload])
        image.chmod(0o755)
        run(name + "-execute", [image])
    report = dict(status="PASS_NATIVE_CID_SHA256", host=[platform.system(), platform.machine(), platform.release()],
                  compiler=pin(compiler), runner=pin(runner), inputs=inputs, calls=calls,
                  legacyHostExecuted=False, allMultiformatsQualified=False, x86Executed=False)
    (out / "native-gate.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report["status"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    parser.add_argument("--compiler-sha256", required=True)
    parser.add_argument("--amu", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
