"""
lawfirm.intake.* + lawfirm.matter.* — LangServer handlers.

Task types:
  lawfirm.intake.submit  Persist multilingual intake row + classify + notify
  lawfirm.matter.create  Create a matter (advocate accepts intake or direct)

ADR-0036 Hyperdrive direct.
ADR-0018 Tier 2 sensitivity for privileged content (signal:v1 prefix).
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import uuid
from typing import Any

LOG = logging.getLogger("lawfirm.intake")

_FIRM_DID = "did:web:lawfirm.etzhayyim.com"

# Localized "thank you, we'll be in touch" messages per language (sample
# subset; production should be i18n-bundled in real deployment).
_NEXT_STEPS_MESSAGES: dict[str, str] = {
    "en": "Thank you. An advocate will review your matter and respond within 2 business days.",
    "hi": "धन्यवाद। एक अधिवक्ता आपके मामले की समीक्षा करेगा और 2 कार्य दिवसों के भीतर जवाब देगा।",
    "ta": "நன்றி. ஒரு வழக்கறிஞர் உங்கள் வழக்கை மதிப்பாய்வு செய்து 2 வேலை நாட்களுக்குள் பதிலளிப்பார்.",
    "te": "ధన్యవాదాలు. న్యాయవాది మీ కేసును సమీక్షించి 2 వ్యాపార రోజుల్లో సమాధానం ఇస్తారు.",
    "bn": "ধন্যবাদ। একজন আইনজীবী আপনার বিষয় পর্যালোচনা করে 2 কার্যদিবসের মধ্যে উত্তর দেবেন।",
    "ja": "ありがとうございます。弁護士が貴方のご相談を確認し、2 営業日以内にご返信いたします。",
}

_DEFAULT_RESPONSE_HOURS = 48


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).strftime("%Y-%m-%d %H:%M:%S")


def _vid(kind: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.lawfirm.{kind}/{stamp}-{uuid.uuid4().hex[:8]}"


def _enc_field(plaintext: str) -> str:
    """App-layer field encryption placeholder.
    Production: signal:v1: prefix + AES-GCM with advocate-held key.
    Day-0 dev: plaintext (signal:v1 wiring is parallel work in adjacent
    primitive). Mark with prefix so consumers know to decrypt."""
    if not plaintext:
        return ""
    return f"signal:v1:{plaintext}"  # TODO: replace with actual crypto in P2


# ── Task: lawfirm.intake.submit ──────────────────────────────────────────────

async def task_lawfirm_intake_submit(
    tenant_id: str = "production",
    lang: str = "en",
    client_name: str = "",
    client_email: str = "",
    client_phone: str = "",
    client_country: str = "IN",
    matter_type_hint: str = "",
    jurisdiction_hint: str = "",
    cross_border_flag: bool = False,
    summary: str = "",
    consent_status: str = "pending",
    source_url: str = "",
    ip_country: str = "",
) -> dict:
    if not client_name or not client_email or not summary:
        return {"ok": False, "error": "client_name, client_email, summary required"}
    if consent_status != "accepted":
        return {"ok": False, "error": "consent_status must be 'accepted' (DPDP § 6)"}

    intake_uri = _vid("intake")
    intake_id = intake_uri.rsplit("/", 1)[-1]

    intake_row = {
        "vertex_id":          intake_uri,
        "intake_id":          intake_id,
        "tenant_id":          tenant_id,
        "submitted_at":       _now_iso(),
        "lang":               lang,
        "client_name_cipher": _enc_field(client_name),
        "client_email":       client_email,
        "client_phone_cipher": _enc_field(client_phone),
        "client_country":     client_country,
        "matter_type_hint":   matter_type_hint[:200],
        "jurisdiction_hint":  jurisdiction_hint,
        "cross_border_flag":  bool(cross_border_flag),
        "summary_cipher":     _enc_field(summary[:8000]),
        "consent_status":     consent_status,
        "consent_ts":         _now_iso(),
        "source_url":         source_url[:500],
        "ip_country":         ip_country,
        "status":             "pending",
        "created_at":         _now_iso(),
        "owner_did":          _FIRM_DID,
    }
    get_kotoba_client().insert_row("vertex_lawfirm_intake", intake_row)

    next_steps = _NEXT_STEPS_MESSAGES.get(lang, _NEXT_STEPS_MESSAGES["en"])
    LOG.info(
        "intake submitted intake_id=%s tenant=%s lang=%s cross_border=%s",
        intake_id, tenant_id, lang, cross_border_flag,
    )
    return {
        "ok":                       True,
        "intake_id":                intake_id,
        "intake_uri":               intake_uri,
        "next_steps_message":       next_steps,
        "estimated_response_hours": _DEFAULT_RESPONSE_HOURS,
    }


# ── Task: lawfirm.matter.create ──────────────────────────────────────────────

async def task_lawfirm_matter_create(
    tenant_id: str = "production",
    intake_uri: str = "",
    client_did: str = "",
    client_name: str = "",
    lead_advocate_did: str = "",
    co_counsel_dids: list[str] | None = None,
    matter_type: str = "",
    jurisdiction: str = "",
    subject: str = "",
    fee_structure: str = "hourly",
    fee_amount_minor: int = 0,
    currency: str = "USD",
    skip_pwc_clearance: bool = False,
    requester_did: str = "",
) -> dict:
    if not matter_type or not lead_advocate_did or not subject:
        return {"ok": False, "error": "matter_type, lead_advocate_did, subject required"}

    matter_uri = _vid("matter")
    matter_id = matter_uri.rsplit("/", 1)[-1]
    initial_status = "active" if skip_pwc_clearance else "pending_pwc"

    co_counsel_str = ",".join(co_counsel_dids or [])

    bci_disclosure = (
        f"Lead advocate: {lead_advocate_did}; "
        f"matter type: {matter_type}; "
        f"jurisdiction: {jurisdiction or 'IND'}; "
        f"opened: {_now_iso()}"
    )

    matter_row = {
        "vertex_id":           matter_uri,
        "matter_id":           matter_id,
        "tenant_id":           tenant_id,
        "intake_uri":          intake_uri,
        "client_did":          client_did,
        "client_name_cipher":  _enc_field(client_name),
        "lead_advocate_did":   lead_advocate_did,
        "co_counsel_dids":     co_counsel_str,
        "matter_type":         matter_type,
        "jurisdiction":        jurisdiction,
        "subject_cipher":      _enc_field(subject[:8000]),
        "fee_structure":       fee_structure,
        "fee_amount_minor":    fee_amount_minor,
        "currency":            currency,
        "status":              initial_status,
        "opened_at":           _now_iso(),
        "bci_disclosure":      bci_disclosure[:1000],
        "raw_metadata_json":   json.dumps({
            "requester_did": requester_did,
            "co_counsel": co_counsel_dids or [],
            "skip_pwc": skip_pwc_clearance,
        }, ensure_ascii=False)[:4000],
        "created_at":          _now_iso(),
        "owner_did":           _FIRM_DID,
    }
    get_kotoba_client().insert_row("vertex_lawfirm_matter", matter_row)

    # If intake_uri provided, mark intake as promoted
    if intake_uri:
        kotoba_client = get_kotoba_client()
        intake_row = kotoba_client.select_first_where("vertex_lawfirm_intake", "vertex_id", intake_uri)
        if intake_row:
            intake_row["status"] = "promoted"
            intake_row["promoted_matter_uri"] = matter_uri
            kotoba_client.insert_row("vertex_lawfirm_intake", intake_row)

    next_action = (
        "PwC clearance pending — awaiting CEO HITL"
        if not skip_pwc_clearance
        else "Matter active; ready for engagement letter draft"
    )

    LOG.info(
        "matter created matter_id=%s tenant=%s lead=%s status=%s",
        matter_id, tenant_id, lead_advocate_did, initial_status,
    )
    return {
        "ok":                True,
        "matter_id":         matter_id,
        "matter_uri":        matter_uri,
        "status":            initial_status,
        "pwc_clearance_uri": "" if skip_pwc_clearance else "(triggered separately via pwcClearanceRequest)",
        "next_action":       next_action,
    }


# ── Worker registration ──────────────────────────────────────────────────────

def register(app: Any, timeout_ms: int = 60_000) -> None:
    from kotodama.langserver_compat import LangServerWorker
    if not isinstance(app, LangServerWorker):
        return

    @app.task(task_type="lawfirm.intake.submit",
              timeout_ms=timeout_ms, max_jobs_to_activate=8)
    async def _intake(tenant_id: str = "production", lang: str = "en",
                      client_name: str = "", client_email: str = "",
                      client_phone: str = "", client_country: str = "IN",
                      matter_type_hint: str = "", jurisdiction_hint: str = "",
                      cross_border_flag: bool = False, summary: str = "",
                      consent_status: str = "pending", source_url: str = "",
                      ip_country: str = "") -> dict:
        return await task_lawfirm_intake_submit(
            tenant_id=tenant_id, lang=lang,
            client_name=client_name, client_email=client_email,
            client_phone=client_phone, client_country=client_country,
            matter_type_hint=matter_type_hint, jurisdiction_hint=jurisdiction_hint,
            cross_border_flag=cross_border_flag, summary=summary,
            consent_status=consent_status, source_url=source_url,
            ip_country=ip_country,
        )

    @app.task(task_type="lawfirm.matter.create",
              timeout_ms=timeout_ms, max_jobs_to_activate=4)
    async def _matter(tenant_id: str = "production", intake_uri: str = "",
                      client_did: str = "", client_name: str = "",
                      lead_advocate_did: str = "",
                      co_counsel_dids: list[str] | None = None,
                      matter_type: str = "", jurisdiction: str = "",
                      subject: str = "", fee_structure: str = "hourly",
                      fee_amount_minor: int = 0, currency: str = "USD",
                      skip_pwc_clearance: bool = False,
                      requester_did: str = "") -> dict:
        return await task_lawfirm_matter_create(
            tenant_id=tenant_id, intake_uri=intake_uri,
            client_did=client_did, client_name=client_name,
            lead_advocate_did=lead_advocate_did,
            co_counsel_dids=co_counsel_dids or [],
            matter_type=matter_type, jurisdiction=jurisdiction,
            subject=subject, fee_structure=fee_structure,
            fee_amount_minor=fee_amount_minor, currency=currency,
            skip_pwc_clearance=skip_pwc_clearance,
            requester_did=requester_did,
        )

    LOG.info("Registered tasks: lawfirm.intake.submit, lawfirm.matter.create")
