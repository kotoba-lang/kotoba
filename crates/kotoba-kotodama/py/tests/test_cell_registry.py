"""test_cell_registry — unit tests for cells.toml registry loader.

Per ADR-2605215200 + ADR-2605202100. Tests for load_cell_registry() and
cells_for_node() added to cell_runner_main in Task 68.

Test cases:
  1. test_load_cell_registry_finds_file         — locates cells.toml from explicit path
  2. test_load_cell_registry_no_file_returns_empty — returns {} when no file found
  3. test_cells_for_node_filter_levi            — levi gets ShinkaHeartbeat + Karma + Validation + Joucho
  4. test_cells_for_node_filter_simeon          — simeon gets EvolutionEmission only
  5. test_cells_for_node_includes_wildcard      — "*" node cells appear on any node
"""

from __future__ import annotations

import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

# Ensure kotodama is importable from the src tree.
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from kotodama.cell_runner_main import cells_for_node, load_cell_registry


# ── Fixtures ──────────────────────────────────────────────────────────────────

CELLS_TOML_CONTENT = textwrap.dedent("""\
    [runner]
    node_name_env = "ETZHAYYIM_NODE_NAME"
    default_log_dir = "/var/log/etzhayyim/cells"
    healthz_port_range = [13000, 14000]

    [[cell]]
    name = "ShinkaHeartbeatCell"
    module = "kotodama.primitives.shinka_murakumo"
    entry = "shinka_heartbeat_cell"
    node = "levi"
    trigger = { kind = "cron", expr = "*/15 * * * *" }
    healthz_port = 13026
    adr = ["2605215200"]

    [[cell]]
    name = "KarmaHegemonObservationCell"
    module = "kotodama.primitives.shinka_murakumo"
    entry = "karma_hegemon_observation_cell"
    node = "levi"
    trigger = { kind = "mst-listener", listens_to = ["com.etzhayyim.shinka.kyumeiSignal"] }
    healthz_port = 13023
    adr = ["2605215200"]

    [[cell]]
    name = "EvolutionValidationCell"
    module = "kotodama.primitives.shinka_murakumo"
    entry = "evolution_validation_cell"
    node = "levi"
    trigger = { kind = "mst-listener", listens_to = ["com.etzhayyim.shinka.observeAdherent"] }
    healthz_port = 13024
    adr = ["2605215200", "2605215400"]

    [[cell]]
    name = "EvolutionEmissionCell"
    module = "kotodama.primitives.shinka_murakumo"
    entry = "evolution_emission_cell"
    node = "simeon"
    trigger = { kind = "mst-listener", listens_to = ["com.etzhayyim.shinka.validateEvolution"] }
    healthz_port = 13025
    adr = ["2605215200", "2605171800"]

    [[cell]]
    name = "JouchoAggregationCell"
    module = "kotodama.primitives.joucho_murakumo"
    entry = "joucho_aggregation_cell"
    node = "levi"
    trigger = { kind = "cron", expr = "0 * * * *" }
    healthz_port = 13027
    adr = ["JOUCHO-MIGRATION-DESIGN.md"]

    [[cell]]
    name = "WildcardCell"
    module = "kotodama.primitives.demo_echo_chain"
    entry = "echo_cell"
    node = "*"
    trigger = { kind = "cron", expr = "0 0 * * *" }
    healthz_port = 13099
    adr = []
""")


@pytest.fixture()
def cells_toml_file(tmp_path: Path) -> Path:
    """Write a temporary cells.toml and return its Path."""
    p = tmp_path / "cells.toml"
    p.write_text(CELLS_TOML_CONTENT, encoding="utf-8")
    return p


@pytest.fixture()
def registry(cells_toml_file: Path) -> dict:
    """Parsed registry dict from the temporary cells.toml."""
    return load_cell_registry(cells_toml_file)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestLoadCellRegistry:
    def test_load_cell_registry_finds_file(self, cells_toml_file: Path) -> None:
        """load_cell_registry returns a non-empty dict when cells.toml exists."""
        result = load_cell_registry(cells_toml_file)
        assert isinstance(result, dict), "Expected dict return from load_cell_registry"
        # Top-level [runner] section must be present.
        assert "runner" in result, "Expected [runner] section in parsed cells.toml"
        # [[cell]] array must be present with at least the 5 religious-corp cells.
        assert "cell" in result, "Expected [[cell]] array in parsed cells.toml"
        assert len(result["cell"]) >= 5, (
            f"Expected ≥5 cells, got {len(result['cell'])}"
        )

    def test_load_cell_registry_no_file_returns_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """load_cell_registry returns {} when no cells.toml found in search path.

        Patches the CELLS_TOML module constant to a nonexistent path so the
        fallback search also misses, and passes a nonexistent explicit path.
        Also monkeypatches Path.home() to a tmp dir without .etzhayyim/cells.toml.
        """
        import kotodama.cell_runner_main as crm

        nonexistent = tmp_path / "does_not_exist.toml"
        # Patch module-level CELLS_TOML so the repo-checkout fallback is also absent.
        monkeypatch.setattr(crm, "CELLS_TOML", nonexistent)
        # Ensure /etc/etzhayyim/cells.toml and ~/.etzhayyim/cells.toml won't be found
        # by routing home() to a fresh temp directory.
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        result = crm.load_cell_registry(nonexistent)
        assert result == {}, f"Expected empty dict, got {result!r}"

    def test_load_cell_registry_runner_section(self, registry: dict) -> None:
        """[runner] section is parsed with correct node_name_env value."""
        runner = registry["runner"]
        assert runner["node_name_env"] == "ETZHAYYIM_NODE_NAME"
        assert runner["healthz_port_range"] == [13000, 14000]

    def test_load_cell_registry_cell_schema(self, registry: dict) -> None:
        """Each [[cell]] entry has the required schema fields."""
        required_keys = {"name", "module", "entry", "node", "trigger", "healthz_port"}
        for cell in registry["cell"]:
            missing = required_keys - set(cell.keys())
            assert not missing, (
                f"Cell {cell.get('name', '?')} missing keys: {missing}"
            )


class TestCellsForNode:
    def test_cells_for_node_filter_levi(self, registry: dict) -> None:
        """levi receives ShinkaHeartbeatCell, KarmaHegemonObservationCell,
        EvolutionValidationCell, JouchoAggregationCell (+ WildcardCell)."""
        result = cells_for_node(registry, "levi")
        names = {c["name"] for c in result}
        assert "ShinkaHeartbeatCell" in names
        assert "KarmaHegemonObservationCell" in names
        assert "EvolutionValidationCell" in names
        assert "JouchoAggregationCell" in names
        # EvolutionEmissionCell is on simeon, not levi.
        assert "EvolutionEmissionCell" not in names

    def test_cells_for_node_filter_simeon(self, registry: dict) -> None:
        """simeon receives EvolutionEmissionCell only (plus WildcardCell)."""
        result = cells_for_node(registry, "simeon")
        names = {c["name"] for c in result}
        assert "EvolutionEmissionCell" in names
        # levi-only cells must not appear on simeon.
        assert "ShinkaHeartbeatCell" not in names
        assert "KarmaHegemonObservationCell" not in names
        assert "EvolutionValidationCell" not in names
        assert "JouchoAggregationCell" not in names

    def test_cells_for_node_includes_wildcard(self, registry: dict) -> None:
        """Cells with node = "*" appear on every node, including naphtali."""
        for node in ("levi", "simeon", "naphtali", "judah", "unknown-tribe"):
            result = cells_for_node(registry, node)
            names = {c["name"] for c in result}
            assert "WildcardCell" in names, (
                f"WildcardCell (node='*') should appear on {node!r}, got {names}"
            )

    def test_cells_for_node_unknown_node_returns_only_wildcards(
        self, registry: dict
    ) -> None:
        """Unknown node gets only wildcard cells."""
        result = cells_for_node(registry, "totally-unknown")
        names = {c["name"] for c in result}
        # Only WildcardCell (node="*") should appear.
        assert names == {"WildcardCell"}, (
            f"Unknown node should only get wildcard cells; got {names}"
        )

    def test_cells_for_node_empty_registry(self) -> None:
        """cells_for_node returns [] when registry is empty."""
        result = cells_for_node({}, "levi")
        assert result == []

    def test_cells_for_node_levi_count(self, registry: dict) -> None:
        """levi has exactly 5 cells: 4 levi-specific + 1 wildcard."""
        result = cells_for_node(registry, "levi")
        assert len(result) == 5, (
            f"Expected 5 cells for levi (4 specific + 1 wildcard), got {len(result)}: "
            f"{[c['name'] for c in result]}"
        )

    def test_cells_for_node_simeon_count(self, registry: dict) -> None:
        """simeon has exactly 2 cells: 1 simeon-specific + 1 wildcard."""
        result = cells_for_node(registry, "simeon")
        assert len(result) == 2, (
            f"Expected 2 cells for simeon (1 specific + 1 wildcard), got {len(result)}: "
            f"{[c['name'] for c in result]}"
        )

    def test_cells_for_node_trigger_structure(self, registry: dict) -> None:
        """Each returned cell has a trigger dict with a 'kind' key."""
        for node in ("levi", "simeon"):
            for cell in cells_for_node(registry, node):
                assert "trigger" in cell, f"Cell {cell['name']} missing trigger"
                assert "kind" in cell["trigger"], (
                    f"Cell {cell['name']} trigger missing 'kind'"
                )

    def test_cells_for_node_healthz_ports_unique_per_node(
        self, registry: dict
    ) -> None:
        """Each node has unique healthz_port values (no collision)."""
        for node in ("levi", "simeon"):
            ports = [c["healthz_port"] for c in cells_for_node(registry, node)]
            assert len(ports) == len(set(ports)), (
                f"Duplicate healthz_port on {node}: {ports}"
            )
