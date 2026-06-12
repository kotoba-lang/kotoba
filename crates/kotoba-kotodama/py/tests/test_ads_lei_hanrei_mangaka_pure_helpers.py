"""Pure helper tests for public_malak_ads, open_lei, hanrei, and mangaka primitives.

Covers pure functions with no DB/HTTP dependencies:
- public_malak_ads: _utc_now / _today / _sha / _run_vid / _advertiser_vid /
                    _creative_vid / _snapshot_vid / _clean_text / _extract_title /
                    _ads_library_url
- open_lei: _utc_now / _as_list / _str_list / gleif_manifest_plan /
            normalize_lei_record
- hanrei: _utc_now / _job_vid / _case_vid / _jurisdiction_vid / _court_vid /
          _new_job_id
- mangaka: _build_workflow
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import public_malak_ads as PMA
from kotodama.primitives import open_lei as OL
from kotodama.primitives import hanrei as HR
from kotodama.primitives import mangaka as MG


# ─── public_malak_ads — _utc_now / _today ────────────────────────────────────

def test_pma_utc_now_returns_string():
    assert isinstance(PMA._utc_now(), str)


def test_pma_utc_now_ends_with_z():
    assert PMA._utc_now().endswith("Z")


def test_pma_today_returns_date_object():
    import datetime
    assert isinstance(PMA._today(), datetime.date)


# ─── public_malak_ads — _sha ─────────────────────────────────────────────────

def test_pma_sha_starts_with_prefix():
    result = PMA._sha("p", "url1")
    assert result.startswith("p-")


def test_pma_sha_is_deterministic():
    assert PMA._sha("x", "a", "b") == PMA._sha("x", "a", "b")


def test_pma_sha_differs_by_parts():
    assert PMA._sha("x", "a") != PMA._sha("x", "b")


# ─── public_malak_ads — vid helpers ──────────────────────────────────────────

def test_pma_run_vid_starts_with_at():
    result = PMA._run_vid("run-001")
    assert result.startswith("at://")


def test_pma_advertiser_vid_contains_platform_and_id():
    result = PMA._advertiser_vid("meta", "adv-123")
    assert "meta" in result
    assert "adv-123" in result


def test_pma_creative_vid_contains_platform_and_ad():
    result = PMA._creative_vid("google", "ad-456")
    assert "google" in result
    assert "ad-456" in result


def test_pma_snapshot_vid_contains_all_parts():
    result = PMA._snapshot_vid("meta", "ad-789", "run-001")
    assert "meta" in result
    assert "ad-789" in result
    assert "run-001" in result


# ─── public_malak_ads — _clean_text ──────────────────────────────────────────

def test_pma_clean_text_strips_tags():
    result = PMA._clean_text("<p>Hello <b>world</b></p>")
    assert "<" not in result
    assert "Hello" in result


def test_pma_clean_text_strips_script():
    result = PMA._clean_text("<script>bad()</script>content")
    assert "bad" not in result
    assert "content" in result


def test_pma_clean_text_respects_limit():
    result = PMA._clean_text("x" * 200, 50)
    assert len(result) <= 50


# ─── public_malak_ads — _extract_title ───────────────────────────────────────

def test_pma_extract_title_from_title_tag():
    result = PMA._extract_title("<html><title>Ad Page Title</title></html>")
    assert result == "Ad Page Title"


def test_pma_extract_title_empty_when_no_title():
    result = PMA._extract_title("<html><body>no title</body></html>")
    assert result == ""


# ─── public_malak_ads — _ads_library_url ─────────────────────────────────────

def test_pma_ads_library_url_meta_format():
    url = PMA._ads_library_url("meta", "etzhayyim", "JP")
    assert "facebook.com" in url


def test_pma_ads_library_url_google_format():
    url = PMA._ads_library_url("google", "etzhayyim", "JP")
    assert "google.com" in url


def test_pma_ads_library_url_linkedin_format():
    url = PMA._ads_library_url("linkedin", "etzhayyim", "JP")
    assert "linkedin.com" in url


def test_pma_ads_library_url_tiktok_format():
    url = PMA._ads_library_url("tiktok", "etzhayyim", "JP")
    assert "tiktok.com" in url


def test_pma_ads_library_url_x_format():
    url = PMA._ads_library_url("x", "etzhayyim", "JP")
    assert "x.com" in url


def test_pma_ads_library_url_unknown_returns_empty():
    url = PMA._ads_library_url("unknown_platform", "etzhayyim", "JP")
    assert url == ""


def test_pma_ads_library_url_country_uppercased():
    url = PMA._ads_library_url("meta", "test", "jp")
    assert "JP" in url


# ─── open_lei — _utc_now ─────────────────────────────────────────────────────

def test_ol_utc_now_returns_string():
    assert isinstance(OL._utc_now(), str)


def test_ol_utc_now_ends_with_z():
    assert OL._utc_now().endswith("Z")


def test_ol_utc_now_contains_t():
    assert "T" in OL._utc_now()


# ─── open_lei — _as_list / _str_list ─────────────────────────────────────────

def test_ol_as_list_with_list():
    result = OL._as_list(["a", "b"])
    assert result == ["a", "b"]


def test_ol_as_list_with_non_list_returns_empty():
    assert OL._as_list("not a list") == []
    assert OL._as_list(None) == []
    assert OL._as_list(42) == []


def test_ol_str_list_converts_items_to_str():
    result = OL._str_list([1, 2, 3])
    assert result == ["1", "2", "3"]


def test_ol_str_list_filters_falsy():
    result = OL._str_list([None, "", "valid"])
    # None and "" are falsy and filtered
    assert "valid" in result
    assert None not in result


def test_ol_str_list_empty_input():
    assert OL._str_list([]) == []


# ─── open_lei — gleif_manifest_plan ──────────────────────────────────────────

def test_ol_gleif_manifest_plan_returns_dict():
    result = OL.gleif_manifest_plan(as_of_date="2026-01-01")
    assert isinstance(result, dict)


def test_ol_gleif_manifest_plan_has_manifest_key():
    result = OL.gleif_manifest_plan(as_of_date="2026-01-01")
    assert "openLeiGleifManifestPlan" in result


def test_ol_gleif_manifest_plan_as_of_date_in_result():
    result = OL.gleif_manifest_plan(as_of_date="2026-05-01")
    manifest = result["openLeiGleifManifestPlan"]
    assert manifest["asOfDate"] == "2026-05-01"


def test_ol_gleif_manifest_plan_default_datasets():
    result = OL.gleif_manifest_plan()
    manifest = result["openLeiGleifManifestPlan"]
    assert len(manifest["datasets"]) > 0


def test_ol_gleif_manifest_plan_mode_default_delta():
    result = OL.gleif_manifest_plan()
    manifest = result["openLeiGleifManifestPlan"]
    assert manifest["mode"] == "delta"


def test_ol_gleif_manifest_plan_custom_mode():
    result = OL.gleif_manifest_plan(mode="backfill")
    manifest = result["openLeiGleifManifestPlan"]
    assert manifest["mode"] == "backfill"


def test_ol_gleif_manifest_plan_invalid_mode_defaults_delta():
    result = OL.gleif_manifest_plan(mode="invalid_mode")
    manifest = result["openLeiGleifManifestPlan"]
    assert manifest["mode"] == "delta"


# ─── open_lei — normalize_lei_record ─────────────────────────────────────────

def test_ol_normalize_lei_record_returns_dict():
    record = {"lei": "549300ABC123", "legalName": "Test Corp"}
    result = OL.normalize_lei_record(record)
    assert isinstance(result, dict)


def test_ol_normalize_lei_record_vertex_id_has_lei():
    record = {"lei": "549300ABC123"}
    result = OL.normalize_lei_record(record)
    assert "549300ABC123" in result["vertex_id"]


def test_ol_normalize_lei_record_vertex_id_starts_with_at():
    record = {"lei": "549300XYZ999"}
    result = OL.normalize_lei_record(record)
    assert result["vertex_id"].startswith("at://")


def test_ol_normalize_lei_record_unknown_status_for_non_issued():
    record = {"lei": "ABC123", "registrationStatus": "LAPSED"}
    result = OL.normalize_lei_record(record)
    assert result["status"] == "lapsed"


def test_ol_normalize_lei_record_active_for_issued():
    record = {
        "attributes": {
            "lei": "ABC123",
            "entity": {},
            "registration": {"status": "ISSUED"},
        }
    }
    result = OL.normalize_lei_record(record)
    assert result["status"] == "active"


def test_ol_normalize_lei_record_has_owner_did():
    result = OL.normalize_lei_record({"lei": "123"})
    assert result["owner_did"].startswith("did:")


# ─── hanrei — _utc_now ───────────────────────────────────────────────────────

def test_hr_utc_now_returns_string():
    assert isinstance(HR._utc_now(), str)


def test_hr_utc_now_contains_t():
    assert "T" in HR._utc_now()


# ─── hanrei — vid helpers ─────────────────────────────────────────────────────

def test_hr_job_vid_starts_with_at():
    result = HR._job_vid("job-001")
    assert result.startswith("at://")


def test_hr_job_vid_contains_job_id():
    result = HR._job_vid("my-job-id")
    assert "my-job-id" in result


def test_hr_case_vid_starts_with_at():
    result = HR._case_vid("rkey-abc")
    assert result.startswith("at://")


def test_hr_jurisdiction_vid_starts_with_at():
    result = HR._jurisdiction_vid("JPN")
    assert result.startswith("at://")


def test_hr_jurisdiction_vid_deterministic():
    a = HR._jurisdiction_vid("JPN")
    b = HR._jurisdiction_vid("JPN")
    assert a == b


def test_hr_jurisdiction_vid_differs_by_iso3():
    a = HR._jurisdiction_vid("JPN")
    b = HR._jurisdiction_vid("USA")
    assert a != b


def test_hr_court_vid_starts_with_at():
    result = HR._court_vid("supreme")
    assert result.startswith("at://")


def test_hr_court_vid_deterministic():
    a = HR._court_vid("supreme")
    b = HR._court_vid("supreme")
    assert a == b


# ─── hanrei — _new_job_id ─────────────────────────────────────────────────────

def test_hr_new_job_id_returns_string():
    assert isinstance(HR._new_job_id(), str)


def test_hr_new_job_id_16_chars():
    result = HR._new_job_id()
    assert len(result) == 16


def test_hr_new_job_id_hex():
    result = HR._new_job_id()
    int(result, 16)  # raises ValueError if not hex


def test_hr_new_job_id_is_random():
    a = HR._new_job_id()
    b = HR._new_job_id()
    assert a != b  # extremely unlikely to collide


# ─── mangaka — _build_workflow ────────────────────────────────────────────────

def test_mg_build_workflow_returns_dict():
    result = MG._build_workflow("manga prompt", "bad quality", 42, "panel_001", "animefull")
    assert isinstance(result, dict)


def test_mg_build_workflow_has_prompt_key():
    result = MG._build_workflow("prompt", "neg", 1, "fname", "ckpt")
    assert "prompt" in result


def test_mg_build_workflow_has_ksampler():
    result = MG._build_workflow("prompt", "neg", 1, "fname", "ckpt")
    inner = result["prompt"]
    assert any(v.get("class_type") == "KSampler" for v in inner.values())


def test_mg_build_workflow_seed_in_ksampler():
    result = MG._build_workflow("prompt", "neg", 999, "fname", "ckpt")
    inner = result["prompt"]
    ksampler = next(v for v in inner.values() if v.get("class_type") == "KSampler")
    assert ksampler["inputs"]["seed"] == 999


def test_mg_build_workflow_checkpoint_in_loader():
    result = MG._build_workflow("prompt", "neg", 1, "fname", "my_checkpoint")
    inner = result["prompt"]
    loader = next(v for v in inner.values() if v.get("class_type") == "CheckpointLoaderSimple")
    assert loader["inputs"]["ckpt_name"] == "my_checkpoint"


def test_mg_build_workflow_filename_in_save():
    result = MG._build_workflow("prompt", "neg", 1, "panel_xyz", "ckpt")
    inner = result["prompt"]
    saver = next(v for v in inner.values() if v.get("class_type") == "SaveImage")
    assert saver["inputs"]["filename_prefix"] == "panel_xyz"


def test_mg_build_workflow_has_clip_text_encode():
    result = MG._build_workflow("positive_prompt", "negative_prompt", 1, "f", "ckpt")
    inner = result["prompt"]
    text_encodes = [v for v in inner.values() if v.get("class_type") == "CLIPTextEncode"]
    assert len(text_encodes) >= 2
    texts = [v["inputs"]["text"] for v in text_encodes]
    assert "positive_prompt" in texts
    assert "negative_prompt" in texts
