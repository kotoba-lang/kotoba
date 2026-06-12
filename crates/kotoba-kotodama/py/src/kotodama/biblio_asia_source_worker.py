"""Run one Asia bibliographic source ingest in an isolated process."""

from __future__ import annotations

import argparse
import json
import sys
import time

from kotodama.primitives.biblio_open_data import task_biblio_asia_open_data_actor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--max-records", type=int, default=200)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--max-ocr-pages", type=int, default=2)
    parser.add_argument("--webp-quality", type=int, default=82)
    args = parser.parse_args(argv)

    started = time.time()
    try:
        result = task_biblio_asia_open_data_actor(
            sourceIds=[args.source],
            maxRecordsPerSource=args.max_records,
            fetchEntrypoints=True,
            ocr=args.ocr,
            maxOcrPagesPerSource=args.max_ocr_pages,
            webpQuality=args.webp_quality,
        )
        out = {
            "source": args.source,
            "seconds": round(time.time() - started, 1),
            "ok": result.get("ok"),
            "runId": result.get("runId"),
            "seen": result.get("rawRecordsSeen"),
            "inserted": result.get("rawRecordsInserted"),
            "entities": result.get("entitiesInserted"),
            "identifiers": result.get("identifiersInserted"),
            "pageAssets": result.get("pageAssetsInserted"),
            "ocrTexts": result.get("ocrTextsInserted"),
            "ocrErrors": result.get("ocrErrors"),
            "error": result.get("error"),
        }
    except Exception as exc:
        out = {
            "source": args.source,
            "seconds": round(time.time() - started, 1),
            "ok": False,
            "error": repr(exc),
        }
    print(json.dumps(out, ensure_ascii=False), flush=True)
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
