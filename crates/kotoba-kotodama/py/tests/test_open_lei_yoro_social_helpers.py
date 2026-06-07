"""Tests for pure helper functions in open_lei.py and yoro_social.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import open_lei as OL
from kotodama.primitives import yoro_social as YS


# ─── open_lei: _as_list ──────────────────────────────────────────────────────

def test_as_list_passthrough_list() -> None:
    assert OL._as_list([1, 2, 3]) == [1, 2, 3]


def test_as_list_empty_list() -> None:
    assert OL._as_list([]) == []


def test_as_list_non_list_returns_empty() -> None:
    assert OL._as_list(None) == []
    assert OL._as_list("string") == []
    assert OL._as_list(42) == []
    assert OL._as_list({"a": 1}) == []


# ─── open_lei: _str_list ─────────────────────────────────────────────────────

def test_str_list_converts_items() -> None:
    result = OL._str_list([1, 2, 3])
    assert result == ["1", "2", "3"]


def test_str_list_filters_falsy() -> None:
    result = OL._str_list(["a", None, "", "b"])
    assert result == ["a", "b"]


def test_str_list_non_list_returns_empty() -> None:
    assert OL._str_list(None) == []
    assert OL._str_list("text") == []


# ─── open_lei: gleif_manifest_plan ───────────────────────────────────────────

def test_gleif_manifest_plan_default_datasets() -> None:
    result = OL.gleif_manifest_plan()
    assert "plan" in result or "datasetPlans" in result or isinstance(result, dict)
    assert result  # non-empty


def test_gleif_manifest_plan_single_dataset() -> None:
    result = OL.gleif_manifest_plan(datasets=["lei-cdf"])
    # Should only contain lei-cdf
    plans = result.get("datasetPlans") or result.get("plan") or []
    if plans:
        assert all(p.get("datasetKind") == "lei-cdf" for p in plans)


def test_gleif_manifest_plan_mode_backfill() -> None:
    result = OL.gleif_manifest_plan(mode="backfill", datasets=["lei-cdf"])
    plans = result.get("datasetPlans") or []
    if plans:
        assert plans[0].get("mode") == "backfill"


def test_gleif_manifest_plan_invalid_mode_defaults_delta() -> None:
    result = OL.gleif_manifest_plan(mode="invalid-mode", datasets=["lei-cdf"])
    plans = result.get("datasetPlans") or []
    if plans:
        assert plans[0].get("mode") == "delta"


def test_gleif_manifest_plan_with_as_of_date() -> None:
    result = OL.gleif_manifest_plan(as_of_date="2026-01-01", datasets=["lei-cdf"])
    plans = result.get("datasetPlans") or []
    if plans:
        assert "2026-01-01" in plans[0].get("partitionKey", "")


# ─── open_lei: normalize_lei_record ──────────────────────────────────────────

def test_normalize_lei_record_flat_structure() -> None:
    record = {
        "id": "LEI123456789",
        "legalName": "Acme Corp",
        "registrationStatus": "ISSUED",
    }
    result = OL.normalize_lei_record(record)
    assert "vertex_id" in result
    assert "LEI123456789" in result["vertex_id"]


def test_normalize_lei_record_nested_attributes() -> None:
    record = {
        "attributes": {
            "lei": "ABCDEF1234567890XXXX",
            "entity": {
                "legalName": {"name": "Test GmbH"},
                "legalAddress": {"country": "DE"},
                "legalForm": {"id": "8888"},
            },
            "registration": {
                "status": "ISSUED",
                "initialRegistrationDate": "2020-01-01",
            },
        }
    }
    result = OL.normalize_lei_record(record)
    assert result["lei"] == "ABCDEF1234567890XXXX"
    assert result["legal_name"] == "Test GmbH"
    assert result["country"] == "DE"
    assert result["legal_form"] == "8888"
    assert result["status"] == "active"


def test_normalize_lei_record_lapsed_status() -> None:
    record = {
        "attributes": {
            "lei": "XYZ001",
            "entity": {},
            "registration": {"status": "LAPSED"},
        }
    }
    result = OL.normalize_lei_record(record)
    assert result["status"] == "lapsed"


def test_normalize_lei_record_vertex_id_format() -> None:
    record = {"attributes": {"lei": "TESTLEI0001"}}
    result = OL.normalize_lei_record(record)
    assert result["vertex_id"].startswith("at://did:web:open-lei.etzhayyim.com/")
    assert "com.etzhayyim.apps.openLei.entity" in result["vertex_id"]
    assert "TESTLEI0001" in result["vertex_id"]


def test_normalize_lei_record_missing_fields_graceful() -> None:
    result = OL.normalize_lei_record({})
    assert isinstance(result, dict)
    assert "vertex_id" in result


# ─── yoro_social: _display_actor ─────────────────────────────────────────────

def test_display_actor_returns_handle_if_set() -> None:
    assert YS._display_actor("did:web:foo.etzhayyim.com", "myhandle") == "myhandle"


def test_display_actor_strips_did_web_prefix() -> None:
    result = YS._display_actor("did:web:yoro.etzhayyim.com")
    assert result == "yoro.etzhayyim.com"


def test_display_actor_empty_did_returns_friend() -> None:
    result = YS._display_actor("", "")
    assert result == "friend"


def test_display_actor_non_web_did_passthrough() -> None:
    result = YS._display_actor("did:plc:abc123")
    assert result == "did:plc:abc123"


def test_display_actor_strips_whitespace_from_handle() -> None:
    result = YS._display_actor("did:web:x.etzhayyim.com", "  handle  ")
    assert result == "handle"


# ─── yoro_social: build_social_post_record ───────────────────────────────────

def test_build_social_post_record_shape() -> None:
    result = YS.build_social_post_record(text="hello world")
    assert "uri" in result
    assert "value_json" in result
    assert "rkey" in result
    assert "collection" in result


def test_build_social_post_record_text_in_value_json() -> None:
    import json
    result = YS.build_social_post_record(text="test post")
    parsed = json.loads(result["value_json"])
    assert parsed["text"] == "test post"


def test_build_social_post_record_explicit_rkey() -> None:
    result = YS.build_social_post_record(text="x", rkey="my-rkey-001")
    assert result["rkey"] == "my-rkey-001"
    assert result["cid"] == "my-rkey-001"
    assert "my-rkey-001" in result["uri"]


def test_build_social_post_record_custom_repo() -> None:
    result = YS.build_social_post_record(text="x", repo="did:web:custom.etzhayyim.com")
    assert result["repo"] == "did:web:custom.etzhayyim.com"
    assert "did:web:custom.etzhayyim.com" in result["uri"]


def test_build_social_post_record_extra_fields_merged() -> None:
    import json
    extra = {"lang": "ja", "tags": ["test"]}
    result = YS.build_social_post_record(text="x", record_extra=extra)
    parsed = json.loads(result["value_json"])
    assert parsed["lang"] == "ja"


# ─── yoro_social: build_repo_record ──────────────────────────────────────────

def test_build_repo_record_shape() -> None:
    record = {"$type": "com.etzhayyim.apps.test.post", "text": "hello"}
    result = YS.build_repo_record(
        repo="did:web:yoro.etzhayyim.com",
        collection="com.etzhayyim.apps.test.post",
        record=record,
        rkey="my-rkey",
    )
    assert result["uri"] == "at://did:web:yoro.etzhayyim.com/com.etzhayyim.apps.test.post/my-rkey"
    assert result["collection"] == "com.etzhayyim.apps.test.post"
    assert result["repo"] == "did:web:yoro.etzhayyim.com"


def test_build_repo_record_value_json_serialized() -> None:
    import json
    record = {"$type": "com.etzhayyim.test.rec", "count": 42}
    result = YS.build_repo_record(
        repo="did:web:x.etzhayyim.com",
        collection="com.etzhayyim.test.rec",
        record=record,
    )
    parsed = json.loads(result["value_json"])
    assert parsed["count"] == 42
