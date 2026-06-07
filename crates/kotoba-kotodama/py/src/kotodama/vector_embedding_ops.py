"""Operator CLI for vector embedding LangServer starts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from kotodama.ingest.zeebe import start_process_if_configured

DEFAULT_PROCESS_ID = "vector_embedding_backfill_batch"
DEFAULT_BPMN = (
    Path(__file__).resolve().parents[5]
    / "00-contracts/bpmn/com/etzhayyim/vector-embedding/backfillBatch.bpmn"
)


def _json_default(value: Any) -> str:
    return str(value)


async def _deploy_async(path: Path, tenant_id: str | None = None) -> dict[str, Any]:
    xml = path.read_text(encoding="utf-8")
    return {
        "ok": True,
        "runtimeKind": "k8s-langserver",
        "agentGatewayMcpUrl": os.environ.get(
            "AGENTGATEWAY_MCP_URL",
            "http://agentgateway-mcp.mitama-udf.svc.cluster.local:8080",
        ),
        "resource": str(path),
        "tenantId": tenant_id or "",
        "contractBytes": len(xml.encode("utf-8")),
        "message": "BPMN retained as process contract/audit document; execution runs through LangServer.",
    }


def deploy_bpmn(path: str = "", tenant_id: str = "") -> dict[str, Any]:
    bpmn_path = Path(path).resolve() if path else DEFAULT_BPMN
    if not bpmn_path.is_file():
        return {"ok": False, "error": f"BPMN file not found: {bpmn_path}"}
    try:
        return asyncio.run(_deploy_async(bpmn_path, tenant_id or None))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "resource": str(bpmn_path)}


def start_backfill(
    *,
    surface: str,
    limit: int,
    shard_id: int | None = None,
    dry_run: bool = False,
    emotion_only: bool = False,
    process_id: str = DEFAULT_PROCESS_ID,
    requested_by: str = "operator",
) -> dict[str, Any]:
    variables = {
        "surface": surface,
        "limit": max(1, min(int(limit or 100), 1000)),
        "shardId": shard_id,
        "dryRun": bool(dry_run),
        "emotionOnly": bool(emotion_only),
        "requestedBy": requested_by,
        "ingestFamily": "vector-embedding",
        "sourceId": surface,
        "mode": "backfill",
    }
    instance_key, error = start_process_if_configured(process_id, variables)
    return {
        "ok": instance_key is not None,
        "bpmnProcessId": process_id,
        "langserverRunId": instance_key,
        "langserverError": error,
        "variables": variables,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vector embedding BPMN ops.")
    sub = parser.add_subparsers(dest="command", required=True)

    deploy = sub.add_parser("deploy")
    deploy.add_argument("--bpmn", default="")
    deploy.add_argument("--tenant-id", default="")

    start = sub.add_parser("start")
    start.add_argument("--surface", choices=["actors", "posts"], required=True)
    start.add_argument("--limit", type=int, default=100)
    start.add_argument("--shard-id", type=int, default=-1)
    start.add_argument("--dry-run", action="store_true")
    start.add_argument("--emotion-only", action="store_true")
    start.add_argument("--process-id", default=DEFAULT_PROCESS_ID)
    start.add_argument("--requested-by", default="operator")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "deploy":
        out = deploy_bpmn(path=args.bpmn, tenant_id=args.tenant_id)
    else:
        out = start_backfill(
            surface=args.surface,
            limit=args.limit,
            shard_id=None if args.shard_id < 0 else args.shard_id,
            dry_run=args.dry_run,
            emotion_only=args.emotion_only,
            process_id=args.process_id,
            requested_by=args.requested_by,
        )
    print(json.dumps(out, ensure_ascii=False, sort_keys=True, default=_json_default))


if __name__ == "__main__":
    main()
