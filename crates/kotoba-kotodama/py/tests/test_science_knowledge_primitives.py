"""Tests for science_knowledge primitives (pure helpers + mocked DB tasks)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path as _P
from unittest.mock import MagicMock, patch

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import science_knowledge as SK  # noqa: E402


# ─── pure helper tests ────────────────────────────────────────────────────

def test_vid_format():
    v = SK._vid("chemistry", "element", "Fe")
    assert v == "at://did:web:chemistry.etzhayyim.com/com.etzhayyim.apps.chemistry.element/Fe"


def test_edge_id_is_deterministic():
    a = SK._edge_id("taxon:1", "model:2")
    b = SK._edge_id("taxon:1", "model:2")
    assert a == b
    assert len(a) == 24


def test_edge_id_differs_for_different_inputs():
    a = SK._edge_id("taxon:1", "model:2")
    b = SK._edge_id("taxon:1", "model:3")
    assert a != b


def test_elements_list_has_expected_first_entries():
    assert len(SK._ELEMENTS) >= 20
    first = SK._ELEMENTS[0]
    assert first["sym"] == "H"
    assert first["en"] == "Hydrogen"
    assert first["z"] == 1


def test_vegetation_profiles_count():
    assert len(SK._VEGETATION_RENDER_PROFILES) == 7


def test_vegetation_profiles_have_required_fields():
    required = {"commonName", "division", "habit", "canopy", "heightRange"}
    for prof in SK._VEGETATION_RENDER_PROFILES:
        assert required.issubset(prof.keys()), f"Missing fields in {prof['commonName']}"


def test_cpk_colors_known_elements():
    assert "H" in SK._CPK_COLORS
    assert "C" in SK._CPK_COLORS
    assert "O" in SK._CPK_COLORS
    # each color should be RGB triple in [0, 1]
    for sym, (r, g, b) in SK._CPK_COLORS.items():
        assert 0.0 <= r <= 1.0
        assert 0.0 <= g <= 1.0
        assert 0.0 <= b <= 1.0


# ─── seed_periodic_elements (mocked DB) ──────────────────────────────────

def _make_cursor_ctx():
    cur = MagicMock()
    cur.__enter__ = lambda s: cur
    cur.__exit__ = MagicMock(return_value=False)
    return cur


def test_seed_periodic_elements_inserts_batch(monkeypatch):
    inserts = []

    class FakeCur:
        def execute(self, sql, params): inserts.append(params)
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(SK, "sync_cursor", lambda: FakeCur())
    result = SK.seed_periodic_elements(batch_size=5)
    assert result["inserted"] == 5
    assert result["total"] == len(SK._ELEMENTS)
    assert len(inserts) == 5


def test_seed_periodic_elements_uses_cpk_color(monkeypatch):
    executed = []

    class FakeCur:
        def execute(self, sql, params): executed.append(params)
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(SK, "sync_cursor", lambda: FakeCur())
    SK.seed_periodic_elements(batch_size=1)
    # H is index 0 — should use CPK white (1.0, 1.0, 1.0)
    params = executed[0]
    # kami_color_r, kami_color_g, kami_color_b are at indices 17, 18, 19
    assert params[17] == 1.0  # R for Hydrogen
    assert params[18] == 1.0  # G
    assert params[19] == 1.0  # B


# ─── seed_vegetation_taxa (mocked DB) ────────────────────────────────────

def test_seed_vegetation_taxa_seeds_all_profiles(monkeypatch):
    executes = []

    class FakeCur:
        def execute(self, sql, params): executes.append(sql)
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(SK, "sync_cursor", lambda: FakeCur())
    result = SK.seed_vegetation_taxa()
    assert result["seeded"] == 7
    # Each profile generates 4 SQL statements (taxon + model_def + edge + UPDATE)
    assert len(executes) == 7 * 4


# ─── seed_pbr_materials (mocked DB) ──────────────────────────────────────

def test_seed_pbr_materials_returns_seeded_count(monkeypatch):
    class FakeCur:
        def execute(self, sql, params): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(SK, "sync_cursor", lambda: FakeCur())
    result = SK.seed_pbr_materials()
    assert "materialsSeeded" in result
    assert isinstance(result["materialsSeeded"], int)
    assert result["materialsSeeded"] >= 0


# ─── ingest_arxiv_batch (mocked HTTP) ────────────────────────────────────

def test_ingest_arxiv_batch_processes_entries(monkeypatch):
    xml_response = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2301.00001v1</id>
        <title>Test Paper</title>
        <summary>Abstract text about AI.</summary>
        <published>2023-01-01T00:00:00Z</published>
        <author><name>Alice</name></author>
      </entry>
    </feed>"""

    class FakeResp:
        async def text(self): return xml_response
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    class FakeSession:
        def get(self, *a, **kw): return FakeResp()
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    import aiohttp
    monkeypatch.setattr(aiohttp, "ClientSession", lambda: FakeSession())

    class FakeCur:
        def execute(self, sql, params): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(SK, "sync_cursor", lambda: FakeCur())

    result = asyncio.run(SK.ingest_arxiv_batch(query="cs.AI", domain="cs_ai", limit=10))
    assert "inserted" in result
    assert result["inserted"] == 1


def test_ingest_arxiv_batch_handles_http_error(monkeypatch):
    import pytest
    import aiohttp

    class ErrorResp:
        async def text(self): raise aiohttp.ClientError("network error")
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    class ErrorSession:
        def get(self, *a, **kw): return ErrorResp()
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    monkeypatch.setattr(aiohttp, "ClientSession", lambda: ErrorSession())

    with pytest.raises(aiohttp.ClientError):
        asyncio.run(SK.ingest_arxiv_batch(query="cs.AI", domain="cs_ai", limit=5))


# ─── embed_paper_batch (mocked) ──────────────────────────────────────────

def test_embed_paper_batch_with_no_pending(monkeypatch):
    class FakeCur:
        def execute(self, sql, params=None): pass
        def fetchall(self): return []
        description = [("vertex_id",), ("abstract",)]
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(SK, "sync_cursor", lambda: FakeCur())
    result = asyncio.run(SK.embed_paper_batch(batch_size=10))
    assert result["embedded"] == 0


# ─── _extract_entities_llm ───────────────────────────────────────────────

def test_extract_entities_llm_returns_list(monkeypatch):
    import urllib.request

    resp_data = json.dumps({"content": [{"text": '[{"name":"transformer","type":"method"}]'}]}).encode()

    class FakeResp:
        def read(self, n): return resp_data
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: FakeResp())
    entities = SK._extract_entities_llm("Abstract about transformer models")
    assert isinstance(entities, list)


def test_extract_entities_llm_returns_empty_on_error(monkeypatch):
    import urllib.request

    def raise_error(*a, **kw):
        raise Exception("network error")

    monkeypatch.setattr(urllib.request, "urlopen", raise_error)
    entities = SK._extract_entities_llm("Some abstract")
    assert entities == []


# ─── _resolve_to_ontology ────────────────────────────────────────────────

def test_resolve_to_ontology_returns_empty_when_no_db_match(monkeypatch):
    class FakeCur:
        def execute(self, sql, params=None): pass
        def fetchone(self): return None
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(SK, "sync_cursor", lambda: FakeCur())
    entities = [{"name": "transformer", "type": "method"}]
    result = SK._resolve_to_ontology(entities)
    assert isinstance(result, list)
    # When no DB match, the entity is excluded from resolved list
    assert len(result) == 0


def test_resolve_to_ontology_includes_matched_element(monkeypatch):
    class FakeCur:
        def execute(self, sql, params=None): pass
        def fetchone(self): return ("at://did:web:chemistry.etzhayyim.com/element/Fe",)
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(SK, "sync_cursor", lambda: FakeCur())
    entities = [{"name": "Iron", "kind": "element"}]
    result = SK._resolve_to_ontology(entities)
    assert len(result) == 1
    assert "element_vid" in result[0]


# ─── register ────────────────────────────────────────────────────────────

def test_register_exposes_seven_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    SK.register(FakeWorker(), timeout_ms=60_000)
    assert set(registered) == {
        "science.paper.fetchArxiv",
        "science.paper.embedBatch",
        "science.paper.linkGraph",
        "science.element.seedElements",
        "science.element.seedMaterials",
        "science.taxon.syncNcbi",
        "science.taxon.seedVegetation",
    }
