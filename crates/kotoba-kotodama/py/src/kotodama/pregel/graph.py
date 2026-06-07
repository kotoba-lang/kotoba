"""pregel LangGraph — email intent analysis + blocker-aware + spam pipeline.

Graph topology:
  parse_email → check_gewp
    ├─[gewp]   → dispatch_gewp → END
    └─[human]  → classify_intent → detect_deps
                    ├─[spam]    → classify_spam
                    │               ├─[phishing] → ingest_malak → register_yabai → END
                    │               ├─[ses]      → ingest_intel → register_yabai → END
                    │               └─[sales]    → register_yabai → END
                    └─[normal]  → detect_blockers
                                    ├─[blocked]  → handle_blocker → END
                                    └─[clear]    → write_vertex → route_email → END

Spam kinds:   phishing | ses | sales
Blocker types: financial | personnel | approval | system | external

State is PregelState (TypedDict). The graph is compiled as `app` which
langgraph-server serves at /runs via the standard L3 runtime.

ADR refs:
  2605080600-langgraph-server-granian-l3-runtime.md
  2605082000-langgraph-graph-definition-as-data.md
  2605080200-pydantic-l6-validation-contract.md
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import asyncpg
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

_log = logging.getLogger(__name__)

# ── LLM client (resolveModelId pattern — no hardcoded model names) ───────────
_LLM_URL   = os.getenv("etzhayyim_LLM_URL", "https://gemma.etzhayyim.com/v1")
_LLM_MODEL = os.getenv("etzhayyim_LLM_MODEL", "gemma-4-E2B-it")
_LLM_KEY   = os.getenv("etzhayyim_LLM_API_KEY", "")

_DB_URL = os.getenv(
    "DATABASE_URL",
    "REDACTED_USE_DATABASE_URL_ENV",
)

_OWNER_DID = os.getenv("PREGEL_OWNER_DID", "did:web:pregel.etzhayyim.com")

# microsoft.etzhayyim.com XRPC endpoint for acknowledgment drafts
_MICROSOFT_XRPC = os.getenv(
    "MICROSOFT_XRPC_BASE", "https://microsoft.etzhayyim.com/xrpc"
)

# Known pipeline tracks for dependency mapping
_TRACKS = {
    "track_a": ["bakshi", "khaitan", "nishith", "law firm", "外弁", "counsel"],
# CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
    "track_b": ["risingwave", "rw migration", "vertex", "migration", "apply"],
    "track_c": ["configmap", "outbox", "eml", "kotodama", "zeebe", "worker"],
    "hubspot": ["hubspot", "crm", "portal", "ingest", "contact"],
    "keiei": ["cto", "cfo", "coo", "clo", "cmo", "chro", "ciso", "cdo", "keiei", "agent role"],
    "vultr": ["vultr", "vke", "gpu", "a40", "a16", "node pool", "cluster"],
    "jasa": ["jasa", "年会費", "membership fee"],
    "tmi": ["tmi", "法律事務所", "弁護士", "請求書"],
    "docusign": ["docusign", "contract", "sow", "signature"],
}

_SALES_SIGNALS = [
    "ご提案", "お打ち合わせ", "ご紹介", "採用", "サービス", "ソリューション",
    "empowers", "leading", "demo", "trial", "free", "seminar", "webinar",
    "イベント", "recruitment", "staffing", "huxley", "bizreach", "kinaxis",
    "alibaba cloud", "agentbay", "salesforce",
]

# ── Spam classification signals ───────────────────────────────────────────────

# Domains whose mail is always SES/要員営業
_SES_DOMAINS: frozenset[str] = frozenset({
    "d-standing.co.jp",
    "nons.jp",
    "ex-high.com",
    "genestinc.com",
    "pikapaka-agent.co.jp",
    "adecco.co.jp",
    "adecco.com",
    "bizreach.co.jp",
    "leverages.jp",
    "persol.co.jp",
    "en-japan.com",
})

# Subject phrase fragments that positively identify SES mail
_SES_SUBJECT_SIGNALS: tuple[str, ...] = (
    "【技術者のご紹介】", "【エンド直】", "【GENEST要員情報】",
    "ノンズ要員", "要員情報", "エンジニア紹介", "技術者紹介",
    "週2日出社", "フルリモート可", "月次稼働",
)

# Domains always treated as phishing / scam regardless of subject
_PHISHING_DOMAINS: frozenset[str] = frozenset({
    "abogadosjubilados.org.ar",
    "moodlelms.com.ng",
    "fhq.com.ng",
})

# Subject signals that indicate phishing (combined with external sender)
_PHISHING_SUBJECT_SIGNALS: tuple[str, ...] = (
    "ready for signature",
    "document shared for your review and signature",
    "pdf document shared",
    "limited partnership agreement",
    "agreement ready",
    "verify your account",
    "your account has been suspended",
)

_ACTOR_YABAI = "did:web:yabai.etzhayyim.com"
_ACTOR_MALAK = "did:web:malak.etzhayyim.com"
_ACTOR_INTEL = "did:web:intel.etzhayyim.com"


def _domain_of(addr: str) -> str:
    """Return lowercase domain from email address."""
    if "@" in addr:
        return addr.split("@")[-1].strip().lower()
    return addr.strip().lower()


def _utc_now_str() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

# Blocker signal keywords per type.
# "financial" covers current case: no company funds.
_BLOCKER_SIGNALS: dict[str, list[str]] = {
    "financial": [
        "資金がない", "資金不足", "funds", "no budget", "予算不足",
        "入金待ち", "支払えない", "payment hold", "キャッシュフロー",
        "法人に資金", "cash flow", "funding gap",
    ],
    "personnel": [
        "担当不在", "person unavailable", "no owner", "未アサイン",
        "担当者不明", "リソース不足", "no assignee", "退職",
    ],
    "approval": [
        "承認待ち", "awaiting approval", "要承認", "決裁", "上位承認",
        "pending approval", "sign-off needed",
    ],
    "system": [
        "アクセス権なし", "no access", "system unavailable", "システム障害",
        "権限なし", "not provisioned", "ログインできない",
    ],
    "external": [
        "外部待ち", "waiting for", "先方待ち", "他社待ち",
        "third-party", "vendor reply", "partner response",
    ],
}

# Follow-up interval per blocker type (hours)
_FOLLOWUP_HOURS: dict[str, int] = {
    "financial": 72,   # 3 days — check if funds arrive
    "personnel": 48,
    "approval":  24,
    "system":    24,
    "external":  48,
}

# Acknowledgment template (sent to original delegated person when blocked)
_ACK_TEMPLATE = (
    "{delegated_to}さん\n\nお疲れ様です。\n\n"
    "先ほどご連絡した件ですが、現在「{blocker_desc}」のため対応が保留となっています。\n"
    "ブロッカーが解消次第、改めてご対応をお願いいたします。\n\n"
    "ブロッカー種別: {blocker_type}\n"
    "元のメール件名: {subject}\n\n"
    "よろしくお願いいたします。\n\n河崎 純真"
)

INTENT_SYSTEM = """You are an email triage assistant for a Japanese AI company CEO.
Classify the email into ONE primary intent and optional secondary intents.

Primary intents (choose exactly one):
  billing    — invoice, payment request, overdue notice
  sales      — sales pitch, product demo, vendor introduction
  hr         — hiring, candidate, employment, HR policy
  ops        — infrastructure, system ops, deployment
  legal      — legal matter, contract, compliance
  tech       — technical question or report (internal)
  info       — informational newsletter, announcement (no action needed)
  urgent     — time-sensitive action needed today
  internal   — internal team coordination

Also output:
  urgency_score: integer 0-100 (100 = drop everything now)
  action_required: true/false — does the human CEO need to DO something?
  action_summary: one sentence max, what exactly the CEO must do (empty if action_required=false)
  is_sales: true/false
  sales_product: product/service name if is_sales else ""
  sales_vendor: vendor org name if is_sales else ""
  folder_target: one of [受信トレイ, 営業, 請求, HR, 法務, 情報]

Reply ONLY with valid JSON. No markdown. No extra keys.
Example:
{"intent_primary":"billing","intent_secondary":["legal"],"urgency_score":70,"action_required":true,"action_summary":"TMI請求書を受領・支払い処理する","is_sales":false,"sales_product":"","sales_vendor":"","folder_target":"請求"}
"""

BLOCKER_SYSTEM = """You are a workflow-blocker detector for a Japanese AI company CEO's email system.
Given the email metadata and an explicit blocker annotation from the CEO, identify if there is a blocker.

Output JSON with:
  has_blocker: true/false
  blocker_type: one of [financial, personnel, approval, system, external, none]
  blocker_description: concise Japanese description of the blocker (empty if none)

Reply ONLY with valid JSON. No markdown.
Example:
{"has_blocker":true,"blocker_type":"financial","blocker_description":"法人の資金不足により支払い処理が保留中"}
"""


class PregelState(TypedDict):
    # input
    message_id: str
    thread_id: Optional[str]
    from_address: str
    from_name: str
    to_addresses: str
    subject: str
    received_at: str
    body_preview: str
    # optional CEO annotation — set when re-running with known blocker context
    blocker_annotation: Optional[str]
    # delegated_to: email of the person we delegated this action to
    delegated_to: Optional[str]

    # GEWP fields (populated by check_gewp node)
    attachment_json: Optional[str]   # raw GEWP JSON string from Layer-1 attachment
    body_html: Optional[str]         # HTML body (needed for Layer-2 comment parsing)
    is_gewp: Optional[bool]          # True when GEWP Layer 1 or 2 present
    gewp_thread_id: Optional[str]    # populated after check_gewp
    gewp_type: Optional[str]         # pregel.message | pregel.barrier | human.intent

    # derived
    sender_id: str

    # classification
    intent_primary: str
    intent_secondary: str
    urgency_score: int
    action_required: bool
    action_summary: str
    is_sales: bool
    sales_product: str
    sales_vendor: str
    folder_target: str
    dependency_tracks: str

    # spam classification (set by classify_spam node)
    spam_kind: str           # phishing | ses | sales | none
    spam_domain: str         # sender domain
    spam_sender_org: str     # canonical org name for intel subject

    # blocker detection
    has_blocker: bool
    blocker_type: str        # financial|personnel|approval|system|external|none
    blocker_description: str
    blocker_id: str
    acknowledgment_draft_id: str

    # spam pipeline results
    yabai_entity_id: str
    yabai_evidence_id: str
    malak_message_id: str
    intel_subject_id: str

    # write result
    written: bool
    error: str


def _hash(val: str) -> str:
    return hashlib.sha256(val.encode()).hexdigest()[:24]


# ── Node 1: parse & normalise ─────────────────────────────────────────────────
def parse_email(state: PregelState) -> dict[str, Any]:
    msg_id = state.get("message_id") or _hash(
        state.get("subject", "") + state.get("received_at", "")
    )
    sender_id = _hash(state.get("from_address", "").lower())
    return {"message_id": msg_id, "sender_id": sender_id}


# ── Node 2: LLM classification ────────────────────────────────────────────────
def classify_intent(state: PregelState) -> dict[str, Any]:
    subject = state.get("subject", "")
    body    = state.get("body_preview", "")
    sender  = state.get("from_name", "") + " <" + state.get("from_address", "") + ">"

    prompt = f"From: {sender}\nSubject: {subject}\n\n{body[:800]}"

    try:
        llm = ChatOpenAI(
            base_url=_LLM_URL,
            api_key=_LLM_KEY or "none",
            model=_LLM_MODEL,
            temperature=0,
            max_tokens=256,
        )
        result = llm.invoke([
            SystemMessage(content=INTENT_SYSTEM),
            HumanMessage(content=prompt),
        ])
        parsed = json.loads(result.content)
    except Exception as exc:
        text = (subject + body).lower()
        is_sales = any(s in text for s in _SALES_SIGNALS)
        parsed = {
            "intent_primary": "sales" if is_sales else "info",
            "intent_secondary": [],
            "urgency_score": 20 if is_sales else 10,
            "action_required": False,
            "action_summary": "",
            "is_sales": is_sales,
            "sales_product": "",
            "sales_vendor": state.get("from_name", ""),
            "folder_target": "営業" if is_sales else "情報",
            "_fallback": str(exc)[:120],
        }

    secondary = parsed.get("intent_secondary", [])
    return {
        "intent_primary":  parsed.get("intent_primary", "info"),
        "intent_secondary": ",".join(secondary) if isinstance(secondary, list) else secondary,
        "urgency_score":   int(parsed.get("urgency_score", 0)),
        "action_required": bool(parsed.get("action_required", False)),
        "action_summary":  parsed.get("action_summary", ""),
        "is_sales":        bool(parsed.get("is_sales", False)),
        "sales_product":   parsed.get("sales_product", ""),
        "sales_vendor":    parsed.get("sales_vendor", ""),
        "folder_target":   parsed.get("folder_target", "受信トレイ"),
    }


# ── Node 3: dependency track detection ───────────────────────────────────────
def detect_deps(state: PregelState) -> dict[str, Any]:
    text = (
        state.get("subject", "") + " "
        + state.get("body_preview", "") + " "
        + state.get("from_address", "") + " "
        + state.get("from_name", "")
    ).lower()
    matched = [track for track, keywords in _TRACKS.items()
               if any(kw in text for kw in keywords)]
    return {"dependency_tracks": ",".join(matched)}


# ── Node 4: blocker detection ─────────────────────────────────────────────────
def detect_blockers(state: PregelState) -> dict[str, Any]:
    """Detect action blockers via heuristics + optional LLM + CEO annotation.

    Priority order:
    1. CEO annotation (explicit, highest confidence)
    2. Heuristic keyword scan of subject + body + annotation
    3. LLM classification (when LLM available and no heuristic match)
    """
    annotation = state.get("blocker_annotation") or ""
    text = (
        annotation + " "
        + state.get("subject", "") + " "
        + state.get("body_preview", "")
    ).lower()

    # Heuristic scan
    heuristic_type = "none"
    for btype, keywords in _BLOCKER_SIGNALS.items():
        if any(kw in text for kw in keywords):
            heuristic_type = btype
            break

    if heuristic_type != "none":
        desc = annotation if annotation else f"{heuristic_type}ブロッカーを検知"
        return {
            "has_blocker": True,
            "blocker_type": heuristic_type,
            "blocker_description": desc,
        }

    # LLM fallback when annotation is present but heuristic missed
    if annotation:
        try:
            llm = ChatOpenAI(
                base_url=_LLM_URL,
                api_key=_LLM_KEY or "none",
                model=_LLM_MODEL,
                temperature=0,
                max_tokens=128,
            )
            prompt = (
                f"Subject: {state.get('subject','')}\n"
                f"CEO annotation: {annotation}\n"
                f"Body: {state.get('body_preview','')[:400]}"
            )
            result = llm.invoke([
                SystemMessage(content=BLOCKER_SYSTEM),
                HumanMessage(content=prompt),
            ])
            parsed = json.loads(result.content)
            if parsed.get("has_blocker"):
                return {
                    "has_blocker": True,
                    "blocker_type": parsed.get("blocker_type", "external"),
                    "blocker_description": parsed.get("blocker_description", annotation),
                }
        except Exception as exc:
            _log.warning("[pregel][detect_blockers] LLM error: %s", exc)

    return {"has_blocker": False, "blocker_type": "none", "blocker_description": ""}


# ── Spam branch: classify_spam (after detect_deps) ───────────────────────────

def classify_spam(state: PregelState) -> dict[str, Any]:
    """Classify spam kind: phishing | ses | sales | none."""
    addr    = state.get("from_address", "").lower()
    subject = state.get("subject", "").lower()
    domain  = _domain_of(addr)
    org     = state.get("from_name", "") or state.get("sales_vendor", "") or domain

    # Phishing: domain allowlist or subject signals
    if domain in _PHISHING_DOMAINS or any(s in subject for s in _PHISHING_SUBJECT_SIGNALS):
        return {
            "spam_kind": "phishing",
            "spam_domain": domain,
            "spam_sender_org": org,
        }

    # SES: domain allowlist or subject signals
    if domain in _SES_DOMAINS or any(s in state.get("subject", "") for s in _SES_SUBJECT_SIGNALS):
        return {
            "spam_kind": "ses",
            "spam_domain": domain,
            "spam_sender_org": org,
        }

    # Fallback: flagged as sales by classifier but no action required
    if state.get("is_sales") and not state.get("action_required"):
        return {
            "spam_kind": "sales",
            "spam_domain": domain,
            "spam_sender_org": org,
        }

    return {"spam_kind": "none", "spam_domain": domain, "spam_sender_org": ""}


def _route_after_deps(state: PregelState) -> str:
    """Branch: pre-screen for obvious spam before classify_spam node runs.

    We do a lightweight check here so the graph can branch without waiting for
    classify_spam (which sets spam_kind). The actual full classification runs
    inside the classify_spam node; this gate just avoids running blocker
    detection on obvious recruiter / phishing mail.
    """
    addr    = state.get("from_address", "").lower()
    subject = state.get("subject", "")
    domain  = _domain_of(addr)

    if domain in _PHISHING_DOMAINS:
        return "classify_spam"
    if any(s in subject for s in _PHISHING_SUBJECT_SIGNALS):
        return "classify_spam"
    if domain in _SES_DOMAINS:
        return "classify_spam"
    if any(s in subject for s in _SES_SUBJECT_SIGNALS):
        return "classify_spam"
    if state.get("is_sales") and not state.get("action_required"):
        return "classify_spam"
    return "detect_blockers"


def _route_after_spam(state: PregelState) -> str:
    """Route spam by kind: phishing→malak, ses→intel, sales→yabai only."""
    kind = state.get("spam_kind", "sales")
    if kind == "phishing":
        return "ingest_malak"
    if kind == "ses":
        return "ingest_intel"
    return "register_yabai"


# ── Spam Node A: ingest_malak (phishing only) ─────────────────────────────────

async def ingest_malak(state: PregelState) -> dict[str, Any]:
    """Write phishing evidence to vertex_malak_trap_message."""
    now       = _utc_now_str()
    message_id = f"trapmsg-{_hash(state['message_id'] + 'malak')}"
    evidence_id = f"evidence-{message_id}"
    subject   = state.get("subject", "")
    sender    = state.get("from_address", "")
    body      = state.get("body_preview", "")[:4000]
    domain    = state.get("spam_domain", _domain_of(sender))

    import re as _re
    urls = _re.findall(r"\bhttps?://[^\s<>\"')]+", body)[:50]

    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            vid = f"at://{_ACTOR_MALAK}/com.etzhayyim.apps.malak.trapMessage/{message_id}"
            await conn.execute(
                """
                INSERT INTO graphar.vertex_malak_trap_message
                    (vertex_id, rkey, repo, message_id, evidence_id,
                     trap_id, trap_kind, recipient, provider,
                     provider_message_id, sender, subject, body_preview,
                     urls_json, headers_json, raw_payload_hash, payload_hash,
                     tlp, received_at, created_at, created_date,
                     sensitivity_ord, owner_did, org_id, user_id, actor_did, org_did)
                SELECT $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,
                       $18,$19,$20,$21,$22,$23,$24,$25,$26,$27
                WHERE NOT EXISTS (
                    SELECT 1 FROM graphar.vertex_malak_trap_message
                    WHERE message_id = $4
                )
                """,
                vid, message_id, _ACTOR_MALAK,
                message_id, evidence_id,
                f"pregel-outlook-trap", "email",
                "j.kawasaki@etzhayyim.com", "microsoft365",
                state.get("message_id", ""),
                sender, subject, body,
                json.dumps(urls), "{}",
                _hash(sender + subject + body), _hash(sender + subject + body),
                "amber", state.get("received_at", now) or now,
                now, now[:10],
                120, _ACTOR_MALAK, _ACTOR_MALAK, _ACTOR_MALAK, _ACTOR_MALAK, _ACTOR_MALAK,
            )
            await conn.execute("FLUSH")
        finally:
            await conn.close()
        return {
            "malak_message_id": message_id,
            "error": "",
        }
    except Exception as exc:
        _log.warning("[pregel][ingest_malak] %s", exc)
        return {"malak_message_id": "", "error": str(exc)[:200]}


# ── Spam Node B: ingest_intel (SES only) ─────────────────────────────────────

async def ingest_intel(state: PregelState) -> dict[str, Any]:
    """Register SES sender company as vertex_intel_subject (org entity)."""
    now    = _utc_now_str()
    domain = state.get("spam_domain", "")
    org    = state.get("spam_sender_org", "") or domain
    ckey   = f"ses-recruiter:{domain}"
    subj_id = _hash(ckey)
    vid    = f"at://{_ACTOR_INTEL}/com.etzhayyim.apps.intel.subject/{subj_id}"

    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            await conn.execute(
                """
                INSERT INTO graphar.vertex_intel_subject
                    (vertex_id, subject_kind, canonical_key, label,
                     jurisdiction, attributes_json, status, created_at)
                SELECT $1,'organization',$2,$3,'JPN',
                       $4,'active',$5::timestamptz
                WHERE NOT EXISTS (
                    SELECT 1 FROM graphar.vertex_intel_subject WHERE canonical_key = $2
                )
                """,
                vid, ckey, org,
                json.dumps({
                    "source": "pregel_ses_ingest",
                    "domain": domain,
                    "first_seen_subject": state.get("subject", "")[:120],
                }),
                now,
            )
            await conn.execute("FLUSH")
        finally:
            await conn.close()
        return {"intel_subject_id": subj_id, "error": ""}
    except Exception as exc:
        _log.warning("[pregel][ingest_intel] %s", exc)
        return {"intel_subject_id": "", "error": str(exc)[:200]}


# ── Spam Node C: register_yabai (all spam kinds) ─────────────────────────────

async def register_yabai(state: PregelState) -> dict[str, Any]:
    """Upsert vertex_yabai_entity + insert vertex_yabai_evidence.

    Mirrors the pattern from gmail_triage._node_register_yabai — same schema,
    same entity_id construction so cross-channel reputation merges automatically.
    """
    now    = _utc_now_str()
    today  = now[:10]
    addr   = state.get("from_address", "").lower().strip()
    domain = state.get("spam_domain", _domain_of(addr))
    kind   = state.get("spam_kind", "sales")
    entity_id = f"email-{addr.replace('@', '-at-').replace('.', '-')}"

    # Map spam_kind → yabai category/confidence/severity
    _YABAI_META: dict[str, tuple[str, float, int]] = {
        "phishing": ("phishing",  0.95, 9),
        "ses":      ("spam",      0.80, 3),
        "sales":    ("sales",     0.65, 2),
    }
    category, confidence, severity = _YABAI_META.get(kind, ("spam", 0.70, 3))

    entity_vid  = f"at://{_ACTOR_YABAI}/com.etzhayyim.apps.yabai.entity/{entity_id}"
    evidence_id = f"ev-{_hash(state['message_id'] + 'yabai')}"
    evidence_vid = f"at://{_ACTOR_YABAI}/com.etzhayyim.apps.yabai.evidence/{evidence_id}"

    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            # Upsert entity (idempotent by entity_id PK)
            await conn.execute(
                """
                INSERT INTO graphar.vertex_yabai_entity
                    (vertex_id, rkey, repo, entity_id, entity_kind,
                     canonical_address, domain, label, first_seen, last_seen,
                     evidence_count, severity, created_date, sensitivity_ord,
                     owner_did, actor_did, org_did)
                SELECT $1,$2,$3,$4,'email_address',
                       $5,$6,$7,$8::timestamptz,$8::timestamptz,
                       1,$9,$10,200,$11,$11,$11
                WHERE NOT EXISTS (
                    SELECT 1 FROM graphar.vertex_yabai_entity WHERE entity_id = $4
                )
                """,
                entity_vid, entity_id, _ACTOR_YABAI,
                entity_id, addr, domain,
                state.get("from_name", "") or addr,
                now, severity, today, _ACTOR_YABAI,
            )
            # Bump evidence_count + last_seen on existing row
            await conn.execute(
                """
                UPDATE graphar.vertex_yabai_entity
                SET evidence_count = evidence_count + 1,
                    last_seen = $2::timestamptz,
                    severity = GREATEST(severity, $3)
                WHERE entity_id = $1
                """,
                entity_id, now, severity,
            )
            # Insert evidence record
            await conn.execute(
                """
                INSERT INTO graphar.vertex_yabai_evidence
                    (vertex_id, rkey, repo, evidence_id, entity_id,
                     category, confidence, severity,
                     source_kind, source_ref, description,
                     observed_at, created_date, sensitivity_ord,
                     owner_did, actor_did, org_did)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,
                        'email_message',$9,$10,
                        $11::timestamptz,$12,200,$13,$13,$13)
                """,
                evidence_vid, evidence_id, _ACTOR_YABAI,
                evidence_id, entity_id,
                category, confidence, severity,
                state.get("message_id", ""),
                f"[{kind}] {state.get('subject','')[:120]}",
                now, today, _ACTOR_YABAI,
            )
            await conn.execute("FLUSH")
        finally:
            await conn.close()
        return {
            "yabai_entity_id": entity_id,
            "yabai_evidence_id": evidence_id,
            "written": True,
            "error": "",
        }
    except Exception as exc:
        _log.warning("[pregel][register_yabai] %s", exc)
        return {
            "yabai_entity_id": "",
            "yabai_evidence_id": "",
            "written": False,
            "error": str(exc)[:200],
        }


def _route_after_blocker(state: PregelState) -> str:
    return "handle_blocker" if state.get("has_blocker") else "write_vertex"


# ── Node 5: blocker handler ───────────────────────────────────────────────────
async def handle_blocker(state: PregelState) -> dict[str, Any]:
    """Write blocker record + edge, update email status, draft ack to delegated person."""
    now     = datetime.now(timezone.utc)
    btype   = state.get("blocker_type", "external")
    bdesc   = state.get("blocker_description", "")
    msg_id  = state.get("message_id", "")
    bid     = _hash(msg_id + btype + now.isoformat()[:16])
    followup = now + timedelta(hours=_FOLLOWUP_HOURS.get(btype, 48))

    ack_draft_id = ""
    delegated_to = state.get("delegated_to") or ""

    # Draft acknowledgment to delegated internal person (if set)
    if delegated_to:
        try:
            import urllib.request
            delegated_name = delegated_to.split("@")[0].replace(".", " ").title()
            ack_body = _ACK_TEMPLATE.format(
                delegated_to=delegated_name,
                blocker_desc=bdesc,
                blocker_type=btype,
                subject=state.get("subject", ""),
            )
            payload = json.dumps({
                "to": [delegated_to],
                "subject": f"【ブロッカー通知】{state.get('subject', '')}",
                "bodyText": ack_body,
            }).encode()
            req = urllib.request.Request(
                f"{_MICROSOFT_XRPC}/com.etzhayyim.apps.microsoft.sendMail",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(json.loads(resp.read().decode()))
                ack_draft_id = result.get("draftId", "") or ""
        except Exception as exc:
            _log.warning("[pregel][handle_blocker] ack send error: %s", exc)

    # Write to RisingWave
    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            await conn.execute(
                """
                INSERT INTO graphar.vertex_email_blocker
                    (blocker_id, email_message_id, blocker_type, description,
                     detected_at, acknowledgment_sent, acknowledgment_draft_id,
                     follow_up_at, owner, actor, org_did, sensitivity_ord)
                SELECT $1,$2,$3,$4,$5,$6,$7,$8,$9,
                       'did:web:pregel.etzhayyim.com','did:web:etzhayyim.com',0
                WHERE NOT EXISTS (
                    SELECT 1 FROM graphar.vertex_email_blocker WHERE blocker_id = $1
                )
                """,
                bid, msg_id, btype, bdesc, now,
                bool(ack_draft_id), ack_draft_id or None,
                followup, _OWNER_DID,
            )
            await conn.execute(
                """
                INSERT INTO graphar.edge_email_blocked_by (src, dst, created_at)
                SELECT $1,$2,$3
                WHERE NOT EXISTS (
                    SELECT 1 FROM graphar.edge_email_blocked_by WHERE src=$1 AND dst=$2
                )
                """,
                msg_id, bid, now,
            )
            # Mark email as blocked
            await conn.execute(
                """
                UPDATE graphar.vertex_email_message
                SET response_status = 'blocked'
                WHERE message_id = $1
                """,
                msg_id,
            )
            await conn.execute("FLUSH")
        finally:
            await conn.close()
        return {
            "blocker_id": bid,
            "acknowledgment_draft_id": ack_draft_id,
            "written": True,
            "error": "",
        }
    except Exception as exc:
        return {
            "blocker_id": bid,
            "written": False,
            "error": str(exc)[:200],
        }


# ── Node 6: write to RisingWave (normal path) ────────────────────────────────
async def write_vertex(state: PregelState) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            await conn.execute(
                """
                INSERT INTO graphar.vertex_email_sender
                    (sender_id, address, display_name, org_domain, sender_type,
                     trust_level, first_seen, last_seen, org_did, sensitivity_ord)
                SELECT $1::varchar,$2::varchar,$3::varchar,$4::varchar,$5::varchar,
                       $6::integer,$7::timestamptz,$8::timestamptz,'did:web:etzhayyim.com',0
                WHERE NOT EXISTS (
                    SELECT 1 FROM graphar.vertex_email_sender WHERE sender_id = $1
                )
                """,
                state["sender_id"],
                state.get("from_address", ""),
                state.get("from_name", ""),
                state.get("from_address", "").split("@")[-1],
                "sales" if state.get("is_sales") else "external_partner",
                30 if state.get("is_sales") else 60,
                now, now,
            )
            await conn.execute(
                "UPDATE graphar.vertex_email_sender SET last_seen=$2 WHERE sender_id=$1",
                state["sender_id"], now,
            )

            received = (
                datetime.fromisoformat(state["received_at"])
                if state.get("received_at") else now
            )
            await conn.execute(
                """
                INSERT INTO graphar.vertex_email_message
                    (message_id, thread_id, from_address, from_name,
                     to_addresses, subject, received_at, body_preview,
                     intent_primary, intent_secondary, urgency_score,
                     action_required, action_summary, is_sales,
                     sales_product, sales_vendor, response_status,
                     folder_target, dependency_tracks,
                     owner, actor, org_did, sensitivity_ord, analyzed_at, model_id)
                SELECT
                    $1::varchar,$2::varchar,$3::varchar,$4::varchar,
                    $5::varchar,$6::varchar,$7::timestamptz,$8::varchar,
                    $9::varchar,$10::varchar,$11::integer,
                    $12::boolean,$13::varchar,$14::boolean,$15::varchar,$16::varchar,
                    'pending',$17::varchar,$18::varchar,
                    $19::varchar,'did:web:pregel.etzhayyim.com','did:web:etzhayyim.com',0,
                    $20::timestamptz,$21::varchar
                WHERE NOT EXISTS (
                    SELECT 1 FROM graphar.vertex_email_message WHERE message_id = $1
                )
                """,
                state["message_id"],
                state.get("thread_id"),
                state.get("from_address", ""),
                state.get("from_name", ""),
                state.get("to_addresses", ""),
                state.get("subject", ""),
                received,
                state.get("body_preview", "")[:500],
                state.get("intent_primary", "info"),
                state.get("intent_secondary", ""),
                state.get("urgency_score", 0),
                state.get("action_required", False),
                state.get("action_summary", ""),
                state.get("is_sales", False),
                state.get("sales_product", ""),
                state.get("sales_vendor", ""),
                state.get("folder_target", "受信トレイ"),
                state.get("dependency_tracks", ""),
                _OWNER_DID,
                now,
                _LLM_MODEL,
            )

            await conn.execute(
                """
                INSERT INTO graphar.edge_email_sent_by (src, dst, role, created_at)
                SELECT $1::varchar,$2::varchar,'from',$3::timestamptz
                WHERE NOT EXISTS (
                    SELECT 1 FROM graphar.edge_email_sent_by WHERE src=$1 AND dst=$2
                )
                """,
                state["message_id"], state["sender_id"], now,
            )

            for track in (state.get("dependency_tracks") or "").split(","):
                if track.strip():
                    await conn.execute(
                        """
                        INSERT INTO graphar.edge_email_re_track
                            (src, dst, confidence_permille, created_at)
                        SELECT $1::varchar,$2::varchar,800,$3::timestamptz
                        WHERE NOT EXISTS (
                            SELECT 1 FROM graphar.edge_email_re_track
                            WHERE src=$1 AND dst=$2
                        )
                        """,
                        state["message_id"], track.strip(), now,
                    )

            await conn.execute("FLUSH")
        finally:
            await conn.close()
        return {"written": True, "error": ""}
    except Exception as exc:
        return {"written": False, "error": str(exc)[:200]}


# ── Node 1b: GEWP bridge — detect and dispatch GEWP messages ─────────────────
async def check_gewp(state: PregelState) -> dict[str, Any]:
    """Query vertex_mailer_inbound_email for GEWP payload, route accordingly.

    Reads attachment_json (Layer 1) or body_html (Layer 2) from the stored
    email record.  If a GEWP payload is found, marks is_gewp=True and
    populates gewp_thread_id / gewp_type so _route_after_parse can
    short-circuit to dispatch_gewp.
    """
    from kotodama.ingest.mailer import parse_inbound_gewp

    message_id = state.get("message_id", "")
    attachment_json = state.get("attachment_json") or ""
    body_html = state.get("body_html") or ""

    # If not pre-loaded in state, fetch from RisingWave
    if not attachment_json and not body_html and message_id:
        try:
            conn = await asyncpg.connect(_DB_URL, timeout=8)
            try:
                row = await conn.fetchrow(
                    "SELECT vertex_id, body_html, attachment_json "
                    "FROM vertex_mailer_inbound_email "
                    "WHERE message_id = $1 LIMIT 1",
                    message_id,
                )
                if row:
                    body_html = row["body_html"] or ""
                    attachment_json = row["attachment_json"] or ""
                    vertex_id = row["vertex_id"] or ""
                else:
                    vertex_id = ""
            finally:
                await conn.close()
        except Exception as exc:
            _log.debug("[check_gewp] db fetch failed for %s: %s", message_id, exc)
            vertex_id = ""
    else:
        vertex_id = ""

    if not attachment_json and not body_html:
        return {"is_gewp": False}

    result = parse_inbound_gewp(
        vertex_id=vertex_id,
        body_html=body_html,
        attachment_json=attachment_json,
    )
    gewp_data = result.get("gewp")
    if gewp_data is None:
        return {"is_gewp": False}

    thread = gewp_data.get("thread", {})
    return {
        "is_gewp": True,
        "gewp_thread_id": thread.get("id", ""),
        "gewp_type": gewp_data.get("type", ""),
    }


async def dispatch_gewp(state: PregelState) -> dict[str, Any]:
    """Handle a confirmed GEWP message: log routing and terminate pipeline."""
    thread_id = state.get("gewp_thread_id", "")
    gewp_type = state.get("gewp_type", "")
    message_id = state.get("message_id", "")
    _log.info(
        "[dispatch_gewp] GEWP message routed: message_id=%s thread_id=%s type=%s",
        message_id, thread_id, gewp_type,
    )
    return {"written": True, "error": ""}


def _route_after_parse(state: PregelState) -> str:
    """After check_gewp: route GEWP messages out of the normal pipeline."""
    return "dispatch_gewp" if state.get("is_gewp") else "classify_intent"


# ── Node 7: route email to projector ─────────────────────────────────────────
async def route_email(state: PregelState) -> dict[str, Any]:
    if not state.get("written"):
        return {}
    try:
        from kotodama.primitives.email_route import task_email_route
        await task_email_route(batchSize=1, accountDid=_OWNER_DID)
    except Exception as exc:
        _log.warning("[pregel][route_email] %s", exc)
    return {}


# ── Build graph ───────────────────────────────────────────────────────────────
def _build() -> StateGraph:
    g = StateGraph(PregelState)

    # Core nodes
    g.add_node("parse_email",     parse_email)
    g.add_node("check_gewp",      check_gewp)
    g.add_node("dispatch_gewp",   dispatch_gewp)
    g.add_node("classify_intent", classify_intent)
    g.add_node("detect_deps",     detect_deps)

    # Spam branch
    g.add_node("classify_spam",   classify_spam)
    g.add_node("ingest_malak",    ingest_malak)
    g.add_node("ingest_intel",    ingest_intel)
    g.add_node("register_yabai",  register_yabai)

    # Normal branch
    g.add_node("detect_blockers", detect_blockers)
    g.add_node("handle_blocker",  handle_blocker)
    g.add_node("write_vertex",    write_vertex)
    g.add_node("route_email",     route_email)

    g.set_entry_point("parse_email")
    g.add_edge("parse_email", "check_gewp")

    # GEWP short-circuit: GEWP messages skip the human intent pipeline
    g.add_conditional_edges(
        "check_gewp",
        _route_after_parse,
        {"dispatch_gewp": "dispatch_gewp", "classify_intent": "classify_intent"},
    )
    g.add_edge("dispatch_gewp",   END)
    g.add_edge("classify_intent", "detect_deps")

    # After detect_deps: spam vs normal
    g.add_conditional_edges(
        "detect_deps",
        _route_after_deps,
        {"classify_spam": "classify_spam", "detect_blockers": "detect_blockers"},
    )

    # Spam sub-routing
    g.add_conditional_edges(
        "classify_spam",
        _route_after_spam,
        {
            "ingest_malak":    "ingest_malak",
            "ingest_intel":    "ingest_intel",
            "register_yabai":  "register_yabai",
        },
    )
    g.add_edge("ingest_malak",    "register_yabai")
    g.add_edge("ingest_intel",    "register_yabai")
    g.add_edge("register_yabai",  END)

    # Normal branch
    g.add_conditional_edges(
        "detect_blockers",
        _route_after_blocker,
        {"handle_blocker": "handle_blocker", "write_vertex": "write_vertex"},
    )
    g.add_edge("handle_blocker",  END)
    g.add_edge("write_vertex",    "route_email")
    g.add_edge("route_email",     END)
    return g


app = _build().compile()


def build_graph():
    """Factory entry point for langgraph_loader (py_factory kind)."""
    return _build().compile()


# ══════════════════════════════════════════════════════════════════════════════
# Inbox Triage pipeline (常駐化)
# Graph: triage_heuristic → [certain→triage_ingest_rw, uncertain→triage_llm→triage_ingest_rw]
# Triggered by `triage` subcommand in __main__.py; also handles backfill.
# ══════════════════════════════════════════════════════════════════════════════

_TRIAGE_OWNER_DID = os.getenv("PREGEL_OWNER_DID", "did:web:pregel.etzhayyim.com")
_TRIAGE_ORG_DID   = os.getenv("PREGEL_ORG_DID",   "did:web:etzhayyim.com")

# Internal sender domains — always KEEP regardless of any signals
_INTERNAL_DOMAINS: frozenset[str] = frozenset({
    "etzhayyim.com", "etzhayyim.com", "etzhayyim.works", "etzhayyim.com",
    "etzhayyim.onmicrosoft.com",
})

# Confidence threshold below which LLM re-classification is triggered (permille)
_LLM_THRESHOLD_PERMILLE = int(os.getenv("TRIAGE_LLM_THRESHOLD", "700"))  # 70%

TRIAGE_SYSTEM = """You are an inbox triage agent for a Japanese AI company CEO.
Classify the email into exactly one category:
  KEEP    — needs CEO attention; internal, legal, billing, partner, important ops
  ARCHIVE — may be relevant later but no action needed now; newsletters, vendor info, announcements
  DELETE  — spam, phishing, SES/要員, mass marketing, cold outreach with no relevance

Also output:
  reason: one short sentence (Japanese ok) explaining your decision
  confidence: integer 0-100 (your confidence in the classification)

Reply ONLY with valid JSON. No markdown.
Example:
{"category":"ARCHIVE","reason":"社内ニュースレターで対応不要","confidence":90}
"""


class TriageState(TypedDict, total=False):
    # input (from listInbox message or CSV row)
    message_id:  str
    from_addr:   str
    from_name:   str
    subject:     str
    received_at: str
    body_preview: str
    is_read:     bool

    # heuristic output
    triage_category:            str    # KEEP | ARCHIVE | DELETE
    triage_reason:              str
    triage_confidence_permille: int    # 0-1000
    triage_method:              str    # heuristic | llm | heuristic-csv

    # db write result
    triage_written: bool
    triage_error:   str


def _is_internal_addr(addr: str) -> bool:
    return _domain_of(addr) in _INTERNAL_DOMAINS


def _is_recent_days(received_at: str, days: int = 7) -> bool:
    """True if received_at is within the last `days` days."""
    try:
        dt = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        return dt > datetime.now(timezone.utc) - timedelta(days=days)
    except Exception:
        return False


# ── Triage Node 1: heuristic classification ───────────────────────────────────
def triage_heuristic(state: TriageState) -> dict[str, Any]:
    from_addr = state.get("from_addr", "")
    subject   = state.get("subject", "")
    body      = state.get("body_preview", "")
    text      = (subject + " " + body).lower()
    domain    = _domain_of(from_addr)

    # Internal senders → always KEEP (high confidence)
    if _is_internal_addr(from_addr):
        return {
            "triage_category":            "KEEP",
            "triage_reason":              "社内送信者",
            "triage_confidence_permille": 1000,
            "triage_method":              "heuristic",
        }

    # Phishing domains → always DELETE
    if domain in _PHISHING_DOMAINS:
        return {
            "triage_category":            "DELETE",
            "triage_reason":              "フィッシングドメイン",
            "triage_confidence_permille": 950,
            "triage_method":              "heuristic",
        }

    # Phishing subject signals
    subj_lower = subject.lower()
    if any(sig in subj_lower for sig in _PHISHING_SUBJECT_SIGNALS):
        return {
            "triage_category":            "DELETE",
            "triage_reason":              "フィッシング件名シグナル",
            "triage_confidence_permille": 900,
            "triage_method":              "heuristic",
        }

    # SES/要員営業 domains → DELETE
    if domain in _SES_DOMAINS:
        return {
            "triage_category":            "DELETE",
            "triage_reason":              "SES・要員営業ドメイン",
            "triage_confidence_permille": 950,
            "triage_method":              "heuristic",
        }

    # SES subject signals
    if any(sig in subject for sig in _SES_SUBJECT_SIGNALS):
        return {
            "triage_category":            "DELETE",
            "triage_reason":              "SES・要員営業件名シグナル",
            "triage_confidence_permille": 920,
            "triage_method":              "heuristic",
        }

    # Sales / marketing signals → ARCHIVE (not DELETE — might be relevant)
    if any(sig.lower() in text for sig in _SALES_SIGNALS):
        return {
            "triage_category":            "ARCHIVE",
            "triage_reason":              "営業・マーケティングシグナル",
            "triage_confidence_permille": 750,
            "triage_method":              "heuristic",
        }

    # No strong signal — low confidence, needs LLM
    return {
        "triage_category":            "KEEP",
        "triage_reason":              "heuristic: 判定不明",
        "triage_confidence_permille": 400,
        "triage_method":              "heuristic",
    }


def _should_run_llm(state: TriageState) -> str:
    conf = state.get("triage_confidence_permille", 0)
    return "triage_llm" if conf < _LLM_THRESHOLD_PERMILLE else "triage_ingest_rw"


# ── Triage Node 2: LLM re-classification (uncertain cases only) ───────────────
def triage_llm(state: TriageState) -> dict[str, Any]:
    subject = state.get("subject", "")
    body    = state.get("body_preview", "")
    sender  = state.get("from_name", "") + " <" + state.get("from_addr", "") + ">"
    prompt  = f"From: {sender}\nSubject: {subject}\n\n{body[:600]}"

    try:
        llm = ChatOpenAI(
            base_url=_LLM_URL,
            api_key=_LLM_KEY or "none",
            model=_LLM_MODEL,
            temperature=0,
            max_tokens=128,
        )
        result = llm.invoke([
            SystemMessage(content=TRIAGE_SYSTEM),
            HumanMessage(content=prompt),
        ])
        parsed = json.loads(result.content)
        category = parsed.get("category", "KEEP").upper()
        if category not in ("KEEP", "ARCHIVE", "DELETE"):
            category = "KEEP"
        conf_pct = int(parsed.get("confidence", 60))
        return {
            "triage_category":            category,
            "triage_reason":              parsed.get("reason", "")[:200],
            "triage_confidence_permille": min(1000, conf_pct * 10),
            "triage_method":              "llm",
        }
    except Exception as exc:
        _log.warning("[triage_llm] LLM failed: %s", exc)
        # Keep heuristic result on LLM failure
        return {"triage_method": "heuristic"}


# ── Triage Node 3: persist to RisingWave ──────────────────────────────────────
async def triage_ingest_rw(state: TriageState) -> dict[str, Any]:
    message_id = state.get("message_id", "")
    if not message_id:
        return {"triage_written": False, "triage_error": "missing message_id"}

    vertex_id  = f"at://{_TRIAGE_OWNER_DID}/com.etzhayyim.apps.pregel.inboxTriage/{message_id}"
    now        = _utc_now_str()

    try:
        conn = await asyncpg.connect(_DB_URL, timeout=10)
        try:
            await conn.execute(
                """
                INSERT INTO graphar.vertex_inbox_triage
                    (actor_did, org_did, at_did, vertex_id, message_id,
                     from_addr, from_name, subject, received_at, body_preview,
                     triage_category, triage_reason, triage_confidence_permille,
                     triage_method, triage_at, created_at)
                VALUES
                    ($1, $2, $3, $4, $5,
                     $6, $7, $8, $9, $10,
                     $11, $12, $13,
                     $14, $15::timestamptz, $16::timestamptz)
                """,
                _TRIAGE_OWNER_DID,
                _TRIAGE_ORG_DID,
                None,
                vertex_id,
                message_id,
                state.get("from_addr", ""),
                state.get("from_name", ""),
                state.get("subject", ""),
                state.get("received_at", ""),
                state.get("body_preview", ""),
                state.get("triage_category", "KEEP"),
                state.get("triage_reason", ""),
                state.get("triage_confidence_permille", 0),
                state.get("triage_method", "heuristic"),
                now,
                now,
            )
        finally:
            await conn.close()
        return {"triage_written": True, "triage_error": ""}
    except Exception as exc:
        _log.warning("[triage_ingest_rw] %s: %s", message_id, exc)
        return {"triage_written": False, "triage_error": str(exc)[:200]}


# ── Build triage graph ────────────────────────────────────────────────────────
def _build_triage() -> StateGraph:
    g = StateGraph(TriageState)

    g.add_node("triage_heuristic",  triage_heuristic)
    g.add_node("triage_llm",        triage_llm)
    g.add_node("triage_ingest_rw",  triage_ingest_rw)

    g.set_entry_point("triage_heuristic")
    g.add_conditional_edges(
        "triage_heuristic",
        _should_run_llm,
        {"triage_llm": "triage_llm", "triage_ingest_rw": "triage_ingest_rw"},
    )
    g.add_edge("triage_llm",       "triage_ingest_rw")
    g.add_edge("triage_ingest_rw", END)
    return g


triage_app = _build_triage().compile()
