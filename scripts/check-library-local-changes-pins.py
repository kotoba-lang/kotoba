#!/usr/bin/env python3
"""Audit current bytes named by a bundled library's local-changes ledger.

This is a source identity preflight, not a native build or product verdict.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def audit(root: Path, manifest_path: Path) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir() or manifest_path.is_symlink():
        raise ValueError("root or manifest is not a regular local source")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != "kotoba.library-local-changes.v1":
        raise ValueError("unknown local-changes schema")
    pins = {}
    counts = {}
    for group in ("files", "added"):
        entries = manifest.get(group)
        if not isinstance(entries, dict):
            raise ValueError(f"missing {group} entries")
        counts[group] = len(entries)
        for name, meta in entries.items():
            relative = Path(name)
            if (relative.is_absolute() or not relative.parts
                    or any(part in (".", "..") for part in relative.parts)):
                raise ValueError(f"invalid {group} path: {name}")
            expected = meta.get("sha256") if isinstance(meta, dict) else None
            if not isinstance(expected, str) or not SHA256.fullmatch(expected):
                raise ValueError(f"invalid {group} sha256: {name}")
            path = root / relative
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
                raise ValueError(f"missing or linked {group} source: {name}")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError(f"stale {group} pin: {name}: {expected} != {actual}")
            previous = pins.setdefault(name, expected)
            if previous != expected:
                raise ValueError(f"conflicting files/added pin: {name}")
    return {"status": "PASS_SOURCE_PIN_AUDIT", "files": counts["files"],
            "added": counts["added"], "uniquePaths": len(pins)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest = args.manifest or args.root / "local-changes.json"
    try:
        print(json.dumps(audit(args.root, manifest), sort_keys=True))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(f"SOURCE_PIN_AUDIT_REFUSED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
