"""Tests for pure helper functions in zeebe_worker_main.py."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub heavy optional deps before loading
for _mn in ("pyzeebe", "httpx", "requests", "wasmtime", "arrow_udf"):
    if _mn not in sys.modules:
        sys.modules[_mn] = types.ModuleType(_mn)

if "pyzeebe" in sys.modules and not hasattr(sys.modules["pyzeebe"], "ZeebeWorker"):
    _pz = sys.modules["pyzeebe"]

    class _ZWStub:
        def __init__(self, *a, **kw): pass
        def task(self, **kw): return lambda f: f
        async def work(self): pass

    _pz.ZeebeWorker = _ZWStub  # type: ignore[attr-defined]
    _pz.ZeebeClient = _ZWStub  # type: ignore[attr-defined]
    _pz.create_insecure_channel = lambda **kw: None  # type: ignore[attr-defined]

_ZWM_MOD_NAME = "_zwm_pure_helpers"
if _ZWM_MOD_NAME not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _ZWM_MOD_NAME,
        _py_src / "kotodama" / "zeebe_worker_main.py",
    )
    _mod = types.ModuleType(_ZWM_MOD_NAME)
    sys.modules[_ZWM_MOD_NAME] = _mod
    assert _spec is not None and _spec.loader is not None
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

ZWM = sys.modules[_ZWM_MOD_NAME]


# ─── _check_columns ──────────────────────────────────────────────────────────

def test_check_columns_star_passes() -> None:
    ZWM._check_columns("*")  # no exception


def test_check_columns_simple_col_passes() -> None:
    ZWM._check_columns("vertex_id")


def test_check_columns_comma_list_passes() -> None:
    ZWM._check_columns("name, status, created_at")


def test_check_columns_distinct_passes() -> None:
    ZWM._check_columns("DISTINCT repo_did")


def test_check_columns_as_alias_passes() -> None:
    ZWM._check_columns("vertex_id AS vid")


def test_check_columns_parens_rejected() -> None:
    import pytest
    with pytest.raises(ValueError):
        ZWM._check_columns("count(*)")


def test_check_columns_semicolon_rejected() -> None:
    import pytest
    with pytest.raises(ValueError):
        ZWM._check_columns("vertex_id; DROP TABLE users")


def test_check_columns_quotes_rejected() -> None:
    import pytest
    with pytest.raises(ValueError):
        ZWM._check_columns('"vertex_id"')


# ─── _bytes32_hex ─────────────────────────────────────────────────────────────

def test_bytes32_hex_passthrough_valid_hex() -> None:
    valid = "0x" + "a" * 64
    assert ZWM._bytes32_hex(valid, field="txHash") == valid


def test_bytes32_hex_hashes_plain_string() -> None:
    result = ZWM._bytes32_hex("hello", field="txHash")
    assert result.startswith("0x")
    assert len(result) == 66


def test_bytes32_hex_deterministic() -> None:
    a = ZWM._bytes32_hex("same-input", field="f")
    b = ZWM._bytes32_hex("same-input", field="f")
    assert a == b


# ─── Malak referral validation ───────────────────────────────────────────────

def test_validate_malak_referral_accepts_reviewable_draft() -> None:
    result = ZWM._validate_malak_agency_referral_draft(
        actor_id="actor-1",
        case_id="case-1",
        agency="INTERPOL",
        legal_basis="customer-consent-and-incident-response",
        approval_ref="approval-123",
        summary="Attribution package draft",
        evidence_ids=[" evidence-1 ", "evidence-2"],
        attribution_confidence=0.82,
        tlp="AMBER",
    )

    assert result["referralId"].startswith("ref-case-1-")
    assert result["normalizedTlp"] == "amber"
    assert result["normalizedKind"] == "agency_intel_package"
    assert result["confidence"] == 0.82
    assert result["evidenceIds"] == ["evidence-1", "evidence-2"]


def test_validate_malak_referral_rejects_low_confidence() -> None:
    import pytest

    with pytest.raises(ValueError, match="attributionConfidence"):
        ZWM._validate_malak_agency_referral_draft(
            actor_id="actor-1",
            case_id="case-1",
            agency="agency",
            legal_basis="basis",
            approval_ref="approval",
            summary="summary",
            evidence_ids=["evidence-1"],
            attribution_confidence=0.69,
        )


def test_validate_malak_referral_requires_evidence() -> None:
    import pytest

    with pytest.raises(ValueError, match="evidenceId"):
        ZWM._validate_malak_agency_referral_draft(
            actor_id="actor-1",
            case_id="case-1",
            agency="agency",
            legal_basis="basis",
            approval_ref="approval",
            summary="summary",
            evidence_ids=[],
            attribution_confidence=0.7,
        )


def test_bytes32_hex_empty_raises() -> None:
    import pytest
    with pytest.raises(ValueError, match="txHash required"):
        ZWM._bytes32_hex("", field="txHash")


def test_bytes32_hex_varies_with_input() -> None:
    a = ZWM._bytes32_hex("input-1", field="f")
    b = ZWM._bytes32_hex("input-2", field="f")
    assert a != b


# ─── _sha256_json ─────────────────────────────────────────────────────────────

def test_sha256_json_returns_hex_string() -> None:
    result = ZWM._sha256_json({"key": "value"})
    assert result.startswith("0x")
    assert len(result) == 66


def test_sha256_json_deterministic() -> None:
    obj = {"a": 1, "b": [2, 3]}
    assert ZWM._sha256_json(obj) == ZWM._sha256_json(obj)


def test_sha256_json_varies_with_input() -> None:
    a = ZWM._sha256_json({"x": 1})
    b = ZWM._sha256_json({"x": 2})
    assert a != b


def test_sha256_json_handles_primitives() -> None:
    result = ZWM._sha256_json(42)
    assert result.startswith("0x")


def test_sha256_json_sorted_keys_for_determinism() -> None:
    # dict with same keys in different order should hash identically
    a = ZWM._sha256_json({"b": 2, "a": 1})
    b = ZWM._sha256_json({"a": 1, "b": 2})
    assert a == b


# ─── _xrpc_base_from_actor ────────────────────────────────────────────────────

def test_xrpc_base_from_actor_did_web() -> None:
    result = ZWM._xrpc_base_from_actor("did:web:mycom.etzhayyim.com")
    assert result == "https://mycom.etzhayyim.com"


def test_xrpc_base_from_actor_non_did_web_returns_empty() -> None:
    assert ZWM._xrpc_base_from_actor("did:plc:abc123") == ""
    assert ZWM._xrpc_base_from_actor("") == ""


def test_xrpc_base_from_actor_with_path() -> None:
    result = ZWM._xrpc_base_from_actor("did:web:example.com:sub")
    assert result == "https://example.com/sub"


def test_xrpc_base_from_actor_empty_path_returns_empty() -> None:
    assert ZWM._xrpc_base_from_actor("did:web:") == ""


# ─── _env_key ─────────────────────────────────────────────────────────────────

def test_env_key_basic() -> None:
    assert ZWM._env_key("my.key") == "MY_KEY"


def test_env_key_uppercases() -> None:
    assert ZWM._env_key("hello") == "HELLO"


def test_env_key_replaces_non_alnum_with_underscore() -> None:
    result = ZWM._env_key("a-b.c/d")
    assert result == "A_B_C_D"


def test_env_key_strips_leading_trailing_underscores() -> None:
    result = ZWM._env_key(".leading.trailing.")
    assert not result.startswith("_")
    assert not result.endswith("_")


def test_env_key_empty_string() -> None:
    result = ZWM._env_key("")
    assert isinstance(result, str)


# ─── _parse_atom_feed ─────────────────────────────────────────────────────────

_ATOM_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>urn:uuid:1234</id>
    <title>Entry One</title>
    <link href="https://example.com/1"/>
    <published>2024-01-01T00:00:00Z</published>
    <summary>Summary of entry one</summary>
  </entry>
  <entry>
    <id>urn:uuid:5678</id>
    <title>Entry Two</title>
    <link href="https://example.com/2"/>
    <updated>2024-02-01T00:00:00Z</updated>
  </entry>
</feed>"""


def test_parse_atom_feed_returns_list() -> None:
    result = ZWM._parse_atom_feed(_ATOM_SAMPLE)
    assert isinstance(result, list)
    assert len(result) == 2


def test_parse_atom_feed_extracts_title() -> None:
    result = ZWM._parse_atom_feed(_ATOM_SAMPLE)
    titles = [e["title"] for e in result]
    assert "Entry One" in titles


def test_parse_atom_feed_extracts_link() -> None:
    result = ZWM._parse_atom_feed(_ATOM_SAMPLE)
    links = [e["link"] for e in result]
    assert "https://example.com/1" in links


def test_parse_atom_feed_invalid_xml_returns_empty() -> None:
    result = ZWM._parse_atom_feed("not xml at all")
    assert result == []


def test_parse_atom_feed_empty_string_returns_empty() -> None:
    result = ZWM._parse_atom_feed("")
    assert result == []


def test_parse_atom_feed_entry_has_required_keys() -> None:
    result = ZWM._parse_atom_feed(_ATOM_SAMPLE)
    for entry in result:
        assert "id" in entry
        assert "title" in entry
        assert "link" in entry


# ─── _parse_oai_pmh ───────────────────────────────────────────────────────────

_OAI_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListRecords>
    <record>
      <header>
        <identifier>oai:example.org:article-001</identifier>
        <datestamp>2024-01-15</datestamp>
      </header>
      <metadata>
        <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"
                   xmlns:dc="http://purl.org/dc/elements/1.1/">
          <dc:title>Article Title</dc:title>
          <dc:identifier>https://example.org/article/001</dc:identifier>
        </oai_dc:dc>
      </metadata>
    </record>
  </ListRecords>
</OAI-PMH>"""


def test_parse_oai_pmh_returns_list() -> None:
    result = ZWM._parse_oai_pmh(_OAI_SAMPLE)
    assert isinstance(result, list)
    assert len(result) == 1


def test_parse_oai_pmh_extracts_identifier() -> None:
    result = ZWM._parse_oai_pmh(_OAI_SAMPLE)
    assert result[0]["id"] == "oai:example.org:article-001"


def test_parse_oai_pmh_extracts_title() -> None:
    result = ZWM._parse_oai_pmh(_OAI_SAMPLE)
    assert result[0]["title"] == "Article Title"


def test_parse_oai_pmh_extracts_datestamp() -> None:
    result = ZWM._parse_oai_pmh(_OAI_SAMPLE)
    assert result[0]["published"] == "2024-01-15"


def test_parse_oai_pmh_invalid_xml_returns_empty() -> None:
    assert ZWM._parse_oai_pmh("not xml") == []


def test_parse_oai_pmh_no_list_records_returns_empty() -> None:
    xml = '<?xml version="1.0"?><OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><GetRecord/></OAI-PMH>'
    assert ZWM._parse_oai_pmh(xml) == []


def test_parse_oai_pmh_entry_has_required_keys() -> None:
    result = ZWM._parse_oai_pmh(_OAI_SAMPLE)
    for rec in result:
        assert "id" in rec
        assert "link" in rec
        assert "title" in rec
        assert "published" in rec


# ─── _enforce_write_scope (via allowlist mock) ────────────────────────────────

def test_enforce_write_scope_no_binding_returns_none() -> None:
    # When _binding_write_allowlist returns None (no binding), scope is unrestricted
    original = ZWM._binding_write_allowlist

    def _mock_allowlist(bpmn_process_id: str):
        return None

    ZWM._binding_write_allowlist = _mock_allowlist
    try:
        result = ZWM._enforce_write_scope("vertex_any", "some_process")
        assert result is None
    finally:
        ZWM._binding_write_allowlist = original


def test_enforce_write_scope_table_in_allowlist_returns_none() -> None:
    original = ZWM._binding_write_allowlist

    def _mock_allowlist(bpmn_process_id: str):
        return {"vertex_allowed", "vertex_denied"}

    ZWM._binding_write_allowlist = _mock_allowlist
    try:
        result = ZWM._enforce_write_scope("vertex_allowed", "my_process")
        assert result is None
    finally:
        ZWM._binding_write_allowlist = original


def test_enforce_write_scope_table_not_in_allowlist_returns_error() -> None:
    original = ZWM._binding_write_allowlist

    def _mock_allowlist(bpmn_process_id: str):
        return {"vertex_allowed"}

    ZWM._binding_write_allowlist = _mock_allowlist
    try:
        result = ZWM._enforce_write_scope("vertex_forbidden", "my_process")
        assert result is not None
        assert "vertex_forbidden" in result
    finally:
        ZWM._binding_write_allowlist = original


def test_enforce_write_scope_empty_allowlist_returns_error() -> None:
    original = ZWM._binding_write_allowlist

    def _mock_allowlist(bpmn_process_id: str):
        return set()  # explicit deny

    ZWM._binding_write_allowlist = _mock_allowlist
    try:
        result = ZWM._enforce_write_scope("vertex_any", "my_process")
        assert result is not None
        assert "empty" in result
    finally:
        ZWM._binding_write_allowlist = original


# ─── _parse_verdict ──────────────────────────────────────────────────────────

def test_parse_verdict_valid_json_object() -> None:
    result = ZWM._parse_verdict('{"ok": true, "score": 9}')
    assert result is not None
    assert result["ok"] is True


def test_parse_verdict_none_returns_none() -> None:
    result = ZWM._parse_verdict(None)
    assert result is None


def test_parse_verdict_empty_string_returns_none() -> None:
    result = ZWM._parse_verdict("")
    assert result is None


def test_parse_verdict_prose_around_json() -> None:
    result = ZWM._parse_verdict('Here is the verdict: {"rating": 8}')
    assert result is not None
    assert result["rating"] == 8


def test_parse_verdict_returns_dict_or_none() -> None:
    result = ZWM._parse_verdict('{"key": "val"}')
    assert isinstance(result, dict) or result is None


# ─── _build_txt2img_workflow ─────────────────────────────────────────────────

def test_build_txt2img_workflow_returns_dict() -> None:
    result = ZWM._build_txt2img_workflow({})
    assert isinstance(result, dict)


def test_build_txt2img_workflow_has_ksampler() -> None:
    result = ZWM._build_txt2img_workflow({"prompt": "a cat"})
    assert "3" in result
    assert result["3"]["class_type"] == "KSampler"


def test_build_txt2img_workflow_custom_size() -> None:
    result = ZWM._build_txt2img_workflow({"size": "512x768"})
    assert result["5"]["inputs"]["width"] == 512
    assert result["5"]["inputs"]["height"] == 768


def test_build_txt2img_workflow_invalid_size_falls_back() -> None:
    result = ZWM._build_txt2img_workflow({"size": "badformat"})
    assert result["5"]["inputs"]["width"] == 832
    assert result["5"]["inputs"]["height"] == 1216


def test_build_txt2img_workflow_custom_steps() -> None:
    result = ZWM._build_txt2img_workflow({"steps": 30})
    assert result["3"]["inputs"]["steps"] == 30


def test_build_txt2img_workflow_custom_prompt() -> None:
    result = ZWM._build_txt2img_workflow({"prompt": "a dog"})
    assert result["6"]["inputs"]["text"] == "a dog"


def test_build_txt2img_workflow_negative_prompt() -> None:
    result = ZWM._build_txt2img_workflow({"negative_prompt": "blurry"})
    assert result["7"]["inputs"]["text"] == "blurry"


def test_build_txt2img_workflow_batch_size() -> None:
    result = ZWM._build_txt2img_workflow({"n": 3})
    assert result["5"]["inputs"]["batch_size"] == 3


# ─── _extract_serverless_images ──────────────────────────────────────────────

def test_extract_serverless_images_none_returns_empty() -> None:
    assert ZWM._extract_serverless_images(None) == []


def test_extract_serverless_images_empty_dict_returns_empty() -> None:
    assert ZWM._extract_serverless_images({}) == []


def test_extract_serverless_images_list_format() -> None:
    output = {"images": [{"data": "base64abc"}, {"data": "base64xyz"}]}
    result = ZWM._extract_serverless_images(output)
    assert "base64abc" in result
    assert "base64xyz" in result


def test_extract_serverless_images_single_image_key() -> None:
    output = {"image": "b64single"}
    result = ZWM._extract_serverless_images(output)
    assert "b64single" in result


def test_extract_serverless_images_mixed_formats() -> None:
    output = {"images": [{"data": "img1"}], "image": "img2"}
    result = ZWM._extract_serverless_images(output)
    assert len(result) == 2


def test_extract_serverless_images_skips_non_dict_items() -> None:
    output = {"images": ["not-a-dict", {"data": "valid"}]}
    result = ZWM._extract_serverless_images(output)
    assert result == ["valid"]


def test_extract_serverless_images_returns_list() -> None:
    result = ZWM._extract_serverless_images({"image": "x"})
    assert isinstance(result, list)


# ─── _check_order_by ─────────────────────────────────────────────────────────

def test_check_order_by_valid_single_col() -> None:
    ZWM._check_order_by("created_at")  # no exception


def test_check_order_by_valid_with_asc() -> None:
    ZWM._check_order_by("created_at ASC")


def test_check_order_by_valid_with_desc() -> None:
    ZWM._check_order_by("name DESC")


def test_check_order_by_valid_multi_col() -> None:
    ZWM._check_order_by("created_at DESC, updated_at ASC")


def test_check_order_by_invalid_raises() -> None:
    import pytest
    with pytest.raises(ValueError, match="orderBy"):
        ZWM._check_order_by("1=1; DROP TABLE users--")


def test_check_order_by_sql_injection_raises() -> None:
    import pytest
    with pytest.raises(ValueError):
        ZWM._check_order_by("id; DELETE FROM vertex_ma_deal")


def test_check_order_by_empty_string_raises() -> None:
    import pytest
    with pytest.raises(ValueError):
        ZWM._check_order_by("")


# ─── _stable_vertex_suffix ───────────────────────────────────────────────────

def test_stable_vertex_suffix_returns_24_hex_chars() -> None:
    result = ZWM._stable_vertex_suffix({"key": "val"})
    assert len(result) == 24
    assert all(c in "0123456789abcdef" for c in result)


def test_stable_vertex_suffix_deterministic() -> None:
    a = ZWM._stable_vertex_suffix({"a": 1, "b": 2})
    b = ZWM._stable_vertex_suffix({"a": 1, "b": 2})
    assert a == b


def test_stable_vertex_suffix_varies_with_input() -> None:
    a = ZWM._stable_vertex_suffix({"a": 1})
    b = ZWM._stable_vertex_suffix({"a": 2})
    assert a != b


def test_stable_vertex_suffix_key_order_invariant() -> None:
    a = ZWM._stable_vertex_suffix({"a": 1, "b": 2})
    b = ZWM._stable_vertex_suffix({"b": 2, "a": 1})
    assert a == b  # sort_keys=True


def test_stable_vertex_suffix_empty_dict() -> None:
    result = ZWM._stable_vertex_suffix({})
    assert len(result) == 24


# ─── _normalize_source_ids ───────────────────────────────────────────────────

def test_normalize_source_ids_list_passthrough() -> None:
    result = ZWM._normalize_source_ids(["src1", "src2"])
    assert result == ["src1", "src2"]


def test_normalize_source_ids_csv_string() -> None:
    result = ZWM._normalize_source_ids("src1, src2, src3")
    assert result == ["src1", "src2", "src3"]


def test_normalize_source_ids_none_returns_empty() -> None:
    assert ZWM._normalize_source_ids(None) == []


def test_normalize_source_ids_filters_blank_entries() -> None:
    result = ZWM._normalize_source_ids("src1,,  , src2")
    assert "" not in result
    assert "src1" in result and "src2" in result


def test_normalize_source_ids_single_string() -> None:
    result = ZWM._normalize_source_ids("only-one")
    assert result == ["only-one"]


def test_normalize_source_ids_strips_whitespace() -> None:
    result = ZWM._normalize_source_ids(["  src1  ", "  src2  "])
    assert result == ["src1", "src2"]


# ─── _check_table ─────────────────────────────────────────────────────────────

def test_check_table_allows_vertex() -> None:
    ZWM._check_table("vertex_foo_bar")  # should not raise


def test_check_table_allows_edge() -> None:
    ZWM._check_table("edge_actor_follows")  # should not raise


def test_check_table_allows_mv() -> None:
    ZWM._check_table("mv_actor_stats")  # should not raise


def test_check_table_rejects_arbitrary_name() -> None:
    try:
        ZWM._check_table("users")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_check_table_rejects_sql_injection() -> None:
    try:
        ZWM._check_table("vertex_foo; DROP TABLE users")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_check_table_rejects_empty_string() -> None:
    try:
        ZWM._check_table("")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_check_table_rejects_uppercase() -> None:
    try:
        ZWM._check_table("Vertex_Foo")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_check_table_allows_numbers_in_name() -> None:
    ZWM._check_table("vertex_foo123_bar")  # should not raise


# ─── _coerce_insert_values ───────────────────────────────────────────────────

def test_coerce_insert_values_int_col(monkeypatch) -> None:
    monkeypatch.setattr(ZWM, "_load_column_types", lambda t: {"age": "integer"})
    result = ZWM._coerce_insert_values("vertex_t", {"age": "42"})
    assert result["age"] == 42
    assert isinstance(result["age"], int)


def test_coerce_insert_values_float_col(monkeypatch) -> None:
    monkeypatch.setattr(ZWM, "_load_column_types", lambda t: {"price": "double precision"})
    result = ZWM._coerce_insert_values("vertex_t", {"price": "3.14"})
    assert abs(result["price"] - 3.14) < 1e-9


def test_coerce_insert_values_bool_string_true(monkeypatch) -> None:
    monkeypatch.setattr(ZWM, "_load_column_types", lambda t: {"active": "boolean"})
    result = ZWM._coerce_insert_values("vertex_t", {"active": "true"})
    assert result["active"] is True


def test_coerce_insert_values_bool_string_false(monkeypatch) -> None:
    monkeypatch.setattr(ZWM, "_load_column_types", lambda t: {"active": "boolean"})
    result = ZWM._coerce_insert_values("vertex_t", {"active": "false"})
    assert result["active"] is False


def test_coerce_insert_values_none_passthrough(monkeypatch) -> None:
    monkeypatch.setattr(ZWM, "_load_column_types", lambda t: {"name": "varchar"})
    result = ZWM._coerce_insert_values("vertex_t", {"name": None})
    assert result["name"] is None


def test_coerce_insert_values_unknown_type_str_coercion(monkeypatch) -> None:
    monkeypatch.setattr(ZWM, "_load_column_types", lambda t: {})
    result = ZWM._coerce_insert_values("vertex_t", {"x": 42})
    assert result["x"] == "42"


def test_coerce_insert_values_str_col_stays_str(monkeypatch) -> None:
    monkeypatch.setattr(ZWM, "_load_column_types", lambda t: {"name": "varchar"})
    result = ZWM._coerce_insert_values("vertex_t", {"name": "Alice"})
    assert result["name"] == "Alice"


def test_coerce_insert_values_empty_values(monkeypatch) -> None:
    monkeypatch.setattr(ZWM, "_load_column_types", lambda t: {})
    result = ZWM._coerce_insert_values("vertex_t", {})
    assert result == {}


# ─── _resolve_wasm_module ─────────────────────────────────────────────────────

def test_resolve_wasm_module_empty_path_raises() -> None:
    try:
        ZWM._resolve_wasm_module("")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "required" in str(e).lower() or "modulepath" in str(e).lower()


def test_resolve_wasm_module_path_escape_raises() -> None:
    try:
        ZWM._resolve_wasm_module("../../etc/passwd")
        assert False, "expected (ValueError or FileNotFoundError)"
    except (ValueError, FileNotFoundError):
        pass
