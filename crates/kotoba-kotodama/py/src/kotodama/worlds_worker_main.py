"""worlds.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.worlds.create.scene")
    async def task_create_scene(**kwargs):
        name = kwargs.get("name", "")
        scene_type = kwargs.get("sceneType", "room")
        author_did = kwargs.get("authorDid", "did:web:worlds.etzhayyim.com")

        scene_id = str(uuid.uuid4())
        vertex_id = f"worlds:scene:{scene_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_worlds_scene
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, name, scene_type, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, date.today(), 0, author_did,
                scene_id, name, scene_type, "draft",
                "did:web:worlds.etzhayyim.com", "did:web:worlds.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"sceneId": scene_id, "status": "draft"}

    @worker.task(task_type="com.etzhayyim.apps.worlds.list.scenes")
    async def task_list_scenes(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                f"SELECT id, name, scene_type, status, created_at FROM vertex_worlds_scene LIMIT {limit} OFFSET {offset}"
            )
        finally:
            await db.close()

        return {"scenes": [dict(r) for r in rows], "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.worlds.get.scene")
    async def task_get_scene(**kwargs):
        scene_id = kwargs.get("sceneId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, name, scene_type, status, created_at, updated_at FROM vertex_worlds_scene WHERE id = $1",
                scene_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.worlds.publish.scene")
    async def task_publish_scene(**kwargs):
        scene_id = kwargs.get("sceneId", "")
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_worlds_scene SET status = 'published', updated_at = $1 WHERE id = $2",
                now, scene_id,
            )
        finally:
            await db.close()

        return {"sceneId": scene_id, "status": "published", "publishedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.worlds.create.asset")
    async def task_create_asset(**kwargs):
        name = kwargs.get("name", "")
        asset_type = kwargs.get("assetType", "mesh")
        scene_id = kwargs.get("sceneId", "")

        asset_id = str(uuid.uuid4())
        vertex_id = f"worlds:asset:{asset_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_worlds_asset
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, name, asset_type, scene_id, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                vertex_id, 0, date.today(), 0, "did:web:worlds.etzhayyim.com",
                asset_id, name, asset_type, scene_id, "active",
                "did:web:worlds.etzhayyim.com", "did:web:worlds.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"assetId": asset_id, "status": "active"}

    @worker.task(task_type="com.etzhayyim.apps.worlds.list.assets")
    async def task_list_assets(**kwargs):
        scene_id = kwargs.get("sceneId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            query = "SELECT id, name, asset_type, scene_id, status, created_at FROM vertex_worlds_asset"
            params = []
            if scene_id:
                query += " WHERE scene_id = $1"
                params.append(scene_id)
            query += f" LIMIT {limit} OFFSET {offset}"
            rows = await db.fetch(query, *params)
        finally:
            await db.close()

        return {"assets": [dict(r) for r in rows], "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.worlds.create.portal")
    async def task_create_portal(**kwargs):
        from_scene_id = kwargs.get("fromSceneId", "")
        to_scene_id = kwargs.get("toSceneId", "")
        label = kwargs.get("label", "")

        portal_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        return {"portalId": portal_id, "fromSceneId": from_scene_id, "toSceneId": to_scene_id, "label": label, "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.worlds.list.portals")
    async def task_list_portals(**kwargs):
        scene_id = kwargs.get("sceneId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        return {"portals": [], "sceneId": scene_id, "offset": offset, "limit": limit}

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
