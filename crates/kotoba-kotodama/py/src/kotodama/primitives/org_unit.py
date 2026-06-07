"""Recursive org unit primitives for legal entities (open-lei actor).

Zeebe task types registered via register():
  openLei.org.register    — create / upsert an org unit (path + level computed)
  openLei.org.dissolve    — mark dissolved, cascade valid_until to active children
  openLei.org.move        — re-parent (update path for self + all descendants)
  openLei.org.addMember   — insert edge_org_unit_member
  openLei.org.removeMember— close membership (set until=now)
  openLei.org.subtree     — query subtree by path prefix (read-only)

Materialized-path design (RisingWave has no WITH RECURSIVE):
  root unit:  path = "/{lei}/{code}"
  sub-unit:   path = "{parent_path}/{code}"
  subtree:    WHERE path LIKE "/{lei}/%" — O(1) prefix scan
  children:   WHERE path LIKE "{parent_path}/%" AND level = parent_level+1
"""
from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

LOG = logging.getLogger("org_unit")

_OWNER_DID = "did:web:open-lei.etzhayyim.com"
_ACTOR_ID  = "sys.langserver.open-lei.org"
_COLLECTION = "com.etzhayyim.apps.openLei.orgUnit"

VALID_ORG_TYPES = frozenset({
    "division", "department", "project", "committee", "team",
    "board", "task_force", "workgroup", "office", "bureau",
})

VALID_MEMBER_ROLES = frozenset({
    "member", "chair", "lead", "secretary", "observer", "sponsor",
})


# ── Pure helpers ──────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_code(provided: str | None, lei: str, name: str) -> str:
    """Return provided code, else deterministic slug from lei+name."""
    if provided and provided.strip():
        return provided.strip().upper().replace(" ", "-")[:32]
    slug = f"{lei[:8]}-{name[:16]}".upper().replace(" ", "-")
    h = hashlib.sha256(f"{lei}:{name}".encode()).hexdigest()[:6]
    return f"{slug}-{h}"


def _make_vertex_id(lei: str, code: str) -> str:
    return f"at://{_OWNER_DID}/{_COLLECTION}/{lei}-{code}"


def _make_edge_id(src_vid: str, dst_vid: str, role: str) -> str:
    h = hashlib.sha256(f"{src_vid}|{dst_vid}|{role}".encode()).hexdigest()[:16]
    return f"edge-org-{role}-{h}"


def compute_path(parent_path: str | None, lei: str, code: str) -> str:
    """Build materialized path for the new org unit."""
    if parent_path:
        return f"{parent_path}/{code}"
    return f"/{lei}/{code}"


def compute_level(parent_level: int | None) -> int:
    return (parent_level if parent_level is not None else -1) + 1


def normalize_org_unit_row(
    *,
    lei: str,
    lei_vertex_id: str,
    org_type: str,
    name: str,
    code: str,
    path: str,
    level: int,
    parent_org_vid: str | None = None,
    name_en: str | None = None,
    purpose: str | None = None,
    url: str | None = None,
    valid_from: str | None = None,
    props: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vertex_id = _make_vertex_id(lei, code)
    now = _utc_now()
    return {
        "vertex_id":      vertex_id,
        "lei_vertex_id":  lei_vertex_id,
        "lei":            lei,
        "parent_org_vid": parent_org_vid,
        "org_type":       org_type,
        "name":           name,
        "name_en":        name_en,
        "code":           code,
        "path":           path,
        "level":          level,
        "status":         "active",
        "valid_from":     valid_from or now[:10],
        "valid_until":    None,
        "purpose":        purpose,
        "url":            url,
        "props":          json.dumps(props) if props else None,
        "created_at":     now,
        "sensitivity_ord": 1,
        "owner_did":      _OWNER_DID,
        "org_id":         _OWNER_DID,
        "user_id":        _OWNER_DID,
        "actor_id":       _ACTOR_ID,
    }


# ── SQL ───────────────────────────────────────────────────────────────────────

_INSERT_ORG_UNIT = """
INSERT INTO vertex_org_unit
  (vertex_id, lei_vertex_id, lei, parent_org_vid, org_type,
   name, name_en, code, path, level,
   status, valid_from, valid_until, purpose, url, props,
   created_at, sensitivity_ord, owner_did, org_id, user_id, actor_id)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""

_INSERT_EDGE_PARENT = """
INSERT INTO edge_org_unit_parent
  (edge_id, src_vid, dst_vid, dst_type, role,
   created_at, sensitivity_ord, owner_did, org_id, user_id, actor_id)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""

_INSERT_MEMBER = """
INSERT INTO edge_org_unit_member
  (edge_id, person_vertex_id, org_unit_vid, role,
   since, until, confidence, source,
   created_at, sensitivity_ord, owner_did, org_id, user_id, actor_id)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""


# ── DB helpers ────────────────────────────────────────────────────────────────

def _fetch_parent_info(cur: Any, parent_org_vid: str) -> tuple[str, int] | None:
    """Return (parent_path, parent_level) or None if not found."""
    _res = client.q(
        "SELECT path, level FROM vertex_org_unit WHERE vertex_id = %s LIMIT 1",
        (parent_org_vid,),
    )
    row = (_res[0] if _res else None)
    if row:
        return str(row[0]), int(row[1])
    return None


def _active_children_paths(cur: Any, path_prefix: str) -> list[str]:
    """Return paths of all active descendant org units."""
    _res = client.q(
        "SELECT path FROM vertex_org_unit WHERE path LIKE %s AND status = 'active' LIMIT {int(10000)}".format(
            int(10000)
        ),
        (f"{path_prefix}/%",),
    )
    return [row[0] for row in _res]


# ── openLei.org.register ──────────────────────────────────────────────────────

def register_org_unit(
    *,
    lei: str,
    lei_vertex_id: str,
    org_type: str,
    name: str,
    parent_org_vid: str | None = None,
    code: str | None = None,
    name_en: str | None = None,
    purpose: str | None = None,
    url: str | None = None,
    valid_from: str | None = None,
    props: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    resolved_code = _make_code(code, lei, name)
    vertex_id = _make_vertex_id(lei, resolved_code)

    path: str
    level: int
    parent_path: str | None = None

    if not dry_run:
        try:
            if True:
                client = get_kotoba_client()
                # Resolve parent context
                if parent_org_vid:
                    info = _fetch_parent_info(cur, parent_org_vid)
                    if info:
                        parent_path, parent_level = info
                        path  = compute_path(parent_path, lei, resolved_code)
                        level = compute_level(parent_level)
                    else:
                        LOG.warning("register_org_unit: parent_org_vid not found, treating as root")
                        path  = compute_path(None, lei, resolved_code)
                        level = 0
                        parent_org_vid = None
                else:
                    path  = compute_path(None, lei, resolved_code)
                    level = 0

                row = normalize_org_unit_row(
                    lei=lei, lei_vertex_id=lei_vertex_id,
                    org_type=org_type, name=name, code=resolved_code,
                    path=path, level=level, parent_org_vid=parent_org_vid,
                    name_en=name_en, purpose=purpose, url=url,
                    valid_from=valid_from, props=props,
                )
                _res = client.q(_INSERT_ORG_UNIT, (
                    row["vertex_id"], row["lei_vertex_id"], row["lei"], row["parent_org_vid"],
                    row["org_type"], row["name"], row["name_en"], row["code"],
                    row["path"], row["level"],
                    row["status"], row["valid_from"], row["valid_until"],
                    row["purpose"], row["url"], row["props"],
                    row["created_at"], row["sensitivity_ord"],
                    row["owner_did"], row["org_id"], row["user_id"], row["actor_id"],
                ))

                # Parent edge
                dst_vid  = parent_org_vid if parent_org_vid else lei_vertex_id
                dst_type = "org_unit" if parent_org_vid else "lei_entity"
                _res = client.q(_INSERT_EDGE_PARENT, (
                    _make_edge_id(vertex_id, dst_vid, "child_of"),
                    vertex_id, dst_vid, dst_type, "child_of",
                    row["created_at"], 1,
                    _OWNER_DID, _OWNER_DID, _OWNER_DID, _ACTOR_ID,
                ))

        except Exception as exc:
            LOG.error("register_org_unit failed: %s", exc)
            return {"ok": False, "vertexId": vertex_id, "error": str(exc)}
    else:
        path  = compute_path(None, lei, resolved_code)
        level = 0

    LOG.info("register_org_unit: %s %s path=%s dry=%s", org_type, name, path, dry_run)
    return {
        "ok":       not dry_run,
        "vertexId": vertex_id,
        "code":     resolved_code,
        "path":     path,
        "level":    level,
        "dryRun":   dry_run,
    }


# ── openLei.org.dissolve ──────────────────────────────────────────────────────

def dissolve_org_unit(
    *,
    org_unit_vid: str,
    valid_until: str | None = None,
    cascade: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    until = valid_until or _utc_now()[:10]
    dissolved = 0
    errors: list[str] = []

    if not dry_run:
        try:
            if True:
                client = get_kotoba_client()
                # Fetch path of target unit
                _res = client.q(
                    "SELECT path FROM vertex_org_unit WHERE vertex_id = %s LIMIT 1",
                    (org_unit_vid,),
                )
                row = (_res[0] if _res else None)
                if not row:
                    return {"ok": False, "error": "org_unit not found", "dissolved": 0}
                own_path = str(row[0])

                # Dissolve self
                _res = client.q(
                    "UPDATE vertex_org_unit SET status = 'dissolved', valid_until = %s WHERE vertex_id = %s",
                    (until, org_unit_vid),
                )
                dissolved += 1

                # Cascade to active descendants
                if cascade:
                    _res = client.q(
                        f"SELECT vertex_id FROM vertex_org_unit WHERE path LIKE %s AND status = 'active' LIMIT {10000}",
                        (f"{own_path}/%",),
                    )
                    children = [r[0] for r in _res]
                    for child_vid in children:
                        _res = client.q(
                            "UPDATE vertex_org_unit SET status = 'dissolved', valid_until = %s WHERE vertex_id = %s",
                            (until, child_vid),
                        )
                        dissolved += 1

        except Exception as exc:
            LOG.error("dissolve_org_unit failed: %s", exc)
            errors.append(str(exc))

    LOG.info("dissolve_org_unit: %s dissolved=%d cascade=%s dry=%s", org_unit_vid, dissolved, cascade, dry_run)
    return {"ok": not errors, "dissolved": dissolved, "validUntil": until, "dryRun": dry_run, "errors": errors}


# ── openLei.org.move ──────────────────────────────────────────────────────────

def move_org_unit(
    *,
    org_unit_vid: str,
    new_parent_org_vid: str | None = None,
    new_parent_lei_vertex_id: str | None = None,
    lei: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Re-parent an org unit. Updates path for self and all descendants."""
    updated = 0
    errors: list[str] = []

    if not dry_run:
        try:
            if True:
                client = get_kotoba_client()
                # Fetch current state
                _res = client.q(
                    "SELECT path, level, code FROM vertex_org_unit WHERE vertex_id = %s LIMIT 1",
                    (org_unit_vid,),
                )
                row = (_res[0] if _res else None)
                if not row:
                    return {"ok": False, "error": "org_unit not found", "updated": 0}
                old_path, old_level, code = str(row[0]), int(row[1]), str(row[2])

                # Resolve new parent
                if new_parent_org_vid:
                    info = _fetch_parent_info(cur, new_parent_org_vid)
                    if not info:
                        return {"ok": False, "error": "new parent not found", "updated": 0}
                    new_parent_path, new_parent_level = info
                    new_path  = compute_path(new_parent_path, lei, code)
                    new_level = compute_level(new_parent_level)
                    new_dst_vid, new_dst_type = new_parent_org_vid, "org_unit"
                else:
                    # Move to root
                    new_path  = compute_path(None, lei, code)
                    new_level = 0
                    new_dst_vid  = new_parent_lei_vertex_id or lei
                    new_dst_type = "lei_entity"

                level_delta = new_level - old_level

                # Update self
                _res = client.q(
                    "UPDATE vertex_org_unit SET path = %s, level = %s, parent_org_vid = %s WHERE vertex_id = %s",
                    (new_path, new_level, new_parent_org_vid, org_unit_vid),
                )
                updated += 1

                # Update descendants: replace old_path prefix with new_path
                _res = client.q(
                    f"SELECT vertex_id, path, level FROM vertex_org_unit WHERE path LIKE %s LIMIT {10000}",
                    (f"{old_path}/%",),
                )
                descendants = _res
                for desc_vid, desc_path, desc_level in descendants:
                    desc_new_path  = new_path + str(desc_path)[len(old_path):]
                    desc_new_level = int(desc_level) + level_delta
                    _res = client.q(
                        "UPDATE vertex_org_unit SET path = %s, level = %s WHERE vertex_id = %s",
                        (desc_new_path, desc_new_level, desc_vid),
                    )
                    updated += 1

                # Update parent edge
                _res = client.q(
                    "DELETE FROM edge_org_unit_parent WHERE src_vid = %s",
                    (org_unit_vid,),
                )
                now = _utc_now()
                _res = client.q(_INSERT_EDGE_PARENT, (
                    _make_edge_id(org_unit_vid, new_dst_vid, "child_of"),
                    org_unit_vid, new_dst_vid, new_dst_type, "child_of",
                    now, 1, _OWNER_DID, _OWNER_DID, _OWNER_DID, _ACTOR_ID,
                ))

        except Exception as exc:
            LOG.error("move_org_unit failed: %s", exc)
            errors.append(str(exc))

    return {"ok": not errors, "updated": updated, "dryRun": dry_run, "errors": errors}


# ── openLei.org.addMember ─────────────────────────────────────────────────────

def add_org_member(
    *,
    person_vertex_id: str,
    org_unit_vid: str,
    role: str = "member",
    since: str | None = None,
    confidence: float = 1.0,
    source: str = "manual",
    dry_run: bool = False,
) -> dict[str, Any]:
    edge_id = _make_edge_id(person_vertex_id, org_unit_vid, role)
    now = _utc_now()
    if not dry_run:
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(_INSERT_MEMBER, (
                    edge_id, person_vertex_id, org_unit_vid, role,
                    since or now[:10], None, confidence, source,
                    now, 1, _OWNER_DID, _OWNER_DID, _OWNER_DID, _ACTOR_ID,
                ))
        except Exception as exc:
            LOG.error("add_org_member failed: %s", exc)
            return {"ok": False, "edgeId": edge_id, "error": str(exc)}

    return {"ok": True, "edgeId": edge_id, "dryRun": dry_run}


# ── openLei.org.removeMember ──────────────────────────────────────────────────

def remove_org_member(
    *,
    person_vertex_id: str,
    org_unit_vid: str,
    role: str | None = None,
    until: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    until_val = until or _utc_now()[:10]
    if not dry_run:
        try:
            if True:
                client = get_kotoba_client()
                if role:
                    _res = client.q(
                        "UPDATE edge_org_unit_member SET until = %s WHERE person_vertex_id = %s AND org_unit_vid = %s AND role = %s AND until IS NULL",
                        (until_val, person_vertex_id, org_unit_vid, role),
                    )
                else:
                    _res = client.q(
                        "UPDATE edge_org_unit_member SET until = %s WHERE person_vertex_id = %s AND org_unit_vid = %s AND until IS NULL",
                        (until_val, person_vertex_id, org_unit_vid),
                    )
        except Exception as exc:
            LOG.error("remove_org_member failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    return {"ok": True, "until": until_val, "dryRun": dry_run}


# ── openLei.org.subtree ───────────────────────────────────────────────────────

def query_org_subtree(
    *,
    lei: str | None = None,
    root_org_vid: str | None = None,
    org_type: str | None = None,
    status: str = "active",
    max_depth: int | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Read-only subtree query. Returns org units under a root."""
    rows: list[dict[str, Any]] = []
    error: str | None = None

    try:
        if True:
            client = get_kotoba_client()
            if root_org_vid:
                _res = client.q(
                    "SELECT path, level FROM vertex_org_unit WHERE vertex_id = %s LIMIT 1",
                    (root_org_vid,),
                )
                res = (_res[0] if _res else None)
                if not res:
                    return {"ok": False, "error": "root org_unit not found", "rows": []}
                prefix = str(res[0])
                min_level = int(res[1])
            elif lei:
                prefix = f"/{lei}"
                min_level = 0
            else:
                return {"ok": False, "error": "lei or root_org_vid required", "rows": []}

            wheres = [f"path LIKE %s"]
            params: list[Any] = [f"{prefix}/%"]
            if status:
                wheres.append("status = %s")
                params.append(status)
            if org_type:
                wheres.append("org_type = %s")
                params.append(org_type)
            if max_depth is not None:
                wheres.append("level <= %s")
                params.append(min_level + int(max_depth))

            where_sql = " AND ".join(wheres)
            bounded = max(1, min(int(limit), 1000))
            _res = client.q(
                f"SELECT vertex_id, lei, parent_org_vid, org_type, name, name_en, code, path, level, status, valid_from, valid_until, purpose FROM vertex_org_unit WHERE {where_sql} ORDER BY path LIMIT {bounded}",
                params,
            )
            for r in _res:
                rows.append({
                    "vertexId": r[0], "lei": r[1], "parentOrgVid": r[2],
                    "orgType": r[3], "name": r[4], "nameEn": r[5],
                    "code": r[6], "path": r[7], "level": r[8],
                    "status": r[9], "validFrom": r[10], "validUntil": r[11],
                    "purpose": r[12],
                })
    except Exception as exc:
        LOG.error("query_org_subtree failed: %s", exc)
        error = str(exc)

    return {"ok": error is None, "rows": rows, "count": len(rows), "error": error}


# ── Zeebe task wrappers ───────────────────────────────────────────────────────

def task_org_register(**kw: Any) -> dict[str, Any]:
    return register_org_unit(
        lei=str(kw.get("lei") or ""),
        lei_vertex_id=str(kw.get("leiVertexId") or ""),
        org_type=str(kw.get("orgType") or "department"),
        name=str(kw.get("name") or ""),
        parent_org_vid=kw.get("parentOrgVid") or None,
        code=kw.get("code") or None,
        name_en=kw.get("nameEn") or None,
        purpose=kw.get("purpose") or None,
        url=kw.get("url") or None,
        valid_from=kw.get("validFrom") or None,
        props=kw.get("props") or None,
        dry_run=bool(kw.get("dryRun")),
    )


def task_org_dissolve(**kw: Any) -> dict[str, Any]:
    return dissolve_org_unit(
        org_unit_vid=str(kw.get("orgUnitVid") or ""),
        valid_until=kw.get("validUntil") or None,
        cascade=bool(kw.get("cascade", True)),
        dry_run=bool(kw.get("dryRun")),
    )


def task_org_move(**kw: Any) -> dict[str, Any]:
    return move_org_unit(
        org_unit_vid=str(kw.get("orgUnitVid") or ""),
        new_parent_org_vid=kw.get("newParentOrgVid") or None,
        new_parent_lei_vertex_id=kw.get("newParentLeiVertexId") or None,
        lei=str(kw.get("lei") or ""),
        dry_run=bool(kw.get("dryRun")),
    )


def task_org_add_member(**kw: Any) -> dict[str, Any]:
    return add_org_member(
        person_vertex_id=str(kw.get("personVertexId") or ""),
        org_unit_vid=str(kw.get("orgUnitVid") or ""),
        role=str(kw.get("role") or "member"),
        since=kw.get("since") or None,
        confidence=float(kw.get("confidence") or 1.0),
        source=str(kw.get("source") or "manual"),
        dry_run=bool(kw.get("dryRun")),
    )


def task_org_remove_member(**kw: Any) -> dict[str, Any]:
    return remove_org_member(
        person_vertex_id=str(kw.get("personVertexId") or ""),
        org_unit_vid=str(kw.get("orgUnitVid") or ""),
        role=kw.get("role") or None,
        until=kw.get("until") or None,
        dry_run=bool(kw.get("dryRun")),
    )


def task_org_subtree(**kw: Any) -> dict[str, Any]:
    return query_org_subtree(
        lei=kw.get("lei") or None,
        root_org_vid=kw.get("rootOrgVid") or None,
        org_type=kw.get("orgType") or None,
        status=str(kw.get("status") or "active"),
        max_depth=int(kw.get("maxDepth")) if kw.get("maxDepth") is not None else None,
        limit=int(kw.get("limit") or 200),
    )


def register(worker: Any, timeout_ms: int = 60_000) -> None:
    t = lambda name, fn: worker.task(task_type=name, single_value=False, timeout_ms=timeout_ms)(fn)  # noqa: E731
    t("openLei.org.register",      task_org_register)
    t("openLei.org.dissolve",      task_org_dissolve)
    t("openLei.org.move",          task_org_move)
    t("openLei.org.addMember",     task_org_add_member)
    t("openLei.org.removeMember",  task_org_remove_member)
    t("openLei.org.subtree",       task_org_subtree)
