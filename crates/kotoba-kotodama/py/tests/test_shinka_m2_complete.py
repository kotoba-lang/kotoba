"""test_shinka_m2_complete.py — Full SDK-mocked tests for shinka_murakumo M2 cells.

Tests:
  A. Charter-rider compliance gate (ADR-2605215400 §5) — 5 tests:
     1. test_evolution_validation_charter_compliant_passes
     2. test_evolution_validation_charter_non_aligned_rejects
     3. test_evolution_validation_charter_unknown_proceeds
     4. test_evolution_validation_charter_query_failure_proceeds
     5. test_evolution_validation_charter_pending_proceeds

  B. Evolution validation — Lv1-7 threshold tests (mocked SDK):
     - Lv1: insufficient/sufficient witnesses
     - Lv5: count threshold
     - Lv6: count threshold + Council co-signer gate
     - Lv7: supermajority gate + appeal window

  C. EvolutionEmissionCell: Stage 3-5 pipeline (mocked pds/ipfs/l2)
  D. ShinkaHeartbeatCell: record construction and PDS dispatch
  E. shinka_tick: full orchestration (mock all cells)

All SDK calls are mocked — no real PDS/IPFS/L2 traffic.
"""

from __future__ import annotations

import sys
from pathlib import Path as _P
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import kotodama.primitives.shinka_murakumo as SM  # noqa: E402

_MODULE = "kotodama.primitives.shinka_murakumo"

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_claim(level: int = 2, adherent_did: str = "did:plc:test001") -> SM.EvolutionClaim:
    return SM.EvolutionClaim(
        claim_id=f"claim-lv{level}-test",
        adherent_did=adherent_did,
        proposed_level=level,
        evidence_cids=["bafybeig5abc123"],
    )


def _attestations(n: int, council: int = 0) -> list[dict]:
    """Build n fake attestation dicts, with `council` of them marked is_council_lv6=True."""
    result = []
    for i in range(n):
        result.append({
            "attestor_did": f"did:plc:attestor{i:03d}",
            "is_council_lv6": i < council,
            "attestation_at": "2026-05-01T00:00:00Z",
            "attestation_uri": f"at://did:plc:attestor{i:03d}/charter-attestation/attest{i}",
            "evidence_cid": f"bafybei{i:04d}",
        })
    return result


# ── §A: Charter-rider compliance gate tests ───────────────────────────────────


class TestCharterComplianceGate:
    """5 tests for the charter-rider compliance gate (ADR-2605215400 §5)."""

    @pytest.mark.asyncio
    async def test_evolution_validation_charter_compliant_passes(self):
        """Adherent compliant → compliance gate allows, proceeds to Lv check."""
        claim = _make_claim(level=2)

        mock_mst = MagicMock()
        # Charter compliance query returns one "compliant" record.
        compliance_record = {
            "value": {
                "complianceStatus": "compliant",
                "recordedAt": "2026-05-20T00:00:00Z",
                "subjectDid": claim.adherent_did,
            }
        }
        # council_attestation_details for Lv2 returns enough attestations.
        mock_mst.query = AsyncMock(return_value=[compliance_record])
        mock_mst.council_attestation_details = AsyncMock(
            return_value=_attestations(3)  # Lv2 requires 3
        )
        mock_pds = MagicMock()
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-test"})

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._pds_mod", mock_pds),
        ):
            result = await SM.evolution_validation_cell(claim)

        # Gate passed — result reflects Lv2 attestation check (3 >= 3)
        assert result.valid is True
        assert result.attestation_count == 3
        # Compliance query was called
        mock_mst.query.assert_called_once()
        call_kwargs = mock_mst.query.call_args
        # First positional arg is collection name
        assert "charter-compliance" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_evolution_validation_charter_non_aligned_rejects(self):
        """Adherent flagged non_aligned → ValidationResult.valid=False, status=invalid."""
        claim = _make_claim(level=3)

        mock_mst = MagicMock()
        compliance_record = {
            "value": {
                "complianceStatus": "non_aligned",
                "recordedAt": "2026-05-20T00:00:00Z",
                "subjectDid": claim.adherent_did,
            }
        }
        mock_mst.query = AsyncMock(return_value=[compliance_record])

        mock_pds = MagicMock()

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._pds_mod", mock_pds),
        ):
            result = await SM.evolution_validation_cell(claim)

        assert result.valid is False
        assert result.status == "invalid"
        assert result.attestation_count == 0
        assert result.required_count == 0
        assert "non-aligned" in result.reason.lower() or "non_aligned" in result.reason
        assert "ChartersComplianceRegistry" in result.reason
        assert "ADR-2605215400" in result.reason
        # council_attestation_details must NOT have been called (gate fires first)
        assert not hasattr(mock_mst, "council_attestation_details") or \
            mock_mst.council_attestation_details.call_count == 0

    @pytest.mark.asyncio
    async def test_evolution_validation_charter_unknown_proceeds(self):
        """No compliance record (unknown) → presumption of innocence, proceeds."""
        claim = _make_claim(level=1)

        mock_mst = MagicMock()
        # Empty list = no compliance record → "unknown"
        mock_mst.query = AsyncMock(return_value=[])
        mock_mst.council_attestation_details = AsyncMock(
            return_value=_attestations(2)  # Lv1 requires 2
        )
        mock_pds = MagicMock()
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-test"})

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._pds_mod", mock_pds),
        ):
            result = await SM.evolution_validation_cell(claim)

        # Unknown → gate passes → Lv1 check succeeds
        assert result.valid is True
        assert result.attestation_count == 2

    @pytest.mark.asyncio
    async def test_evolution_validation_charter_query_failure_proceeds(self):
        """mst.query raises → infrastructure failure → gate defaults to unknown, advances."""
        claim = _make_claim(level=2)

        mock_mst = MagicMock()
        # Compliance query raises a network error.
        mock_mst.query = AsyncMock(side_effect=ConnectionRefusedError("projector down"))
        mock_mst.council_attestation_details = AsyncMock(
            return_value=_attestations(3)  # Lv2 requires 3
        )
        mock_pds = MagicMock()
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-test"})

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._pds_mod", mock_pds),
        ):
            result = await SM.evolution_validation_cell(claim)

        # Infrastructure failure → unknown → gate passes → Lv2 check runs
        assert result.valid is True
        assert result.attestation_count == 3

    @pytest.mark.asyncio
    async def test_evolution_validation_charter_pending_proceeds(self):
        """Compliance status pending → gate passes (only non_aligned blocks)."""
        claim = _make_claim(level=4)

        mock_mst = MagicMock()
        compliance_record = {
            "value": {
                "complianceStatus": "pending",
                "recordedAt": "2026-05-20T00:00:00Z",
                "subjectDid": claim.adherent_did,
            }
        }
        mock_mst.query = AsyncMock(return_value=[compliance_record])
        mock_mst.council_attestation_details = AsyncMock(
            return_value=_attestations(7)  # Lv4 requires 7
        )
        mock_pds = MagicMock()
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-test"})

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._pds_mod", mock_pds),
        ):
            result = await SM.evolution_validation_cell(claim)

        # Pending → gate passes → Lv4 check runs → valid
        assert result.valid is True
        assert result.attestation_count == 7


# ── §B: Evolution validation threshold tests ──────────────────────────────────


class TestEvolutionValidation:
    """Evolution validation Lv1-7 threshold tests with mocked compliance + attestations."""

    def _mst_with_compliance(
        self,
        compliance_status: str = "compliant",
        attestation_count: int = 0,
        council_count: int = 0,
        objections: list | None = None,
    ) -> MagicMock:
        """Build a mock _mst_mod with compliance + attestation pre-wired."""
        mock = MagicMock()
        compliance_record = {
            "value": {
                "complianceStatus": compliance_status,
                "recordedAt": "2026-05-20T00:00:00Z",
            }
        }
        mock.query = AsyncMock(return_value=[compliance_record])
        mock.council_attestation_details = AsyncMock(
            return_value=_attestations(attestation_count, council_count)
        )
        mock.council_objections = AsyncMock(return_value=objections or [])
        return mock

    @pytest.mark.asyncio
    async def test_lv1_insufficient_witnesses(self):
        """Lv1 advancement fails with 1 attestation (requires 2)."""
        claim = _make_claim(level=1)
        mock_mst = self._mst_with_compliance(attestation_count=1)
        mock_pds = MagicMock()

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._pds_mod", mock_pds),
        ):
            result = await SM.evolution_validation_cell(claim)

        assert result.valid is False
        assert result.attestation_count == 1
        assert result.required_count == 2

    @pytest.mark.asyncio
    async def test_lv1_sufficient_witnesses(self):
        """Lv1 advancement passes with 2 attestations."""
        claim = _make_claim(level=1)
        mock_mst = self._mst_with_compliance(attestation_count=2)
        mock_pds = MagicMock()
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-lv1"})

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._pds_mod", mock_pds),
        ):
            result = await SM.evolution_validation_cell(claim)

        assert result.valid is True
        assert result.attestation_count == 2

    @pytest.mark.asyncio
    async def test_lv5_sufficient_witnesses(self):
        """Lv5 advancement passes with 9 attestations (requires 9)."""
        claim = _make_claim(level=5)
        mock_mst = self._mst_with_compliance(attestation_count=9)
        mock_pds = MagicMock()
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-lv5"})

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._pds_mod", mock_pds),
        ):
            result = await SM.evolution_validation_cell(claim)

        assert result.valid is True

    @pytest.mark.asyncio
    async def test_lv6_insufficient_council_cosigners(self):
        """Lv6 fails when count OK but Council Lv6+ co-signers < COUNCIL_GATE_LV6."""
        claim = _make_claim(level=6)
        mock_mst = self._mst_with_compliance(attestation_count=9, council_count=1)
        mock_pds = MagicMock()

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._pds_mod", mock_pds),
        ):
            result = await SM.evolution_validation_cell(claim)

        assert result.valid is False
        assert "Council Lv6+" in result.reason

    @pytest.mark.asyncio
    async def test_lv6_passes_with_council_cosigners(self):
        """Lv6 passes when count >= 9 and council_count >= COUNCIL_GATE_LV6 (2)."""
        claim = _make_claim(level=6)
        mock_mst = self._mst_with_compliance(attestation_count=9, council_count=2)
        mock_pds = MagicMock()
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-lv6"})

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._pds_mod", mock_pds),
        ):
            result = await SM.evolution_validation_cell(claim)

        assert result.valid is True

    @pytest.mark.asyncio
    async def test_lv7_supermajority_fails(self):
        """Lv7 fails when council_count < COUNCIL_SUPERMAJORITY_LV7 (4)."""
        claim = _make_claim(level=7)
        mock_mst = self._mst_with_compliance(attestation_count=9, council_count=3)
        mock_pds = MagicMock()

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._pds_mod", mock_pds),
        ):
            result = await SM.evolution_validation_cell(claim)

        assert result.valid is False
        assert result.status == "invalid"

    @pytest.mark.asyncio
    async def test_lv7_pending_no_objections(self):
        """Lv7 supermajority passed, first validation → status=pending."""
        claim = SM.EvolutionClaim(
            claim_id="claim-lv7-pending",
            adherent_did="did:plc:test001",
            proposed_level=7,
            validated_at=None,  # first validation
        )
        mock_mst = MagicMock()
        compliance_record = {
            "value": {"complianceStatus": "compliant", "recordedAt": "2026-05-20T00:00:00Z"}
        }
        mock_mst.query = AsyncMock(return_value=[compliance_record])
        mock_mst.council_attestation_details = AsyncMock(
            return_value=_attestations(9, council=4)  # supermajority passes
        )
        mock_mst.council_objections = AsyncMock(return_value=[])  # no objections
        mock_pds = MagicMock()

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._pds_mod", mock_pds),
        ):
            result = await SM.evolution_validation_cell(claim)

        assert result.valid is False  # not final until window closes
        assert result.status == "pending"
        assert "objection window" in result.reason.lower()


# ── §C: EvolutionEmissionCell tests ──────────────────────────────────────────


class TestEvolutionEmissionCell:
    """Test the Stage 3-5 pipeline: MST → IPFS pin → Base L2 anchor."""

    @pytest.mark.asyncio
    async def test_emission_writes_mst_and_returns_anchor_tx(self):
        """EvolutionEmissionCell writes MST record, pins IPFS, and returns anchor tx."""
        claim = _make_claim(level=3)
        anchor_tx = "0xdeadbeef" + "00" * 28

        mock_pds = MagicMock()
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-emission-test"})

        mock_ipfs = MagicMock()
        mock_ipfs.pin_many = AsyncMock(return_value=None)

        mock_l2 = MagicMock()
        mock_l2.anchor = AsyncMock(return_value=anchor_tx)

        with (
            patch(f"{_MODULE}._pds_mod", mock_pds),
            patch(f"{_MODULE}._ipfs_mod", mock_ipfs),
            patch(f"{_MODULE}._l2_mod", mock_l2),
        ):
            tx = await SM.evolution_emission_cell(claim)

        assert tx == anchor_tx
        mock_pds.put_record.assert_called_once()
        mock_ipfs.pin_many.assert_called_once()
        mock_l2.anchor.assert_called_once()

    @pytest.mark.asyncio
    async def test_emission_with_no_evidence_cids_skips_ipfs(self):
        """No evidence_cids → IPFS pin_many is skipped."""
        claim = SM.EvolutionClaim(
            claim_id="claim-no-cids",
            adherent_did="did:plc:test001",
            proposed_level=2,
            evidence_cids=[],
        )
        anchor_tx = "0xabcdef01"

        mock_pds = MagicMock()
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-no-cids"})
        mock_ipfs = MagicMock()
        mock_ipfs.pin_many = AsyncMock()
        mock_l2 = MagicMock()
        mock_l2.anchor = AsyncMock(return_value=anchor_tx)

        with (
            patch(f"{_MODULE}._pds_mod", mock_pds),
            patch(f"{_MODULE}._ipfs_mod", mock_ipfs),
            patch(f"{_MODULE}._l2_mod", mock_l2),
        ):
            tx = await SM.evolution_emission_cell(claim)

        assert tx == anchor_tx
        mock_ipfs.pin_many.assert_not_called()


# ── §D: ShinkaHeartbeatCell tests ────────────────────────────────────────────


class TestShinkaHeartbeatCell:
    """Heartbeat cell: record construction and PDS dispatch."""

    @pytest.mark.asyncio
    async def test_heartbeat_dispatches_and_returns_dict(self):
        """ShinkaHeartbeatCell writes heartbeat record and returns status dict."""
        mock_pds = MagicMock()
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-heartbeat"})

        with (
            patch(f"{_MODULE}._pds_mod", mock_pds),
            patch(f"{_MODULE}._ShinkaHeartbeatRecord", None),  # use raw dict fallback
        ):
            result = await SM.shinka_heartbeat_cell(
                cycle=42,
                cells_observed=3,
                cells_validated=1,
                cells_emitted=1,
                errors=[],
            )

        assert result["heartbeatWritten"] is True
        assert result["cycle"] == 42
        assert result["nodeName"] == "levi"
        assert result["cellsObserved"] == 3
        mock_pds.put_record.assert_called_once()

    @pytest.mark.asyncio
    async def test_heartbeat_with_errors_included(self):
        """Heartbeat includes error list when provided."""
        mock_pds = MagicMock()
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-hb-err"})

        with (
            patch(f"{_MODULE}._pds_mod", mock_pds),
            patch(f"{_MODULE}._ShinkaHeartbeatRecord", None),
        ):
            result = await SM.shinka_heartbeat_cell(
                cycle=10,
                errors=["observation: timeout"],
            )

        assert result["errors"] == ["observation: timeout"]


# ── §E: shinka_tick orchestration tests ──────────────────────────────────────


class TestShinkaTick:
    """End-to-end shinka_tick orchestration with all cells mocked."""

    @pytest.mark.asyncio
    async def test_tick_no_did_returns_early(self):
        """tick(None) logs intent and returns observed=0."""
        mock_pds = MagicMock()
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-tick"})

        with (
            patch(f"{_MODULE}._pds_mod", mock_pds),
            patch(f"{_MODULE}._mst_mod", MagicMock()),
            patch(f"{_MODULE}._ShinkaHeartbeatRecord", None),
        ):
            result = await SM.shinka_tick(None)

        assert result["observed"] == 0
        assert result["adherentDid"] is None

    @pytest.mark.asyncio
    async def test_tick_with_did_no_pending_evolution(self):
        """tick(did) with no proposed_evolution skips validation + emission."""
        adherent_did = "did:plc:test001"

        mock_mst = MagicMock()
        # Compliance query: compliant
        compliance_record = {
            "value": {"complianceStatus": "compliant", "recordedAt": "2026-05-20T00:00:00Z"}
        }
        mock_mst.query = AsyncMock(side_effect=[
            [],              # Step 1: no prior evolution records
            [],              # Step 2: no kyumei signals (mst.query fallback)
        ])

        mock_pds = MagicMock()
        mock_pds.put_record = AsyncMock(return_value={"cid": "bafy-tick-nodid"})

        with (
            patch(f"{_MODULE}._mst_mod", mock_mst),
            patch(f"{_MODULE}._pds_mod", mock_pds),
            patch(f"{_MODULE}._projector_mod", None),
            patch(f"{_MODULE}._ShinkaHeartbeatRecord", None),
        ):
            result = await SM.shinka_tick(adherent_did)

        assert result["observed"] == 1
        assert result["validated"] == 0
        assert result["emitted"] == 0
        assert result["adherentDid"] == adherent_did
