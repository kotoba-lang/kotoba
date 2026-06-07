"""CLI smoke for Python visibility over the live RisingWave schema."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from kotodama.rw_sql import live_migration_coverage


def evaluate_thresholds(
    payload: dict[str, Any],
    *,
    min_tables: int = 0,
    min_columns: int = 0,
    min_vertex_tables: int = 0,
    min_edge_tables: int = 0,
    min_graph_ratio: float = 0.0,
) -> list[dict[str, Any]]:
    checks = [
        ("tableCount", min_tables),
        ("columnCount", min_columns),
        ("vertexTableCount", min_vertex_tables),
        ("edgeTableCount", min_edge_tables),
    ]
    failures: list[dict[str, Any]] = []
    for key, minimum in checks:
        if minimum and int(payload.get(key) or 0) < minimum:
            failures.append({"metric": key, "actual": payload.get(key), "minimum": minimum})
    if min_graph_ratio and float(payload.get("graphTableRatio") or 0.0) < min_graph_ratio:
        failures.append(
            {
                "metric": "graphTableRatio",
                "actual": payload.get("graphTableRatio"),
                "minimum": min_graph_ratio,
            }
        )
    return failures


def build_coverage_payload(
    schema: str = "public",
    *,
    min_tables: int = 0,
    min_columns: int = 0,
    min_vertex_tables: int = 0,
    min_edge_tables: int = 0,
    min_graph_ratio: float = 0.0,
) -> dict[str, Any]:
    coverage = live_migration_coverage(schema)
    payload = {
        "ok": True,
        "schema": schema,
        "tableCount": coverage.table_count,
        "columnCount": coverage.column_count,
        "vertexTableCount": coverage.vertex_table_count,
        "edgeTableCount": coverage.edge_table_count,
        "graphTableCount": coverage.graph_table_count,
        "graphTableRatio": coverage.graph_table_ratio,
    }
    failed_checks = evaluate_thresholds(
        payload,
        min_tables=min_tables,
        min_columns=min_columns,
        min_vertex_tables=min_vertex_tables,
        min_edge_tables=min_edge_tables,
        min_graph_ratio=min_graph_ratio,
    )
    if failed_checks:
        payload["ok"] = False
        payload["failedChecks"] = failed_checks
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report Python reflection coverage for Kysely-managed RisingWave schema",
    )
    parser.add_argument("--schema", default="public")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--min-tables", type=int, default=0)
    parser.add_argument("--min-columns", type=int, default=0)
    parser.add_argument("--min-vertex-tables", type=int, default=0)
    parser.add_argument("--min-edge-tables", type=int, default=0)
    parser.add_argument("--min-graph-ratio", type=float, default=0.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = build_coverage_payload(
            str(args.schema),
            min_tables=int(args.min_tables or 0),
            min_columns=int(args.min_columns or 0),
            min_vertex_tables=int(args.min_vertex_tables or 0),
            min_edge_tables=int(args.min_edge_tables or 0),
            min_graph_ratio=float(args.min_graph_ratio or 0.0),
        )
    except Exception as exc:  # noqa: BLE001 - CLI should emit machine-readable failure.
        payload = {"ok": False, "schema": str(args.schema), "error": str(exc)[:500]}
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            sort_keys=True,
        )
    )
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
