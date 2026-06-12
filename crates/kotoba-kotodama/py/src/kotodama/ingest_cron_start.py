"""Kubernetes CronJob entrypoint for durable ingest process starts.

The CronJob only creates the Zeebe process instance. The BPMN process owns
`houbun.createRun`, so run persistence happens exactly once inside the durable
workflow instead of before the token exists.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from kotodama.ingest.core import IngestRun
from kotodama.ingest.zeebe import start_process_if_configured


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start a durable ingest BPMN process.")
    parser.add_argument("--family", default="houbun")
    parser.add_argument("--source-id", default="egov-jpn")
    parser.add_argument("--mode", default="delta")
    parser.add_argument("--process-id", default="ingest_houbun_egov_jpn_delta")
    parser.add_argument("--requested-by", default="k8s-cron")
    parser.add_argument("--law-id", default="")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--since", default="")
    parser.add_argument("--max-articles", type=int, default=80)
    parser.add_argument("--crawl", default="CC-MAIN-2026-12")
    parser.add_argument("--domain-filter", default="")
    parser.add_argument("--phases", default="")
    parser.add_argument("--min-pages", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--surface", default="")
    parser.add_argument("--shard-id", type=int, default=-1)
    parser.add_argument("--cc-data-dir", default="")
    parser.add_argument("--allow-subprocess", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    input_payload: dict[str, Any] = {
        "lawId": args.law_id,
        "limit": args.limit,
        "offset": args.offset,
        "since": args.since,
        "maxArticles": args.max_articles,
        "crawl": args.crawl,
        "domainFilter": args.domain_filter,
        "phases": args.phases,
        "minPages": args.min_pages,
        "batchSize": args.batch_size,
        "surface": args.surface,
        "shardId": None if args.shard_id < 0 else args.shard_id,
        "ccDataDir": args.cc_data_dir,
        "allowSubprocess": args.allow_subprocess,
        "dryRun": args.dry_run,
    }
    input_json = json.dumps(input_payload, sort_keys=True, separators=(",", ":"))
    run = IngestRun(
        ingest_family=args.family,
        source_id=args.source_id,
        mode=args.mode,
        status="planned",
        bpmn_process_id=args.process_id,
        requested_by=args.requested_by,
        input_json=input_json,
    ).with_run_id()
    variables = {
        "runId": run.run_id,
        "ingestFamily": run.ingest_family,
        "sourceId": run.source_id,
        "mode": run.mode,
        "inputJson": input_json,
        "requestedBy": run.requested_by,
        "lawId": args.law_id,
        "limit": args.limit,
        "offset": args.offset,
        "since": args.since,
        "maxArticles": args.max_articles,
        "crawl": args.crawl,
        "domainFilter": args.domain_filter,
        "phases": args.phases,
        "minPages": args.min_pages,
        "batchSize": args.batch_size,
        "surface": args.surface,
        "shardId": None if args.shard_id < 0 else args.shard_id,
        "ccDataDir": args.cc_data_dir,
        "allowSubprocess": args.allow_subprocess,
        "dryRun": args.dry_run,
    }
    instance_key, zeebe_error = start_process_if_configured(args.process_id, variables)
    print(
        json.dumps(
            {
                "ok": instance_key is not None,
                "runId": run.run_id,
                "status": "started" if instance_key else "failed",
                "bpmnProcessId": args.process_id,
                "zeebeProcessInstanceKey": instance_key,
                "zeebeError": zeebe_error,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
