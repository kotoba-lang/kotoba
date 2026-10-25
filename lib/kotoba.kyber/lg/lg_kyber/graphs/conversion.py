"""kyber Conversion actor — Free→Paid upgrade trigger.

Runs daily at 10:15 JST. Checks free tenants who are at 80%+ of quota
and sends upgrade prompts.

Pipeline: find_quota_heavy → enqueue_upgrade → report

Revenue tiers (ADR-2605220002):
  Free → Starter ¥3,800/月
  Starter → Professional ¥12,000/月
  Professional → Business ¥38,000/月
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from lg_kyber.db import execute, fetch

_log = logging.getLogger(__name__)

_UPGRADE_SUBJECT_FREE = "kyber — 無料プランの上限に近づいています (Starter ¥3,800/月)"
_UPGRADE_SUBJECT_STARTER = "kyber — Starter プランの上限に近づいています (Professional ¥12,000/月)"

_UPGRADE_BODY_FREE = """\
こんにちは！

kyber の無料プランをご利用いただきありがとうございます。
今月の API 利用が上限の80%を超えています。

◆ Starter プラン (¥3,800/月) にアップグレードすると:
  - API コール数 10倍
  - GL/AP/AR データ無制限
  - HR + 在庫管理モジュール
  - AT Protocol データポータビリティ保証

アップグレード: https://kyber.etzhayyim.com/billing/upgrade?plan=starter

引き続きよろしくお願いします。

kyber team
"""

_UPGRADE_BODY_STARTER = """\
こんにちは！

kyber Starter プランをご利用いただきありがとうございます。
今月の API 利用が上限の80%を超えています。

◆ Professional プラン (¥12,000/月) にアップグレードすると:
  - API コール数 無制限
  - 全モジュール + 優先サポート
  - Murakumo LLM 自動仕訳提案
  - マルチテナント管理

アップグレード: https://kyber.etzhayyim.com/billing/upgrade?plan=professional

引き続きよろしくお願いします。

kyber team
"""


class ConversionState(TypedDict, total=False):
    run_date: str
    free_heavy: list[dict]
    starter_heavy: list[dict]
    sent_free: int
    sent_starter: int
    summary: str


async def find_quota_heavy(state: ConversionState) -> ConversionState:
    today = datetime.now(timezone.utc).date().isoformat()
    free_heavy: list[dict] = []
    starter_heavy: list[dict] = []
    try:
        free_rows = await fetch(
            """
            SELECT t.tenant_id, t.org_did,
                   COALESCE(t.contact_email, '') AS contact_email,
                   COALESCE(t.api_call_count, 0) AS api_calls,
                   COALESCE(t.api_call_quota, 1000) AS quota
            FROM vertex_kyber_tenant t
            WHERE t.tier = 'free'
              AND t.status = 'active'
              AND COALESCE(t.api_call_count, 0) >= COALESCE(t.api_call_quota, 1000) * 0.8
            LIMIT 50
            """
        )
        free_heavy = [dict(r) for r in free_rows]
    except Exception as e:
        _log.warning("[kyber.conversion] free_heavy query failed: %s", e)
    try:
        starter_rows = await fetch(
            """
            SELECT t.tenant_id, t.org_did,
                   COALESCE(t.contact_email, '') AS contact_email,
                   COALESCE(t.api_call_count, 0) AS api_calls,
                   COALESCE(t.api_call_quota, 10000) AS quota
            FROM vertex_kyber_tenant t
            WHERE t.tier = 'starter'
              AND t.status = 'active'
              AND COALESCE(t.api_call_count, 0) >= COALESCE(t.api_call_quota, 10000) * 0.8
            LIMIT 50
            """
        )
        starter_heavy = [dict(r) for r in starter_rows]
    except Exception as e:
        _log.warning("[kyber.conversion] starter_heavy query failed: %s", e)

    _log.info("[kyber.conversion] free_heavy=%d starter_heavy=%d", len(free_heavy), len(starter_heavy))
    return {**state, "run_date": today, "free_heavy": free_heavy, "starter_heavy": starter_heavy}


async def enqueue_upgrade(state: ConversionState) -> ConversionState:
    sent_free = 0
    sent_starter = 0

    for tenant in (state.get("free_heavy") or []):
        email = (tenant.get("contact_email") or "").strip()
        org_did = tenant.get("org_did", "unknown")
        try:
            existing = await fetch(
                "SELECT 1 FROM vertex_kyber_outbox WHERE org_did = $1 AND kind = 'conversion-free-starter' AND created_at > NOW() - INTERVAL '30 days' LIMIT 1",
                org_did,
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
                str(uuid.uuid4()), org_did, "conversion-free-starter",
                _UPGRADE_SUBJECT_FREE, _UPGRADE_BODY_FREE, email,
                "queued-no-recipient" if not email else "queued",
                datetime.now(timezone.utc),
            )
            sent_free += 1
        except Exception as e:
            _log.warning("[kyber.conversion] free insert failed for %s: %s", org_did, e)

    for tenant in (state.get("starter_heavy") or []):
        email = (tenant.get("contact_email") or "").strip()
        org_did = tenant.get("org_did", "unknown")
        try:
            existing = await fetch(
                "SELECT 1 FROM vertex_kyber_outbox WHERE org_did = $1 AND kind = 'conversion-starter-pro' AND created_at > NOW() - INTERVAL '30 days' LIMIT 1",
                org_did,
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
                str(uuid.uuid4()), org_did, "conversion-starter-pro",
                _UPGRADE_SUBJECT_STARTER, _UPGRADE_BODY_STARTER, email,
                "queued-no-recipient" if not email else "queued",
                datetime.now(timezone.utc),
            )
            sent_starter += 1
        except Exception as e:
            _log.warning("[kyber.conversion] starter insert failed for %s: %s", org_did, e)

    return {**state, "sent_free": sent_free, "sent_starter": sent_starter}


async def report(state: ConversionState) -> ConversionState:
    run_date = state.get("run_date", "")
    sf = state.get("sent_free", 0)
    ss = state.get("sent_starter", 0)
    summary = f"[{run_date}] kyber conversion: free→starter={sf}件 starter→pro={ss}件"
    _log.info("[kyber.conversion] %s", summary)
    return {**state, "summary": summary}


def _build() -> Any:
    sg = StateGraph(ConversionState)
    sg.add_node("find_quota_heavy", find_quota_heavy)
    sg.add_node("enqueue_upgrade", enqueue_upgrade)
    sg.add_node("report", report)
    sg.add_edge(START, "find_quota_heavy")
    sg.add_edge("find_quota_heavy", "enqueue_upgrade")
    sg.add_edge("enqueue_upgrade", "report")
    sg.add_edge("report", END)
    return sg.compile()


GRAPH = _build()
