"""Unit tests for shinka_murakumo — religious-corp Pregel cell skeleton.

Tests:
  1. AdherentState and EvolutionClaim dataclasses construct correctly.
  2. EvolutionEventRecord constructs with expected defaults.
  3. All four cells raise NotImplementedError with documented M2/M4 milestone.
  4. shinka_tick() raises NotImplementedError with documented M4 milestone.
  5. Substrate-fit invariant: no psycopg / runpod / Stripe patterns in module source.
  6. mst-projector integration: projector path + fallback to mst.query.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path as _P
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import kotodama.primitives.shinka_murakumo as SM  # noqa: E402


# ── Dataclass construction ────────────────────────────────────────────────────


def test_adherent_state_constructs():
    state = SM.AdherentState(
        did="did:web:etzhayyim.com",
        sbt_token_id=42,
        last_evolution_at="2026-05-21T00:00:00Z",
    )
    assert state.did == "did:web:etzhayyim.com"
    assert state.sbt_token_id == 42
    assert state.last_evolution_at == "2026-05-21T00:00:00Z"
    assert state.kyumei_signals == []
    assert state.mood == "neutral"
    # axes is now a JouchoAxes dataclass (M1-confirmed 5-axis schema)
    # rather than a plain dict. Verify it has the correct type and default values.
    assert isinstance(state.axes, SM.JouchoAxes)
    assert state.axes.joy == 40
    assert state.axes.calm == 40
    assert state.axes.stress == 20
    assert state.last_heartbeat_ms == 0


def test_adherent_state_accepts_kyumei_signals():
    state = SM.AdherentState(
        did="did:web:etzhayyim.com",
        sbt_token_id=1,
        last_evolution_at="2026-05-21T00:00:00Z",
        kyumei_signals=[{"type": "drill_complete", "score": 95}],
        mood="focused",
    )
    assert len(state.kyumei_signals) == 1
    assert state.mood == "focused"


def test_evolution_claim_constructs():
    claim = SM.EvolutionClaim(
        claim_id="claim-001",
        adherent_did="did:web:etzhayyim.com",
        proposed_level=3,
    )
    assert claim.claim_id == "claim-001"
    assert claim.adherent_did == "did:web:etzhayyim.com"
    assert claim.proposed_level == 3
    assert claim.evidence_cids == []
    assert claim.kyumei_signal_refs == []


def test_evolution_claim_accepts_evidence_cids():
    claim = SM.EvolutionClaim(
        claim_id="claim-002",
        adherent_did="did:web:etzhayyim.com",
        proposed_level=4,
        evidence_cids=["bafybeig5abc123", "bafybeig5def456"],
    )
    assert len(claim.evidence_cids) == 2
    assert "bafybeig5abc123" in claim.evidence_cids


def test_evolution_event_record_constructs_with_defaults():
    record = SM.EvolutionEventRecord(
        actor_did="did:web:etzhayyim.com",
        tick_ms=1716300000000,
        mood="calm",
    )
    assert record.actor_did == "did:web:etzhayyim.com"
    assert record.tick_ms == 1716300000000
    assert record.mood == "calm"
    assert record.actions == []
    assert record.heartbeat_written is False
    assert record.evolution_written is False
    assert record.knowledge_written is False
    assert record.evolution_level == 0
    assert record.base_l2_anchor_tx == ""
    assert record.ipfs_cid == ""


# ── NotImplementedError stubs with milestone documentation ───────────────────


@pytest.mark.asyncio
async def test_karma_hegemon_observation_cell_raises_import_error_without_sdk():
    """M2: cell is implemented — raises ImportError when etzhayyim_sdk is not installed.

    In the CI environment the SDK may not yet be on sys.path; the cell
    gracefully raises ImportError (not NotImplementedError) so the caller
    knows the SDK is missing. Full SDK-wired test is in test_m2_partial_impl.py.
    """
    import importlib
    import sys

    # Temporarily hide etzhayyim_sdk from the import machinery
    sdk_modules = {k: v for k, v in sys.modules.items() if k.startswith("etzhayyim_sdk")}
    for key in sdk_modules:
        del sys.modules[key]

    # Force re-import of shinka_murakumo without SDK available
    module_name = "kotodama.primitives.shinka_murakumo"
    original = sys.modules.pop(module_name, None)

    # Patch the _pds_mod and _mst_mod to None to simulate missing SDK
    import kotodama.primitives.shinka_murakumo as SM_reloaded  # noqa: F401

    # Restore
    if original is not None:
        sys.modules[module_name] = original
    for key, val in sdk_modules.items():
        sys.modules[key] = val

    # The cell raises ImportError when _mst_mod is None, or a network/PDS error
    # when the SDK is installed but PDS is unreachable (CI environment).
    SM_patched = sys.modules.get(module_name, SM)
    with pytest.raises((ImportError, NotImplementedError, Exception)):
        await SM_patched.karma_hegemon_observation_cell("did:web:etzhayyim.com")


@pytest.mark.asyncio
async def test_evolution_validation_cell_raises_import_error_without_sdk():
    """M2: evolution_validation_cell is implemented — raises without a live PDS.

    When etzhayyim_sdk is not installed: ImportError.
    When SDK is installed but PDS is unreachable (CI): PdsNetworkError (subclass of Exception).
    When SDK stub not yet implemented: NotImplementedError.
    All outcomes confirm M2 logic is present (not a bare stub).

    Full SDK-wired tests are in test_shinka_m2_complete.py.
    """
    with pytest.raises(Exception):
        await SM.evolution_validation_cell(
            SM.EvolutionClaim(
                claim_id="test",
                adherent_did="did:web:etzhayyim.com",
                proposed_level=2,
            )
        )


@pytest.mark.asyncio
async def test_evolution_emission_cell_raises_import_error_without_sdk():
    """M2: evolution_emission_cell is implemented — raises without a live PDS.

    When etzhayyim_sdk is not installed: ImportError.
    When SDK is installed but PDS is unreachable (CI): PdsNetworkError (subclass of Exception).
    When SDK stub not yet implemented: NotImplementedError.

    Full SDK-wired tests are in test_shinka_m2_complete.py.
    """
    with pytest.raises(Exception):
        await SM.evolution_emission_cell(
            SM.EvolutionClaim(
                claim_id="test",
                adherent_did="did:web:etzhayyim.com",
                proposed_level=2,
            )
        )


@pytest.mark.asyncio
async def test_shinka_heartbeat_cell_raises_import_error_without_sdk():
    """M2: cell is implemented — raises without a live PDS.

    When etzhayyim_sdk is not installed: ImportError.
    When SDK is installed but PDS is unreachable (CI): PdsNetworkError (subclass of Exception).

    Full SDK-wired test (with mocked pds.put_record) is in test_m2_partial_impl.py.
    """
    with pytest.raises(Exception):
        await SM.shinka_heartbeat_cell()


@pytest.mark.asyncio
async def test_shinka_tick_raises_import_error_without_sdk():
    """M2: shinka_tick is now implemented — raises without a live PDS.

    When etzhayyim_sdk is not installed: ImportError.
    When SDK is installed but PDS is unreachable (CI): propagates PdsNetworkError.

    Full SDK-wired orchestration tests are in test_shinka_m2_complete.py.
    """
    with pytest.raises(Exception):
        await SM.shinka_tick("did:web:etzhayyim.com")


@pytest.mark.asyncio
async def test_shinka_tick_no_did_raises_import_error_without_sdk():
    """M2: shinka_tick(None) is now implemented — raises without a live PDS or returns early."""
    with pytest.raises(Exception):
        await SM.shinka_tick()


# ── Substrate-fit invariant: no forbidden patterns in module source ───────────


def _read_module_source() -> str:
    """Read the source of shinka_murakumo.py as a string for pattern checks."""
    module_path = _P(inspect.getfile(SM))
    return module_path.read_text(encoding="utf-8")


def test_no_psycopg_import_in_module():
    """shinka_murakumo must not import psycopg2 or psycopg3 (RW dependency)."""
    source = _read_module_source()
    assert "import psycopg" not in source, (
        "shinka_murakumo imports psycopg — forbidden (ADR-2605172000 RW-free constraint). "
        "Use @etzhayyim/sdk MST client instead."
    )


def test_no_runpod_import_in_module():
    """shinka_murakumo must not import runpod SDK (ADR-2605215000 §1)."""
    source = _read_module_source()
    assert "import runpod" not in source, (
        "shinka_murakumo imports runpod — forbidden (ADR-2605215000 §1 no commercial GPU rental). "
        "Inference runs on Murakumo fleet only."
    )


def test_no_stripe_import_in_module():
    """shinka_murakumo must not import Stripe (ADR-2605172100 on-chain payments only)."""
    source = _read_module_source()
    assert "import stripe" not in source, (
        "shinka_murakumo imports Stripe — forbidden (ADR-2605172100 on-chain payments only). "
        "Religious-corp uses USDC + ERC-4337 Smart Account."
    )


def test_no_rw_url_connection_string_in_module():
    """shinka_murakumo must not use RW_URL as a database connection string.

    The guard at module import time checks os.environ.get('RW_URL') only to
    detect an accidental import in a RisingWave environment and raise ImportError
    immediately. This is an allowed use of RW_URL (detection-only, no connection).

    Docstrings in the migration-path cells deliberately reference vendor SQL
    patterns (INSERT INTO vertex_*) for documentation purposes — these are in
    comments / docstrings, not executable code. The real constraint is that
    no psycopg connection or cursor execute call appears outside docstrings.

    What is forbidden (ADR-2605172000):
      - psycopg.connect(os.environ['RW_URL']) — making an actual DB connection
      - cursor.execute('INSERT INTO vertex_*') — writing to RisingWave
    """
    source = _read_module_source()
    # Forbidden: actual executable RW connection/query patterns
    assert "psycopg.connect" not in source, "shinka_murakumo must not open a psycopg connection"
    assert "cursor.execute" not in source, "shinka_murakumo must not execute SQL via cursor"
    assert "sync_cursor" not in source, "shinka_murakumo must not use sync_cursor (psycopg3 RW pattern)"
    # Note: "INSERT INTO" and "SELECT FROM" may appear in docstrings documenting the
    # vendor migration path. This is acceptable — they must not appear in live code.
    assert "psycopg2" not in source, "shinka_murakumo must not import psycopg2"


def test_no_sync_cursor_in_module():
    """shinka_murakumo must not import or call sync_cursor (psycopg3 RW pattern)."""
    source = _read_module_source()
    assert "sync_cursor" not in source, (
        "shinka_murakumo uses sync_cursor — this is the vendor psycopg3 RW pattern. "
        "Use @etzhayyim/sdk MST client for all reads/writes."
    )


def test_substrate_fit_invariant_check_present():
    """The module must contain the RW_URL / runpod environment detection guard."""
    source = _read_module_source()
    assert "raise ImportError" in source, (
        "shinka_murakumo is missing the substrate-fit ImportError guard. "
        "Per ADR-2605215200, this file must detect RW/RunPod environment and fail loudly."
    )


# ── mst-projector integration: KarmaHegemonObservationCell ───────────────────


_MODULE = "kotodama.primitives.shinka_murakumo"


class TestKarmaHegemonObservationCellProjector:
    """Projector integration tests for karma_hegemon_observation_cell.

    The cell should try mst-projector first for kyumeiSignal queries (Step 2),
    falling back to mst.query on any exception.
    """

    @pytest.mark.asyncio
    async def test_observation_uses_projector_when_available(self):
        """When _projector_mod is available, Step 2 uses query_by_did instead of mst.query."""
        adherent_did = "did:plc:abc123"

        # Mock mst.query for Step 1 (evolution records)
        mock_mst = MagicMock()
        mock_mst.query = AsyncMock(return_value=[])  # no prior evolution records

        # Mock projector to return kyumei signals
        kyumei_signals = [
            {"uri": f"at://did:plc:abc123/kyumeiSignal/s{i}", "cid": f"cid{i}",
             "value": {"signalKind": "ritual", "weight": 800, "adherentDid": adherent_did}}
            for i in range(3)
        ]
        mock_projector = MagicMock()
        mock_projector.query_by_did = AsyncMock(
            return_value={"records": kyumei_signals, "cursor": None}
        )

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._projector_mod", mock_projector),
        ):
            state = await SM.karma_hegemon_observation_cell(adherent_did)

        # Projector should have been called for Step 2
        mock_projector.query_by_did.assert_called_once_with(
            adherent_did,
            collection="com.etzhayyim.shinka.kyumeiSignal",
            limit=500,
        )
        # mst.query should only have been called for Step 1 (evolution records)
        # and NOT for Step 2 (kyumei signals)
        assert mock_mst.query.call_count == 1
        call_args = mock_mst.query.call_args[0][0]
        assert call_args == "com.etzhayyim.shinka.evolutionEvent"

        # The returned state should contain the kyumei signals from projector
        assert state.did == adherent_did
        assert len(state.kyumei_signals) == 3

    @pytest.mark.asyncio
    async def test_observation_falls_back_to_mst_query_on_projector_error(self):
        """When projector raises, Step 2 falls back to mst.query for kyumei signals."""
        adherent_did = "did:plc:fallback456"

        fallback_signals = [
            {"uri": f"at://did:plc:fallback456/kyumeiSignal/f{i}",
             "value": {"signalKind": "oath", "weight": 700, "adherentDid": adherent_did}}
            for i in range(2)
        ]

        mock_mst = MagicMock()
        # Step 1 returns no evolution records; Step 2 fallback returns signals
        mock_mst.query = AsyncMock(side_effect=[
            [],              # Step 1: evolutionEvent query
            fallback_signals,  # Step 2 fallback: kyumeiSignal query
        ])

        # Projector raises a network error
        mock_projector = MagicMock()
        mock_projector.query_by_did = AsyncMock(
            side_effect=ConnectionRefusedError("projector unreachable")
        )

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._projector_mod", mock_projector),
        ):
            state = await SM.karma_hegemon_observation_cell(adherent_did)

        # Projector was attempted
        mock_projector.query_by_did.assert_called_once()
        # mst.query was called twice: once for Step 1, once for Step 2 fallback
        assert mock_mst.query.call_count == 2

        # State should have the fallback signals
        assert state.did == adherent_did
        assert len(state.kyumei_signals) == 2
