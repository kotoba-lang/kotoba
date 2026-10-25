"""kyber Marketing actor — Japan SMB / nokyo / manufacturing outreach.

Runs every 6h. Top-of-funnel: discover leads from vertex_kyber_lead,
enrich, score, and draft outreach (queued-no-recipient; human-gated).

Target segments:
  - Japan SMB (製造業、農協、法律事務所、スタートアップ)
  - OSS ERP評価中の開発者
  - AT Protocol / DID-native infrastructure 関心層

Pipeline: discover → enrich → score → route → draft → report
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from lg_kyber.db import execute, fetch, fetchval

_log = logging.getLogger(__name__)

_DRAFT_CAP = 10

_ICP_SEGMENTS = {
    "manufacturing": ["製造", "factory", "manufacturing", "産業"],
    "nokyo": ["農協", "nokyo", "農業", "farming", "agriculture"],
    "lawfirm": ["法律", "弁護士", "法務", "law", "legal"],
    "startup": ["startup", "スタートアップ", "SaaS", "tech"],
    "oss_developer": ["oss", "open source", "github", "developer", "erp"],
}

_TOUCH_TEMPLATES = {
    "manufacturing": (
        "件名: kyber — 製造業向けオープンソース ERP (無料トライアル)\n\n"
        "kyber は AT Protocol DID-native の会計・HR・在庫 SaaS です。\n"
        "製造業の現場で使われる在庫管理・原価計算を即日開始できます。\n\n"
        "無料トライアル: https://kyber.etzhayyim.com/signup\n"
        "詳細: https://kyber.etzhayyim.com/solutions/manufacturing\n\n"
        "ご不明な点があればお気軽にご返信ください。\n\nkyber team"
    ),
    "nokyo": (
        "件名: kyber — 農協・農業法人向けクラウド会計 (無料トライアル)\n\n"
        "kyber は農協・農業法人の会計・HR 管理を自動化する SaaS です。\n"
        "APQC PCF 全業界対応、いつでも自社サーバーに移行可能。\n\n"
        "無料トライアル: https://kyber.etzhayyim.com/signup\n\n"
        "ご不明な点があればお気軽にご返信ください。\n\nkyber team"
    ),
    "lawfirm": (
        "件名: kyber — 法律事務所向けクラウド会計 (無料トライアル)\n\n"
        "kyber は法律事務所の会計・請求書管理を効率化する SaaS です。\n"
        "AT Protocol により完全なデータポータビリティを保証します。\n\n"
        "無料トライアル: https://kyber.etzhayyim.com/signup\n\n"
        "ご不明な点があればお気軽にご返信ください。\n\nkyber team"
    ),
    "startup": (
        "件名: kyber — スタートアップ向けオープンソース ERP (無料)\n\n"
        "kyber は ERP を「脱出できる」形で提供する SaaS です。\n"
        "Murakumo LLM による自動仕訳提案、MCP endpoint で AI エージェント連携。\n\n"
        "無料トライアル: https://kyber.etzhayyim.com/signup\n\n"
        "ご不明な点があればお気軽にご返信ください。\n\nkyber team"
    ),
    "oss_developer": (
        "件名: kyber — OSS ERP の代替を探している方へ\n\n"
        "kyber は AT Protocol DID-native のオープンソース ERP です。\n"
        "Frappe/ERPNext の代替として、完全なデータポータビリティを保証します。\n\n"
        "GitHub: https://github.com/etzhayyim/open-kyber\n"
        "Cloud: https://kyber.etzhayyim.com/signup\n\n"
        "ご不明な点があればお気軽にご返信ください。\n\nkyber team"
    ),
}


class MarketingState(TypedDict, total=False):
    run_date: str
    leads: list[dict]
    enriched: list[dict]
    scored: list[dict]
    drafted: int
    summary: str


async def discover(state: MarketingState) -> MarketingState:
    today = datetime.now(timezone.utc).date().isoformat()
    leads: list[dict] = []
    try:
        rows = await fetch(
            """
            SELECT vertex_id, source, domain, contact_email, company, signal, tech_stack
            FROM vertex_kyber_lead
            WHERE outreach_status IN ('new', 'enriched')
            ORDER BY created_at ASC
            LIMIT 50
            """
        )
        leads = [dict(r) for r in rows]
    except Exception as e:
        _log.warning("[kyber.marketing] discover query failed: %s", e)
    _log.info("[kyber.marketing] discovered %d leads", len(leads))
    return {**state, "run_date": today, "leads": leads}


async def enrich(state: MarketingState) -> MarketingState:
    enriched = []
    for lead in (state.get("leads") or []):
        sig = (lead.get("signal") or "").lower()
        company = (lead.get("company") or "").lower()
        text = f"{sig} {company}"
        segment = "startup"
        for seg, keywords in _ICP_SEGMENTS.items():
            if any(k.lower() in text for k in keywords):
                segment = seg
                break
        lead = dict(lead)
        lead["icp_segment"] = segment
        enriched.append(lead)
    return {**state, "enriched": enriched}


async def score(state: MarketingState) -> MarketingState:
    scored = []
    for lead in (state.get("enriched") or []):
        s = 50
        sig = (lead.get("signal") or "").lower()
        if lead.get("contact_email"):
            s += 20
        if "oss" in sig or "open source" in sig:
            s += 15
        if lead.get("icp_segment") in ("manufacturing", "nokyo", "lawfirm"):
            s += 15
        lead = dict(lead)
        lead["score"] = min(s, 100)
        scored.append(lead)
    scored.sort(key=lambda l: -l["score"])
    return {**state, "scored": scored}


async def route(state: MarketingState) -> MarketingState:
    kept = [l for l in (state.get("scored") or []) if l.get("score", 0) >= 50]
    return {**state, "scored": kept[:_DRAFT_CAP]}


async def draft(state: MarketingState) -> MarketingState:
    drafted = 0
    for lead in (state.get("scored") or []):
        seg = lead.get("icp_segment", "startup")
        body = _TOUCH_TEMPLATES.get(seg, _TOUCH_TEMPLATES["startup"])
        email = (lead.get("contact_email") or "").strip()
        org_did = "did:web:kyber.etzhayyim.com"
        try:
            existing = await fetchval(
                "SELECT 1 FROM vertex_kyber_outbox WHERE org_did = $1 AND kind = 'marketing-outreach' AND body_text LIKE $2 LIMIT 1",
                org_did, f"%{lead.get('domain', '')}%",
            )
            if existing:
                continue
        except Exception:
            pass
        try:
            await execute(
                """
                INSERT INTO vertex_kyber_outbox
                  (vertex_id, org_did, kind, subject, body_text,
                   recipient_email, status, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                """,
                str(uuid.uuid4()), org_did, "marketing-outreach",
                f"kyber — {seg} 向けご案内",
                body,
                email,
                "queued-no-recipient",
                datetime.now(timezone.utc),
            )
            await execute(
                "UPDATE vertex_kyber_lead SET outreach_status = 'drafted' WHERE vertex_id = $1",
                lead["vertex_id"],
            )
            drafted += 1
        except Exception as e:
            _log.warning("[kyber.marketing] draft insert failed: %s", e)
    return {**state, "drafted": drafted}


async def report(state: MarketingState) -> MarketingState:
    run_date = state.get("run_date", "")
    total = len(state.get("leads") or [])
    drafted = state.get("drafted", 0)
    summary = f"[{run_date}] kyber marketing: {total}件発見 → {drafted}件draft"
    _log.info("[kyber.marketing] %s", summary)
    return {**state, "summary": summary}


def _build() -> Any:
    sg = StateGraph(MarketingState)
    sg.add_node("discover", discover)
    sg.add_node("enrich", enrich)
    sg.add_node("score", score)
    sg.add_node("route", route)
    sg.add_node("draft", draft)
    sg.add_node("report", report)
    sg.add_edge(START, "discover")
    sg.add_edge("discover", "enrich")
    sg.add_edge("enrich", "score")
    sg.add_edge("score", "route")
    sg.add_edge("route", "draft")
    sg.add_edge("draft", "report")
    sg.add_edge("report", END)
    return sg.compile()


GRAPH = _build()
