"""Public LINE/Telegram open-channel ingest primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import hashlib
import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


OWNER_DID = "did:web:os-messaging.etzhayyim.com"
ACTOR_ID = "sys.langserver.os-messaging.open-channels"
KNOWN_PLATFORMS = {"telegram", "line"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today() -> str:
    return _utc_now()[:10]


def _sha(prefix: str, *parts: Any) -> str:
    raw = "\x1f".join(str(p or "") for p in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def _clean(value: str, limit: int = 1000) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _meta(raw: str, name: str) -> str:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)["\']',
        rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.I)
        if match:
            return html.unescape(match.group(1)).strip()
    return ""


def _title(raw: str) -> str:
    og_title = _meta(raw, "og:title")
    if og_title:
        return og_title[:240]
    match = re.search(r"<title[^>]*>([\s\S]*?)</title>", raw, re.I)
    return _clean(match.group(1), 240) if match else ""


def _channel_vid(platform: str, channel_id: str) -> str:
    return f"at://{OWNER_DID}/com.etzhayyim.apps.osMessaging.openChannel/{platform}-{channel_id}"


def _message_vid(platform: str, message_id: str) -> str:
    return f"at://{OWNER_DID}/com.etzhayyim.apps.osMessaging.openMessage/{platform}-{message_id}"


def _run_vid(run_id: str) -> str:
    return f"at://{OWNER_DID}/com.etzhayyim.apps.osMessaging.openScraperRun/{run_id}"


def _canonical_seed(raw: dict[str, Any]) -> dict[str, str]:
    platform = str(raw.get("platform") or "").lower()
    channel_url = str(raw.get("channelUrl") or raw.get("channel_url") or raw.get("url") or "").strip()
    channel_id = str(raw.get("channelId") or raw.get("channel_id") or "").strip().lstrip("@")
    if platform == "telegram" and not channel_url and channel_id:
        channel_url = f"https://t.me/s/{urllib.parse.quote(channel_id)}"
    if platform == "telegram" and "t.me/" in channel_url and not channel_id:
        channel_id = channel_url.rstrip("/").rsplit("/", 1)[-1].lstrip("@")
    if platform == "line" and not channel_id and channel_url:
        channel_id = _sha("line", channel_url)
    return {
        "platform": platform,
        "channel_id": channel_id,
        "channel_url": channel_url,
        "country": str(raw.get("country") or "").upper(),
        "language": str(raw.get("language") or "").lower(),
    }


def _fetch(url: str, timeout_sec: float) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "kotodama-os-messaging-open-channels/1 (+https://os-messaging.etzhayyim.com)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            return {"httpStatus": int(resp.status), "text": resp.read(1_000_000).decode("utf-8", "replace"), "error": ""}
    except urllib.error.HTTPError as e:
        return {"httpStatus": int(e.code), "text": e.read(200_000).decode("utf-8", "replace"), "error": str(e.reason or e)}
    except Exception as e:  # noqa: BLE001
        return {"httpStatus": 0, "text": "", "error": f"transport: {e}"}


def _insert_ignore(table: str, row: dict[str, Any]) -> int:
    client = get_kotoba_client()
    return 1 if client.insert_row(table, row) else 0


def _update_run(vertex_id: str, status: str, **fields: Any) -> None:
    client = get_kotoba_client()
    # Fetch existing data for the run to merge updates
    existing_run = client.select_first_where(
        "vertex_os_messaging_open_scraper_run", "vertex_id", vertex_id
    )
    if existing_run:
        # Merge new status and fields into the existing run data
        # 'vertex_id' is already in existing_run and will be used by insert_row for upserting
        updated_run_data = {**existing_run, "status": status, **fields}
        client.insert_row("vertex_os_messaging_open_scraper_run", updated_run_data)


def queue_seed_runs(seeds: Any = None, limit: int = 50) -> dict[str, Any]:
    raw_seeds = seeds if isinstance(seeds, list) else []
    queued = 0
    skipped = 0
    rows = []
    now = _utc_now()
    for raw in raw_seeds[: max(1, min(int(limit or 50), 200))]:
        if not isinstance(raw, dict):
            skipped += 1
            continue
        seed = _canonical_seed(raw)
        if seed["platform"] not in KNOWN_PLATFORMS or not seed["channel_url"] or not seed["channel_id"]:
            skipped += 1
            continue
        run_id = _sha("run", seed["platform"], seed["channel_id"], now[:13])
        vertex_id = _run_vid(run_id)
        row = {
            "vertex_id": vertex_id,
            "_seq": int(time.time() * 1000),
            "created_date": _today(),
            "sensitivity_ord": 0,
            "owner_did": OWNER_DID,
            **seed,
            "started_at": now,
            "finished_at": None,
            "status": "queued",
            "messages_seen": 0,
            "messages_new": 0,
            "error_message": None,
            "user_agent": "kotodama-os-messaging-open-channels/1",
            "org_id": OWNER_DID,
            "user_id": OWNER_DID,
            "actor_id": ACTOR_ID,
        }
        inserted = _insert_ignore("vertex_os_messaging_open_scraper_run", row)
        queued += inserted
        rows.append({"vertexId": vertex_id, "platform": seed["platform"], "channelId": seed["channel_id"], "created": bool(inserted)})

    return {"queued": queued, "skipped": skipped, "runs": rows}


def _claim_runs(max_runs: int) -> list[dict[str, Any]]:
    client = get_kotoba_client()
    # R0: Order by and limit applied in Python as select_where does not support ORDER BY.
    # Fetches all queued runs up to a reasonable limit, then sorts and limits them.
    all_queued_runs = client.select_where(
        "vertex_os_messaging_open_scraper_run",
        "status",
        "queued",
        columns=["vertex_id", "platform", "channel_id", "channel_url", "country", "language", "started_at"],
        limit=2000 # Increased limit to allow for in-Python sorting and limiting
    )
    # Sort by 'started_at' and then apply the limit
    sorted_runs = sorted(all_queued_runs, key=lambda x: x.get("started_at", ""))
    rows = sorted_runs[:max_runs]
    for row in rows:
        _update_run(str(row["vertex_id"]), "running", error_message="phase:claimed")
    return rows


def _parse_messages(platform: str, channel_url: str, raw: str) -> list[dict[str, str]]:
    if platform != "telegram":
        return []
    messages = []
    for block in re.findall(r'<div class="tgme_widget_message[^"]*"[\s\S]*?</div>\s*</div>', raw, flags=re.I):
        data_post = re.search(r'data-post=["\']([^"\']+)["\']', block)
        text_match = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>([\s\S]*?)</div>', block, flags=re.I)
        if not data_post or not text_match:
            continue
        message_id = data_post.group(1).replace("/", "-")
        message_url = urllib.parse.urljoin(channel_url, data_post.group(1))
        messages.append({
            "message_id": message_id,
            "message_text": _clean(text_match.group(1), 4000),
            "message_url": message_url,
            "published_at": "",
        })
    return messages[:50]


def process_queue(max_runs: int = 5, timeout_sec: float = 20.0) -> dict[str, Any]:
    runs = _claim_runs(max(1, min(int(max_runs or 5), 20)))
    results = []
    for run in runs:
        fetched = _fetch(str(run.get("channel_url") or ""), timeout_sec)
        text = str(fetched.get("text") or "")
        ok = bool(text and int(fetched.get("httpStatus") or 0) < 500)
        now = _utc_now()
        channel_vertex_id = _channel_vid(str(run["platform"]), str(run["channel_id"]))
        if ok:
            _insert_ignore("vertex_os_messaging_open_channel", {
                "vertex_id": channel_vertex_id,
                "_seq": int(time.time() * 1000),
                "created_date": _today(),
                "sensitivity_ord": 0,
                "owner_did": OWNER_DID,
                "platform": run["platform"],
                "channel_id": run["channel_id"],
                "channel_url": run["channel_url"],
                "title": _title(text),
                "description": _meta(text, "og:description")[:1000],
                "country": run.get("country"),
                "language": run.get("language"),
                "first_seen_at": now,
                "last_seen_at": now,
                "source_url": run["channel_url"],
                "org_id": OWNER_DID,
                "user_id": OWNER_DID,
                "actor_id": ACTOR_ID,
            })
        messages_new = 0
        messages = _parse_messages(str(run["platform"]), str(run["channel_url"]), text) if ok else []
        for msg in messages:
            messages_new += _insert_ignore("vertex_os_messaging_open_message", {
                "vertex_id": _message_vid(str(run["platform"]), msg["message_id"]),
                "_seq": int(time.time() * 1000),
                "created_date": _today(),
                "sensitivity_ord": 0,
                "owner_did": OWNER_DID,
                "platform": run["platform"],
                "channel_vertex_id": channel_vertex_id,
                "channel_id": run["channel_id"],
                "platform_message_id": msg["message_id"],
                "author_label": None,
                "message_text": msg["message_text"],
                "message_url": msg["message_url"],
                "published_at": msg["published_at"] or None,
                "observed_at": now,
                "source_url": run["channel_url"],
                "org_id": OWNER_DID,
                "user_id": OWNER_DID,
                "actor_id": ACTOR_ID,
            })
        status = "completed" if ok else "failed"
        _update_run(
            str(run["vertex_id"]),
            status,
            finished_at=now,
            messages_seen=len(messages),
            messages_new=messages_new,
            error_message=None if ok else str(fetched.get("error") or "empty response")[:500],
        )
        results.append({"vertexId": run["vertex_id"], "status": status, "messagesSeen": len(messages), "messagesNew": messages_new})

    return {
        "processed": len(results),
        "completed": sum(1 for r in results if r.get("status") == "completed"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
        "runs": results,
    }


def task_queue_seed_runs(**kwargs: Any) -> dict[str, Any]:
    return queue_seed_runs(seeds=kwargs.get("seeds"), limit=int(kwargs.get("limit") or 50))


def task_process_queue(**kwargs: Any) -> dict[str, Any]:
    return process_queue(
        max_runs=int(kwargs.get("maxRuns") or kwargs.get("max") or 5),
        timeout_sec=float(kwargs.get("timeoutSec") or 20.0),
    )


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="osMessaging.openChannels.queueSeedRuns",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_queue_seed_runs)
    worker.task(
        task_type="osMessaging.openChannels.processQueue",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_process_queue)
