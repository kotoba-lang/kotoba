"""Pure tests for Alembic revision files (ADR-2605080400).

No DB, no network, no RisingWave connection required.

Coverage:
- Every revision file under alembic/versions/ is importable as a module
- Each has ``revision``, ``down_revision``, ``upgrade``, ``downgrade`` attributes
- No revision targets vertex_* / edge_* / mv_* tables (scope guard)
- upgrade() and downgrade() are callable
- Revision chain forms a valid DAG (no duplicate revision IDs)
- py_audit_langgraph_event revision creates correct table + indexes
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional

import pytest

_py_root = Path(__file__).resolve().parents[1]
_versions_dir = _py_root / "alembic" / "versions"

_REVISION_FILES = sorted(_versions_dir.glob("*.py"))

_FORBIDDEN_RE = re.compile(
    r"(?:CREATE|DROP|ALTER)\s+(?:TABLE|MATERIALIZED\s+VIEW|INDEX\s+ON)\s+"
    r"(?:IF\s+(?:NOT\s+)?EXISTS\s+)?(?:ON\s+)?([a-zA-Z_][a-zA-Z0-9_.]*)",
    re.IGNORECASE,
)
_FORBIDDEN_PREFIXES = ("vertex_", "edge_", "mv_", "graphar.")


def _load_revision(path: Path) -> ModuleType:
    """Load a revision module, stubbing out alembic.op (proxy requires live context)."""
    import unittest.mock as mock
    import types

    # alembic.op is a proxy that fails outside a migration context; stub it.
    stub_op = mock.MagicMock()
    stub_alembic = types.ModuleType("alembic")
    stub_alembic.op = stub_op  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader, f"Cannot load {path}"
    mod = importlib.util.module_from_spec(spec)

    # Inject the stub into sys.modules for the duration of exec_module
    orig = sys.modules.get("alembic")
    sys.modules["alembic"] = stub_alembic
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    finally:
        if orig is not None:
            sys.modules["alembic"] = orig
        else:
            sys.modules.pop("alembic", None)
    return mod


# ---------------------------------------------------------------------------
# Parametrized checks over every revision file
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rev_file", _REVISION_FILES, ids=[f.name for f in _REVISION_FILES])
class TestRevisionFiles:
    def test_has_required_attributes(self, rev_file: Path) -> None:
        mod = _load_revision(rev_file)
        for attr in ("revision", "down_revision", "upgrade", "downgrade"):
            assert hasattr(mod, attr), f"{rev_file.name}: missing attribute '{attr}'"

    def test_revision_is_string(self, rev_file: Path) -> None:
        mod = _load_revision(rev_file)
        assert isinstance(mod.revision, str) and mod.revision, \
            f"{rev_file.name}: 'revision' must be a non-empty string"

    def test_upgrade_and_downgrade_are_callable(self, rev_file: Path) -> None:
        mod = _load_revision(rev_file)
        assert callable(mod.upgrade), f"{rev_file.name}: 'upgrade' is not callable"
        assert callable(mod.downgrade), f"{rev_file.name}: 'downgrade' is not callable"

    def test_no_graph_schema_tables(self, rev_file: Path) -> None:
        source = rev_file.read_text(encoding="utf-8")
        for m in _FORBIDDEN_RE.finditer(source):
            table = m.group(1).lower()
            for prefix in _FORBIDDEN_PREFIXES:
                assert not table.startswith(prefix), (
                    f"{rev_file.name}: DDL targeting '{table}' (prefix '{prefix}') "
                    f"violates ADR-2605080400 scope — use Kysely TypeScript migration instead."
                )

    def test_python_owned_table_prefix(self, rev_file: Path) -> None:
        source = rev_file.read_text(encoding="utf-8")
        create_matches = re.findall(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
            source, re.IGNORECASE,
        )
        for table in create_matches:
            assert table.startswith("py_") or table.startswith("_sqlmesh") or table.startswith("pyzeebe"), (
                f"{rev_file.name}: table '{table}' does not use a Python-owned prefix "
                f"(py_* / _sqlmesh* / pyzeebe*) per ADR-2605080400"
            )


# ---------------------------------------------------------------------------
# Revision chain: no duplicate revision IDs
# ---------------------------------------------------------------------------

def test_no_duplicate_revision_ids() -> None:
    seen: dict[str, str] = {}
    for path in _REVISION_FILES:
        mod = _load_revision(path)
        rev_id = mod.revision
        assert rev_id not in seen, (
            f"Duplicate revision ID '{rev_id}' in {path.name} and {seen[rev_id]}"
        )
        seen[rev_id] = path.name


def test_revision_chain_no_cycle() -> None:
    """Verify down_revision references form a DAG (no cycles)."""
    revisions: dict[str, Optional[str]] = {}
    for path in _REVISION_FILES:
        mod = _load_revision(path)
        down = mod.down_revision
        # down_revision can be None, str, or tuple; normalise to str|None
        if isinstance(down, (list, tuple)):
            down = down[0] if down else None
        revisions[mod.revision] = down

    # Walk each chain; if we re-visit a node it's a cycle
    for start in revisions:
        visited = set()
        cur: Optional[str] = start
        while cur is not None:
            assert cur not in visited, f"Cycle detected at revision '{cur}'"
            visited.add(cur)
            cur = revisions.get(cur)


# ---------------------------------------------------------------------------
# Specific checks for 20260508_0001 (py_audit_langgraph_event)
# ---------------------------------------------------------------------------

class TestAuditLanggraphEventRevision:
    @pytest.fixture(autouse=True)
    def _mod(self):
        target = _versions_dir / "20260508_0001_py_audit_langgraph_event.py"
        assert target.exists(), "Revision file not found"
        self.mod = _load_revision(target)

    def test_revision_id(self) -> None:
        assert self.mod.revision == "20260508_0001"

    def test_is_initial_revision(self) -> None:
        assert self.mod.down_revision is None

    def test_creates_py_audit_table(self) -> None:
        source = (
            _versions_dir / "20260508_0001_py_audit_langgraph_event.py"
        ).read_text()
        assert "py_audit_langgraph_event" in source

    def test_creates_run_index(self) -> None:
        source = (
            _versions_dir / "20260508_0001_py_audit_langgraph_event.py"
        ).read_text()
        assert "idx_py_audit_lg_run" in source

    def test_creates_assistant_index(self) -> None:
        source = (
            _versions_dir / "20260508_0001_py_audit_langgraph_event.py"
        ).read_text()
        assert "idx_py_audit_lg_assistant" in source

    def test_downgrade_drops_table(self) -> None:
        source = (
            _versions_dir / "20260508_0001_py_audit_langgraph_event.py"
        ).read_text()
        assert "DROP TABLE IF EXISTS py_audit_langgraph_event" in source

    def test_has_ts_ms_bigint_column(self) -> None:
        source = (
            _versions_dir / "20260508_0001_py_audit_langgraph_event.py"
        ).read_text()
        assert "ts_ms" in source and "BIGINT" in source.upper()
