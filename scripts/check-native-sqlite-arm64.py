#!/usr/bin/env python3
"""Compile and execute pinned Kotoba SQLite fixtures through Amu selfhost.

Python stages and hashes source bytes and observes native process results only.
The Kotoba fixtures assert SQLite behavior; no host SQLite implementation is
used by this gate.
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
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
FIXTURES = (
    ("sqlite.notepad-linux-storage", PACKAGE / "test/native/notepad-linux-storage.kotoba"),
    ("sqlite.notepad-sidecar-refusal", PACKAGE / "test/native/notepad-sidecar-refusal.kotoba"),
    ("sqlite.notepad-existing-file-mutation", PACKAGE / "test/native/notepad-existing-file-mutation.kotoba"),
)
LEGACY_FIXTURE = PACKAGE / "test/fixtures/legacy-cron-notepad-20261102.sqlite"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(name, argv, cwd, env, calls, timeout=900):
    result = subprocess.run(list(map(str, argv)), cwd=cwd, env=env,
                           capture_output=True, timeout=timeout)
    (cwd / (name + ".stdout")).write_bytes(result.stdout)
    (cwd / (name + ".stderr")).write_bytes(result.stderr)
    calls.append({"name": name, "exit": result.returncode,
                  "stdoutSha256": hashlib.sha256(result.stdout).hexdigest(),
                  "stderrSha256": hashlib.sha256(result.stderr).hexdigest()})
    (cwd / "calls.json").write_text(json.dumps(calls, indent=2) + "\n")
    if result.returncode != 0 or result.stderr:
        raise RuntimeError(f"{name} failed: exit={result.returncode} stderr={result.stderr[-1200:]!r}")


def main(amu, compiler, out, amu_pin=None):
    assert platform.system() == "Linux" and platform.machine() in ("aarch64", "arm64"), \
        "native ARM64 Linux runner required"
    amu = Path(amu).resolve()
    compiler = Path(compiler).resolve()
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "data").mkdir()
    legacy_fixture_sha256 = sha(LEGACY_FIXTURE)
    (out / "data/legacy.db").write_bytes(LEGACY_FIXTURE.read_bytes())
    source_root = out / "src"
    staged = {}
    for module, source in (*MODULES, *FIXTURES):
        relative = (Path("sqlite") / source.name) if module.startswith("sqlite.") else Path("kotoba/sqlite") / source.name
        destination = source_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        staged[module] = destination

    calls = []
    env = dict(os.environ, PATH="/nonexistent", KEXE_ALLOW="35,37,38,39",
               KEXE_CAP_RESOURCES_35=":".join(map(str, (ROOT, amu, out))),
               KEXE_STACK_BYTES="8388608")
    guest_env = dict(os.environ, PATH="/nonexistent", KEXE_ALLOW="35,37,38,39",
                     KEXE_CAP_RESOURCES_35=str(out), KEXE_STACK_BYTES="8388608",
                     KEXE_COMMAND="1")
    receipts = []
    for fixture_module, _ in FIXTURES:
        lock_lines = ["KSL1", f"entry {staged[fixture_module]}"]
        graph = dict(MODULES)
        graph[fixture_module] = next(source for name, source in FIXTURES if name == fixture_module)
        graph_paths = {module: staged[module] for module in graph}
        lock_lines.append(f"root {source_root}")
        lock_lines.extend(f"file {sha(path)} {path}"
                          for _, path in sorted(graph_paths.items(), key=lambda item: item[1].as_posix()))
        lock = out / (fixture_module.replace(".", "-") + ".ksl")
        lock.write_text("\n".join(lock_lines) + "\n")
        stem = fixture_module.replace(".", "-")
        payload = out / (stem + ".kseed")
        image = out / (stem + ".elf")
        run("compile-" + fixture_module.rsplit(".", 1)[-1],
            [compiler, "compile", staged[fixture_module], "--target", "aarch64-macos",
             "--output", payload, "--source-path", source_root, "--source-lock", lock,
             "--source-lock-sha256", sha(lock)], out, env, calls)
        runner = amu / "seed/x86_64-kx64-runner.kotoba"
        run("pack-" + fixture_module.rsplit(".", 1)[-1],
            [compiler, "compile", runner, "--target", "aarch64-linux", "--output", image,
             "--format", "packed", "--payload", payload], out, env, calls)
        image.chmod(0o755)
        receipts.append({"fixture": fixture_module, "image": image.name,
                         "imageSha256": sha(image), "payloadSha256": sha(payload),
                         "runnerSha256": sha(runner), "sourceLockSha256": sha(lock)})

    positive = out / receipts[0]["image"]
    database = out / "data/overflow.db"
    run("sqlite-upsert-positive-and-readback", [positive, database], out, guest_env, calls, timeout=300)
    if not database.is_file():
        raise RuntimeError("Kotoba positive fixture did not publish its SQLite image")
    database_before = sha(database)

    refusal = out / receipts[1]["image"]
    sidecar_cases = []
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = Path(str(database) + suffix)
        sidecar.write_bytes(b"native SQLite sidecar refusal control\n")
        sidecar_before = sha(sidecar)
        run("sqlite-sidecar-refusal-" + suffix[1:], [refusal, database], out, guest_env, calls, timeout=300)
        if sha(database) != database_before or sha(sidecar) != sidecar_before:
            raise RuntimeError(f"SQLite database or sidecar changed while {suffix} existed")
        sidecar_cases.append({"suffix": suffix, "sidecarSha256": sidecar_before,
                              "databaseSha256": database_before, "preserved": True})
        sidecar.unlink()

    legacy_mutation = out / receipts[2]["image"]
    legacy_path = out / "data/legacy.db"
    run("sqlite-existing-file-mutation", [legacy_mutation, "data/legacy.db"], out, guest_env,
        calls, timeout=300)

    receipt = {
        "schema": "kotoba.sqlite.native-linux-arm64.v1",
        "platform": [platform.system(), platform.machine()],
        "amuPin": amu_pin or subprocess.run(["git", "-C", str(amu), "rev-parse", "HEAD"],
                                              check=True, capture_output=True, text=True).stdout.strip(),
        "compiler": {"path": str(compiler), "sha256": sha(compiler)},
        "runtime": "Amu selfhost F2; native aarch64-linux static Kotoba; PATH=/nonexistent",
        "sources": {module: {"path": str(path.relative_to(out)), "sha256": sha(path)}
                    for module, path in sorted(staged.items())},
        "fixtures": receipts,
        "databaseSha256": database_before,
        "legacyFixtureSha256": legacy_fixture_sha256,
        "legacyMutation": {
            "fixture": LEGACY_FIXTURE.name,
            "image": legacy_mutation.name,
            "inputDatabase": "SQLite 3.54.1 standard file generated once with three existing rows",
            "nativeResult": "updated an existing row, inserted a second row for a different job, deleted one job, published atomically, reopened and read back through Kotoba",
        },
        "sidecarRefusals": sidecar_cases,
        "result": "Kotoba positive upsert/readback, pre-existing WAL/SHM/rollback-journal refusals, and existing SQLite database mutation/reopen passed",
        "hostSqliteOracle": False,
    }
    (out / "native-sqlite-arm64.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--amu", required=True)
    parser.add_argument("--compiler", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--amu-pin", help="source revision when the mounted checkout has external git metadata")
    args = parser.parse_args()
    main(args.amu, args.compiler, args.output, args.amu_pin)
