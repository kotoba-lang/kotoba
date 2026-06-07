"""Unit tests for OS Messaging open-channel Zeebe primitives."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import os_messaging_open_channels as M  # noqa: E402


class _Cursor:
    def __init__(self, rows=None, cols=None):
        self.sqls = []
        self.params = []
        self._rows = rows or []
        self.description = [(c,) for c in (cols or [])]
        self.rowcount = 1

    def execute(self, sql, params=None):
        self.sqls.append(sql)
        self.params.append(params)

    def fetchall(self):
        return self._rows


class _SyncCursorFactory:
    def __init__(self, cursors):
        self.cursors = list(cursors)
        self.opened = []

    def __call__(self):
        factory = self

        class _Ctx:
            def __enter__(self):
                cur = factory.cursors.pop(0) if factory.cursors else _Cursor()
                factory.opened.append(cur)
                return cur

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()


def test_queue_seed_runs_inserts_telegram_run(monkeypatch):
    factory = _SyncCursorFactory([_Cursor(), _Cursor()])
    monkeypatch.setattr(M, "sync_cursor", factory)
    monkeypatch.setattr(M, "_utc_now", lambda: "2026-04-26T12:00:00Z")

    out = M.queue_seed_runs(seeds=[{"platform": "telegram", "channelId": "etzhayyim"}])

    assert out["queued"] == 1
    row = factory.opened[0].params[0]
    assert row["platform"] == "telegram"
    assert row["channel_url"] == "https://t.me/s/etzhayyim"
    assert row["status"] == "queued"


def test_process_queue_writes_channel_and_messages(monkeypatch):
    run = (
        "at://did:web:os-messaging.etzhayyim.com/com.etzhayyim.apps.osMessaging.openScraperRun/run-1",
        "telegram",
        "etzhayyim",
        "https://t.me/s/etzhayyim",
        "JP",
        "ja",
    )
    select_cursor = _Cursor(
        rows=[run],
        cols=["vertex_id", "platform", "channel_id", "channel_url", "country", "language"],
    )
    factory = _SyncCursorFactory([select_cursor])
    monkeypatch.setattr(M, "sync_cursor", factory)
    monkeypatch.setattr(M, "_fetch", lambda _url, _timeout: {
        "httpStatus": 200,
        "text": (
            '<html><meta property="og:title" content="etzhayyim">'
            '<div class="tgme_widget_message" data-post="etzhayyim/1">'
            '<div class="tgme_widget_message_text">hello</div></div></div></html>'
        ),
        "error": "",
    })

    out = M.process_queue(max_runs=1)

    assert out["processed"] == 1
    assert out["completed"] == 1
    executed = "\n".join(sql for cur in factory.opened for sql in cur.sqls)
    assert "INSERT INTO vertex_os_messaging_open_channel" in executed
    assert "INSERT INTO vertex_os_messaging_open_message" in executed
    assert "UPDATE vertex_os_messaging_open_scraper_run SET status = %(status)s" in executed


def test_async_task_process_queue(monkeypatch):
    monkeypatch.setattr(M, "process_queue", lambda max_runs, timeout_sec: {
        "processed": max_runs,
        "timeoutSec": timeout_sec,
    })

    out = asyncio.run(M.task_process_queue(maxRuns=2, timeoutSec=3))

    assert out == {"processed": 2, "timeoutSec": 3.0}
