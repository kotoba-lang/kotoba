"""Export public-domain colorization process-mining logs from kotoba Datom log."""

from __future__ import annotations

import argparse
import csv
import json

import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

EVENT_COLUMNS = (
    "case_id",
    "activity",
    "timestamp",
    "resource",
    "lifecycle",
    "work_id",
    "artifact_id",
    "detail",
)


def _fetch_event_rows(limit: int | None = None) -> list[dict[str, Any]]:
    client = get_kotoba_client()
    query_edn = """
    [:find ?case_id ?activity ?timestamp ?resource ?lifecycle ?work_id ?artifact_id ?detail
     :where
     [?e :view_pd_color_process_event_log/case_id ?case_id]
     [?e :view_pd_color_process_event_log/activity ?activity]
     [?e :view_pd_color_process_event_log/timestamp ?timestamp]
     [?e :view_pd_color_process_event_log/resource ?resource]
     [?e :view_pd_color_process_event_log/lifecycle ?lifecycle]
     [?e :view_pd_color_process_event_log/work_id ?work_id]
     [?e :view_pd_color_process_event_log/artifact_id ?artifact_id]
     [?e :view_pd_color_process_event_log/detail ?detail]]
    """
    rows_tuples = client.q(query_edn)
    # Convert tuples to dicts
    rows = [dict(zip(EVENT_COLUMNS, row, strict=False)) for row in rows_tuples]

    # R0: Order By and Limit applied in Python as q() doesn't directly support ORDER BY in the same way as SQL.
    rows.sort(key=lambda r: (str(r.get("case_id") or ""), str(r.get("timestamp") or ""), str(r.get("activity") or "")))
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return rows


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_case[str(row.get("case_id") or "")].append(row)

    variants: Counter[str] = Counter()
    published_cases = []
    for case_rows in by_case.values():
        activities = []
        for row in sorted(case_rows, key=lambda r: (str(r.get("timestamp") or ""), str(r.get("activity") or ""))):
            activity = str(row.get("activity") or "")
            if activity.startswith("04 Localization ready"):
                activity = "04 Localization ready"
            if not activities or activities[-1] != activity:
                activities.append(activity)
        variant = " > ".join(activities)
        variants[variant] += 1
        if any(row.get("activity") == "05 Published" for row in case_rows):
            published_cases.append(case_rows)

    latest_published = None
    published_events = [row for row in rows if row.get("activity") == "05 Published"]
    if published_events:
        latest_published = max(published_events, key=lambda row: str(row.get("timestamp") or ""))

    return {
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": "kotoba Datom log view_pd_color_process_event_log",
        "eventCount": len(rows),
        "caseCount": len(by_case),
        "publishedCaseCount": len(published_cases),
        "activityCount": len({str(row.get("activity") or "") for row in rows}),
        "variants": [
            {"variant": variant, "count": count}
            for variant, count in variants.most_common()
        ],
        "latestPublishedCase": latest_published,
    }


def _write_csv(rows: list[dict[str, Any]], output_path: str | None) -> None:
    out = open(output_path, "w", newline="", encoding="utf-8") if output_path else sys.stdout
    try:
        writer = csv.DictWriter(out, fieldnames=EVENT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if output_path:
            out.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("csv", "summary"), help="export format")
    parser.add_argument("--limit", type=int, default=0, help="optional row limit")
    parser.add_argument("--output", default="", help="write output to this path instead of stdout")
    args = parser.parse_args(argv)



    rows = _fetch_event_rows(args.limit or None)
    if args.command == "csv":
        _write_csv(rows, args.output or None)
    else:
        payload = _summary(rows)
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text + "\n")
        else:
            print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
