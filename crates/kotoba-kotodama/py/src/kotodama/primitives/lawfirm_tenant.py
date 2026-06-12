"""
lawfirm.tenant.* — LangServer handlers.

Task types:
  lawfirm.tenant.bootstrap   Provision sandbox/production tenant for a firm
  lawfirm.tenant.suspend     Pause tenant (pilot ended, 90-day retention)
  lawfirm.tenant.promote     Sandbox → saas-prod transition

Backs com.etzhayyim.apps.lawfirm.tenantBootstrap lexicon
(00-contracts/lexicons/com/etzhayyim/apps/lawfirm/tenantBootstrap.json).

Schema target: kotoba Datom log (vertex_lawfirm_tenant, vertex_lawfirm_tenant_event, edge_lawfirm_tenant_lead).

ADR-0036 Hyperdrive direct.
ADR-0029 depth-1 root DID per tenant (did:web:<slug>.lawfirm.etzhayyim.com).
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

LOG = logging.getLogger("lawfirm.tenant")

_FIRM_DID = "did:web:lawfirm.etzhayyim.com"
_SLUG_REGEX = re.compile(r"^[a-z][a-z0-9-]{1,15}$")
_VALID_REGIONS = {"vultr-lax", "vultr-mum", "vultr-tyo"}
_BUILT_OUT_REGIONS = {"vultr-lax"}  # Phase 1 only
_VALID_TIERS = {"sandbox", "saas-prod"}


def _now_iso() -> datetime:
    return datetime.now(tz=timezone.utc)








def _enc_field(plaintext: str) -> str:
    """App-layer field encryption placeholder.
    Production: signal:v1: prefix + AES-GCM. Day-0: prefix-marker only."""
    if not plaintext:
        return ""
    return f"signal:v1:{plaintext}"


# ── Task: lawfirm.tenant.bootstrap ────────────────────────────────────────────

async def task_lawfirm_tenant_bootstrap(
    slug: str = "",
    legal_name: str = "",
    country: str = "",
    data_region: str = "vultr-lax",
    tier: str = "sandbox",
    pilot_lead_id: str = "",
    admin_email: str = "",
    consent_regions: list[str] | None = None,
) -> dict:
    if not slug or not _SLUG_REGEX.match(slug):
        return {"ok": False, "error": "InvalidSlug",
                "detail": "slug must match ^[a-z][a-z0-9-]{1,15}$"}
    if not legal_name:
        return {"ok": False, "error": "InvalidInput", "detail": "legal_name required"}
    if data_region not in _VALID_REGIONS:
        return {"ok": False, "error": "InvalidRegion", "detail": f"data_region must be one of {sorted(_VALID_REGIONS)}"}
    if data_region not in _BUILT_OUT_REGIONS:
        return {"ok": False, "error": "RegionUnavailable",
                "detail": f"{data_region} not built out (Phase 1 = vultr-lax only)"}
    if tier not in _VALID_TIERS:
        return {"ok": False, "error": "InvalidTier", "detail": f"tier must be one of {sorted(_VALID_TIERS)}"}
    if tier == "sandbox" and not pilot_lead_id:
        return {"ok": False, "error": "PilotLeadMissing",
                "detail": "tier=sandbox requires pilot_lead_id"}

    # Idempotency check: existing (slug, tier) pair
    tenant_id = f"{tier.replace('saas-', '')}-{slug}" if tier == "sandbox" else f"prod-{slug}"
    vertex_id = f"at://did:web:lawfirm.etzhayyim.com/com.etzhayyim.apps.lawfirm.tenant/{tenant_id}"
    existing_candidates = get_kotoba_client().select_where(
        "vertex_lawfirm_tenant", "slug", slug,
        columns=["vertex_id", "status", "tier"]
    )
    existing = [row for row in existing_candidates if row.get("tier") == tier]
    if existing:
        row = existing[0]
        return {
            "ok": True,
            "status": "already_exists",
            "tenantDid": _tenant_did(slug, tier),
            "pdsUrl": _pds_url(slug, tier),
            "xrpcEndpoint": "https://lawfirm.etzhayyim.com",
            "kpiDashboardUrl": f"https://kpi-lawfirm.etzhayyim.com/{slug}",
            "tenant_id": tenant_id,
            "vertex_id": row["vertex_id"],
            "existing_status": row.get("status"),
        }

    # Different (slug, tier=other) collision check
    other_tier = get_kotoba_client().select_where(
        "vertex_lawfirm_tenant", "slug", slug,
        columns=["tier", "legal_name", "country"]
    )
    if other_tier:
        for r in other_tier:
            if r.get("legal_name") != legal_name or r.get("country") != country:
                return {"ok": False, "error": "SlugTaken",
                        "detail": f"slug '{slug}' already used by different firm"}

    tenant_did = _tenant_did(slug, tier)
    pds_url = _pds_url(slug, tier)
    kpi_url = f"https://kpi-lawfirm.etzhayyim.com/{slug}"
    now = _now_iso()
    consent_str = ",".join(consent_regions or []) if consent_regions else ""

    row_data = {
        "vertex_id": vertex_id, "tenant_id": tenant_id, "slug": slug, "tenant_did": tenant_did,
        "legal_name": legal_name, "country": country, "data_region": data_region, "tier": tier,
        "status": "active", "pilot_lead_id": pilot_lead_id or None,
        "admin_email_ct": _enc_field(admin_email),
        "consent_regions": consent_str,
        "pds_url": pds_url, "xrpc_endpoint": "https://lawfirm.etzhayyim.com",
        "kpi_dashboard_url": kpi_url,
        "provisioned_at": now, "created_at": now,
        "sensitivity_ord": 200, "owner_did": _FIRM_DID,
    }
    if not get_kotoba_client().insert_row("vertex_lawfirm_tenant", row_data):
        return {"ok": False, "error": "PersistFailed"}

    # Audit event
    event_vid = f"at://did:web:lawfirm.etzhayyim.com/com.etzhayyim.apps.lawfirm.tenantEvent/{tenant_id}-provisioned-{now.isoformat()}"
    event_row_data = {
        "vertex_id": event_vid, "tenant_id": tenant_id, "event_kind": "provisioned",
        "from_status": None, "to_status": "active", "from_tier": None, "to_tier": tier,
        "reason": "tenantBootstrap procedure", "actor_did": _FIRM_DID,
        "occurred_at": now, "created_at": now,
        "sensitivity_ord": 200, "owner_did": _FIRM_DID,
    }
    get_kotoba_client().insert_row("vertex_lawfirm_tenant_event", event_row_data)

    # tenant ↔ lead edge (sandbox tier only)
    if tier == "sandbox" and pilot_lead_id:
        lead_vid = f"at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.lead/{pilot_lead_id}"
        edge_id = f"edge:tenant:{tenant_id}:for-lead:{pilot_lead_id}"
        edge_row_data = {
            "edge_id": edge_id, "src_vid": vertex_id, "dst_vid": lead_vid,
            "tenant_id": tenant_id, "lead_id": pilot_lead_id, "rel_kind": "sandbox_for_lead",
            "created_at": now, "sensitivity_ord": 200, "owner_did": _FIRM_DID,
        }
        get_kotoba_client().insert_row("edge_lawfirm_tenant_lead", edge_row_data)

    LOG.info(
        "tenant provisioned slug=%s tier=%s did=%s lead=%s",
        slug, tier, tenant_did, pilot_lead_id or "-",
    )
    return {
        "ok": True,
        "status": "created",
        "tenantDid": tenant_did,
        "pdsUrl": pds_url,
        "xrpcEndpoint": "https://lawfirm.etzhayyim.com",
        "kpiDashboardUrl": kpi_url,
        "tenant_id": tenant_id,
        "vertex_id": vertex_id,
    }


def _tenant_did(slug: str, tier: str) -> str:
    if tier == "sandbox":
        return f"did:web:{slug}.sandbox.lawfirm.etzhayyim.com"
    return f"did:web:{slug}.lawfirm.etzhayyim.com"


def _pds_url(slug: str, tier: str) -> str:
    if tier == "sandbox":
        return f"https://{slug}.sandbox.lawfirm.etzhayyim.com"
    return f"https://{slug}.lawfirm.etzhayyim.com"


# ── Task: lawfirm.tenant.suspend (pilot end, 90-day retention) ────────────────

async def task_lawfirm_tenant_suspend(
    slug: str = "",
    reason: str = "pilot-end",
) -> dict:
    if not slug:
        return {"ok": False, "error": "slug required"}

    rows = get_kotoba_client().select_where(
        "vertex_lawfirm_tenant", "slug", slug,
        columns=["vertex_id", "tenant_id", "status"]
    )
    if not rows:
        return {"ok": False, "error": "TenantNotFound"}

    now = _now_iso()
    suspended = 0
    for row in rows:
        if row.get("status") == "suspended":
            continue
        update_data = {
            "vertex_id": row["vertex_id"],
            "status": "suspended",
            "suspended_at": now,
        }
        if get_kotoba_client().insert_row("vertex_lawfirm_tenant", update_data):
            event_vid = f"at://did:web:lawfirm.etzhayyim.com/com.etzhayyim.apps.lawfirm.tenantEvent/{row['tenant_id']}-suspended-{now.isoformat()}"
            event_row_data = {
                "vertex_id": event_vid, "tenant_id": row["tenant_id"],
                "event_kind": "suspended", "from_status": row.get("status"),
                "to_status": "suspended", "reason": reason,
                "actor_did": _FIRM_DID, "occurred_at": now, "created_at": now,
                "sensitivity_ord": 200, "owner_did": _FIRM_DID,
            }
            get_kotoba_client().insert_row("vertex_lawfirm_tenant_event", event_row_data)
            suspended += 1

    return {"ok": True, "suspended_count": suspended}


# ── Task: lawfirm.tenant.promote (sandbox → saas-prod) ────────────────────────

async def task_lawfirm_tenant_promote(
    slug: str = "",
    monthly_rate_usd: float = 5000.0,
) -> dict:
    if not slug:
        return {"ok": False, "error": "slug required"}

    sandbox_candidates = get_kotoba_client().select_where(
        "vertex_lawfirm_tenant", "slug", slug,
        columns=["vertex_id", "tenant_id", "country", "data_region", "tier", "status"]
    )
    sandbox = [
        row for row in sandbox_candidates
        if row.get("tier") == "sandbox" and row.get("status") == "active"
    ]
    if not sandbox:
        return {"ok": False, "error": "ActiveSandboxNotFound"}

    # Provision saas-prod tier reusing the same firm metadata
    src = sandbox[0]
    legal_rows = get_kotoba_client().select_where(
        "vertex_lawfirm_tenant", "vertex_id", src["vertex_id"],
        columns=["legal_name", "admin_email_ct", "consent_regions", "pilot_lead_id"]
    )
    if not legal_rows:
        return {"ok": False, "error": "PromotionMetadataMissing"}
    meta = legal_rows[0]

    # Bootstrap the prod tier (idempotent)
    prod_result = await task_lawfirm_tenant_bootstrap(
        slug=slug,
        legal_name=meta["legal_name"],
        country=src.get("country", ""),
        data_region=src.get("data_region", "vultr-lax"),
        tier="saas-prod",
        pilot_lead_id="",
        admin_email="",  # already encrypted in source row, do not re-encrypt
        consent_regions=(meta.get("consent_regions") or "").split(",") if meta.get("consent_regions") else None,
    )
    if not prod_result.get("ok"):
        return prod_result

    # Audit promotion
    now = _now_iso()
    event_vid = f"at://did:web:lawfirm.etzhayyim.com/com.etzhayyim.apps.lawfirm.tenantEvent/{src['tenant_id']}-promoted-{now.isoformat()}"
    event_row_data = {
        "vertex_id": event_vid, "tenant_id": src["tenant_id"],
        "event_kind": "promoted", "from_status": "active", "to_status": "active",
        "from_tier": "sandbox", "to_tier": "saas-prod",
        "reason": f"pilot conversion at USD {monthly_rate_usd}/mo",
        "actor_did": _FIRM_DID, "occurred_at": now, "created_at": now,
        "sensitivity_ord": 200, "owner_did": _FIRM_DID,
    }
    get_kotoba_client().insert_row("vertex_lawfirm_tenant_event", event_row_data)

    return {
        "ok": True,
        "status": "promoted",
        "sandbox_tenant_id": src["tenant_id"],
        "prod_tenant_id": prod_result.get("tenant_id"),
        "prod_did": prod_result.get("tenantDid"),
        "monthly_rate_usd": monthly_rate_usd,
    }


# ── LangServer registration ─────────────────────────────────────────────────────

def register(app: Any, timeout_ms: int = 60_000) -> None:
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="lawfirm.tenant.bootstrap",
              timeout_ms=timeout_ms, max_jobs_to_activate=4)
    async def _bootstrap(slug: str = "", legal_name: str = "",
                         country: str = "", data_region: str = "vultr-lax",
                         tier: str = "sandbox", pilot_lead_id: str = "",
                         admin_email: str = "",
                         consent_regions: list[str] | None = None) -> dict:
        return await task_lawfirm_tenant_bootstrap(
            slug=slug, legal_name=legal_name, country=country,
            data_region=data_region, tier=tier,
            pilot_lead_id=pilot_lead_id, admin_email=admin_email,
            consent_regions=consent_regions,
        )

    @app.task(task_type="lawfirm.tenant.suspend",
              timeout_ms=timeout_ms, max_jobs_to_activate=4)
    async def _suspend(slug: str = "", reason: str = "pilot-end") -> dict:
        return await task_lawfirm_tenant_suspend(slug=slug, reason=reason)

    @app.task(task_type="lawfirm.tenant.promote",
              timeout_ms=timeout_ms, max_jobs_to_activate=2)
    async def _promote(slug: str = "", monthly_rate_usd: float = 5000.0) -> dict:
        return await task_lawfirm_tenant_promote(
            slug=slug, monthly_rate_usd=monthly_rate_usd,
        )

    LOG.info("Registered tasks: lawfirm.tenant.{bootstrap,suspend,promote}")
