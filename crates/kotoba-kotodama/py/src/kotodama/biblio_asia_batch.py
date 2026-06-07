"""Batch runner for India/China/Korea bibliographic source ingest."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any


DEFAULT_SOURCES = [
    "ind-crl-inb",
    "ind-ndli",
    "chn-nlc",
    "kor-nlk-openapi",
    "kor-nld-accessible",
    "ind-nli-opac",
    "kor-nlk-lod",
]

TRANSIENT_ERROR_MARKERS = (
    "cluster recovery",
    "table reader closed",
    "connection reset",
    "connection refused",
    "server closed the connection",
    "couldn't get a connection",
    "service is currently unavailable",
    "transport error",
    "not visible after insert",
    "read visibility may be stalled",
)


def _is_retryable(result: dict[str, Any]) -> bool:
    if result.get("ok"):
        return False
    text = " ".join(
        str(result.get(key) or "")
        for key in ("error", "stderr", "stdoutTail")
    ).lower()
    return any(marker in text for marker in TRANSIENT_ERROR_MARKERS)


def _run_source_once(args: argparse.Namespace, source: str) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "kotodama.biblio_asia_source_worker",
        "--source",
        source,
        "--max-records",
        str(args.max_records),
        "--max-ocr-pages",
        str(args.max_ocr_pages),
        "--webp-quality",
        str(args.webp_quality),
    ]
    if args.ocr:
        cmd.append("--ocr")
    env = os.environ.copy()
    env.setdefault("BIBLIO_KOHA_DETAIL_LIMIT", str(args.koha_detail_limit))
    env.setdefault("BIBLIO_HTTP_TIMEOUT_MAX_SEC", str(args.http_timeout_max_sec))
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=args.source_timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "source": source,
            "seconds": round(time.time() - started, 1),
            "ok": False,
            "timeout": True,
            "error": f"source timeout after {args.source_timeout_sec}s",
            "stderr": (exc.stderr or "")[-2000:],
        }
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    try:
        payload = json.loads(stdout.splitlines()[-1]) if stdout else {}
    except Exception:
        payload = {"source": source, "ok": False, "error": "worker emitted non-json output"}
    payload.setdefault("source", source)
    payload.setdefault("ok", proc.returncode == 0)
    payload["returnCode"] = proc.returncode
    if stderr:
        payload["stderr"] = stderr[-2000:]
    if stdout:
        payload["stdoutTail"] = stdout[-2000:]
    return payload


def _run_source(args: argparse.Namespace, source: str) -> dict[str, Any]:
    max_attempts = max(1, int(args.source_retries) + 1)
    last: dict[str, Any] | None = None
    for attempt in range(1, max_attempts + 1):
        result = _run_source_once(args, source)
        result["attempt"] = attempt
        result["maxAttempts"] = max_attempts
        retryable = _is_retryable(result)
        result["retryable"] = retryable
        last = result
        if result.get("ok") or not retryable or attempt >= max_attempts:
            return result
        print(
            json.dumps(
                {
                    "source": source,
                    "ok": False,
                    "attempt": attempt,
                    "maxAttempts": max_attempts,
                    "retryInSeconds": args.source_retry_delay_sec,
                    "error": result.get("error"),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        time.sleep(args.source_retry_delay_sec)
    return last or {"source": source, "ok": False, "error": "source did not run"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", dest="sources")
    parser.add_argument("--max-records", type=int, default=200)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--max-ocr-pages", type=int, default=2)
    parser.add_argument("--webp-quality", type=int, default=82)
    parser.add_argument("--source-timeout-sec", type=int, default=900)
    parser.add_argument(
        "--source-retries",
        type=int,
        default=int(os.environ.get("SOURCE_RETRIES", "2")),
    )
    parser.add_argument(
        "--source-retry-delay-sec",
        type=int,
        default=int(os.environ.get("SOURCE_RETRY_DELAY_SECONDS", "60")),
    )
    parser.add_argument("--http-timeout-max-sec", type=int, default=20)
    parser.add_argument("--koha-detail-limit", type=int, default=0)
    args = parser.parse_args(argv)

    started = time.time()
    results = []
    for source in args.sources or DEFAULT_SOURCES:
        result = _run_source(args, source)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        results.append(result)

    ok_count = sum(1 for item in results if item.get("ok"))
    summary = {
        "ok": ok_count == len(results),
        "sources": len(results),
        "successes": ok_count,
        "failures": len(results) - ok_count,
        "seconds": round(time.time() - started, 1),
    }
    print(json.dumps({"summary": summary, "results": results}, ensure_ascii=False), flush=True)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
