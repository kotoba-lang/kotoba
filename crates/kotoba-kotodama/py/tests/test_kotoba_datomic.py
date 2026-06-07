"""Unit tests for the kotoba Datomic substrate client (RW-free replacement).

Covers the pure EDN serialization + vertex/edge row→entity mapping + rw_sql-shim
query construction. Live transact/q paths (XRPC POST to a kotoba node) are not
exercised here — they mirror the proven actor methods/transact.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama import kotoba_datomic as kd


# ── EDN serialization ──
def test_edn_val_scalars() -> None:
    assert kd.edn_val(None) == "nil"
    assert kd.edn_val(True) == "true"
    assert kd.edn_val(False) == "false"
    assert kd.edn_val(42) == "42"
    assert kd.edn_val(3.5) == "3.5"


def test_edn_val_string_vs_keyword_passthrough() -> None:
    assert kd.edn_val("hello world") == '"hello world"'
    assert kd.edn_val(":vertex.employee/name") == ":vertex.employee/name"
    # a colon string with a space is NOT a keyword → quoted
    assert kd.edn_val(":not a kw") == '":not a kw"'


def test_edn_val_string_escaping() -> None:
    assert kd.edn_val('say "hi"') == '"say \\"hi\\""'
    assert kd.edn_val("a\nb") == '"a\\nb"'


def test_edn_val_collections() -> None:
    assert kd.edn_val([1, 2, 3]) == "[1 2 3]"
    assert kd.edn_val({":a": 1}) == "{:a 1}"


def test_to_tx_edn_empty_and_nonempty() -> None:
    assert kd.to_tx_edn([]) == "[]"
    out = kd.to_tx_edn([{":vertex.x/vertex-id": "at://1"}])
    assert out.startswith("[{")
    assert ":vertex.x/vertex-id" in out
    assert '"at://1"' in out


# ── table → attribute namespace ──
def test_table_attr_namespace() -> None:
    assert kd.table_attr_namespace("vertex_employee") == "vertex.employee"
    assert kd.table_attr_namespace("edge_actor_has_role") == "edge.actor-has-role"
    assert kd.table_attr_namespace("plain_table") == "ent.plain-table"


def test_identity_attr() -> None:
    assert kd.identity_attr("vertex_employee") == ":vertex.employee/vertex-id"
    assert kd.identity_attr("edge_x", "edge_id") == ":edge.x/edge-id"


# ── row → entity ──
def test_row_to_entity_maps_and_drops_none() -> None:
    ent = kd.row_to_entity(
        "vertex_employee",
        {"vertex_id": "at://did/x", "name": "Ada", "hired_at": "2026-01-01", "manager": None},
    )
    assert ent == {
        ":vertex.employee/vertex-id": "at://did/x",
        ":vertex.employee/name": "Ada",
        ":vertex.employee/hired-at": "2026-01-01",
    }
    assert ":vertex.employee/manager" not in ent  # None dropped (no NULL datom)


def test_schema_install_edn_declares_unique_identity() -> None:
    edn = kd.schema_install_edn("vertex_employee", ["vertex_id", "name"])
    assert ":vertex.employee/vertex-id" in edn
    assert ":db.unique/identity" in edn
    assert ":db.cardinality/one" in edn


# ── client construction + select query shape (no network) ──
def test_client_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KOTOBA_URL", raising=False)
    monkeypatch.delenv("KOTODAMA_KOTOBA_GRAPH", raising=False)
    c = kd.KotobaDatomicClient()
    assert c.url == kd.DEFAULT_URL
    assert c.graph == kd.DEFAULT_GRAPH


def test_select_rows_builds_pull_query(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_q(self, query_edn, args=(), *, graph=None):  # noqa: ANN001
        captured["query"] = query_edn
        return [[{":vertex.employee/vertex-id": "at://1", ":vertex.employee/name": "Ada"}]]

    monkeypatch.setattr(kd.KotobaDatomicClient, "q", fake_q)
    c = kd.KotobaDatomicClient()
    rows = c.select_rows("vertex_employee", ["vertex_id", "name"])
    assert "(pull ?e [:vertex.employee/vertex-id :vertex.employee/name])" in captured["query"]
    assert "[?e :vertex.employee/vertex-id _]" in captured["query"]
    # projected back to plain RW-shaped row (kebab → snake)
    assert rows == [{"vertex_id": "at://1", "name": "Ada"}]


def test_transact_requires_credential_or_dryrun(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KOTOBA_TOKEN", raising=False)
    monkeypatch.delenv("KOTOBA_SESSION_POP", raising=False)
    monkeypatch.delenv("KOTODAMA_KOTOBA_DRYRUN", raising=False)
    c = kd.KotobaDatomicClient()
    with pytest.raises(kd.KotobaTransactError):
        c.transact("[]")


def test_transact_dryrun_skips_write(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    monkeypatch.setenv("KOTODAMA_KOTOBA_DRYRUN", "1")
    c = kd.KotobaDatomicClient()
    res = c.insert_row("vertex_employee", {"vertex_id": "at://1", "name": "Ada"})
    assert res.get("dry_run") is True
    out = capsys.readouterr().out
    assert "dry-run" in out
