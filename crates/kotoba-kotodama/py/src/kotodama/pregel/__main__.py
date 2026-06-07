"""pregel CLI — smoke test + inbox polling + LangGraph triage 常駐化.

Usage:
  python -m kotodama.pregel               # smoke test (default)
  python -m kotodama.pregel poll          # one-shot intent-analysis poll
  python -m kotodama.pregel poll --loop   # continuous intent-analysis poll (60s)
  python -m kotodama.pregel poll --since 2026-05-13T00:00:00Z
  python -m kotodama.pregel triage        # one-shot: classify + RW ingest + folder move
  python -m kotodama.pregel triage --loop --interval 300  # continuous (5min cycle)
  python -m kotodama.pregel triage --dry-run              # classify + RW only, no moves

triage mode (常駐化):
  1. listInbox XRPC → up to --top messages since cursor
  2. triage_app (heuristic → optional LLM → RW ingest) per message
  3. Batch-move DELETE → deleteditems, ARCHIVE → archive (20/call)
  4. Persist cursor to ~/.etzhayyim/triage-live-cursor.txt
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .graph import app, triage_app, TriageState, _is_internal_addr, _is_recent_days

# ── Cursor persistence ────────────────────────────────────────────────────────
_CURSOR_FILE = Path(os.getenv("PREGEL_CURSOR_FILE", Path.home() / ".etzhayyim" / "pregel-inbox-cursor.txt"))
_MICROSOFT_XRPC = os.getenv("MICROSOFT_XRPC_BASE", "https://microsoft.etzhayyim.com/xrpc")
_FROM_UPN       = os.getenv("PREGEL_FROM_UPN", "j.kawasaki@etzhayyim.com")
_POLL_INTERVAL  = int(os.getenv("PREGEL_POLL_INTERVAL", "60"))


_MICROSOFT_AUD = "did:web:microsoft.etzhayyim.com"
_TOKEN_TTL     = 300  # seconds; refresh before expiry


def _mint_token(lxm: str) -> str:
    """Mint a short-lived AT Protocol service auth token via etzhayyim CLI."""
    result = subprocess.run(
        ["etzhayyim", "agent-token", "--lxm", lxm, "--aud", _MICROSOFT_AUD, "--ttl", str(_TOKEN_TTL)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"etzhayyim agent-token failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _load_cursor() -> str:
    if _CURSOR_FILE.exists():
        return _CURSOR_FILE.read_text().strip()
    return ""


def _save_cursor(since: str) -> None:
    _CURSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CURSOR_FILE.write_text(since)


def _fetch_inbox(since: str = "", top: int = 50) -> tuple[list[dict], str]:
    """Call listInbox XRPC, return (messages, nextLink)."""
    params: dict = {"fromUpn": _FROM_UPN, "top": top}
    if since:
        params["since"] = since
    payload = json.dumps(params).encode()
    try:
        token = _mint_token("com.etzhayyim.apps.microsoft.listInbox")
    except Exception as exc:
        print(f"[pregel][poll] listInbox error: token mint failed: {exc}")
        return [], ""
    req = urllib.request.Request(
        f"{_MICROSOFT_XRPC}/com.etzhayyim.apps.microsoft.listInbox",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            data = json.loads(json.loads(raw))  # Worker double-encodes JSON
            return data.get("messages", []), data.get("nextLink", "")
    except Exception as exc:
        print(f"[pregel][poll] listInbox error: {exc}")
        return [], ""


async def _process_message(
    msg: dict,
    *,
    blocker_annotation: str = "",
    delegated_to: str = "",
) -> None:
    state = {
        "message_id":        msg.get("id", ""),
        "thread_id":         msg.get("conversationId"),
        "from_address":      msg.get("fromAddress", ""),
        "from_name":         msg.get("fromName", ""),
        "to_addresses":      msg.get("toAddresses", ""),
        "subject":           msg.get("subject", ""),
        "received_at":       msg.get("receivedAt", ""),
        "body_preview":      msg.get("bodyPreview", ""),
        "blocker_annotation": blocker_annotation or None,
        "delegated_to":      delegated_to or None,
    }
    result = await app.ainvoke(state)
    blocker_tag = f" BLOCKED({result.get('blocker_type','')})" if result.get("has_blocker") else ""
    print(
        f"[{result.get('intent_primary','?'):10s}] "
        f"urgency={result.get('urgency_score',0):3d} "
        f"action={str(result.get('action_required',False)):5s}"
        f"{blocker_tag} "
        f"written={result.get('written','?')} "
        f"→ {msg.get('subject','')[:70]}"
    )


async def poll_once(
    since: str,
    *,
    blocker_annotation: str = "",
    delegated_to: str = "",
) -> str:
    """Fetch one page of inbox since cursor, process each message. Returns new cursor."""
    messages, _next = _fetch_inbox(since=since, top=50)
    if not messages:
        return since

    print(f"[pregel][poll] {len(messages)} new message(s) since {since or 'beginning'}")
    for msg in messages:
        await _process_message(msg, blocker_annotation=blocker_annotation, delegated_to=delegated_to)

    # New cursor = latest receivedAt among processed messages
    latest = max((m.get("receivedAt", "") for m in messages), default=since)
    return latest


async def run_poll(args: argparse.Namespace) -> None:
    since = args.since or _load_cursor()
    blocker_annotation = args.blocker or ""
    delegated_to = args.delegated_to or ""

    if args.loop:
        print(f"[pregel][poll] loop mode, interval={_POLL_INTERVAL}s, since={since or 'beginning'}")
        while True:
            new_since = await poll_once(since, blocker_annotation=blocker_annotation, delegated_to=delegated_to)
            if new_since != since:
                _save_cursor(new_since)
                since = new_since
            await asyncio.sleep(_POLL_INTERVAL)
    else:
        new_since = await poll_once(since, blocker_annotation=blocker_annotation, delegated_to=delegated_to)
        if new_since != since:
            _save_cursor(new_since)
        print(f"[pregel][poll] cursor → {new_since}")


# ── Triage 常駐化 ─────────────────────────────────────────────────────────────

_TRIAGE_CURSOR_FILE = Path(os.getenv(
    "TRIAGE_CURSOR_FILE",
    str(Path.home() / ".etzhayyim" / "triage-live-cursor.txt"),
))
_TRIAGE_MOVED_FILE = Path(os.getenv(
    "TRIAGE_MOVED_FILE",
    str(Path.home() / ".etzhayyim" / "triage-moved.txt"),
))
_TRIAGE_MOVE_URL = f"{_MICROSOFT_XRPC}/com.etzhayyim.apps.microsoft.batchMoveMessages"
_TRIAGE_CATEGORY_TO_FOLDER = {
    "DELETE":  "deleteditems",
    "ARCHIVE": "archive",
}


def _load_triage_cursor() -> str:
    if _TRIAGE_CURSOR_FILE.exists():
        return _TRIAGE_CURSOR_FILE.read_text().strip()
    return ""


def _save_triage_cursor(since: str) -> None:
    _TRIAGE_CURSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TRIAGE_CURSOR_FILE.write_text(since)


def _load_moved_ids() -> set[str]:
    if _TRIAGE_MOVED_FILE.exists():
        return {line.strip() for line in _TRIAGE_MOVED_FILE.read_text().splitlines() if line.strip()}
    return set()


def _append_moved_id(message_id: str) -> None:
    _TRIAGE_MOVED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _TRIAGE_MOVED_FILE.open("a") as fh:
        fh.write(message_id + "\n")


def _batch_move(message_ids: list[str], target_folder: str) -> dict:
    """Call batchMoveMessages XRPC for up to 20 IDs."""
    payload = json.dumps({
        "upn": _FROM_UPN,
        "messageIds": message_ids,
        "targetFolder": target_folder,
    }).encode()
    try:
        token = _mint_token("com.etzhayyim.apps.microsoft.batchMoveMessages")
    except Exception as exc:
        print(f"[triage][move] batchMoveMessages error: token mint failed: {exc}")
        return {}
    req = urllib.request.Request(
        _TRIAGE_MOVE_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw)
    except Exception as exc:
        print(f"[triage][move] batchMoveMessages error: {exc}")
        return {}


async def _triage_one(msg: dict) -> dict:
    """Run triage_app on a single inbox message dict."""
    state: TriageState = {
        "message_id":  msg.get("id", ""),
        "from_addr":   msg.get("fromAddress", ""),
        "from_name":   msg.get("fromName", ""),
        "subject":     msg.get("subject", ""),
        "received_at": msg.get("receivedAt", ""),
        "body_preview": msg.get("bodyPreview", ""),
        "is_read":     bool(msg.get("isRead", False)),
    }
    return await triage_app.ainvoke(state)


async def run_triage_batch(
    messages: list[dict],
    *,
    moved_ids: set[str],
    dry_run: bool = False,
) -> tuple[str, int, int]:
    """Classify messages, ingest to RW, batch-move DELETE/ARCHIVE.

    Returns (new_cursor, moved_ok, moved_fail).
    """
    # Group by category after classification
    pending: dict[str, list[str]] = {"DELETE": [], "ARCHIVE": []}
    results: list[dict] = []

    for msg in messages:
        result = await _triage_one(msg)
        results.append(result)
        category = result.get("triage_category", "KEEP")
        msg_id   = result.get("message_id") or msg.get("id", "")

        # Safety guards: internal senders & recent mail never get moved
        from_addr = msg.get("fromAddress", "")
        recv_at   = msg.get("receivedAt", "")
        if _is_internal_addr(from_addr):
            category = "KEEP"
        if category == "DELETE" and _is_recent_days(recv_at, days=7):
            category = "ARCHIVE"

        method   = result.get("triage_method", "?")
        conf_pct = result.get("triage_confidence_permille", 0) // 10
        print(
            f"[{category:7s}] conf={conf_pct:3d}% method={method:9s} "
            f"→ {msg.get('subject','')[:60]}"
        )

        if category in ("DELETE", "ARCHIVE") and msg_id and msg_id not in moved_ids:
            pending[category].append(msg_id)

    # Batch-move DELETE then ARCHIVE (max 20 per call)
    moved_ok = moved_fail = 0
    if not dry_run:
        for category, folder in _TRIAGE_CATEGORY_TO_FOLDER.items():
            ids = pending[category]
            for i in range(0, len(ids), 20):
                chunk = ids[i:i + 20]
                resp  = _batch_move(chunk, folder)
                for r in resp.get("results", []):
                    if r.get("ok"):
                        moved_ok += 1
                        _append_moved_id(r.get("id", ""))
                    else:
                        moved_fail += 1

    latest = max((m.get("receivedAt", "") for m in messages), default="")
    return latest, moved_ok, moved_fail


async def run_triage(args: argparse.Namespace) -> None:
    since    = args.since or _load_triage_cursor()
    top      = int(args.top)
    interval = int(args.interval)
    dry_run  = bool(args.dry_run)
    moved_ids = _load_moved_ids()

    if args.loop:
        print(f"[triage] loop mode, top={top}, interval={interval}s, dry_run={dry_run}")
        while True:
            messages, _ = _fetch_inbox(since=since, top=top)
            if messages:
                print(f"[triage] {len(messages)} message(s) since {since or 'beginning'}")
                new_since, ok, fail = await run_triage_batch(
                    messages, moved_ids=moved_ids, dry_run=dry_run
                )
                moved_ids = _load_moved_ids()  # refresh after writes
                if new_since and new_since != since:
                    _save_triage_cursor(new_since)
                    since = new_since
                print(f"[triage] moved ok={ok} fail={fail}  cursor→{since}")
            else:
                print(f"[triage] no new messages since {since or 'beginning'}")
            await asyncio.sleep(interval)
    else:
        messages, _ = _fetch_inbox(since=since, top=top)
        if not messages:
            print(f"[triage] no new messages since {since or 'beginning'}")
            return
        print(f"[triage] {len(messages)} message(s)")
        new_since, ok, fail = await run_triage_batch(
            messages, moved_ids=moved_ids, dry_run=dry_run
        )
        if new_since and new_since != since:
            _save_triage_cursor(new_since)
        print(f"[triage] moved ok={ok} fail={fail}  cursor→{new_since}")


# ── Smoke test (default mode) ─────────────────────────────────────────────────
SMOKE_EMAILS = [
    {
        "message_id": "smoke-nishino-trackbc",
        "from_address": "y.nishino@etzhayyim.com",
        "from_name": "西野 能彦",
        "to_addresses": "j.kawasaki@etzhayyim.com",
        "subject": "[GO] D-Day Track C 起動依頼 / ConfigMap mount + Track B 実行可能性確認",
        "received_at": "2026-05-11T16:56:00+09:00",
        "body_preview": "河崎さん、何をすればいいのか分かりません。workstationとは何を指しているのか…",
    },
    {
        "message_id": "smoke-tmi-invoice",
        "from_address": "Sumire_Hoshino@tmi.gr.jp",
        "from_name": "成本 治男 (TMI)",
        "to_addresses": "j.kawasaki@etzhayyim.com",
        "subject": "COMMONS株式会社/工事解約 請求書",
        "received_at": "2026-02-05T15:52:00+09:00",
        "body_preview": "請求書正本PDFを発行させていただきます。よろしくご査収のほどお願い申し上げます。",
    },
    {
        "message_id": "smoke-justco-blocker",
        "from_address": "justco@myworkday.com",
        "from_name": "JustCo Workday No-Reply",
        "to_addresses": "j.kawasaki@etzhayyim.com",
        "subject": "JustCo (Japan) - Final Reminder: Outstanding Balance",
        "received_at": "2026-04-16T23:01:00+09:00",
        "body_preview": "We regret that despite several reminders, outstandings due to us remain unpaid.",
        "blocker_annotation": "法人に資金がないのでブロッカー",
        "delegated_to": "a.nakamura@etzhayyim.com",
    },
    {
        "message_id": "smoke-alibaba-sales",
        "from_address": "noreply@alibabacloud.com",
        "from_name": "Alibaba Cloud",
        "to_addresses": "j.kawasaki@etzhayyim.com",
        "subject": "AgentBay empowers a leading cross-border e-commerce platform",
        "received_at": "2026-05-12T13:02:00+09:00",
        "body_preview": "AgentBay is the next-generation agentic computing infrastructure.",
    },
    # Spam pipeline smoke tests
    {
        "message_id": "smoke-phishing-lpa",
        "from_address": "info@abogadosjubilados.org.ar",
        "from_name": "Abogados",
        "to_addresses": "j.kawasaki@etzhayyim.com",
        "subject": "Limited Partnership Agreement Ready for Signature",
        "received_at": "2026-05-13T03:13:00+09:00",
        "body_preview": "Please review and sign the attached Limited Partnership Agreement.",
    },
    {
        "message_id": "smoke-ses-dstanding",
        "from_address": "dss@d-standing.co.jp",
        "from_name": "D-Standing",
        "to_addresses": "j.kawasaki@etzhayyim.com",
        "subject": "【エンド直】90万円以上 / Go / フルリモート / ECアプリケーション運営企業",
        "received_at": "2026-05-13T02:00:00+09:00",
        "body_preview": "エンド直案件のご紹介です。Go言語のバックエンドエンジニアを募集しています。",
    },
]


async def run_smoke() -> None:
    print("=== pregel smoke ===\n")
    for email in SMOKE_EMAILS:
        result = await app.ainvoke(email)
        blocker_tag = f" BLOCKED({result.get('blocker_type','')})" if result.get("has_blocker") else ""
        spam_tag = f" SPAM({result.get('spam_kind','')})" if result.get("spam_kind", "none") != "none" else ""
        yabai_tag = f" yabai={result.get('yabai_entity_id','')[:12]}" if result.get("yabai_entity_id") else ""
        malak_tag = f" malak={result.get('malak_message_id','')[:12]}" if result.get("malak_message_id") else ""
        intel_tag = f" intel={result.get('intel_subject_id','')[:12]}" if result.get("intel_subject_id") else ""
        print(
            f"[{result.get('intent_primary','?'):10s}] "
            f"urgency={result.get('urgency_score',0):3d} "
            f"action={str(result.get('action_required',False)):5s}"
            f"{blocker_tag}{spam_tag}{yabai_tag}{malak_tag}{intel_tag} "
            f"written={result.get('written','?')} "
            f"→ {email['subject'][:60]}"
        )
    print("\n=== done ===")


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m kotodama.pregel")
    sub = parser.add_subparsers(dest="cmd")

    p_poll = sub.add_parser("poll", help="Pull Outlook inbox and run through pregel")
    p_poll.add_argument("--since",        default="", help="ISO8601 lower bound for receivedAt")
    p_poll.add_argument("--loop",         action="store_true", help="Run continuously")
    p_poll.add_argument("--blocker",      default="", help="CEO blocker annotation (applied to all fetched messages)")
    p_poll.add_argument("--delegated-to", default="", dest="delegated_to",
                        help="Email to notify when blocker detected")

    p_triage = sub.add_parser("triage", help="LangGraph triage + RW ingest + folder move")
    p_triage.add_argument("--since",    default="", help="ISO8601 lower bound for receivedAt")
    p_triage.add_argument("--top",      default="100", help="Max messages per poll cycle")
    p_triage.add_argument("--interval", default="300", help="Poll interval in seconds (loop mode)")
    p_triage.add_argument("--loop",     action="store_true", help="Run continuously")
    p_triage.add_argument("--dry-run",  action="store_true", dest="dry_run",
                          help="Classify + ingest to RW but skip actual folder moves")

    args = parser.parse_args()

    if args.cmd == "poll":
        asyncio.run(run_poll(args))
    elif args.cmd == "triage":
        asyncio.run(run_triage(args))
    else:
        asyncio.run(run_smoke())


if __name__ == "__main__":
    main()
