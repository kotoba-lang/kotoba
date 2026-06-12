"""robot.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.robotics.workflow.start")
    async def task_workflow_start(**kwargs):
        process_id = kwargs.get("processId", "")
        robot_did = kwargs.get("robotDid", "")
        mission_id = kwargs.get("missionId", "")
        variables = kwargs.get("variables", {})

        instance_id = str(uuid.uuid4())
        vertex_id = f"robotics:workflow_instance:{instance_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_robot_workflow_instance
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, process_id, robot_did, mission_id, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                vertex_id, 0, date.today(), 0, robot_did,
                instance_id, process_id, robot_did, mission_id, "running",
                "did:web:robot.etzhayyim.com", "did:web:robot.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"instanceId": instance_id, "status": "running"}

    @worker.task(task_type="com.etzhayyim.apps.robotics.workflow.plan")
    async def task_workflow_plan(**kwargs):
        process_id = kwargs.get("processId", "")
        context = kwargs.get("context", {})

        plan_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        return {
            "planId": plan_id,
            "processId": process_id,
            "steps": [],
            "estimatedDurationMs": 0,
            "createdAt": now,
        }

    @worker.task(task_type="com.etzhayyim.apps.robotics.mission.plan")
    async def task_mission_plan(**kwargs):
        robot_did = kwargs.get("robotDid", "")
        goal = kwargs.get("goal", "")
        constraints = kwargs.get("constraints", {})

        mission_id = str(uuid.uuid4())
        vertex_id = f"robotics:mission:{mission_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_robot_mission
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, robot_did, goal, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, date.today(), 0, robot_did,
                mission_id, robot_did, goal, "planned",
                "did:web:robot.etzhayyim.com", "did:web:robot.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"missionId": mission_id, "status": "planned"}

    @worker.task(task_type="com.etzhayyim.apps.robotics.mission.status")
    async def task_mission_status(**kwargs):
        mission_id = kwargs.get("missionId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, robot_did, goal, status, created_at, updated_at "
                "FROM vertex_robot_mission WHERE id = $1",
                mission_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.robotics.mission.simulate")
    async def task_mission_simulate(**kwargs):
        mission_id = kwargs.get("missionId", "")
        dry_run = kwargs.get("dryRun", True)

        sim_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        return {
            "simulationId": sim_id,
            "missionId": mission_id,
            "dryRun": dry_run,
            "result": "success",
            "collisions": 0,
            "estimatedDurationMs": 5000,
            "simulatedAt": now,
        }

    @worker.task(task_type="com.etzhayyim.apps.robotics.telemetry.ingest")
    async def task_telemetry_ingest(**kwargs):
        robot_did = kwargs.get("robotDid", "")
        topic = kwargs.get("topic", "")
        payload = kwargs.get("payload", {})
        timestamp = kwargs.get("timestamp", datetime.utcnow().isoformat())

        telemetry_id = str(uuid.uuid4())
        vertex_id = f"robotics:telemetry:{telemetry_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_robot_telemetry
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, robot_did, topic, ts,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, date.today(), 0, robot_did,
                telemetry_id, robot_did, topic, timestamp,
                "did:web:robot.etzhayyim.com", "did:web:robot.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"id": telemetry_id, "ingested": True}

    @worker.task(task_type="com.etzhayyim.apps.robotics.process.catalog")
    async def task_process_catalog(**kwargs):
        category = kwargs.get("category", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        catalog = [
            {"id": "reachy-mini-patrol", "category": "inspection", "description": "Autonomous patrol route"},
            {"id": "reachy-mini-pickup", "category": "manipulation", "description": "Object pickup and placement"},
            {"id": "reachy-mini-dropship", "category": "fulfillment", "description": "Dropshipping dispatch"},
        ]
        if category:
            catalog = [p for p in catalog if p["category"] == category]

        return {
            "processes": catalog[offset:offset + limit],
            "total": len(catalog),
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.robotics.fulfillment.close")
    async def task_fulfillment_close(**kwargs):
        fulfillment_id = kwargs.get("fulfillmentId", "")
        outcome = kwargs.get("outcome", "delivered")
        notes = kwargs.get("notes", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_robot_mission SET status = $1, updated_at = $2 WHERE id = $3",
                outcome, now, fulfillment_id,
            )
        finally:
            await db.close()

        return {"fulfillmentId": fulfillment_id, "outcome": outcome, "closedAt": now}

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
