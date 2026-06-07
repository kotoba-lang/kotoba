"""Unit tests for Yoro social Zeebe primitive."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import yoro_social as Y  # noqa: E402


class _Cursor:
    def __init__(self):
        self.sqls = []
        self.params = []

    def execute(self, sql, params=None):
        self.sqls.append(sql)
        self.params.append(params)


class _SyncCursorFactory:
    def __init__(self):
        self.cursors = []

    def __call__(self):
        factory = self

        class _Ctx:
            def __enter__(self):
                cur = _Cursor()
                factory.cursors.append(cur)
                return cur

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()


def test_build_social_post_record_matches_at_uri_shape():
    row = Y.build_social_post_record(created_at="2026-04-25T10:27:24Z", rkey="rk")

    assert row["uri"] == "at://did:web:yoro.etzhayyim.com/app.bsky.feed.post/rk"
    assert row["repo"] == "did:web:yoro.etzhayyim.com"
    assert row["collection"] == "app.bsky.feed.post"
    assert row["cid"] == "rk"
    value = json.loads(row["value_json"])
    assert value == {
        "$type": "app.bsky.feed.post",
        "text": (
            "Murakumo actor pulse: Karmada hub and murakumo-k3s actor worker "
            "path alive at 2026-04-25T10:27:24Z."
        ),
        "createdAt": "2026-04-25T10:27:24Z",
    }


def test_task_inserts_record_and_flushes(monkeypatch):
    factory = _SyncCursorFactory()
    monkeypatch.setattr(Y, "sync_cursor", factory)

    out = asyncio.run(
        Y.task_yoro_social_post_graph_fallback(
            text="worker path alive",
            createdAt="2026-04-25T10:27:24Z",
            rkey="rk",
            flush=True,
        )
    )

    assert out["ok"] is True
    assert out["uri"] == "at://did:web:yoro.etzhayyim.com/app.bsky.feed.post/rk"
    assert len(factory.cursors) == 1
    assert factory.cursors[0].sqls[0] == "DELETE FROM vertex_repo_record WHERE uri = %(uri)s"
    assert "INSERT INTO vertex_repo_record" in factory.cursors[0].sqls[1]
    assert factory.cursors[0].sqls[2] == "DELETE FROM vertex_post WHERE vertex_id = %(vertex_id)s"
    assert "INSERT INTO vertex_post" in factory.cursors[0].sqls[3]
    assert factory.cursors[0].params[3]["facets"] == "[]"
    assert factory.cursors[0].sqls[4] == "FLUSH"


def test_respond_to_mention_builds_reply_record(monkeypatch):
    factory = _SyncCursorFactory()
    monkeypatch.setattr(Y, "sync_cursor", factory)

    out = asyncio.run(
        Y.task_yoro_social_respond_to_mention_graph_fallback(
            authorDid="did:web:alice.etzhayyim.com",
            postUri="at://did:web:alice.etzhayyim.com/app.bsky.feed.post/p1",
            postCid="cid1",
            postText="hello @yoro",
        )
    )

    assert out["ok"] is True
    row = factory.cursors[0].params[0]
    value = json.loads(row["value_json"])
    assert value["reply"]["root"] == {
        "uri": "at://did:web:alice.etzhayyim.com/app.bsky.feed.post/p1",
        "cid": "cid1",
    }
    assert "@alice.etzhayyim.com" in value["text"]


def test_respond_to_follow_writes_follow_and_welcome(monkeypatch):
    factory = _SyncCursorFactory()
    monkeypatch.setattr(Y, "sync_cursor", factory)

    out = asyncio.run(
        Y.task_yoro_social_respond_to_follow_graph_fallback(
            followerDid="did:web:bob.etzhayyim.com",
            followRkey="f1",
            flush=True,
        )
    )

    assert out["ok"] is True
    follow_params, welcome_row = factory.cursors[0].params[0], factory.cursors[0].params[1]
    assert "edge_follows" in factory.cursors[0].sqls[0]
    assert follow_params[2] == "did:web:bob.etzhayyim.com"
    assert welcome_row["collection"] == "app.bsky.feed.post"
    assert "Welcome @bob.etzhayyim.com" in json.loads(welcome_row["value_json"])["text"]
    assert factory.cursors[0].sqls[-1] == "FLUSH"
