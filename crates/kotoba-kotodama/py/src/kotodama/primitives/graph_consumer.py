"""Graph consumer primitives for BPMN/LangServer.

Projection logic runs locally via psycopg3 (direct RisingWave connection).
Each run is recorded as graph-visible audit data in vertex_graph_consume_tick.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import datetime as _dt
import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from kotodama import rw_schema


GRAPH_DID = "did:web:graph.etzhayyim.com"
CONSUME_TICK_COLLECTION = "com.etzhayyim.apps.graph.consumeTick"
DEFAULT_TIMEOUT_SEC = 30.0

# Process-scoped memory cursor — avoids cold-start DB round-trip on every tick.
_memory_cursor: int = 0

# ── Collection → table for delete path ───────────────────────────────────────
_COLLECTION_TO_TABLE: dict[str, str] = {
    "app.bsky.actor.profile": "vertex_profile",
    "app.bsky.feed.post": "vertex_repo_record",
    "app.bsky.graph.follow": "edge_follows",
    "app.bsky.feed.like": "edge_likes",
    "app.bsky.feed.repost": "edge_reposts",
    "app.bsky.graph.list": "vertex_list",
    "app.bsky.graph.listitem": "edge_list_item",
    "app.bsky.feed.generator": "vertex_list",
    "app.bsky.labeler.service": "vertex_list",
}

_MAPS_CONTROL_PLANE = {"mapsSource", "mapsJob", "mapsDataset"}
_MAPS_LABEL_SPECIAL = {"asset": "PhysicalAsset"}

# Process-scoped column cache for convention fallback.
_convention_col_cache: dict[str, set[str]] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _camel_to_snake(s: str) -> str:
    return re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), s)


def _maps_entity_label(entity: str) -> str:
    return _MAPS_LABEL_SPECIAL.get(entity, entity[0].upper() + entity[1:])


def _convention_candidates(collection: str) -> list[str]:
    m = re.match(r"^ai\.etzhayyim\.apps\.([^.]+)\.([^.]+)$", collection)
    if not m:
        return []
    app, entity = m.group(1), m.group(2)
    if app == "maps" and not re.match(r"^edge[A-Z]", entity) and entity not in _MAPS_CONTROL_PLANE:
        return ["vertex_spatial"]
    if re.match(r"^edge[A-Z]", entity):
        return [f"edge_{app}_{_camel_to_snake(entity[4:])}", f"edge_{app}"]
    return [f"vertex_{app}_{_camel_to_snake(entity)}", f"vertex_{app}"]


# ── Typed collection handlers ─────────────────────────────────────────────────

def _handle_collection(
    collection: str, rec: dict, ctx: dict
) -> Optional[list[tuple[str, dict]]]:
    """Return [(table, row), ...] or None for convention fallback."""
    repo = ctx["repo"]
    rkey = ctx["rkey"]
    vid = ctx["vid"]
    seq = ctx["seq"]
    cd = ctx["created_date"]
    base = {"_seq": seq, "created_date": cd, "sensitivity_ord": 300, "owner_did": repo}

    if collection == "app.bsky.actor.profile":
        avatar = rec.get("avatar")
        banner = rec.get("banner")
        main: dict = {
            **base,
            "vertex_id": vid, "repo": repo, "rkey": rkey, "collection": collection,
            "did": repo,
            "display_name": rec.get("displayName"),
            "description": rec.get("description"),
            "avatar_cid": avatar.get("ref") if isinstance(avatar, dict) else None,
            "banner_cid": banner.get("ref") if isinstance(banner, dict) else None,
            "created_at": rec.get("createdAt"),
        }
        result: list[tuple[str, dict]] = [("vertex_profile", main)]
        for suffix, label, text in [
            ("profile-description", "ProfileDescription", (rec.get("description") or "").strip()),
            ("profile-display-name", "ProfileDisplayName", (rec.get("displayName") or "").strip()),
        ]:
            if text:
                result.append(("vertex_profile_fragment", {
                    **base,
                    "vertex_id": f"{vid}#{suffix}",
                    "rkey": rkey, "repo": repo, "label": label,
                    "text": text, "props": "{}",
                }))
        return result

    if collection == "app.bsky.feed.post":
        # vertex_post was dropped in migration 0012; route to vertex_repo_record
        return [("vertex_repo_record", {
            "uri": vid, "cid": None, "collection": collection,
            "rkey": rkey, "repo": repo, "repo_rev": None,
            "value_json": json.dumps(rec),
            "indexed_at": _utc_now_iso(),
            "takedown_ref": None,
            "ts_ms": int(time.time() * 1000),
            "created_at": rec.get("createdAt"),
        })]

    if collection == "app.bsky.graph.follow":
        subj = rec.get("subject")
        return [("edge_follows", {
            **base,
            "edge_id": vid, "src_vid": repo,
            "dst_vid": subj if isinstance(subj, str) else None,
            "rkey": rkey, "repo": repo,
            "created_at": rec.get("createdAt"),
        })]

    if collection == "app.bsky.feed.like":
        subj = rec.get("subject") or {}
        uri = subj.get("uri") if isinstance(subj, dict) else None
        cid = subj.get("cid") if isinstance(subj, dict) else None
        return [("edge_likes", {
            **base,
            "edge_id": vid, "src_vid": repo, "dst_vid": uri,
            "subject_uri": uri, "subject_cid": cid,
            "rkey": rkey, "repo": repo,
        })]

    if collection == "app.bsky.feed.repost":
        subj = rec.get("subject") or {}
        uri = subj.get("uri") if isinstance(subj, dict) else None
        cid = subj.get("cid") if isinstance(subj, dict) else None
        return [("edge_reposts", {
            **base,
            "edge_id": vid, "src_vid": repo, "dst_vid": uri,
            "subject_uri": uri, "subject_cid": cid,
            "rkey": rkey, "repo": repo,
        })]

    if collection in ("app.bsky.graph.list", "app.bsky.feed.generator", "app.bsky.labeler.service"):
        suffix = collection.split(".")[-1]
        label = "".join(p[0].upper() + p[1:] for p in re.split(r"[-_]", suffix))
        return [("vertex_list", {
            **base,
            "vertex_id": vid, "rkey": rkey, "repo": repo, "label": label,
            "display_name": rec.get("name") or rec.get("displayName"),
            "description": rec.get("description"),
            "purpose": rec.get("purpose"),
        })]

    if collection == "app.bsky.graph.listitem":
        lst = rec.get("list")
        subj = rec.get("subject")
        return [("edge_list_item", {
            **base,
            "edge_id": vid,
            "src_vid": lst if isinstance(lst, str) else None,
            "dst_vid": subj if isinstance(subj, str) else None,
        })]

    if collection == "com.etzhayyim.apps.media_gamers.record.translationLink":
        return [("vertex_translation_link", {
            **base,
            "vertex_id": vid, "rkey": rkey, "repo": repo,
            "source_uri": rec.get("sourceUri") if isinstance(rec.get("sourceUri"), str) else None,
            "source_lang": rec.get("sourceLang") if isinstance(rec.get("sourceLang"), str) else None,
            "translated_uri": rec.get("translatedUri") if isinstance(rec.get("translatedUri"), str) else None,
            "lang": rec.get("lang") if isinstance(rec.get("lang"), str) else None,
            "source": rec.get("source") if isinstance(rec.get("source"), str) else None,
            "quality_score": rec.get("qualityScore") if isinstance(rec.get("qualityScore"), (int, float)) else None,
            "created_at": rec.get("createdAt") if isinstance(rec.get("createdAt"), str) else None,
            "org_id": rec.get("org_id") if isinstance(rec.get("org_id"), str) else None,
            "user_id": rec.get("user_id") if isinstance(rec.get("user_id"), str) else None,
            "actor_id": rec.get("actor_id") if isinstance(rec.get("actor_id"), str) else None,
        })]

    return None  # convention fallback


def _get_convention_cols(cur: Any, table: str) -> Optional[set[str]]:
    if table in _convention_col_cache:
        return _convention_col_cache[table]
    try:
        _res = client.q(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s",
            (table,),
        )
        rows = _res
        if not rows:
            return None
        cols = {str(r[0]) for r in rows}
        _convention_col_cache[table] = cols
        return cols
    except Exception:
        return None


def _build_convention_row(rec: dict, ctx: dict, cols: set[str]) -> dict:
    row: dict = {}
    if "vertex_id" in cols:
        row["vertex_id"] = ctx["vid"]
    if "rkey" in cols:
        row["rkey"] = ctx["rkey"]
    if "repo" in cols:
        row["repo"] = ctx["repo"]
    if "_seq" in cols:
        row["_seq"] = ctx["seq"]
    if "created_date" in cols:
        row["created_date"] = ctx["created_date"]
    if "sensitivity_ord" in cols:
        row["sensitivity_ord"] = 300
    if "owner_did" in cols:
        row["owner_did"] = ctx["repo"]
    for k, v in rec.items():
        if v is None:
            continue
        snake = _camel_to_snake(k)
        if snake in cols:
            row[snake] = v
        elif k in cols:
            row[k] = v
    if rec.get("displayName") is not None and "display_name" in cols:
        row["display_name"] = rec["displayName"]
    if rec.get("createdAt") is not None and "created_at" in cols:
        row["created_at"] = rec["createdAt"]
    return row


def _project_rows_for_insert(
    table: str,
    rows: list[dict],
    fallback_cols: Optional[set[str]] = None,
) -> tuple[list[dict], set[str]]:
    """Project rows onto the live RisingWave table schema.

    The Kysely-managed live DB is the schema source of truth. If reflection is
    temporarily unavailable, keep the previous per-cursor column probe behavior
    by falling back to the supplied column set.
    """
    try:
        schema = rw_schema.load_schema()
        projected = [schema.project_known_columns(table, row) for row in rows]
        return projected, set(schema.column_names(table))
    except Exception:
        if not fallback_cols:
            return rows, set()
        return (
            [{key: value for key, value in row.items() if key in fallback_cols} for row in rows],
            set(fallback_cols),
        )


# ── Core local consumer ───────────────────────────────────────────────────────

def _consume_commits_local(batch_size: int = 50) -> dict[str, Any]:
    """
    Direct Python port of consumeRepoCommits() — no HTTP call to CF Worker.
    Uses sync_cursor() / psycopg3 → RisingWave direct connection.
    """
    global _memory_cursor

    try:
        if True:
            client = get_kotoba_client()
            # 1. Read cursor (memory first, DB fallback on cold start)
            last_seq = _memory_cursor
            if last_seq == 0:
                try:
                    _res = client.q(
                        "SELECT last_seq FROM vertex_consumer_cursor WHERE consumer_id = 'graph-worker'"
                    )
                    row = (_res[0] if _res else None)
                    if row:
                        last_seq = int(row[0] or 0)
                except Exception:
                    pass

            # 2. Fetch unprocessed commits
            _res = client.q(
                f"SELECT seq, repo, collection, rkey, action, rev, cid, prev, sig, value_json, ts_ms "
                f"FROM vertex_repo_commit WHERE seq > %s ORDER BY seq ASC LIMIT {int(batch_size)}",
                (last_seq,),
            )
            commits = _res
            if not commits:
                return {"ok": True, "processed": 0, "lastSeq": last_seq}

            # 3. Dispatch each commit → (table → rows)
            by_table: dict[str, list[dict]] = {}
            profile_repos_to_refresh: set[str] = set()

            for commit in commits:
                seq, repo, collection, rkey, action = (
                    int(commit[0] or 0), str(commit[1] or ""), str(commit[2] or ""),
                    str(commit[3] or ""), str(commit[4] or ""),
                )
                ts_ms = int(commit[10] or 0) if commit[10] else int(time.time() * 1000)
                vid = f"at://{repo}/{collection}/{rkey}"
                created_date = _dt.datetime.fromtimestamp(
                    ts_ms / 1000, tz=_dt.UTC
                ).strftime("%Y-%m-%d")

                if action == "delete":
                    explicit = _COLLECTION_TO_TABLE.get(collection)
                    tables = [explicit] if explicit else _convention_candidates(collection)
                    for tbl in tables:
                        try:
                            _res = client.q(f"DELETE FROM {tbl} WHERE vertex_id = %s", (vid,))
                            break
                        except Exception:
                            pass
                    if collection == "app.bsky.actor.profile":
                        try:
                            _res = client.q(
                                "DELETE FROM vertex_profile_fragment WHERE repo = %s", (repo,)
                            )
                        except Exception:
                            pass
                    continue

                # Parse record JSON (unwrap dispatch envelope if present)
                try:
                    rec: dict = json.loads(commit[9] or "{}")
                except (json.JSONDecodeError, TypeError):
                    print(f"[consumer] skip bad JSON rkey={rkey}")
                    continue
                if isinstance(rec, dict) and isinstance(rec.get("recordJson"), str):
                    try:
                        inner = json.loads(rec["recordJson"])
                        if isinstance(inner, dict):
                            rec = inner
                    except (json.JSONDecodeError, TypeError):
                        pass

                ctx = {
                    "repo": repo, "rkey": rkey, "vid": vid,
                    "seq": seq, "created_date": created_date,
                }

                # Typed handler first
                handled = _handle_collection(collection, rec, ctx)
                if handled is not None:
                    for tbl, r in handled:
                        by_table.setdefault(tbl, []).append(r)
                    if collection == "app.bsky.actor.profile":
                        profile_repos_to_refresh.add(repo)
                    continue

                # Convention fallback
                candidates = _convention_candidates(collection)
                if not candidates:
                    print(f"[consumer] skip unhandled collection={collection}")
                    continue

                conv_table: Optional[str] = None
                conv_cols: Optional[set[str]] = None
                for cand in candidates:
                    probe = _get_convention_cols(cur, cand)
                    if probe:
                        conv_table = cand
                        conv_cols = probe
                        break

                if not conv_table or not conv_cols:
                    print(
                        f"[consumer] convention table not found for collection={collection} "
                        f"(tried: {', '.join(candidates)})"
                    )
                    continue

                row = _build_convention_row(rec, ctx, conv_cols)

                if conv_table == "vertex_spatial" and "label" in conv_cols:
                    mm = re.match(r"^ai\.etzhayyim\.apps\.maps\.([^.]+)$", collection)
                    if mm:
                        row["label"] = _maps_entity_label(mm.group(1))
                elif re.match(r"^vertex_[^_]+$", conv_table):
                    # Single-table-with-collection pattern (mangaka/animeka)
                    if "collection" in conv_cols:
                        row["collection"] = collection
                    if "label" in conv_cols and "label" not in row:
                        row["label"] = collection.split(".")[-1]
                    if "kind" in conv_cols and "kind" not in row:
                        row["kind"] = collection.split(".")[-1]

                by_table.setdefault(conv_table, []).append(row)

            # 4. Delete stale profile fragments before re-inserting
            if profile_repos_to_refresh:
                repos = list(profile_repos_to_refresh)
                ph = ", ".join(["%s"] * len(repos))
                try:
                    _res = client.q(f"DELETE FROM vertex_profile_fragment WHERE repo IN ({ph})", repos)
                except Exception:
                    pass

            # 5. Batch INSERT per table; per-row fallback on error
            for table, rows in by_table.items():
                if not rows:
                    continue
                table_cols = _get_convention_cols(cur, table)
                rows, live_cols = _project_rows_for_insert(table, rows, table_cols)
                all_cols: set[str] = set()
                for r in rows:
                    all_cols.update(r.keys())
                if live_cols:
                    all_cols &= live_cols
                if not all_cols:
                    print(f"[consumer] {table}: no insertable columns, skipping")
                    continue
                col_list = list(all_cols)

                try:
                    params: list = []
                    val_rows: list[str] = []
                    for r in rows:
                        ph_parts = []
                        for c in col_list:
                            params.append(r.get(c))
                            ph_parts.append("%s")
                        val_rows.append(f"({', '.join(ph_parts)})")
                    col_sql = ", ".join(f'"{c}"' for c in col_list)
                    _res = client.q(
                        f"INSERT INTO {table} ({col_sql}) VALUES {', '.join(val_rows)}",
                        params,
                    )
                    print(f"[consumer] {table}: {len(rows)} rows (batch)")
                except Exception as batch_err:
                    print(
                        f"[consumer] {table}: batch INSERT failed, per-row fallback: {batch_err}"
                    )
                    inserted = 0
                    for r in rows:
                        r_cols = [c for c in r.keys() if not live_cols or c in live_cols]
                        if not r_cols:
                            continue
                        try:
                            col_sql = ", ".join(f'"{c}"' for c in r_cols)
                            ph = ", ".join(["%s"] * len(r_cols))
                            _res = client.q(
                                f"INSERT INTO {table} ({col_sql}) VALUES ({ph})",
                                [r.get(c) for c in r_cols],
                            )
                            inserted += 1
                        except Exception:
                            pass
                    print(f"[consumer] {table}: {inserted}/{len(rows)} rows (per-row fallback)")

            # 6. Persist cursor
            new_seq = int(commits[-1][0] or 0)
            _memory_cursor = new_seq
            try:
                _res = client.q(
                    "UPDATE vertex_consumer_cursor SET last_seq = %s WHERE consumer_id = 'graph-worker'",
                    (new_seq,),
                )
            except Exception:
                pass

            print(f"[consumer] processed={len(commits)} cursor={new_seq}")
            return {"ok": True, "processed": len(commits), "lastSeq": new_seq}

    except Exception as exc:
        return {"ok": False, "processed": 0, "lastSeq": _memory_cursor, "error": str(exc)[:500]}


# ── HTTP fallback (kept for optional CF Worker URL override) ──────────────────

def _http_post_json(url: str, payload: dict[str, Any], bearer: str = "") -> dict[str, Any]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "kotodama-graph-consumer/1",
    }
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw or "{}")
            except json.JSONDecodeError:
                parsed = {"raw": raw[:500]}
            return {"httpStatus": resp.status, "body": parsed}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")[:500]
        return {"httpStatus": e.code, "body": {"ok": False, "error": raw or e.reason}}
    except Exception as e:  # noqa: BLE001
        return {"httpStatus": 0, "body": {"ok": False, "error": f"transport: {e}"}}


def _call_graph_consumer_http(consumer_url: str, batch_size: int, bearer: str = "") -> dict[str, Any]:
    url = consumer_url.rstrip("/")
    result = _http_post_json(url, {"batchSize": batch_size}, bearer)
    body = result.get("body") if isinstance(result.get("body"), dict) else {}
    ok = bool(body.get("ok")) and int(result.get("httpStatus") or 0) < 400
    return {
        "ok": ok,
        "httpStatus": int(result.get("httpStatus") or 0),
        "processed": int(body.get("processed") or 0),
        "lastSeq": int(body.get("lastSeq") or 0),
        "error": "" if ok else str(body.get("error") or f"http {result.get('httpStatus')}")[:500],
    }


# ── Audit write ───────────────────────────────────────────────────────────────

def write_consume_tick(tick: dict[str, Any], *, flush: bool = True) -> dict[str, Any]:
    ts = str(tick.get("ts") or _utc_now_iso())
    rkey = "consume-tick-" + ts.replace("-", "").replace(":", "").replace(".", "")
    rkey = rkey.replace("T", "").replace("Z", "")
    uri = f"at://{GRAPH_DID}/{CONSUME_TICK_COLLECTION}/{rkey}"
    value = {"$type": CONSUME_TICK_COLLECTION, "v": 1, **tick}
    row = {
        "vertex_id": uri,
        "tick_id": rkey,
        "ok": bool(tick.get("ok")),
        "http_status": int(tick.get("httpStatus") or 0),
        "processed": int(tick.get("processed") or 0),
        "last_seq": int(tick.get("lastSeq") or 0),
        "error": str(tick.get("error") or "")[:4096],
        "value_json": json.dumps(value, separators=(",", ":"), ensure_ascii=False),
        "observed_at": ts,
        "created_at": ts,
        "owner_did": GRAPH_DID,
        "sensitivity_ord": 2,
    }
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_graph_consume_tick (
              vertex_id, tick_id, ok, http_status, processed, last_seq,
              error, value_json, observed_at, created_at, owner_did, sensitivity_ord
            )
            VALUES (
              %(vertex_id)s, %(tick_id)s, %(ok)s, %(http_status)s, %(processed)s, %(last_seq)s,
              %(error)s, %(value_json)s, %(observed_at)s, %(created_at)s, %(owner_did)s, %(sensitivity_ord)s
            )
            ON CONFLICT (vertex_id) DO UPDATE SET
              ok = EXCLUDED.ok,
              http_status = EXCLUDED.http_status,
              processed = EXCLUDED.processed,
              last_seq = EXCLUDED.last_seq,
              error = EXCLUDED.error,
              value_json = EXCLUDED.value_json,
              observed_at = EXCLUDED.observed_at
            """,
            row,
        )
    return {"uri": uri, "rkey": rkey}


# ── Zeebe task handler ────────────────────────────────────────────────────────

def task_graph_repo_consume_commits(
    consumerUrl: str = "",
    batchSize: int = 50,
    flush: bool = False,
) -> dict[str, Any]:
    url = consumerUrl or os.environ.get("GRAPH_CONSUMER_URL") or os.environ.get("GRAPH_WORKER_CONSUME_URL") or ""
    batch_size = max(1, min(int(batchSize or 50), 500))
    ts = _utc_now_iso()
    started = time.monotonic()

    if url:
        # Optional HTTP override (CF Worker URL set → delegate to it)
        bearer = os.environ.get("GRAPH_CONSUMER_BEARER") or ""
        result = _call_graph_consumer_http(url, batch_size, bearer)
        tick = {
            "ts": ts,
            "ok": result["ok"],
            "processed": result["processed"],
            "lastSeq": result["lastSeq"],
            "httpStatus": result["httpStatus"],
            "latencyMs": int((time.monotonic() - started) * 1000),
            "error": result["error"],
        }
    else:
        # Default: direct local consumer (no CF Worker needed)
        result = _consume_commits_local(batch_size)
        tick = {
            "ts": ts,
            "ok": result["ok"],
            "processed": result["processed"],
            "lastSeq": result["lastSeq"],
            "httpStatus": 0,
            "latencyMs": int((time.monotonic() - started) * 1000),
            "error": result.get("error", ""),
        }

    audit = write_consume_tick(tick, flush=flush)
    return {
        "ok": tick["ok"],
        "processed": tick["processed"],
        "lastSeq": tick["lastSeq"],
        "httpStatus": tick["httpStatus"],
        "error": tick.get("error", ""),
        "auditUri": audit["uri"],
    }


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="graph.repo.consumeCommits",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_graph_repo_consume_commits)
