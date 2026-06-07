"""tia.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

import asyncio
import os
import uuid
from datetime import datetime, date

import asyncpg
from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")
DB_URL = os.getenv("DATABASE_URL", "REDACTED_USE_DATABASE_URL_ENV")


async def get_db():
    return await asyncpg.connect(DB_URL)


async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.tia.analyzeIntent")
    async def task_analyze_intent(**kwargs):
        text = kwargs.get("text", "")
        context = kwargs.get("context", {})

        now = datetime.utcnow().isoformat()

        return {
            "intent": "unknown",
            "confidence": 0.0,
            "text": text,
            "analyzedAt": now,
        }

    @worker.task(task_type="com.etzhayyim.apps.tia.classifySignal")
    async def task_classify_signal(**kwargs):
        signal_text = kwargs.get("signal", "")
        source = kwargs.get("source", "")

        signal_id = str(uuid.uuid4())
        vertex_id = f"tia:signal:{signal_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_tia_signal
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, signal_text, source, classification, risk_score,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                vertex_id, 0, date.today(), 0, "did:web:tia.etzhayyim.com",
                signal_id, signal_text, source, "unclassified", 0.0,
                "did:web:tia.etzhayyim.com", "did:web:tia.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"signalId": signal_id, "classification": "unclassified", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.tia.extractEntities")
    async def task_extract_entities(**kwargs):
        text = kwargs.get("text", "")
        entity_types = kwargs.get("entityTypes", [])

        now = datetime.utcnow().isoformat()

        return {
            "entities": [],
            "text": text,
            "extractedAt": now,
        }

    @worker.task(task_type="com.etzhayyim.apps.tia.scoreRisk")
    async def task_score_risk(**kwargs):
        subject = kwargs.get("subject", "")
        context = kwargs.get("context", {})

        now = datetime.utcnow().isoformat()

        return {
            "subject": subject,
            "riskScore": 0.0,
            "riskLevel": "low",
            "scoredAt": now,
        }

    @worker.task(task_type="com.etzhayyim.apps.tia.generateSummary")
    async def task_generate_summary(**kwargs):
        signal_ids = kwargs.get("signalIds", [])
        time_range = kwargs.get("timeRange", "24h")

        now = datetime.utcnow().isoformat()

        return {
            "summary": "",
            "signalCount": len(signal_ids),
            "timeRange": time_range,
            "generatedAt": now,
        }

    @worker.task(task_type="com.etzhayyim.apps.tia.lookupProfile")
    async def task_lookup_profile(**kwargs):
        subject = kwargs.get("subject", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, signal_text, source, classification, risk_score, created_at "
                "FROM vertex_tia_signal WHERE source = $1 ORDER BY created_at DESC LIMIT 1",
                subject,
            )
        finally:
            await db.close()

        if not row:
            return {"subject": subject, "profile": None}
        return {"subject": subject, "profile": dict(row)}

    @worker.task(task_type="com.etzhayyim.apps.tia.submitFeedback")
    async def task_submit_feedback(**kwargs):
        signal_id = kwargs.get("signalId", "")
        feedback = kwargs.get("feedback", "")
        correct_classification = kwargs.get("correctClassification", "")

        now = datetime.utcnow().isoformat()

        if signal_id and correct_classification:
            db = await get_db()
            try:
                await db.execute(
                    "UPDATE vertex_tia_signal SET classification = $1, updated_at = $2 WHERE id = $3",
                    correct_classification, now, signal_id,
                )
            finally:
                await db.close()

        return {"signalId": signal_id, "feedback": feedback, "submittedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.tia.getInsights")
    async def task_get_insights(**kwargs):
        time_range = kwargs.get("timeRange", "24h")
        limit = int(kwargs.get("limit", 10))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                "SELECT id, signal_text, source, classification, risk_score, created_at "
                "FROM vertex_tia_signal ORDER BY risk_score DESC LIMIT $1 OFFSET $2",
                limit, offset,
            )
            total_row = await db.fetchrow("SELECT COUNT(*) AS cnt FROM vertex_tia_signal")
        finally:
            await db.close()

        return {
            "signals": [dict(r) for r in rows],
            "total": total_row["cnt"] if total_row else 0,
            "timeRange": time_range,
            "offset": offset,
            "limit": limit,
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
