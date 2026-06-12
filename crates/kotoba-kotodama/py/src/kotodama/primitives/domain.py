"""domain.etzhayyim.com (TLD registration assistance) primitives.

T2 actor (ADR-2604282300): kotodama module + BPMN + Zeebe, no CF Worker.
All graph reads/writes hit kotoba Datom log (ADR-2605262130, ADR-2605312345).

BPMN coverage (ADR-0056 BPMN-as-actor):
  eligibilityCheck.bpmn      XRPC    → domain.eligibility.check
  registerAssist.bpmn        XRPC    → domain.register.assist
  refreshTldCatalog.bpmn     monthly → domain.tld.catalog.refresh (Phase 1 stub)

Tables (created by 20260507230000_vertex_domain_schema.ts):
  vertex_domain_tld
  vertex_domain_registrar
  vertex_domain_legal_regulator
  vertex_domain_eligibility_advice
  vertex_domain_registration
  edge_domain_registrar_supports_tld
  edge_domain_tld_accepts_regulator
  mv_domain_registrable_via

Eligibility resolution priority (most-specific first):
  1. exact match: (tld, jurisdiction, actorKind)
  2. fallback:    (tld, jurisdiction, 'any')
  3. fallback:    (tld, '*', 'any')               — for open TLDs
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

_DOMAIN_ACTOR = "did:web:domain.etzhayyim.com"

# Open-policy fallback set when the requested TLD is restricted and the
# (tld, jurisdiction, actorKind) combination is not eligible.
_OPEN_LEGAL_TLDS = (".lawyer", ".legal", ".attorney")

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(s: str, *, max_len: int = 64) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-.")
    return s[:max_len] or "x"


def _hash12(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def _normalize_tld(tld: str) -> str:
    t = (tld or "").strip().lower()
    if not t:
        return ""
    if not t.startswith("."):
        t = "." + t
    return t




# ──────────────────────────────────────────────────────────────────────
# domain.eligibility.check
# ──────────────────────────────────────────────────────────────────────

_SQL_ADVICE_EXACT = (
    "SELECT vertex_id, tld, jurisdiction, regulator_slug, actor_kind, eligible, "
    "       basis, policy_excerpt, source_url "
    "FROM vertex_domain_eligibility_advice "
    "WHERE status = 'active' AND tld = %s AND jurisdiction = %s AND actor_kind = %s "
    "LIMIT 1"
)

_SQL_ADVICE_TLD_JURIS = (
    "SELECT vertex_id, tld, jurisdiction, regulator_slug, actor_kind, eligible, "
    "       basis, policy_excerpt, source_url "
    "FROM vertex_domain_eligibility_advice "
    "WHERE status = 'active' AND tld = %s AND jurisdiction = %s "
    "ORDER BY CASE WHEN actor_kind = 'any' THEN 1 ELSE 0 END DESC, eligible DESC "
    "LIMIT 1"
)

_SQL_TLD = (
    "SELECT tld, operator, restricted, eligibility_summary, "
    "       eligibility_policy_url, verification_required "
    "FROM vertex_domain_tld WHERE tld = %s AND status = 'active' LIMIT 1"
)

_SQL_REGULATOR_NAME = (
    "SELECT name FROM vertex_domain_legal_regulator "
    "WHERE regulator_slug = %s AND status = 'active' LIMIT 1"
)


def _resolve_advice(tld: str, jurisdiction: str, actor_kind: str) -> dict[str, Any] | None:
    client = get_kotoba_client()

    # SQL: _SQL_ADVICE_EXACT (WHERE status = 'active' AND tld = %s AND jurisdiction = %s AND actor_kind = %s LIMIT 1)
    # R0: Multi-predicate WHERE clause converted to Python filtering after select_where.
    all_advice_exact = client.select_where(
        "vertex_domain_eligibility_advice",
        "tld",
        tld,
        columns=["vertex_id", "tld", "jurisdiction", "regulator_slug", "actor_kind", "eligible",
                 "basis", "policy_excerpt", "source_url", "status"],
        limit=2000 # Fetching a broader set for in-Python filtering
    )
    # Filter in Python
    rows_exact = [
        a for a in all_advice_exact
        if a["status"] == "active" and a["jurisdiction"] == jurisdiction and a["actor_kind"] == actor_kind
    ]
    if rows_exact:
        rows = [rows_exact[0]] # Simulate LIMIT 1
    else:
        rows = []

    if not rows:
        # SQL: _SQL_ADVICE_TLD_JURIS (WHERE status = 'active' AND tld = %s AND jurisdiction = %s ORDER BY CASE WHEN actor_kind = 'any' THEN 1 ELSE 0 END DESC, eligible DESC LIMIT 1)
        # R0: Multi-predicate WHERE clause and ORDER BY converted to Python filtering and sorting after select_where.
        all_advice_tld_juris = client.select_where(
            "vertex_domain_eligibility_advice",
            "tld",
            tld,
            columns=["vertex_id", "tld", "jurisdiction", "regulator_slug", "actor_kind", "eligible",
                     "basis", "policy_excerpt", "source_url", "status"],
            limit=2000 # Fetching a broader set for in-Python filtering
        )
        # Filter in Python
        filtered_advice_tld_juris = [
            a for a in all_advice_tld_juris
            if a["status"] == "active" and a["jurisdiction"] == jurisdiction
        ]
        # Apply ORDER BY in Python
        filtered_advice_tld_juris.sort(
            key=lambda r: (1 if r["actor_kind"] == "any" else 0, r["eligible"]),
            reverse=True # DESC
        )
        if filtered_advice_tld_juris:
            rows = [filtered_advice_tld_juris[0]] # Simulate LIMIT 1
        else:
            rows = []

    if not rows:
        return None
    r = rows[0]
    return {
        "vertex_id": r["vertex_id"], "tld": r["tld"], "jurisdiction": r["jurisdiction"],
        "regulator_slug": r["regulator_slug"], "actor_kind": r["actor_kind"], "eligible": bool(r["eligible"]),
        "basis": r["basis"] or "", "policy_excerpt": r["policy_excerpt"] or "", "source_url": r["source_url"] or "",
    }

def _tld_metadata(tld: str) -> dict[str, Any] | None:
    client = get_kotoba_client()
    # SQL: _SQL_TLD (WHERE tld = %s AND status = 'active' LIMIT 1)
    # R0: Multi-predicate WHERE clause converted to Python filtering after select_where.
    all_tld_meta = client.select_where(
        "vertex_domain_tld",
        "tld",
        tld,
        columns=["tld", "operator", "restricted", "eligibility_summary",
                 "eligibility_policy_url", "verification_required", "status"],
        limit=2000 # Fetching a broader set for in-Python filtering
    )
    # Filter in Python
    rows = [
        t for t in all_tld_meta
        if t["status"] == "active"
    ]
    if not rows:
        return None
    r = rows[0] # Simulate LIMIT 1
    return {
        "tld": r["tld"], "operator": r["operator"] or "", "restricted": bool(r["restricted"]),
        "eligibility_summary": r["eligibility_summary"] or "",
        "eligibility_policy_url": r["eligibility_policy_url"] or "",
        "verification_required": bool(r["verification_required"]),
    }


def _regulator_name(slug: str | None) -> str:
    if not slug:
        return ""
    client = get_kotoba_client()
    # SQL: _SQL_REGULATOR_NAME (WHERE regulator_slug = %s AND status = 'active' LIMIT 1)
    # R0: Multi-predicate WHERE clause converted to Python filtering after select_where.
    all_regulators = client.select_where(
        "vertex_domain_legal_regulator",
        "regulator_slug",
        slug,
        columns=["name", "status"],
        limit=2000 # Fetching a broader set for in-Python filtering
    )
    # Filter in Python
    rows = [
        r for r in all_regulators
        if r["status"] == "active"
    ]
    return str(rows[0]["name"]) if rows else ""

async def task_domain_eligibility_check(**kwargs: Any) -> dict[str, Any]:
    """Resolve (tld, jurisdiction, actorKind) → eligibility verdict.

    Returns the matched advice row from `vertex_domain_eligibility_advice`,
    along with verification requirement (from TLD catalog) and a list of
    open-policy alternatives if the requested TLD is restricted and the
    actor does not qualify.
    """
    tld = _normalize_tld(str(kwargs.get("tld") or ""))
    jurisdiction = str(kwargs.get("jurisdiction") or "").strip().upper()
    actor_kind = str(kwargs.get("actorKind") or "any").strip().lower()
    if not tld or not jurisdiction:
        return {"ok": False, "eligible": False, "tld": tld,
                "error": "tld and jurisdiction are required"}

    tld_meta = _tld_metadata(tld)
    if not tld_meta:
        return {"ok": False, "eligible": False, "tld": tld,
                "error": f"TLD {tld!r} is not in catalog"}

    advice = _resolve_advice(tld, jurisdiction, actor_kind)
    if advice is None:
        # No jurisdiction-specific advice. For open TLDs, default to eligible.
        if not tld_meta["restricted"]:
            return {
                "ok": True, "eligible": True, "tld": tld,
                "matchedAdviceSlug": "",
                "basis": f"{tld} is an open generic TLD with no occupational eligibility requirement.",
                "policyExcerpt": tld_meta["eligibility_summary"],
                "verificationRequired": False,
                "regulatorSlug": "",
                "regulatorName": "",
                "sourceUrl": tld_meta["eligibility_policy_url"],
                "alternatives": [],
            }
        # Restricted TLD without specific advice — refuse and offer alternatives.
        return {
            "ok": True, "eligible": False, "tld": tld,
            "matchedAdviceSlug": "",
            "basis": (f"No eligibility advice for ({tld}, {jurisdiction}, {actor_kind}). "
                      f"{tld} is restricted; verification required."),
            "policyExcerpt": tld_meta["eligibility_summary"],
            "verificationRequired": True,
            "regulatorSlug": "",
            "regulatorName": "",
            "sourceUrl": tld_meta["eligibility_policy_url"],
            "alternatives": list(_OPEN_LEGAL_TLDS) if tld == ".law" else [],
        }

    advice_slug = (advice["vertex_id"] or "").rsplit("/", 1)[-1]
    out: dict[str, Any] = {
        "ok": True,
        "eligible": advice["eligible"],
        "tld": tld,
        "matchedAdviceSlug": advice_slug,
        "basis": advice["basis"],
        "policyExcerpt": advice["policy_excerpt"] or tld_meta["eligibility_summary"],
        "verificationRequired": tld_meta["verification_required"],
        "regulatorSlug": advice["regulator_slug"] or "",
        "regulatorName": _regulator_name(advice["regulator_slug"]),
        "sourceUrl": advice["source_url"] or tld_meta["eligibility_policy_url"],
        "alternatives": [],
    }
    if not advice["eligible"] and tld == ".law":
        out["alternatives"] = list(_OPEN_LEGAL_TLDS)
    return out


# ──────────────────────────────────────────────────────────────────────
# domain.register.assist
# ──────────────────────────────────────────────────────────────────────

_SQL_SUPPORTING_REGISTRARS = (
    "SELECT r.registrar_slug, r.name, r.jp_friendly, r.notes, "
    "       e.handles_verification "
    "FROM edge_domain_registrar_supports_tld e "
    "JOIN vertex_domain_registrar r ON r.registrar_slug = e.registrar_slug "
    "WHERE e.tld = %s AND r.status = 'active' "
    "ORDER BY e.handles_verification DESC, r.jp_friendly DESC"
)




def _select_registrars(tld: str, *, prefer_jp: bool = True) -> list[dict[str, Any]]:
    client = get_kotoba_client()

    # R0: JOIN operation implemented in Python due to complexity.
    # Fetch edge_domain_registrar_supports_tld for the given tld
    edges = client.select_where(
        "edge_domain_registrar_supports_tld",
        "tld",
        tld,
        columns=["registrar_slug", "tld", "handles_verification"],
        limit=2000 # Fetching a broader set for in-Python join
    )

    # Fetch active vertex_domain_registrar
    all_registrars = client.select_where(
        "vertex_domain_registrar",
        "status",
        "active",
        columns=["registrar_slug", "name", "jp_friendly", "notes", "status"],
        limit=2000 # Fetching a broader set for in-Python join
    )
    # Convert list of dicts to a dict for easier lookup
    registrar_map = {r["registrar_slug"]: r for r in all_registrars}

    out: list[dict[str, Any]] = []
    for edge in edges:
        registrar_slug = edge["registrar_slug"]
        registrar = registrar_map.get(registrar_slug)
        if registrar and registrar["status"] == "active": # Ensure registrar is active after join
            out.append({
                "slug": registrar["registrar_slug"],
                "name": registrar["name"] or "",
                "jpFriendly": bool(registrar["jp_friendly"]) if registrar["jp_friendly"] is not None else None,
                "notes": registrar["notes"] or "",
                "handlesVerification": bool(edge["handles_verification"]) if edge["handles_verification"] is not None else False,
            })

    if prefer_jp:
        # ORDER BY e.handles_verification DESC, r.jp_friendly DESC
        out.sort(key=lambda r: (
            0 if r.get("handlesVerification") else 1, # handlesVerification DESC
            0 if r.get("jpFriendly") else 1,          # jpFriendly DESC
        ), reverse=True) # Overall reverse to simulate DESC for both fields in the SQL

    return out

async def task_domain_register_assist(**kwargs: Any) -> dict[str, Any]:
    """Run eligibility check, recommend a registrar, append a draft ledger row.

    Phase 1: ledger row carries `status='planning'`. Operator completes the
    registrar's own signup flow off-platform, then calls a future
    `recordRegistration` (Phase 2) to flip status to 'active'.
    """
    domain_name = str(kwargs.get("domainName") or "").strip().lower()
    tld_raw = str(kwargs.get("tld") or "").strip()
    tld = _normalize_tld(tld_raw)
    registrant_did = str(kwargs.get("registrantDid") or "").strip()
    registrant_name = str(kwargs.get("registrantName") or "").strip()
    actor_kind = str(kwargs.get("actorKind") or "any").strip().lower()
    jurisdiction = str(kwargs.get("jurisdiction") or "").strip().upper()
    regulator_slug = str(kwargs.get("regulatorSlug") or "").strip().lower() or None
    preferred_registrar = str(kwargs.get("preferredRegistrar") or "").strip().lower() or None
    ns_provider = str(kwargs.get("nsProvider") or "cloudflare").strip().lower()
    evidence_url = str(kwargs.get("evidenceUrl") or "").strip() or None

    if not domain_name or not tld or not registrant_did or not jurisdiction:
        return {"ok": False, "eligible": False,
                "error": "domainName, tld, registrantDid, and jurisdiction are required"}

    # 1) Eligibility check (reuse the same primitive logic).
    elig = await task_domain_eligibility_check(
        tld=tld, jurisdiction=jurisdiction, actorKind=actor_kind,
        regulatorSlug=regulator_slug or "",
    )
    if not elig.get("ok"):
        return {"ok": False, "eligible": False, "error": elig.get("error", "eligibility lookup failed")}

    eligible = bool(elig.get("eligible"))

    # 2) Registrar recommendation.
    candidates = _select_registrars(tld)
    if preferred_registrar:
        candidates.sort(key=lambda r: 0 if r.get("slug") == preferred_registrar else 1)
    primary = candidates[0]["slug"] if candidates else ""
    alternates = [c["slug"] for c in candidates[1:5]]

    rationale_parts: list[str] = []
    if not candidates:
        rationale_parts.append(f"No catalogued registrar carries {tld}.")
    else:
        if candidates[0].get("handlesVerification"):
            rationale_parts.append(
                f"{candidates[0]['name']} handles registry verification flow.")
        if candidates[0].get("jpFriendly"):
            rationale_parts.append("JP-friendly registrar.")
    rationale = " ".join(rationale_parts) or "Catalog-ranked default."

    verification_notes = ""
    if elig.get("verificationRequired"):
        if regulator_slug == "jfba" or jurisdiction == "JP":
            verification_notes = (
                "JFBA 弁護士検索の公開 registry URL を Registrant Name に対応させて準備。"
                "Registrar によっては独立 verification agent から書類請求あり (14 日以内に応答必須)。"
            )
        else:
            verification_notes = (
                "Prepare a public-register URL from the relevant Legal Regulator "
                "and respond within 14 days to any verification request from the registry."
            )

    # 3) Draft ledger row (always inserted; status reflects eligibility).
    advice_slug = elig.get("matchedAdviceSlug") or ""
    advice_vid = (
        f"at://{_DOMAIN_ACTOR}/com.etzhayyim.apps.domain.eligibilityAdvice/{advice_slug}"
        if advice_slug else None
    )

    seed = f"reg|{domain_name}|{tld}|{registrant_did}|{int(time.time())}"
    reg_id = f"r-{_hash12(seed)}"
    vertex_id = f"at://{_DOMAIN_ACTOR}/com.etzhayyim.apps.domain.registration/{reg_id}"
    status = "planning" if eligible else "blocked"
    notes = ("Draft created via registerAssist. "
             + (f"Eligibility blocked — see alternatives: {','.join(elig.get('alternatives') or [])}."
                if not eligible else "Operator must complete signup at the recommended registrar."))

    client = get_kotoba_client()
    row_dict = {
        "vertex_id": vertex_id,
        "owner_did": _DOMAIN_ACTOR,
        "sensitivity_ord": 0,
        "domain_name": domain_name,
        "tld": tld,
        "registrar_slug": primary or None,
        "registrant_did": registrant_did,
        "registrant_name": registrant_name or None,
        "registrant_kind": actor_kind,
        "jurisdiction": jurisdiction,
        "regulator_slug": regulator_slug,
        "eligibility_evidence_url": evidence_url,
        "eligibility_advice_vid": advice_vid,
        "registered_at": None,
        "expires_at": None,
        "auto_renew": False,
        "ns_provider": ns_provider,
        "status": status,
        "notes": notes,
        "created_at": _now_iso(),
        "org_id": _DOMAIN_ACTOR,
        "user_id": registrant_did,
        "actor_id": "domain.register.assist",
    }
    client.insert_row("vertex_domain_registration", row_dict)

    return {
        "ok": True,
        "eligible": eligible,
        "registrationVid": vertex_id,
        "registrarRecommendation": {
            "primary": primary,
            "alternates": alternates,
            "rationale": rationale,
        },
        "verificationRequired": bool(elig.get("verificationRequired")),
        "verificationNotes": verification_notes,
        "alternativesIfBlocked": list(elig.get("alternatives") or []) if not eligible else [],
        "policyExcerpt": elig.get("policyExcerpt", ""),
        "sourceUrl": elig.get("sourceUrl", ""),
    }


# ──────────────────────────────────────────────────────────────────────
# domain.tld.catalog.refresh — Phase 1 stub
# ──────────────────────────────────────────────────────────────────────


async def task_domain_tld_catalog_refresh(**_kwargs: Any) -> dict[str, Any]:
    """Phase 1 stub. Phase 2 will fetch each TLD's eligibility_policy_url,
    diff against vertex_domain_eligibility_advice.policy_excerpt, and bump
    effective_at + status when registry policies change.
    (Now uses kotoba Datom log instead of RisingWave.)"""
    client = get_kotoba_client()
    tld_count_float = client.aggregate_where(
        "vertex_domain_tld", "count", "*", "status", "active"
    )
    tld_count = int(tld_count_float)
    return {
        "ok": True,
        "tldsChecked": tld_count,
        "tldsUpdated": 0,
        "phase1Stub": True,
    }


# ──────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 30_000) -> None:
    """Wire all domain.* task types onto the shared LangServer worker.

    Static manifest below repeats each task_type as a literal so the
    BPMN worker-task coverage linter discovers camelCase names — its
    `t("...")` regex is `[a-z0-9_.-]`-only and misses camelCase, while
    its `task_type="..."` regex is lazy and matches anywhere in the file.

      task_type="domain.eligibility.check"
      task_type="domain.register.assist"
      task_type="domain.tld.catalog.refresh"
    """
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("domain.eligibility.check",     task_domain_eligibility_check)
    t("domain.register.assist",       task_domain_register_assist)
    t("domain.tld.catalog.refresh",   task_domain_tld_catalog_refresh)
