"""Batch driver for the PhenotypeAgent fleet, mirroring the
``run_batch_spec_gen.py`` pattern from ADR-2605171300.

Reads a list of DIDs (from stdin or ``--from``), generates a
PhenotypeAgent file per DID with bounded concurrency. Deterministic by
default (no LLM call); pass ``--llm`` to use the OpenRouter / Murakumo
fallback for event_weights specialization.

Usage:
  cat dids.txt | uv run python -m scripts.run_phenotype_batch --concurrency 10
  uv run python -m scripts.run_phenotype_batch --from dids.txt --llm
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve()
_PKG_SRC = _HERE.parent.parent / "src"
if str(_PKG_SRC) not in sys.path:
    sys.path.insert(0, str(_PKG_SRC))

from scripts.gen_phenotype_agent import write_agent  # noqa: E402


def _read_dids(path: Path | None) -> list[str]:
    if path is None:
        text = sys.stdin.read()
    else:
        text = path.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate PhenotypeAgent fleet from a DID list")
    p.add_argument("--from", dest="src", type=Path, default=None, help="Path to DID list (default stdin)")
    p.add_argument("--concurrency", type=int, default=10)
    p.add_argument("--llm", action="store_true", help="Forwarded to gen_phenotype_agent")
    p.add_argument("--output-dir", type=Path, default=None)
    args = p.parse_args(argv)

    dids = _read_dids(args.src)
    if not dids:
        print("no DIDs to process", file=sys.stderr)
        return 1

    start = time.monotonic()
    written = 0
    errors: list[tuple[str, str]] = []

    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(write_agent, did, args.output_dir): did for did in dids}
        for fut in cf.as_completed(futures):
            did = futures[fut]
            try:
                fut.result()
                written += 1
            except Exception as exc:  # noqa: BLE001
                errors.append((did, str(exc)))

    elapsed = time.monotonic() - start
    print(f"wrote {written}/{len(dids)} agents in {elapsed:.2f}s")
    if errors:
        print(f"{len(errors)} error(s):", file=sys.stderr)
        for did, msg in errors[:10]:
            print(f"  {did}: {msg}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
