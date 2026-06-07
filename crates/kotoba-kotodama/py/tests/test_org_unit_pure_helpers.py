"""Tests for pure helpers in org_unit.py: compute_path, compute_level, _make_code,
_make_vertex_id, _make_edge_id, normalize_org_unit_row, and dry_run paths for
register_org_unit, dissolve_org_unit, move_org_unit, add_org_member, remove_org_member."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import org_unit as OU


# ── compute_path ─────────────────────────────────────────────────────────────

def test_compute_path_root() -> None:
    assert OU.compute_path(None, "LEI123", "DEPT-001") == "/LEI123/DEPT-001"


def test_compute_path_nested() -> None:
    assert OU.compute_path("/LEI123/DEPT-001", "LEI123", "TEAM-A") == "/LEI123/DEPT-001/TEAM-A"


def test_compute_path_deep_nesting() -> None:
    parent = "/ABC/D/E"
    assert OU.compute_path(parent, "ABC", "F") == "/ABC/D/E/F"


def test_compute_path_root_empty_parent() -> None:
    assert OU.compute_path("", "LEIXX", "CODE") == "/LEIXX/CODE"


# ── compute_level ─────────────────────────────────────────────────────────────

def test_compute_level_root_no_parent() -> None:
    assert OU.compute_level(None) == 0


def test_compute_level_child() -> None:
    assert OU.compute_level(0) == 1


def test_compute_level_grandchild() -> None:
    assert OU.compute_level(1) == 2


def test_compute_level_deep() -> None:
    assert OU.compute_level(4) == 5


# ── _make_code ────────────────────────────────────────────────────────────────

def test_make_code_provided_returned() -> None:
    code = OU._make_code("DEPT-001", "LEI123", "Finance")
    assert code == "DEPT-001"


def test_make_code_provided_uppercased() -> None:
    code = OU._make_code("dept-001", "LEI123", "Finance")
    assert code == "DEPT-001"


def test_make_code_provided_spaces_become_dashes() -> None:
    code = OU._make_code("dept 001", "LEI123", "Finance")
    assert code == "DEPT-001"


def test_make_code_generated_when_none() -> None:
    code = OU._make_code(None, "LEI123ABC", "Finance Dept")
    assert code  # non-empty
    assert len(code) <= 40


def test_make_code_generated_deterministic() -> None:
    c1 = OU._make_code(None, "LEI123", "Engineering")
    c2 = OU._make_code(None, "LEI123", "Engineering")
    assert c1 == c2


def test_make_code_generated_different_inputs_differ() -> None:
    c1 = OU._make_code(None, "LEI123", "Engineering")
    c2 = OU._make_code(None, "LEI123", "Finance")
    assert c1 != c2


def test_make_code_empty_string_treated_as_none() -> None:
    code_empty = OU._make_code("", "LEI123", "Finance")
    code_none  = OU._make_code(None, "LEI123", "Finance")
    assert code_empty == code_none


# ── _make_vertex_id ───────────────────────────────────────────────────────────

def test_make_vertex_id_format() -> None:
    vid = OU._make_vertex_id("LEI123", "DEPT-001")
    assert vid.startswith("at://did:web:open-lei.etzhayyim.com/")
    assert "LEI123-DEPT-001" in vid


def test_make_vertex_id_collection() -> None:
    vid = OU._make_vertex_id("LEI123", "DEPT-001")
    assert "com.etzhayyim.apps.openLei.orgUnit" in vid


# ── _make_edge_id ─────────────────────────────────────────────────────────────

def test_make_edge_id_format() -> None:
    eid = OU._make_edge_id("src-vid", "dst-vid", "child_of")
    assert eid.startswith("edge-org-child_of-")


def test_make_edge_id_deterministic() -> None:
    e1 = OU._make_edge_id("A", "B", "child_of")
    e2 = OU._make_edge_id("A", "B", "child_of")
    assert e1 == e2


def test_make_edge_id_different_roles_differ() -> None:
    e1 = OU._make_edge_id("A", "B", "child_of")
    e2 = OU._make_edge_id("A", "B", "member_of")
    assert e1 != e2


# ── normalize_org_unit_row ────────────────────────────────────────────────────

def test_normalize_org_unit_row_required_fields() -> None:
    row = OU.normalize_org_unit_row(
        lei="LEI123", lei_vertex_id="lei-vid",
        org_type="department", name="Finance",
        code="FIN-001", path="/LEI123/FIN-001", level=0,
    )
    for key in ("vertex_id", "lei", "org_type", "name", "code", "path", "level",
                "status", "valid_from", "created_at", "sensitivity_ord",
                "owner_did", "org_id", "user_id", "actor_id"):
        assert key in row, f"missing key: {key}"


def test_normalize_org_unit_row_status_active() -> None:
    row = OU.normalize_org_unit_row(
        lei="L", lei_vertex_id="v", org_type="team", name="Alpha",
        code="ALPHA", path="/L/ALPHA", level=0,
    )
    assert row["status"] == "active"


def test_normalize_org_unit_row_valid_until_none() -> None:
    row = OU.normalize_org_unit_row(
        lei="L", lei_vertex_id="v", org_type="team", name="Beta",
        code="BETA", path="/L/BETA", level=0,
    )
    assert row["valid_until"] is None


def test_normalize_org_unit_row_vertex_id_contains_code() -> None:
    row = OU.normalize_org_unit_row(
        lei="LEI789", lei_vertex_id="v", org_type="project", name="P",
        code="PROJ-X", path="/LEI789/PROJ-X", level=1,
    )
    assert "LEI789-PROJ-X" in row["vertex_id"]


def test_normalize_org_unit_row_optional_fields_none() -> None:
    row = OU.normalize_org_unit_row(
        lei="L", lei_vertex_id="v", org_type="committee", name="C",
        code="C1", path="/L/C1", level=0,
    )
    assert row["parent_org_vid"] is None
    assert row["name_en"] is None
    assert row["purpose"] is None
    assert row["url"] is None
    assert row["props"] is None


def test_normalize_org_unit_row_props_serialized() -> None:
    row = OU.normalize_org_unit_row(
        lei="L", lei_vertex_id="v", org_type="board", name="B",
        code="B1", path="/L/B1", level=0,
        props={"key": "val"},
    )
    import json
    parsed = json.loads(row["props"])
    assert parsed["key"] == "val"


def test_normalize_org_unit_row_valid_from_custom() -> None:
    row = OU.normalize_org_unit_row(
        lei="L", lei_vertex_id="v", org_type="team", name="T",
        code="T1", path="/L/T1", level=0,
        valid_from="2025-01-01",
    )
    assert row["valid_from"] == "2025-01-01"


# ── register_org_unit (dry_run=True, no DB needed) ────────────────────────────

def test_register_org_unit_dry_run_returns_ok_false() -> None:
    result = OU.register_org_unit(
        lei="LEI000", lei_vertex_id="lei-vid", org_type="department", name="HR",
        dry_run=True,
    )
    # dry_run returns ok=False (no write happened)
    assert result["ok"] is False
    assert result["dryRun"] is True


def test_register_org_unit_dry_run_has_vertex_id() -> None:
    result = OU.register_org_unit(
        lei="LEI000", lei_vertex_id="lei-vid", org_type="department", name="HR",
        dry_run=True,
    )
    assert result["vertexId"]


def test_register_org_unit_dry_run_path_computed() -> None:
    result = OU.register_org_unit(
        lei="LXYZ", lei_vertex_id="lei-vid", org_type="team", name="Alpha",
        code="ALPHA", dry_run=True,
    )
    assert result["path"] == "/LXYZ/ALPHA"
    assert result["level"] == 0


def test_register_org_unit_dry_run_code_generated_if_omitted() -> None:
    result = OU.register_org_unit(
        lei="LGEN", lei_vertex_id="lei-vid", org_type="project", name="GenTest",
        dry_run=True,
    )
    assert result["code"]


def test_register_org_unit_dry_run_provided_code_used() -> None:
    result = OU.register_org_unit(
        lei="LXXX", lei_vertex_id="lei-vid", org_type="committee", name="Ethics",
        code="ETHICS-01", dry_run=True,
    )
    assert result["code"] == "ETHICS-01"
    assert "ETHICS-01" in result["path"]


# ── dissolve_org_unit (dry_run=True) ─────────────────────────────────────────

def test_dissolve_org_unit_dry_run_ok() -> None:
    result = OU.dissolve_org_unit(org_unit_vid="some-vid", dry_run=True)
    assert result["ok"] is True
    assert result["dryRun"] is True
    assert result["dissolved"] == 0


def test_dissolve_org_unit_dry_run_valid_until_today() -> None:
    import re
    result = OU.dissolve_org_unit(org_unit_vid="some-vid", dry_run=True)
    assert re.match(r"\d{4}-\d{2}-\d{2}", result["validUntil"])


def test_dissolve_org_unit_dry_run_custom_valid_until() -> None:
    result = OU.dissolve_org_unit(
        org_unit_vid="some-vid", valid_until="2025-12-31", dry_run=True,
    )
    assert result["validUntil"] == "2025-12-31"


def test_dissolve_org_unit_dry_run_empty_errors() -> None:
    result = OU.dissolve_org_unit(org_unit_vid="some-vid", dry_run=True)
    assert result["errors"] == []


# ── move_org_unit (dry_run=True) ──────────────────────────────────────────────

def test_move_org_unit_dry_run_ok() -> None:
    result = OU.move_org_unit(org_unit_vid="vid", lei="LEI", dry_run=True)
    assert result["ok"] is True
    assert result["dryRun"] is True
    assert result["updated"] == 0


def test_move_org_unit_dry_run_empty_errors() -> None:
    result = OU.move_org_unit(org_unit_vid="vid", lei="LEI", dry_run=True)
    assert result["errors"] == []


# ── add_org_member (dry_run=True) ─────────────────────────────────────────────

def test_add_org_member_dry_run_ok() -> None:
    result = OU.add_org_member(
        person_vertex_id="did:web:alice", org_unit_vid="org-vid",
        role="member", dry_run=True,
    )
    assert result["ok"] is True
    assert result["dryRun"] is True


def test_add_org_member_dry_run_has_edge_id() -> None:
    result = OU.add_org_member(
        person_vertex_id="did:web:alice", org_unit_vid="org-vid",
        role="chair", dry_run=True,
    )
    assert result["edgeId"]
    assert "edge-org-chair-" in result["edgeId"]


def test_add_org_member_dry_run_different_roles_different_edge_ids() -> None:
    r1 = OU.add_org_member(
        person_vertex_id="did:web:alice", org_unit_vid="org-vid",
        role="member", dry_run=True,
    )
    r2 = OU.add_org_member(
        person_vertex_id="did:web:alice", org_unit_vid="org-vid",
        role="lead", dry_run=True,
    )
    assert r1["edgeId"] != r2["edgeId"]


# ── remove_org_member (dry_run=True) ──────────────────────────────────────────

def test_remove_org_member_dry_run_ok() -> None:
    result = OU.remove_org_member(
        person_vertex_id="did:web:bob", org_unit_vid="org-vid", dry_run=True,
    )
    assert result["ok"] is True
    assert result["dryRun"] is True


def test_remove_org_member_dry_run_until_date() -> None:
    result = OU.remove_org_member(
        person_vertex_id="did:web:bob", org_unit_vid="org-vid",
        until="2025-06-30", dry_run=True,
    )
    assert result["until"] == "2025-06-30"


def test_remove_org_member_dry_run_until_defaults_to_today() -> None:
    import re
    result = OU.remove_org_member(
        person_vertex_id="did:web:bob", org_unit_vid="org-vid", dry_run=True,
    )
    assert re.match(r"\d{4}-\d{2}-\d{2}", result["until"])


# ── task wrappers ─────────────────────────────────────────────────────────────

def test_task_org_register_dry_run() -> None:
    result = OU.task_org_register(
        lei="LWRAP", leiVertexId="v", orgType="team", name="Wrap Team",
        code="WRAP", dryRun=True,
    )
    assert result["dryRun"] is True
    assert result["path"] == "/LWRAP/WRAP"


def test_task_org_dissolve_dry_run() -> None:
    result = OU.task_org_dissolve(orgUnitVid="some-vid", dryRun=True)
    assert result["dryRun"] is True


def test_task_org_move_dry_run() -> None:
    result = OU.task_org_move(orgUnitVid="v", lei="L", dryRun=True)
    assert result["dryRun"] is True


def test_task_org_add_member_dry_run() -> None:
    result = OU.task_org_add_member(
        personVertexId="did:web:alice", orgUnitVid="org", role="member", dryRun=True,
    )
    assert result["ok"] is True


def test_task_org_remove_member_dry_run() -> None:
    result = OU.task_org_remove_member(
        personVertexId="did:web:bob", orgUnitVid="org", dryRun=True,
    )
    assert result["ok"] is True
