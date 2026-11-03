#!/usr/bin/env python3
"""Run the pinned Kotoba SQLite legacy-file mutation guest on native x86_64.

Python stages exact source/fixture bytes and observes the Amu KX64 process.
The Kotoba guest performs the SQLite checks and mutation; no host SQL engine
participates in this gate.
"""
import argparse
import hashlib
import json
import platform
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "lib/kotoba.sql"
MODULES = (
    ("kotoba.sqlite.database", PACKAGE / "src/kotoba/sqlite/database.kotoba"),
    ("kotoba.sqlite.header", PACKAGE / "src/kotoba/sqlite/header.kotoba"),
    ("kotoba.sqlite.notepad-record", PACKAGE / "src/kotoba/sqlite/notepad_record.kotoba"),
    ("kotoba.sqlite.page", PACKAGE / "src/kotoba/sqlite/page.kotoba"),
    ("kotoba.sqlite.reader", PACKAGE / "src/kotoba/sqlite/reader.kotoba"),
    ("kotoba.sqlite.record", PACKAGE / "src/kotoba/sqlite/record.kotoba"),
    ("kotoba.sqlite.schema", PACKAGE / "src/kotoba/sqlite/schema.kotoba"),
    ("kotoba.sqlite.varint", PACKAGE / "src/kotoba/sqlite/varint.kotoba"),
)
FIXTURE_NAME = "sqlite.notepad-existing-file-mutation"
FIXTURE = PACKAGE / "test/native/notepad-existing-file-mutation.kotoba"
DATABASE_FIXTURE = PACKAGE / "test/fixtures/legacy-cron-notepad-20261102.sqlite"
ALLOW = "3,35,37,38,39"
AMU_COMMIT = "897c816bedb15f851558c2f857bfd2be3ef25d41"
AMU_BINARY_SHA256 = "3ef5d23c261be698c66bd75bc09745912e210d023f46cd6ec3c8e0c14ca5d285"
AMU_RUNNER_SHA256 = "c9f1fe1b5c1748450fb11b233cbdc9d9234880a60dc480c0387b173f60d905be"
AMU_PROJECT_PROFILE = "seed/experimental/98-x86_64-project-fs-cli.kotoba"
AMU_PROFILE_SHA256 = "40e8ab9d6c220c27b93de3328798b2acf91c0cca9a21623441ba136398075d30"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(name, argv, cwd, env, calls, timeout=900):
    started = time.monotonic()
    result = subprocess.run(list(map(str, argv)), cwd=cwd, env=env,
                            capture_output=True, timeout=timeout)
    (cwd / f"{name}.stdout").write_bytes(result.stdout)
    (cwd / f"{name}.stderr").write_bytes(result.stderr)
    calls.append({"name": name, "exit": result.returncode,
                  "seconds": round(time.monotonic() - started, 3),
                  "stdoutSha256": sha(result.stdout), "stderrSha256": sha(result.stderr)})
    (cwd / "calls.json").write_text(json.dumps(calls, indent=2) + "\n")
    if result.returncode != 0 or result.stderr:
        raise RuntimeError(f"{name} failed: exit={result.returncode} "
                           f"stderr={result.stderr.decode(errors='replace')[-2000:]}")
    return result


def main(amu, out):
    assert platform.system() == "Linux" and platform.machine() in ("x86_64", "amd64"), \
        "native Linux x86_64 runner required"
    amu = Path(amu).resolve()
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    revision = subprocess.check_output(["git", "-C", str(amu), "rev-parse", "HEAD"], text=True).strip()
    if revision != AMU_COMMIT:
        raise RuntimeError(f"Amu source revision mismatch: expected {AMU_COMMIT}, got {revision}")
    binary = amu / "bin/amu-linux-x86_64"
    runner_source = amu / "seed/x86_64-kx64-runner.kotoba"
    profile_source = amu / AMU_PROJECT_PROFILE
    if sha(binary.read_bytes()) != AMU_BINARY_SHA256:
        raise RuntimeError("pinned Amu compiler digest mismatch")
    if sha(runner_source.read_bytes()) != AMU_RUNNER_SHA256:
        raise RuntimeError("pinned Amu KX64 runner-source digest mismatch")
    profile = profile_source.read_bytes()
    if sha(profile) != AMU_PROFILE_SHA256:
        raise RuntimeError("pinned experimental Amu x86 project-profile digest mismatch")

    manifest = (amu / "seed/FULL-MANIFEST").read_text(encoding="ascii").splitlines()
    modules = [line for line in manifest if line and not line.startswith("#")]
    if len(modules) != 60 or "seed/98-x86_64-project.kotoba" not in modules:
        raise RuntimeError("pinned Amu FULL-MANIFEST differs from the expected 60-module closure")
    project_source = out / "amu-project.kotoba"
    with project_source.open("wb") as unity:
        for module in modules:
            source = profile if module == "seed/98-x86_64-project.kotoba" else (amu / module).read_bytes()
            unity.write(source + b"\n")

    data_dir = out / "data"
    data_dir.mkdir()
    source_root = out / "src"
    staged = {}
    for module, source in (*MODULES, (FIXTURE_NAME, FIXTURE)):
        relative = (Path("sqlite") / source.name) if module == FIXTURE_NAME \
            else Path("kotoba/sqlite") / source.name
        destination = source_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        staged[module] = destination

    graph = dict(MODULES)
    graph[FIXTURE_NAME] = FIXTURE
    staged_graph = {module: staged[module] for module in graph}
    entry = staged[FIXTURE_NAME]
    lock_lines = ["KSL2", f"entry {entry}"]
    lock_lines.extend(f"module {module} {path}"
                      for module, path in sorted(staged_graph.items()))
    lock_lines.extend(f"file {sha(path.read_bytes())} {path}"
                      for path in sorted(staged_graph.values(), key=lambda item: item.as_posix()))
    lock = out / "sqlite-notepad.ksl"
    lock.write_text("\n".join(lock_lines) + "\n", encoding="ascii")

    env = {"PATH": "/nonexistent", "KEXE_STACK_BYTES": "8388608",
           "KEXE_CAP_RESOURCES_35": str(out)}
    calls = []
    compiler = binary
    generations = []
    for index in range(1, 4):
        image = out / f"amu-F{index}.elf"
        run(f"derive-F{index}", [compiler, "compile", project_source, "--target", "x86_64-linux",
            "--output", image, "--format", "static"], out, env, calls, timeout=1800)
        image.chmod(0o700)
        generations.append({"sha256": sha(image.read_bytes()), "bytes": image.stat().st_size})
        compiler = image
    if generations[0] != generations[1] or generations[1] != generations[2]:
        raise RuntimeError(f"Amu selfhost project compiler did not reach F1=F2=F3: {generations}")

    artifact = out / "sqlite-notepad.kx64"
    run("compile-sqlite-notepad", [compiler, "compile", entry, "--target", "x86_64-linux",
        "--output", artifact, "--format", "kx64-v1", "--source-lock", lock,
        "--source-lock-sha256", sha(lock.read_bytes())], out, env, calls)
    header, separator, payload = artifact.read_bytes().partition(b"\n\n")
    match = re.fullmatch(rb"KX64V1 x86_64-linux sysv-ctx-v11 ([0-9]+) 0", header)
    if not separator or not match or len(payload) != int(match.group(1)):
        raise RuntimeError("Amu compiler emitted an invalid x86_64 KX64 artifact")
    payload_path = out / "sqlite-notepad.payload"
    payload_path.write_bytes(payload)

    # The compiler's FS35 admission root is the temporary output directory;
    # stage the already digest-verified runner source under that root before
    # invoking the selfhosted compiler.
    staged_runner_source = out / "x86_64-kx64-runner.kotoba"
    staged_runner_source.write_bytes(runner_source.read_bytes())
    if sha(staged_runner_source.read_bytes()) != AMU_RUNNER_SHA256:
        raise RuntimeError("staged Amu KX64 runner-source digest mismatch")
    runner = out / "x86_64-kx64-runner.elf"
    run("compile-kx64-runner", [compiler, "compile", staged_runner_source, "--target", "x86_64-linux",
        "--output", runner, "--format", "kx64-runner"], out, env, calls)
    runner.chmod(0o700)

    database = data_dir / "legacy.db"
    original = DATABASE_FIXTURE.read_bytes()
    database.write_bytes(original)
    input_sha256 = sha(original)
    runtime_env = dict(PATH="/nonexistent", KEXE_ALLOW=ALLOW,
                       KEXE_CAP_RESOURCES_35=str(out), KEXE_STACK_BYTES="8388608",
                       KEXE_STRUCTURED_REPORT="1", KEXE_COMMAND="1", KEXE_FUEL="1000000000")
    result = run("sqlite-legacy-existing-file-mutation-x86", [runner, payload_path, "0", "0",
        "x86_64", ALLOW, "--", "data/legacy.db"], out, runtime_env, calls, timeout=300)
    if not re.search(rb":result 0\b", result.stdout):
        raise RuntimeError("native Kotoba guest did not report successful legacy SQLite mutation")
    if sha(database.read_bytes()) == input_sha256:
        raise RuntimeError("native Kotoba guest did not publish a changed SQLite image")
    if sha(DATABASE_FIXTURE.read_bytes()) != input_sha256:
        raise RuntimeError("tracked standard SQLite input fixture changed")

    receipt = {
        "schema": "kotoba.native-sqlite-x86.v1",
        "qualification": "bounded standard cron_notepad mutation through Amu KX64 on native Linux x86_64",
        "amuRevision": revision,
        "amuCompilerSha256": AMU_BINARY_SHA256,
        "amuProjectProfile": AMU_PROJECT_PROFILE,
        "amuProjectProfileSha256": AMU_PROFILE_SHA256,
        "projectUnitySha256": sha(project_source.read_bytes()),
        "compilerGenerations": generations,
        "compilerSha256": sha(compiler.read_bytes()),
        "runnerSourceSha256": sha(runner_source.read_bytes()),
        "runnerSha256": sha(runner.read_bytes()),
        "artifactSha256": sha(artifact.read_bytes()),
        "payloadSha256": sha(payload),
        "sourceLockSha256": sha(lock.read_bytes()),
        "fixture": DATABASE_FIXTURE.name,
        "fixtureSha256": input_sha256,
        "publishedDatabaseSha256": sha(database.read_bytes()),
        "allowedWires": ALLOW,
        "hostSqliteOracle": False,
        "result": "Kotoba read a standard SQLite cron_notepad file, updated an existing row, inserted another job's row, deleted one job, published through scoped FS2/FS35, reopened the image, and checked preserved/updated/deleted values through Kotoba",
        "calls": calls,
    }
    (out / "native-sqlite-x86.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--amu", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    main(args.amu, args.output)
