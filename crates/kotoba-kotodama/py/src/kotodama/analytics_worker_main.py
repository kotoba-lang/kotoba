"""analytics.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.analytics.createDashboard")
    async def task_create_dashboard(**kwargs):
        name = kwargs.get("name", "")
        owner_did = kwargs.get("ownerDid", "did:web:analytics.etzhayyim.com")
        description = kwargs.get("description", "")

        dashboard_id = str(uuid.uuid4())
        vertex_id = f"analytics:dashboard:{dashboard_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_analytics_dashboard
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, name, description, actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                vertex_id, 0, date.today(), 0, owner_did,
                dashboard_id, name, description,
                "did:web:analytics.etzhayyim.com", "did:web:analytics.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"dashboardId": dashboard_id, "name": name, "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.analytics.recordEvent")
    async def task_record_event(**kwargs):
        event_name = kwargs.get("eventName", "")
        actor_did = kwargs.get("actorDid", "did:web:analytics.etzhayyim.com")
        properties = kwargs.get("properties", {})

        event_id = str(uuid.uuid4())
        vertex_id = f"analytics:event:{event_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_analytics_event
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, event_name, actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
                vertex_id, 0, date.today(), 0, actor_did,
                event_id, event_name,
                "did:web:analytics.etzhayyim.com", "did:web:analytics.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"eventId": event_id, "eventName": event_name, "recordedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.analytics.listDashboards")
    async def task_list_dashboards(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                "SELECT id, name, description, created_at FROM vertex_analytics_dashboard "
                "ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset,
            )
            total = await db.fetchval("SELECT COUNT(*) FROM vertex_analytics_dashboard")
        finally:
            await db.close()

        return {
            "dashboards": [dict(r) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.analytics.getDashboard")
    async def task_get_dashboard(**kwargs):
        dashboard_id = kwargs.get("dashboardId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, name, description, created_at FROM vertex_analytics_dashboard WHERE id = $1",
                dashboard_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.analytics.listEvents")
    async def task_list_events(**kwargs):
        event_name = kwargs.get("eventName", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if event_name:
                rows = await db.fetch(
                    "SELECT id, event_name, actor_did, created_at FROM vertex_analytics_event "
                    "WHERE event_name = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    event_name, limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_analytics_event WHERE event_name = $1", event_name
                )
            else:
                rows = await db.fetch(
                    "SELECT id, event_name, actor_did, created_at FROM vertex_analytics_event "
                    "ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_analytics_event")
        finally:
            await db.close()

        return {
            "events": [dict(r) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.analytics.getMetrics")
    async def task_get_metrics(**kwargs):
        metric_name = kwargs.get("metricName", "")
        period = kwargs.get("period", "day")
        now = datetime.utcnow().isoformat()

        return {
            "metricName": metric_name,
            "period": period,
            "value": 0,
            "change": 0.0,
            "computedAt": now,
        }

    @worker.task(task_type="com.etzhayyim.apps.analytics.createReport")
    async def task_create_report(**kwargs):
        name = kwargs.get("name", "")
        dashboard_id = kwargs.get("dashboardId", "")

        report_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        return {"reportId": report_id, "name": name, "dashboardId": dashboard_id, "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.analytics.listReports")
    async def task_list_reports(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        return {
            "reports": [],
            "total": 0,
            "offset": offset,
            "limit": limit,
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
