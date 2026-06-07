"""Pure-path tests for business_person career-enrichment and LEI tasks.

Covers tasks not tested in test_business_person_guards.py:
  - select_persons_from_centrality_mv  (noop cursor → empty)
  - select_stale_persons               (noop cursor → empty)
  - fetch_news_career                  (empty persons → empty output)
  - extract_career_llm                 (empty pageTexts → empty)
  - write_career_enrichment            (empty extractions → early return)
  - mine_relations                     (empty persons → early return)
  - extract_relations_llm              (empty pairs → empty)
  - write_relations                    (empty relations → early return)
  - extract_corporate_hp_roles         (no input → empty)
  - select_orgs_needing_lei            (noop cursor → empty)
  - resolve_lei                        (empty orgs → empty)
  - fetch_lei_hierarchy                (empty resolved → empty)
  - write_lei_entities                 (empty enriched → early return)
  - select_global_target_orgs         (noop cursor → pending = all global orgs)
  - discover_global_execs              (empty orgs → empty)
  - write_global_execs                 (empty persons → early return)
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# ── db_sync stub with iterable description ────────────────────────────────────
_db_stub = types.ModuleType("kotodama.db_sync")


def _noop_cursor():
    class _C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **kw): pass
        def fetchone(self): return None
        def fetchall(self): return []
        description = []  # iterable: [d[0] for d in []] = []
        rowcount = 0
    return _C()


_db_stub.sync_cursor = _noop_cursor  # type: ignore[attr-defined]

if "kotodama" not in sys.modules:
    _pkg = types.ModuleType("kotodama")
    _pkg.__path__ = [str(_py_src / "kotodama")]  # type: ignore[attr-defined]
    _pkg.__package__ = "kotodama"
    sys.modules["kotodama"] = _pkg

# stub llm so local imports inside tasks don't fail
_llm_stub = types.ModuleType("kotodama.llm")
_llm_stub.call_tier = lambda *a, **kw: {"content": "", "model": "", "usage": {}}  # type: ignore[attr-defined]
_llm_stub.call_tier_json = lambda *a, **kw: {"data": {"events": [], "relations": [], "persons": []}}  # type: ignore[attr-defined]
_llm_stub.LlmError = type("LlmError", (Exception,), {})  # type: ignore[attr-defined]
sys.modules["kotodama.llm"] = _llm_stub
_pyma = sys.modules["kotodama"]
if not hasattr(_pyma, "llm"):
    _pyma.llm = _llm_stub  # type: ignore[attr-defined]

# ── load business_person in isolation with our stub ───────────────────────────
_MOD_NAME = "_bp_career_lei_pure"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "primitives" / "business_person.py"
    _prev_db = sys.modules.get("kotodama.db_sync")
    sys.modules["kotodama.db_sync"] = _db_stub
    try:
        _spec = importlib.util.spec_from_file_location(_MOD_NAME, _src)
        _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
        sys.modules[_MOD_NAME] = _mod
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    finally:
        if _prev_db is not None:
            sys.modules["kotodama.db_sync"] = _prev_db

BP = sys.modules[_MOD_NAME]

import pytest  # noqa: E402


# ─── select_persons_from_centrality_mv ────────────────────────────────────────

def test_select_persons_centrality_mv_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_select_persons_from_centrality_mv())
    assert isinstance(result, dict)


def test_select_persons_centrality_mv_empty_with_noop() -> None:
    result = asyncio.run(BP.task_business_person_select_persons_from_centrality_mv())
    assert result["personsCount"] == 0
    assert result["persons"] == []


# ─── select_stale_persons ────────────────────────────────────────────────────

def test_select_stale_persons_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_select_stale_persons())
    assert isinstance(result, dict)


def test_select_stale_persons_empty_with_noop() -> None:
    result = asyncio.run(BP.task_business_person_select_stale_persons())
    assert result["personsCount"] == 0


def test_select_stale_persons_has_persons_key() -> None:
    result = asyncio.run(BP.task_business_person_select_stale_persons())
    assert "persons" in result


# ─── fetch_news_career ────────────────────────────────────────────────────────

def test_fetch_news_career_empty_persons_returns_empty() -> None:
    result = asyncio.run(BP.task_business_person_fetch_news_career(persons=[]))
    assert result["pageTexts"] == []


def test_fetch_news_career_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_fetch_news_career())
    assert isinstance(result, dict)


def test_fetch_news_career_has_page_texts_key() -> None:
    result = asyncio.run(BP.task_business_person_fetch_news_career())
    assert "pageTexts" in result


# ─── extract_career_llm ───────────────────────────────────────────────────────

def test_extract_career_llm_empty_returns_empty() -> None:
    result = asyncio.run(BP.task_business_person_extract_career_llm())
    assert result["extractions"] == []
    assert result["extractionsCount"] == 0


def test_extract_career_llm_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_extract_career_llm(pageTexts=[]))
    assert isinstance(result, dict)


# ─── write_career_enrichment ──────────────────────────────────────────────────

def test_write_career_enrichment_empty_ok() -> None:
    result = asyncio.run(BP.task_business_person_write_career_enrichment())
    assert result["ok"] is True
    assert result["recordsWritten"] == 0


def test_write_career_enrichment_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_write_career_enrichment(extractions=[]))
    assert isinstance(result, dict)


# ─── mine_relations ───────────────────────────────────────────────────────────

def test_mine_relations_empty_persons_returns_empty() -> None:
    result = asyncio.run(BP.task_business_person_mine_relations(persons=[]))
    assert result["pairs"] == []


def test_mine_relations_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_mine_relations())
    assert isinstance(result, dict)


def test_mine_relations_has_pairs_key() -> None:
    result = asyncio.run(BP.task_business_person_mine_relations(persons=[]))
    assert "pairs" in result


# ─── extract_relations_llm ───────────────────────────────────────────────────

def test_extract_relations_llm_empty_returns_empty() -> None:
    result = asyncio.run(BP.task_business_person_extract_relations_llm())
    assert result["relations"] == []
    assert result["relationsCount"] == 0


def test_extract_relations_llm_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_extract_relations_llm(pairs=[]))
    assert isinstance(result, dict)


# ─── write_relations ─────────────────────────────────────────────────────────

def test_write_relations_empty_ok() -> None:
    result = asyncio.run(BP.task_business_person_write_relations())
    assert result["ok"] is True
    assert result["written"] == 0


def test_write_relations_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_write_relations(relations=[]))
    assert isinstance(result, dict)


# ─── extract_corporate_hp_roles ──────────────────────────────────────────────

def test_extract_corporate_hp_roles_empty_returns_ok() -> None:
    result = asyncio.run(BP.task_business_person_extract_corporate_hp_roles())
    assert result["ok"] is True


def test_extract_corporate_hp_roles_empty_rows_zero() -> None:
    result = asyncio.run(BP.task_business_person_extract_corporate_hp_roles())
    assert result["recordsExtracted"] == 0
    assert result["rows"] == []


def test_extract_corporate_hp_roles_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_extract_corporate_hp_roles())
    assert isinstance(result, dict)


# ─── select_orgs_needing_lei ─────────────────────────────────────────────────

def test_select_orgs_needing_lei_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_select_orgs_needing_lei())
    assert isinstance(result, dict)


def test_select_orgs_needing_lei_empty_with_noop() -> None:
    result = asyncio.run(BP.task_business_person_select_orgs_needing_lei())
    assert result["orgsCount"] == 0
    assert result["orgs"] == []


# ─── resolve_lei ─────────────────────────────────────────────────────────────

def test_resolve_lei_empty_orgs_returns_empty() -> None:
    result = asyncio.run(BP.task_business_person_resolve_lei(orgs=[]))
    assert result["resolvedCount"] == 0


def test_resolve_lei_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_resolve_lei())
    assert isinstance(result, dict)


def test_resolve_lei_has_resolved_key() -> None:
    result = asyncio.run(BP.task_business_person_resolve_lei(orgs=[]))
    assert "resolved" in result


# ─── fetch_lei_hierarchy ─────────────────────────────────────────────────────

def test_fetch_lei_hierarchy_empty_returns_empty() -> None:
    result = asyncio.run(BP.task_business_person_fetch_lei_hierarchy(resolved=[]))
    assert result["enrichedCount"] == 0
    assert result["enriched"] == []


def test_fetch_lei_hierarchy_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_fetch_lei_hierarchy())
    assert isinstance(result, dict)


# ─── write_lei_entities ───────────────────────────────────────────────────────

def test_write_lei_entities_empty_ok() -> None:
    result = asyncio.run(BP.task_business_person_write_lei_entities())
    assert result["ok"] is True
    assert result["entitiesWritten"] == 0
    assert result["edgesWritten"] == 0


def test_write_lei_entities_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_write_lei_entities(enriched=[]))
    assert isinstance(result, dict)


# ─── select_global_target_orgs ───────────────────────────────────────────────

def test_select_global_target_orgs_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_select_global_target_orgs())
    assert isinstance(result, dict)


def test_select_global_target_orgs_has_keys() -> None:
    result = asyncio.run(BP.task_business_person_select_global_target_orgs())
    assert "orgs" in result
    assert "total" in result
    assert "pending" in result


def test_select_global_target_orgs_noop_all_pending() -> None:
    result = asyncio.run(BP.task_business_person_select_global_target_orgs())
    # noop cursor → covered=set() → all global orgs pending
    assert result["pending"] == result["total"]
    assert result["total"] > 0


# ─── discover_global_execs ───────────────────────────────────────────────────

def test_discover_global_execs_empty_orgs_returns_empty() -> None:
    result = asyncio.run(BP.task_business_person_discover_global_execs(orgs=[]))
    assert result["persons"] == []
    assert result["discovered"] == 0


def test_discover_global_execs_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_discover_global_execs(orgs=[]))
    assert isinstance(result, dict)


# ─── write_global_execs ──────────────────────────────────────────────────────

def test_write_global_execs_empty_returns_ok() -> None:
    result = asyncio.run(BP.task_business_person_write_global_execs(persons=[]))
    assert result["ok"] is True
    assert result["written"] == 0


def test_write_global_execs_has_skipped_key() -> None:
    result = asyncio.run(BP.task_business_person_write_global_execs(persons=[]))
    assert "skipped" in result


def test_write_global_execs_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_write_global_execs(persons=[]))
    assert isinstance(result, dict)
