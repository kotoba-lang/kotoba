"""Pure-path tests for SQLMesh model files (ADR-2605080500).

Validates model file structure without requiring SQLMesh or a live DB.
Checks:
- Each .sql file in sqlmesh/models/ has a MODEL(...) block
- Required fields: name, kind, dialect, description
- No vertex_* / edge_* table names appear as DDL targets (read-only OK)
- Audit files in sqlmesh/audits/ have AUDIT(...) blocks
- Coverage-gap minimax model matches the deployed RisingWave SQL shape
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_py_root = Path(__file__).resolve().parents[1]
_models_dir = _py_root / "sqlmesh" / "models"
_audits_dir = _py_root / "sqlmesh" / "audits"

_MODEL_FILES = sorted(_models_dir.glob("*.sql"))
_AUDIT_FILES = sorted(_audits_dir.glob("*.sql"))

_MODEL_BLOCK_RE = re.compile(r"MODEL\s*\(", re.IGNORECASE)
_AUDIT_BLOCK_RE = re.compile(r"AUDIT\s*\(", re.IGNORECASE)
_DDL_FORBIDDEN_RE = re.compile(
    r"(?:CREATE|DROP|ALTER)\s+(?:TABLE|MATERIALIZED\s+VIEW)\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?(vertex_|edge_)",
    re.IGNORECASE,
)

_REQUIRED_MODEL_FIELDS = ("name", "kind", "dialect", "description")


def _parse_model_block(sql: str) -> dict[str, str]:
    """Extract key=value pairs from the first MODEL(...) block."""
    m = re.search(r"MODEL\s*\((.*?)\)", sql, re.IGNORECASE | re.DOTALL)
    if not m:
        return {}
    block = m.group(1)
    result: dict[str, str] = {}
    for field in _REQUIRED_MODEL_FIELDS:
        fm = re.search(rf"\b{field}\s+([^\s,)]+)", block, re.IGNORECASE)
        if fm:
            result[field] = fm.group(1).strip("'\"")
    return result


@pytest.mark.parametrize("model_file", _MODEL_FILES, ids=[f.name for f in _MODEL_FILES])
class TestModelFiles:
    def test_has_model_block(self, model_file: Path) -> None:
        assert _MODEL_BLOCK_RE.search(model_file.read_text()), \
            f"{model_file.name}: missing MODEL(...) block"

    def test_required_fields_present(self, model_file: Path) -> None:
        fields = _parse_model_block(model_file.read_text())
        for field in _REQUIRED_MODEL_FIELDS:
            assert field in fields, \
                f"{model_file.name}: MODEL block missing required field '{field}'"

    def test_dialect_is_postgres(self, model_file: Path) -> None:
        fields = _parse_model_block(model_file.read_text())
        assert fields.get("dialect") == "postgres", \
            f"{model_file.name}: dialect must be 'postgres' for RisingWave compat"

    def test_no_ddl_on_graph_schema_tables(self, model_file: Path) -> None:
        sql = model_file.read_text()
        match = _DDL_FORBIDDEN_RE.search(sql)
        assert match is None, (
            f"{model_file.name}: DDL targeting vertex_*/edge_* table "
            f"'{match.group(0) if match else ''}' found — graph-schema DDL "
            f"belongs in 30-graph/graph-schema/migrations/"
        )

    def test_select_statement_present(self, model_file: Path) -> None:
        sql = model_file.read_text()
        assert re.search(r"\bSELECT\b", sql, re.IGNORECASE), \
            f"{model_file.name}: no SELECT statement found"

    def test_filename_matches_model_name(self, model_file: Path) -> None:
        fields = _parse_model_block(model_file.read_text())
        name = fields.get("name", "")
        # name is like 'dev.mv_foo' — stem should end with the file stem
        assert model_file.stem in name, \
            f"{model_file.name}: MODEL name '{name}' does not contain file stem '{model_file.stem}'"


class TestCoverageGapMinimax:
    """Shape tests specific to the coverage-gap minimax model."""

    @pytest.fixture
    def sql(self) -> str:
        return (_models_dir / "mv_coverage_gap_minimax.sql").read_text()

    def test_sources_vertex_coverage_recipe(self, sql: str) -> None:
        assert "vertex_coverage_recipe" in sql

    def test_sources_vertex_coverage_stats(self, sql: str) -> None:
        assert "vertex_coverage_stats" in sql

    def test_computes_regret(self, sql: str) -> None:
        assert "regret" in sql.lower()

    def test_excludes_defer(self, sql: str) -> None:
        assert "'defer'" in sql

    def test_left_join_on_stats(self, sql: str) -> None:
        assert re.search(r"LEFT\s+JOIN\s+vertex_coverage_stats", sql, re.IGNORECASE)

    def test_orders_by_regret(self, sql: str) -> None:
        assert re.search(r"ORDER\s+BY\s+regret", sql, re.IGNORECASE)


class TestWorldCollectionCoverageLive:
    """Shape tests for mv_world_collection_coverage_live."""

    @pytest.fixture
    def sql(self) -> str:
        return (_models_dir / "mv_world_collection_coverage_live.sql").read_text()

    def test_sources_dim_world_domain_collection(self, sql: str) -> None:
        assert "dim_world_domain_collection" in sql

    def test_joins_mv_world_did_per_host(self, sql: str) -> None:
        assert "mv_world_did_per_host" in sql

    def test_joins_mv_world_record_per_host_collection(self, sql: str) -> None:
        assert "mv_world_record_per_host_collection" in sql

    def test_computes_coverage_rate(self, sql: str) -> None:
        assert "coverage_rate" in sql.lower()

    def test_greatest_coalesce_pattern(self, sql: str) -> None:
        assert re.search(r"GREATEST\s*\(", sql, re.IGNORECASE)


@pytest.mark.parametrize("audit_file", _AUDIT_FILES, ids=[f.name for f in _AUDIT_FILES])
class TestAuditFiles:
    def test_has_audit_block(self, audit_file: Path) -> None:
        assert _AUDIT_BLOCK_RE.search(audit_file.read_text()), \
            f"{audit_file.name}: missing AUDIT(...) block"

    def test_has_select_statement(self, audit_file: Path) -> None:
        assert re.search(r"\bSELECT\b", audit_file.read_text(), re.IGNORECASE), \
            f"{audit_file.name}: no SELECT statement"
