"""wvme.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.wvme.create.scan")
    async def task_create_scan(**kwargs):
        target = kwargs.get("target", "")
        scan_type = kwargs.get("scanType", "full")
        initiator_did = kwargs.get("initiatorDid", "did:web:wvme.etzhayyim.com")

        scan_id = str(uuid.uuid4())
        vertex_id = f"wvme:scan:{scan_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_wvme_scan
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, target, scan_type, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, date.today(), 0, initiator_did,
                scan_id, target, scan_type, "running",
                "did:web:wvme.etzhayyim.com", "did:web:wvme.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"scanId": scan_id, "status": "running"}

    @worker.task(task_type="com.etzhayyim.apps.wvme.list.scans")
    async def task_list_scans(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                f"SELECT id, target, scan_type, status, created_at FROM vertex_wvme_scan LIMIT {limit} OFFSET {offset}"
            )
        finally:
            await db.close()

        return {"scans": [dict(r) for r in rows], "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.wvme.get.scan")
    async def task_get_scan(**kwargs):
        scan_id = kwargs.get("scanId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, target, scan_type, status, created_at, updated_at FROM vertex_wvme_scan WHERE id = $1",
                scan_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.wvme.list.vulnerabilities")
    async def task_list_vulnerabilities(**kwargs):
        scan_id = kwargs.get("scanId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            query = "SELECT id, scan_id, cve_id, severity, status, created_at FROM vertex_wvme_vulnerability"
            params = []
            if scan_id:
                query += " WHERE scan_id = $1"
                params.append(scan_id)
            query += f" LIMIT {limit} OFFSET {offset}"
            rows = await db.fetch(query, *params)
        finally:
            await db.close()

        return {"vulnerabilities": [dict(r) for r in rows], "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.wvme.get.vulnerability")
    async def task_get_vulnerability(**kwargs):
        vuln_id = kwargs.get("vulnerabilityId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, scan_id, cve_id, severity, status, created_at FROM vertex_wvme_vulnerability WHERE id = $1",
                vuln_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.wvme.create.remediation")
    async def task_create_remediation(**kwargs):
        vuln_id = kwargs.get("vulnerabilityId", "")
        description = kwargs.get("description", "")

        remediation_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_wvme_vulnerability SET status = 'remediating', updated_at = $1 WHERE id = $2",
                now, vuln_id,
            )
        finally:
            await db.close()

        return {"remediationId": remediation_id, "vulnerabilityId": vuln_id, "status": "pending", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.wvme.list.remediations")
    async def task_list_remediations(**kwargs):
        scan_id = kwargs.get("scanId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            query = "SELECT id, scan_id, cve_id, severity, status FROM vertex_wvme_vulnerability WHERE status IN ('remediating', 'remediated')"
            params = []
            if scan_id:
                query += " AND scan_id = $1"
                params.append(scan_id)
            query += f" LIMIT {limit} OFFSET {offset}"
            rows = await db.fetch(query, *params)
        finally:
            await db.close()

        return {"remediations": [dict(r) for r in rows], "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.wvme.get.scanReport")
    async def task_get_scan_report(**kwargs):
        scan_id = kwargs.get("scanId", "")

        db = await get_db()
        try:
            scan = await db.fetchrow(
                "SELECT id, target, scan_type, status FROM vertex_wvme_scan WHERE id = $1",
                scan_id,
            )
            vuln_count = await db.fetchval(
                "SELECT COUNT(*) FROM vertex_wvme_vulnerability WHERE scan_id = $1",
                scan_id,
            )
        finally:
            await db.close()

        if not scan:
            return {"error": "not found"}
        return {
            "scanId": scan_id,
            "scan": dict(scan),
            "vulnerabilityCount": vuln_count or 0,
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
