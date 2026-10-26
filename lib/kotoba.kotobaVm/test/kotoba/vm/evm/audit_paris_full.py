"""Audit a native full-state run against its pinned Paris manifest and ELF.

This audits orchestration receipts; fixture execution and comparison remain native.
Usage: python3 audit_paris_full.py /path/to/paris-full v45
"""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import sys


def directory_digest(files) -> str:
    digest = hashlib.sha256()
    for file in sorted(files, key=lambda item: item.name):
        digest.update(file.name.encode())
        digest.update(b"\0")
        digest.update(file.read_bytes())
        digest.update(b"\n")
    return digest.hexdigest()


def audit(path: Path, version: str) -> dict:
    manifest_path = path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    expected = {case["id"]: case for case in manifest["cases"]}
    if len(expected) != len(manifest["cases"]):
        raise ValueError("duplicate case IDs in manifest")
    results = path / f"results-{version}"
    failures = path / f"failures-{version}"
    runs = path / f"runs-{version}"
    config = json.loads((path / f"run-{version}.json").read_text())
    artifact = path.parent / "native-project" / f"full-state-{version}.elf"

    result_ids = {f.name for f in results.iterdir() if f.is_file()}
    failure_files = sorted(failures.glob("*.json"))
    failure_ids = {f.stem for f in failure_files}
    passed_result_ids = set()
    policy_refusal_ids = []
    semantic_mismatch_ids = []
    actual_gas = {}
    for f in results.iterdir():
        if not f.is_file():
            continue
        fields = f.read_text(errors="replace").strip().split("~")
        case = expected.get(f.name)
        exception = case is not None and case["exception"] is not None
        if len(fields) > 1 and fields[1] in ("8", "10", "12"):
            policy_refusal_ids.append(f.name)
            continue
        if (case is None or len(fields) != 6 or fields[0] != f.name
                or (fields[1] == "11") != exception
                or (not exception and fields[2] != case["root"])
                or fields[3] != case["logs"] or fields[-1] != "pass"
                or not fields[4].isdigit()):
            semantic_mismatch_ids.append(f.name)
        else:
            passed_result_ids.add(f.name)
            actual_gas[f.name] = int(fields[4])

    # GeneralStateTests specifies root/logs but not gasUsed. Its pinned
    # BlockchainTests projection supplies the independent block gasUsed.
    fixture_roots = list(path.glob("tests-*/BlockchainTests/GeneralStateTests"))
    if len(fixture_roots) != 1:
        raise ValueError("expected exactly one pinned BlockchainTests tree")
    by_path = defaultdict(list)
    for ident in passed_result_ids:
        by_path[expected[ident]["path"]].append(expected[ident])
    gas_compared = 0
    rejected_compared = 0
    gas_mismatches = []
    missing_fixture_ids = []
    for relative_path, cases in by_path.items():
        fixture_path = fixture_roots[0] / relative_path
        if not fixture_path.exists():
            missing_fixture_ids.extend(case["id"] for case in cases)
            continue
        fixture = json.loads(fixture_path.read_text())
        for case in cases:
            ident = case["id"]
            indexes = case["indexes"]
            if relative_path.startswith("Pyspecs/"):
                key = case["name"].replace("[fork_Paris-state_test", "[fork_Paris-blockchain_test")
            else:
                key = (f"{case['name']}_d{indexes['data']}g{indexes['gas']}"
                       f"v{indexes['value']}_Paris")
            entry = fixture.get(key)
            if entry is None or not entry.get("blocks") or ident not in actual_gas:
                missing_fixture_ids.append(ident)
                continue
            block = entry["blocks"][0]
            expected_gas_hex = block.get("blockHeader", {}).get("gasUsed")
            if expected_gas_hex is None:
                rejected_compared += 1
                if (block.get("expectException") != case["exception"]
                        or actual_gas[ident] != 0):
                    gas_mismatches.append(ident)
            else:
                gas_compared += 1
                if (case["exception"] is not None
                        or actual_gas[ident] != int(expected_gas_hex, 16)):
                    gas_mismatches.append(ident)

    receipt_files = sorted(runs.glob("*.json"))
    receipts = [json.loads(f.read_text()) for f in receipt_files]
    abnormal = [r for r in receipts if r.get("exit") != 0]
    failure_reasons = Counter(json.loads(f.read_text())["reason"] for f in failure_files)
    missing = expected.keys() - result_ids - failure_ids
    artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return {
        "version": version,
        "manifestCases": len(expected),
        "nativeResults": len(result_ids),
        "passedResults": len(passed_result_ids),
        "hostFailures": len(failure_ids),
        "resultsSha256": directory_digest(f for f in results.iterdir() if f.is_file()),
        "hostFailuresSha256": directory_digest(failure_files),
        "batchReceiptsSha256": directory_digest(receipt_files),
        "missingCount": len(missing),
        "firstMissingIds": sorted(missing)[:20],
        "duplicateResultAndFailureIds": sorted(result_ids & failure_ids),
        "unknownResultIds": sorted(result_ids - expected.keys()),
        "unknownFailureIds": sorted(failure_ids - expected.keys()),
        "nonconformingResultIds": sorted(policy_refusal_ids + semantic_mismatch_ids),
        "policyRefusalIds": sorted(policy_refusal_ids),
        "semanticMismatchIds": sorted(semantic_mismatch_ids),
        "gasUsedCompared": gas_compared,
        "rejectedTransactionsCompared": rejected_compared,
        "gasUsedMismatchIds": sorted(gas_mismatches),
        "missingBlockchainFixtureIds": sorted(missing_fixture_ids),
        "failureIds": sorted(failure_ids),
        "failureReasons": dict(failure_reasons),
        "batchReceipts": len(receipts),
        "abnormalBatchExits": [
            {k: r.get(k) for k in ("batch", "round", "exit", "unfinishedCase")}
            for r in abnormal
        ],
        "artifactSha256": artifact_hash,
        "manifestSha256": manifest_hash,
        "artifactSha256Matches": artifact_hash == config["artifactSha256"],
        "manifestSha256Matches": manifest_hash == config["manifestSha256"],
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: audit_paris_full.py PARIS_FULL_DIRECTORY VERSION")
    print(json.dumps(audit(Path(sys.argv[1]), sys.argv[2]), ensure_ascii=False, indent=2))
