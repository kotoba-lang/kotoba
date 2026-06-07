"""Karma witness invitation primitives.

Triggered by `karma.evaluate` (recommendation = 'require-witness') to
fan-out invitations to candidate witnesses, who can then accept (→
produces vertex_karma_witness row) or decline.

Pyzeebe task types:
  karma.witness.inviteFanOut         per-invitee INSERT
  karma.witness.respondToInvitation  accept/decline persistence
  karma.witness.sweepExpired         R/PT1H sweeper
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("karma.witness")

KARMA_DID = "did:web:karma.etzhayyim.com"

VALID_RESPONSES = ("accept", "decline")
VALID_ATTESTATION_KINDS = ("confirms", "disputes", "contextualizes", "addsEvidence")
INVITATION_PENDING_LIMIT = 200


# ── Helpers ────────────────────────────────────────────────────────────


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_ts() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _now_iso() -> str:
    return (
        _dt.datetime.now(tz=_dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _content_addressed_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return f"{prefix}-{digest[:24]}"


# ── Task: invite fan-out ───────────────────────────────────────────────


async def task_karma_witness_invite_fan_out(**kwargs: Any) -> dict[str, Any]:
    edge_id = kwargs.get("edgeId") or ""
    candidate = kwargs.get("candidate")
    inviter_did = kwargs["inviterDid"]
    invitee_dids = kwargs.get("inviteeDids") or []
    if not isinstance(invitee_dids, list):
        invitee_dids = []
    message = kwargs.get("message") or ""
    rationale_cid = kwargs.get("rationaleCid")
    expires_in_days = int(kwargs.get("expiresInDays") or 14)

    invited_at_ms = _now_ms()
    invited_at = _now_ts()
    expires_at_ms = invited_at_ms + expires_in_days * 24 * 60 * 60 * 1000
    today_iso = datetime.now(timezone.utc).date().isoformat()

    candidate_json = json.dumps(candidate, separators=(",", ":")) if candidate else None

    invitation_ids: list[str] = []
    seen: set[str] = set()

    # Reject inviter from inviting themselves; dedup invitee list.
    for invitee in invitee_dids:
        if not invitee or invitee == inviter_did or invitee in seen:
            continue
        seen.add(invitee)

        # Prevent re-inviting an invitee who already attested this edge.
        if edge_id:
            # R0: Multi-predicate filter applied in Python over selected data.
            witnesses = get_kotoba_client().select_where("vertex_karma_witness", "edge_id", edge_id)
            already_witnessed = any(w.get("witness_did") == invitee for w in witnesses)
            if already_witnessed:
                LOG.info("invite skip: %s already witnessed %s", invitee, edge_id)
                continue

        # Prevent duplicate pending invitation.
        if edge_id:
            # R0: Multi-predicate filter applied in Python over selected data.
            pending_invitations = get_kotoba_client().select_where(
                "vertex_karma_witness_invitation", "edge_id", edge_id
            )
            already_pending = any(
                pi.get("invitee_did") == invitee and pi.get("status") == "pending"
                for pi in pending_invitations
            )
            if already_pending:
                LOG.info("invite skip: pending invitation already exists for %s/%s", invitee, edge_id)
                continue

        nonce = uuid.uuid4().hex
        invitation_id = _content_addressed_id(
            "inv", edge_id or "candidate", inviter_did, invitee, str(invited_at_ms), nonce
        )
        vertex_id = f"invitation-{invitation_id}"

        row_dict = {
            "vertex_id": vertex_id,
            "created_date": today_iso,
            "sensitivity_ord": 1,
            "owner_did": inviter_did,
            "invitation_id": invitation_id,
            "edge_id": edge_id or None,
            "candidate_json": candidate_json,
            "inviter_did": inviter_did,
            "invitee_did": invitee,
            "message": message,
            "rationale_cid": rationale_cid,
            "invited_at": invited_at,
            "invited_at_ms": invited_at_ms,
            "expires_at_ms": expires_at_ms,
            "status": "pending",
            "created_at": invited_at,
            "org_id": inviter_did,
            "user_id": inviter_did,
            "actor_id": "karma.witness.inviteFanOut",
        }
        get_kotoba_client().insert_row("vertex_karma_witness_invitation", row_dict)
        invitation_ids.append(invitation_id)

    return {
        "invitationIds": invitation_ids,
        "inviteCount": len(invitation_ids),
        "expiresAtMs": expires_at_ms,
    }


# ── Task: respond to invitation ────────────────────────────────────────


async def task_karma_witness_respond_to_invitation(**kwargs: Any) -> dict[str, Any]:
    invitation_id = kwargs["invitationId"]
    responder_did = kwargs["responderDid"]
    response = (kwargs["response"] or "").lower()
    attestation_kind = (kwargs.get("attestationKind") or "confirms").lower()
    signature = kwargs.get("signature") or ""
    signature_alg = kwargs.get("signatureAlg") or "es256"
    rationale_cid = kwargs.get("rationaleCid")

    if response not in VALID_RESPONSES:
        raise ValueError(f"karma.witness.respond: invalid response {response}")
    if response == "accept":
        if attestation_kind not in VALID_ATTESTATION_KINDS:
            raise ValueError(
                f"karma.witness.respond: invalid attestationKind {attestation_kind}"
            )
        if not signature:
            raise ValueError("karma.witness.respond: signature required for accept")

    now_ms = _now_ms()
    responded_at = _now_ts()
    today_iso = datetime.now(timezone.utc).date().isoformat()
    witness_id = ""

    # Load + verify invitation.
    invitation_row = get_kotoba_client().select_first_where(
        "vertex_karma_witness_invitation", "invitation_id", invitation_id
    )
    if not invitation_row:
        raise ValueError(f"invitation {invitation_id} not found")
    edge_id = invitation_row["edge_id"]
    invitee_did = invitation_row["invitee_did"]
    expires_at_ms = invitation_row["expires_at_ms"]
    status = invitation_row["status"]

    if status != "pending":
        raise ValueError(f"invitation already responded (status={status})")
    if int(expires_at_ms) <= now_ms:
        # Lazy expire: mark + reject.
        invitation_row["status"] = "expired"
        invitation_row["responded_at"] = responded_at
        invitation_row["responded_at_ms"] = now_ms
        get_kotoba_client().insert_row("vertex_karma_witness_invitation", invitation_row)
        raise ValueError("invitation expired")
    if responder_did != invitee_did:
        raise ValueError("responder mismatch")

    if response == "accept":
        witness_id = _content_addressed_id(
            "witness", edge_id or "candidate", responder_did, attestation_kind, str(now_ms)
        )
        vertex_id = f"witness-{witness_id}"
        witness_row_dict = {
            "vertex_id": vertex_id,
            "created_date": today_iso,
            "sensitivity_ord": 1,
            "owner_did": responder_did,
            "witness_id": witness_id,
            "edge_id": edge_id or "",
            "witness_did": responder_did,
            "witness_organism_cid": None,
            "attestation_kind": attestation_kind,
            "signature": signature,
            "signature_alg": signature_alg,
            "ts_ms": now_ms,
            "created_at": responded_at,
            "org_id": responder_did,
            "user_id": responder_did,
            "actor_id": "karma.witness.respondToInvitation",
        }
        get_kotoba_client().insert_row("vertex_karma_witness", witness_row_dict)

    invitation_row["status"] = "accepted" if response == "accept" else "declined"
    invitation_row["response"] = response
    invitation_row["response_witness_id"] = witness_id or None
    invitation_row["responded_at"] = responded_at
    invitation_row["responded_at_ms"] = now_ms
    get_kotoba_client().insert_row("vertex_karma_witness_invitation", invitation_row)

    return {
        "witnessId": witness_id,
        "respondedAt": responded_at,
    }


# ── Task: sweep expired ────────────────────────────────────────────────


async def task_karma_witness_sweep_expired(**kwargs: Any) -> dict[str, Any]:
    now_ms = _now_ms()
    responded_at = _now_ts()

    # R0: Multi-predicate filter, order, and limit applied in Python over selected data.
    pending_invitations = get_kotoba_client().select_where(
        "vertex_karma_witness_invitation", "status", "pending"
    )
    
    expired_invitations = []
    for inv in pending_invitations:
        if inv.get("expires_at_ms") <= now_ms:
            expired_invitations.append(inv)
    
    # Sort by expires_at_ms and limit
    expired_invitations.sort(key=lambda x: x.get("expires_at_ms", 0))
    expired_invitations = expired_invitations[:INVITATION_PENDING_LIMIT]
    
    expired_ids = []
    for inv_row in expired_invitations:
        inv_row["status"] = "expired"
        inv_row["responded_at"] = responded_at
        inv_row["responded_at_ms"] = now_ms
        get_kotoba_client().insert_row("vertex_karma_witness_invitation", inv_row)
        expired_ids.append(inv_row["invitation_id"])

    still_pending = get_kotoba_client().aggregate_where(
        "vertex_karma_witness_invitation", "count", "*", "status", "pending"
    )

    return {"expired": len(expired_ids), "stillPending": still_pending}


# ── Worker registration ────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    """Register karma witness invitation task types.

      task_type="karma.witness.inviteFanOut"
      task_type="karma.witness.respondToInvitation"
      task_type="karma.witness.sweepExpired"
    """
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("karma.witness.inviteFanOut",        task_karma_witness_invite_fan_out,        ms=60_000)
    t("karma.witness.respondToInvitation", task_karma_witness_respond_to_invitation, ms=30_000)
    t("karma.witness.sweepExpired",        task_karma_witness_sweep_expired,         ms=60_000)


__all__ = [
    "register",
    "task_karma_witness_invite_fan_out",
    "task_karma_witness_respond_to_invitation",
    "task_karma_witness_sweep_expired",
]
