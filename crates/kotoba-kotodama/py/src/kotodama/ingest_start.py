"""Thin Kubernetes CronJob entrypoint for durable ingest starts."""

from __future__ import annotations

import argparse
import json
import sys

from kotodama.handlers.ingest import ingest_start


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--mode", default="delta")
    parser.add_argument("--requested-by", default="k8s-cron")
    parser.add_argument("--input-json", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = {
        "ingestFamily": args.family,
        "sourceId": args.source,
        "mode": args.mode,
        "requestedBy": args.requested_by,
        "inputJson": args.input_json,
        "dryRun": args.dry_run,
    }
    result = ingest_start(json.dumps(payload, separators=(",", ":")))
    print(result)
    try:
        decoded = json.loads(result)
    except json.JSONDecodeError:
        return 1
    return 0 if decoded.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
