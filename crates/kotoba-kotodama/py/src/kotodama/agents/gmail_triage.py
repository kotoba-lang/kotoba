"""Gmail spam/phishing triage LangGraph agent.

Graph id: ``gmail.triage.v1``
Task surface: invoked from ``kotodama.ingest.gmail.triage`` (the BPMN
``gmail.triage`` Zeebe task delegates to it via ``_make_gmail_task``).

Architecture (ADR-0032 + ADR-2605072000 LangGraph Agent Loop Pattern):

    START → claim_unprocessed (DB)
              ↓
            t1_sql_rules (rule classifier — label/keyword/auth/allowlist)
              ↓
            gray_zone_gate ──no gray──→ register_yabai
              │
              └──has gray──→ t3_llm_rescore (LLM #1, Murakumo gemma-4-e4b)
                              ↓
                            register_yabai (chain actor → vertex_yabai_*)
                              │   ↓ uses t2_threat_synth (LLM #2) per spam
                              ↓
                            mark_triaged (DB UPDATE) → END

LLM call budget: up to 1 + N_spam (N_spam capped at 5 per batch).

Chain actor pattern: ``register_yabai`` upserts ``vertex_yabai_entity``
+ ``vertex_yabai_evidence`` directly via Hyperdrive sync_cursor (ADR-0036).
The yabai actor reads them through its existing read XRPC. Cross-actor
write via ``generic.pds.dispatch`` is not used here — yabai schema is
domain-tier (Hyperdrive direct), not social-tier.

State persistence: gmail email rows are flagged with triaged_at /
triage_classification / triage_score / triage_reasons (ALTER applied
in 20260508996000_alter_vertex_gmail_email_triage.ts).
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import json
import re
import time
from typing import Any, TypedDict
from urllib.parse import urlparse

from langgraph.graph import END, START, StateGraph

from kotodama import llm
from kotodama.primitives import langgraph_registry

# ── Constants ──────────────────────────────────────────────────────────

ACTOR_GMAIL = "did:web:gmail.etzhayyim.com"
ACTOR_YABAI = "did:web:yabai.etzhayyim.com"

# Score thresholds (ADR-0032 §Tier-1)
SCORE_SPAM = 70   # >=70 → spam
SCORE_GRAY_LOW = 40   # 40-69 → gray (hand to T3 LLM)
SCORE_TRASH = 60   # TRASH label baseline
SCORE_SPAM_LABEL = 85   # SPAM label baseline

# Keyword score (matches gmail.py:_phish_score keywords + extends)
PHISH_KEYWORDS_RE = re.compile(
    r"urgent|verify|password|invoice|payment|account|suspend|"
    r"unauthorized|locked|expire|click here|confirm.{0,20}identity|"
    r"reset.{0,20}password|tax.{0,20}refund",
    re.IGNORECASE,
)

# Allowlist domains — score floor for known-safe senders
ALLOWLIST_DOMAINS = frozenset({
    "etzhayyim.com", "etzhayyim.com", "etzhayyim.com",
    "google.com", "googlemail.com", "gmail.com",
    "apple.com", "icloud.com",
    "amazon.com", "amazon.co.jp",
    "microsoft.com", "outlook.com", "office.com",
    "github.com", "anthropic.com",
    "paypay-bank.co.jp", "rakuten-bank.co.jp",
    "shimoda-bs.jp", "yashin.co.jp",
    "servcorp.co.jp", "servcorp.net",
    "vultr.com", "cloudflare.com",
})


# ── Graph state ────────────────────────────────────────────────────────


class GmailTriageState(TypedDict, total=False):
    # Inputs
    batchSize: int
    accountEmail: str

    # claim_unprocessed output
    claimed: list[dict[str, Any]]   # rows from vertex_gmail_email

    # t1_sql_rules output (in-place mutate per row): adds keys
    #   classification: spam | trash | gray | clean
    #   score: int
    #   reasons: list[str]

    # t2_reputation output: rep dict { entity_id → {count, max_sev, ...} }
    reputation: dict[str, dict[str, Any]]

    # gray_zone_gate output
    grayIds: list[str]

    # t3_llm_rescore output: updates classification/score/reasons for gray rows
    # threat_synth output: per-row "iocDescription" key (JSON string)

    # register_yabai output
    yabaiEntities: int
    yabaiEvidence: int

    # mark_triaged output
    triagedTotal: int
    spamTotal: int
    trashTotal: int
    grayTotal: int
    cleanTotal: int

    # Bookkeeping
    llmCalls: int
    error: str


# ── Helpers ────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _domain_of(addr: str) -> str:
    if not addr:
        return ""
    m = re.search(r"<([^>]+)>", addr) or re.search(r"\S+@\S+", addr)
    raw = m.group(1) if m and m.lastindex else (m.group(0) if m else addr)
    if "@" in raw:
        return raw.rsplit("@", 1)[1].strip().lower().rstrip(">")
    return raw.strip().lower().rstrip(">")


def _allowlisted(addr: str) -> bool:
    d = _domain_of(addr)
    if not d:
        return False
    if d in ALLOWLIST_DOMAINS:
        return True
    return any(d.endswith("." + a) for a in ALLOWLIST_DOMAINS)


def _has_label(labels_csv: str, want: str) -> bool:
    if not labels_csv:
        return False
    parts = [p.strip().upper() for p in str(labels_csv).split(",")]
    return want.upper() in parts


def _phish_score(
    spf: str, dkim: str, dmarc: str,
    reply_to: str, from_addr: str,
    subject: str, body_urls_json: str,
) -> tuple[int, list[str]]:
    """Re-implementation of ingest/gmail.py:_phish_score with reasons trail."""
    score = 0
    reasons: list[str] = []
    if spf and spf not in ("pass", "none"):
        score += 20
        reasons.append(f"spf={spf}")
    if dkim and dkim not in ("pass", "none"):
        score += 20
        reasons.append(f"dkim={dkim}")
    if dmarc and dmarc not in ("pass", "none"):
        score += 25
        reasons.append(f"dmarc={dmarc}")
    if reply_to and from_addr:
        rt_dom = _domain_of(reply_to)
        fr_dom = _domain_of(from_addr)
        if rt_dom and fr_dom and rt_dom != fr_dom:
            score += 15
            reasons.append(f"reply-to-mismatch:{rt_dom}!={fr_dom}")
    if subject and PHISH_KEYWORDS_RE.search(subject):
        score += 15
        reasons.append("subject-keyword")
    try:
        urls = json.loads(body_urls_json) if body_urls_json else []
    except Exception:
        urls = []
    if urls:
        score += 10
        reasons.append(f"urls:{len(urls)}")
        # bonus for non-allowlisted host
        for u in urls[:3]:
            try:
                host = (urlparse(u).hostname or "").lower()
                if host and not any(host == a or host.endswith("." + a) for a in ALLOWLIST_DOMAINS):
                    score += 5
                    reasons.append(f"url-host:{host}")
                    break
            except Exception:
                pass
    return min(score, 100), reasons


def _sanitize_addr(addr: str) -> str:
    """Build idempotent vertex_id key segment from email address."""
    d = _domain_of(addr) or "unknown"
    local = ""
    m = re.search(r"<([^>]+)>", addr) or re.search(r"\S+@\S+", addr)
    raw = (m.group(1) if m and m.lastindex else (m.group(0) if m else addr)).strip(" <>")
    if "@" in raw:
        local = raw.rsplit("@", 1)[0].lower()
    sanitized = re.sub(r"[^a-z0-9._-]", "_", f"{local}_at_{d}").strip("_") or "unknown"
    return sanitized[:120]


# ── Graph nodes ────────────────────────────────────────────────────────


async def _node_claim(state: GmailTriageState) -> GmailTriageState:
    batch = max(1, min(int(state.get("batchSize") or 50), 200))
    account_filter = (state.get("accountEmail") or "").strip()
    sql = (
        "SELECT vertex_id, email_id, from_addr, reply_to, subject, snippet, "
        "body_urls_json, labels, spf_result, dkim_result, dmarc_result, account_email "
        "FROM vertex_gmail_email WHERE triaged_at IS NULL "
    )
    params: tuple[Any, ...] = ()
    if account_filter:
        sql += "AND account_email = %s "
        params = (account_filter,)
    sql += f"ORDER BY internal_date DESC LIMIT {int(batch)}"
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, params)
        cols = [d[0] for d in []]
        claimed = [dict(zip(cols, row)) for row in (_res or [])]
    return {**state, "claimed": claimed, "llmCalls": int(state.get("llmCalls") or 0)}


async def _node_t1(state: GmailTriageState) -> GmailTriageState:
    """Rule-based classifier — no LLM."""
    out: list[dict[str, Any]] = []
    gray_ids: list[str] = []
    for row in state.get("claimed") or []:
        labels = str(row.get("labels") or "")
        from_addr = str(row.get("from_addr") or "")
        subject = str(row.get("subject") or "")
        # Hard signals first
        if _has_label(labels, "SPAM"):
            row["classification"] = "spam"
            row["score"] = SCORE_SPAM_LABEL
            row["reasons"] = ["gmail-label:SPAM"]
        elif _has_label(labels, "TRASH"):
            row["classification"] = "trash"
            row["score"] = SCORE_TRASH
            row["reasons"] = ["gmail-label:TRASH"]
        elif _allowlisted(from_addr):
            row["classification"] = "clean"
            row["score"] = 0
            row["reasons"] = [f"allowlist:{_domain_of(from_addr)}"]
        else:
            score, reasons = _phish_score(
                str(row.get("spf_result") or ""),
                str(row.get("dkim_result") or ""),
                str(row.get("dmarc_result") or ""),
                str(row.get("reply_to") or ""),
                from_addr,
                subject,
                str(row.get("body_urls_json") or ""),
            )
            row["score"] = score
            row["reasons"] = reasons
            if score >= SCORE_SPAM:
                row["classification"] = "spam"
            elif score >= SCORE_GRAY_LOW:
                row["classification"] = "gray"
                gray_ids.append(str(row.get("vertex_id") or ""))
            else:
                row["classification"] = "clean"
        out.append(row)
    return {**state, "claimed": out, "grayIds": gray_ids}


def _reputation_score_bump(rep: dict[str, Any]) -> tuple[int, list[str]]:
    """Translate sender reputation row into (delta, reasons).

    Pure function. Tested in test_gmail_triage_pure.py.
    """
    if not rep:
        return 0, []
    cnt = int(rep.get("evidence_count_24h") or 0)
    max_sev = int(rep.get("max_severity_24h") or 0)
    delta = 0
    reasons: list[str] = []
    if cnt >= 5:
        delta += 25
        reasons.append(f"rep:cnt24h={cnt}")
    elif cnt >= 3:
        delta += 15
        reasons.append(f"rep:cnt24h={cnt}")
    if max_sev >= 8:
        delta += 10
        reasons.append(f"rep:maxSev={max_sev}")
    return delta, reasons


async def _node_t2_reputation(state: GmailTriageState) -> GmailTriageState:
    """T2 sender reputation lookup — no LLM, single MV scan.

    Reads `mv_yabai_sender_reputation_24h` for every claimed sender's
    entity_id, applies score bump, and may promote gray → spam if the
    bumped score crosses SCORE_SPAM. Reasons trail records the bump.
    """
    rows = state.get("claimed") or []
    if not rows:
        return {**state, "reputation": {}, "grayIds": []}
    entity_ids = sorted({f"email-{_sanitize_addr(str(r.get('from_addr') or ''))}" for r in rows})
    rep: dict[str, dict[str, Any]] = {}
    if entity_ids:
        if True:
            client = get_kotoba_client()
            placeholders = ",".join(["%s"] * len(entity_ids))
            _res = client.q(
                f"SELECT entity_id, evidence_count_24h, max_severity_24h, "
                f"avg_confidence_24h, distinct_categories_24h "
                f"FROM mv_yabai_sender_reputation_24h "
                f"WHERE entity_id IN ({placeholders})",
                tuple(entity_ids),
            )
            for row in _res or []:
                rep[str(row[0])] = {
                    "evidence_count_24h": row[1],
                    "max_severity_24h": row[2],
                    "avg_confidence_24h": row[3],
                    "distinct_categories_24h": row[4],
                }
    gray_ids: list[str] = []
    for row in rows:
        eid = f"email-{_sanitize_addr(str(row.get('from_addr') or ''))}"
        delta, extra_reasons = _reputation_score_bump(rep.get(eid) or {})
        if delta:
            row["score"] = min(100, int(row.get("score") or 0) + delta)
            row["reasons"] = list(row.get("reasons") or []) + extra_reasons
            # Promote gray → spam if bumped over threshold
            if row.get("classification") == "gray" and row["score"] >= SCORE_SPAM:
                row["classification"] = "spam"
            elif row.get("classification") == "clean" and row["score"] >= SCORE_SPAM:
                row["classification"] = "spam"
            elif row.get("classification") == "clean" and row["score"] >= SCORE_GRAY_LOW:
                row["classification"] = "gray"
        if row.get("classification") == "gray":
            gray_ids.append(str(row.get("vertex_id") or ""))
    return {**state, "claimed": rows, "reputation": rep, "grayIds": gray_ids}


def _has_gray(state: GmailTriageState) -> str:
    return "t3" if (state.get("grayIds") or []) else "synth"


async def _node_t3_llm(state: GmailTriageState) -> GmailTriageState:
    """LLM #1 — Murakumo re-score for gray-zone emails (40 <= score < 70).

    Capped at 5 LLM calls per batch (cost guard); excess gray rows stay gray.
    """
    gray_ids = set(state.get("grayIds") or [])
    if not gray_ids:
        return state
    rows = [r for r in (state.get("claimed") or []) if str(r.get("vertex_id") or "") in gray_ids]
    rows = rows[:5]
    llm_calls = int(state.get("llmCalls") or 0)
    system = (
        "You are a phishing/spam triage classifier. Given an email metadata "
        "object, return JSON {\"classification\":\"spam|gray|clean\","
        "\"confidence\":0.0-1.0,\"reasons\":[short strings]}. Be conservative: "
        "only mark spam if there are clear adversarial signals (impersonation, "
        "credential phishing, urgent payment demand, mismatched reply-to)."
    )
    for row in rows:
        prompt = json.dumps({
            "from": row.get("from_addr"),
            "replyTo": row.get("reply_to"),
            "subject": row.get("subject"),
            "snippet": (str(row.get("snippet") or ""))[:400],
            "spf": row.get("spf_result"),
            "dkim": row.get("dkim_result"),
            "dmarc": row.get("dmarc_result"),
            "urlCount": len(json.loads(row.get("body_urls_json") or "[]") or []) if row.get("body_urls_json") else 0,
            "ruleScore": row.get("score"),
            "ruleReasons": row.get("reasons"),
        }, ensure_ascii=False)
        try:
            result = llm.call_tier_json(
                tier="fast",
                system=system,
                user=prompt,
                max_tokens=200,
                temperature=0.0,
            )
            llm_calls += 1
            cls = str(result.get("classification") or "gray").lower()
            if cls not in {"spam", "gray", "clean"}:
                cls = "gray"
            conf = float(result.get("confidence") or 0.5)
            row["classification"] = cls
            row["score"] = int(round(min(99, max(0, int(row.get("score") or 0) + (20 if cls == "spam" else (-20 if cls == "clean" else 0))))))
            extra_reasons = result.get("reasons") or []
            if isinstance(extra_reasons, list):
                row["reasons"] = list(row.get("reasons") or []) + [f"t3:{str(x)[:60]}" for x in extra_reasons[:3]]
            row["reasons"].append(f"t3-conf:{conf:.2f}")
        except Exception as exc:
            row["reasons"] = list(row.get("reasons") or []) + [f"t3-err:{type(exc).__name__}"]
    return {**state, "llmCalls": llm_calls}


async def _node_threat_synth(state: GmailTriageState) -> GmailTriageState:
    """LLM #2 — threat intelligence synthesis for confirmed spam rows.

    Generates structured IOC JSON used as `event.description`
    so the yabai dashboard sees natural-language threat summary instead of
    a canned string. Only fires for spam classification (not trash/gray);
    capped at 3 calls per batch (cost guard).

    Failure mode: LLM error → fall back to canned description (graceful
    degradation, no row drop).
    """
    rows = [r for r in (state.get("claimed") or []) if str(r.get("classification") or "") == "spam"]
    rows = rows[:3]
    if not rows:
        return state
    llm_calls = int(state.get("llmCalls") or 0)
    system = (
        "You are a threat intelligence synthesizer. Given an email metadata "
        "object that has been flagged as spam/phishing, produce a JSON object: "
        "{\"threat_type\": one of [credential_phishing, invoice_fraud, "
        "malware_delivery, sextortion, advance_fee, business_email_compromise, "
        "tech_support_scam, generic_spam], "
        "\"iocs\": [up to 5 short IOC strings — domains, sender handles, "
        "subject keywords, suspect URLs], "
        "\"summary\": \"2-sentence English threat description\", "
        "\"recommended_action\": one of [block_sender, report_to_fcc, ignore, manual_review]}. "
        "Be conservative: empty iocs is fine if signals are weak."
    )
    for row in rows:
        prompt = json.dumps({
            "from": row.get("from_addr"),
            "replyTo": row.get("reply_to"),
            "subject": row.get("subject"),
            "snippet": (str(row.get("snippet") or ""))[:400],
            "ruleScore": row.get("score"),
            "ruleReasons": row.get("reasons"),
            "labels": row.get("labels"),
        }, ensure_ascii=False)
        try:
            result = llm.call_tier_json(
                tier="fast",
                system=system,
                user=prompt,
                max_tokens=300,
                temperature=0.0,
            )
            llm_calls += 1
            # Validate + bound result
            threat_type = str(result.get("threat_type") or "generic_spam")[:50]
            iocs = result.get("iocs") or []
            if not isinstance(iocs, list):
                iocs = []
            iocs = [str(x)[:80] for x in iocs[:5]]
            summary = str(result.get("summary") or "")[:300]
            action = str(result.get("recommended_action") or "manual_review")[:30]
            ioc_desc = json.dumps({
                "threat_type": threat_type,
                "iocs": iocs,
                "summary": summary,
                "recommended_action": action,
            }, ensure_ascii=False)
            row["iocDescription"] = ioc_desc[:480]
        except Exception as exc:
            row["reasons"] = list(row.get("reasons") or []) + [f"synth-err:{type(exc).__name__}"]
    return {**state, "llmCalls": llm_calls}


def _yabai_evidence_meta(classification: str) -> tuple[str, float, int]:
    """Return (category, confidence, severity) per ADR-0032 yabai mapping."""
    if classification == "spam":
        return ("FraudSignal", 0.85, 8)
    if classification == "trash":
        return ("IntelExtraction", 0.60, 4)
    if classification == "gray":
        return ("FraudSignal", 0.55, 5)
    return ("", 0.0, 0)


async def _node_register_yabai(state: GmailTriageState) -> GmailTriageState:
    """Chain actor: cross-write into vertex_yabai_entity + vertex_yabai_evidence.

    Idempotent via PK upsert. Only spam/trash/gray rows produce yabai rows;
    clean rows are skipped.
    """
    rows = [
        r for r in (state.get("claimed") or [])
        if str(r.get("classification") or "") in {"spam", "trash", "gray"}
    ]
    if not rows:
        return {**state, "yabaiEntities": 0, "yabaiEvidence": 0}
    today = _today()
    now = _now_iso()
    base_entity = {
        "_seq": None,
        "created_date": today,
        "sensitivity_ord": 200,
        "owner_did": ACTOR_YABAI,
        "repo": ACTOR_YABAI,
        "source": "gmail-classifier",
        "created_at": now,
        "org_id": "etzhayyim",
        "user_id": "jun784",
        "actor_id": "sys.gmail-triage",
    }
    entity_count = 0
    evidence_count = 0
    seen_entities: set[str] = set()
    if True:
        client = get_kotoba_client()
        for row in rows:
            from_addr = str(row.get("from_addr") or "")
            if not from_addr:
                continue
            sender_key = _sanitize_addr(from_addr)
            entity_id = f"email-{sender_key}"
            entity_vid = f"at://{ACTOR_YABAI}/com.etzhayyim.apps.yabai.entity/{entity_id}"
            if entity_vid not in seen_entities:
                _res = client.q(
                    "INSERT INTO vertex_yabai_entity ("
                    "vertex_id, _seq, created_date, sensitivity_ord, owner_did, rkey, repo, "
                    "entity_id, entity_type, name, value, canonical_name, aliases, source, "
                    "created_at, org_id, user_id, actor_id"
                    ") VALUES ("
                    "%s, %s, %s::date, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s"
                    ") ON CONFLICT (vertex_id) DO UPDATE SET "
                    "name = EXCLUDED.name, value = EXCLUDED.value, "
                    "canonical_name = EXCLUDED.canonical_name, source = EXCLUDED.source",
                    (
                        entity_vid, None, today, 200, ACTOR_YABAI,
                        entity_id, ACTOR_YABAI,
                        entity_id, "email_address",
                        from_addr.lower(), from_addr.lower(), from_addr.lower(),
                        "", "gmail-classifier",
                        now, "etzhayyim", "jun784", "sys.gmail-triage",
                    ),
                )
                seen_entities.add(entity_vid)
                entity_count += 1
            cls = str(row.get("classification") or "")
            category, confidence, severity = _yabai_evidence_meta(cls)
            if not category:
                continue
            email_id = str(row.get("email_id") or "")
            evidence_id = "ev-" + email_id + "-" + cls
            evidence_vid = f"at://{ACTOR_YABAI}/com.etzhayyim.apps.yabai.evidence/{evidence_id}"
            reasons_csv = ",".join(str(x) for x in (row.get("reasons") or []))[:480]
            _res = client.q(
                "INSERT INTO vertex_yabai_evidence ("
                "vertex_id, _seq, created_date, sensitivity_ord, owner_did, rkey, repo, "
                "evidence_id, entity_id, category, confidence, severity, probability, "
                "source, source_reliability, jurisdiction, summary, description, "
                "verification_id, occurred_at, created_at, org_id, user_id, actor_id"
                ") VALUES ("
                "%s, %s, %s::date, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s"
                ") ON CONFLICT (vertex_id) DO UPDATE SET "
                "confidence = EXCLUDED.confidence, severity = EXCLUDED.severity, "
                "summary = EXCLUDED.summary, description = EXCLUDED.description",
                (
                    evidence_vid, None, today, 200, ACTOR_YABAI,
                    evidence_id, ACTOR_YABAI,
                    evidence_id, entity_id, category,
                    float(confidence), int(severity), float(confidence),
                    "gmail-classifier", "medium", "jp",
                    f"Gmail classified as {cls.upper()}",
                    # Prefer LLM-synthesized IOC JSON when available (Phase 3),
                    # fall back to subject + reasons trail.
                    (
                        str(row.get("iocDescription") or "").strip()
                        or (str(row.get("subject") or "")[:240] + " | reasons: " + reasons_csv)
                    )[:480],
                    "", now, now,
                    "etzhayyim", "jun784", "sys.gmail-triage",
                ),
            )
            evidence_count += 1
    return {**state, "yabaiEntities": entity_count, "yabaiEvidence": evidence_count}


async def _node_mark_triaged(state: GmailTriageState) -> GmailTriageState:
    rows = state.get("claimed") or []
    if not rows:
        return {**state, "triagedTotal": 0, "spamTotal": 0, "trashTotal": 0, "grayTotal": 0, "cleanTotal": 0}
    now = _now_iso()
    counts = {"spam": 0, "trash": 0, "gray": 0, "clean": 0}
    if True:
        client = get_kotoba_client()
        for row in rows:
            vid = row.get("vertex_id")
            cls = str(row.get("classification") or "clean")
            counts[cls] = counts.get(cls, 0) + 1
            score = int(row.get("score") or 0)
            reasons_csv = ",".join(str(x) for x in (row.get("reasons") or []))[:480]
            _res = client.q(
                "UPDATE vertex_gmail_email SET triaged_at = %s, triage_classification = %s, "
                "triage_score = %s, triage_reasons = %s WHERE vertex_id = %s",
                (now, cls, score, reasons_csv, vid),
            )
    return {
        **state,
        "triagedTotal": len(rows),
        "spamTotal": counts["spam"],
        "trashTotal": counts["trash"],
        "grayTotal": counts["gray"],
        "cleanTotal": counts["clean"],
    }


# ── Graph compile ──────────────────────────────────────────────────────


def _build_graph() -> Any:
    builder: StateGraph = StateGraph(GmailTriageState)
    builder.add_node("claim", _node_claim)
    builder.add_node("t1", _node_t1)
    builder.add_node("t2_rep", _node_t2_reputation)
    builder.add_node("t3", _node_t3_llm)
    builder.add_node("synth", _node_threat_synth)
    builder.add_node("register", _node_register_yabai)
    builder.add_node("mark", _node_mark_triaged)
    builder.add_edge(START, "claim")
    builder.add_edge("claim", "t1")
    builder.add_edge("t1", "t2_rep")
    builder.add_conditional_edges("t2_rep", _has_gray, {"t3": "t3", "synth": "synth"})
    builder.add_edge("t3", "synth")
    builder.add_edge("synth", "register")
    builder.add_edge("register", "mark")
    builder.add_edge("mark", END)
    return builder.compile()


gmail_triage_graph = _build_graph()
langgraph_registry.register("gmail.triage.v1", gmail_triage_graph)


__all__ = ["gmail_triage_graph", "GmailTriageState"]
