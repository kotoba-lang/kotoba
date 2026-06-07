"""Google Tasks ingest Zeebe worker — per-list tasks.list with updatedMin cursor."""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

TASKS_TOKEN_TABLE = "vertex_gtasks_oauth_token"
TASKS_LIST_TABLE = "vertex_gtasks_list"
TASKS_TASK_TABLE = "vertex_gtasks_task"
ACTOR_DID = "did:web:tasks.etzhayyim.com"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _str(v: Any) -> str:
    return "" if v is None else str(v)











def _http_json(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, method=method, data=body, headers={"accept": "application/json", "user-agent": "etzhayyim-tasks-zeebe/1", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))





def _refresh_access_token(refresh_token: str) -> str:
    client_id = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_SECRET", "")
    body = urllib.parse.urlencode({"refresh_token": refresh_token, "client_id": client_id, "client_secret": client_secret, "grant_type": "refresh_token"}).encode()
    data = _http_json("https://oauth2.googleapis.com/token", method="POST", headers={"content-type": "application/x-www-form-urlencoded"}, body=body)
    return _str(data.get("access_token"))


def _list_row(token: dict[str, Any], lst: dict[str, Any]) -> dict[str, Any]:
    list_id = _str(lst.get("id"))
    actor = ACTOR_DID
    now = now_iso()
    return {
        "vertex_id": f"at://{actor}/com.etzhayyim.apps.tasks.list/{list_id}",
        "_seq": int(time.time() * 1000),
        "created_date": now[:10],
        "sensitivity_ord": 100,
        "owner_did": actor,
        "rkey": list_id,
        "repo": actor,
        "list_id": list_id,
        "account_did": _str(token.get("account_did")),
        "title": _str(lst.get("title")),
        "etag": _str(lst.get("etag")),
        "self_link": _str(lst.get("selfLink")),
        "updated_time": _str(lst.get("updated")),
        "created_at": now,
        "org_id": "anon",
        "user_id": _str(token.get("account_did")),
        "actor_id": "tasks-mcp",
    }


def _task_row(token: dict[str, Any], list_id: str, t: dict[str, Any]) -> dict[str, Any]:
    task_id = _str(t.get("id"))
    actor = ACTOR_DID
    now = now_iso()
    return {
        "vertex_id": f"at://{actor}/com.etzhayyim.apps.tasks.task/{list_id}_{task_id}",
        "_seq": int(time.time() * 1000),
        "created_date": now[:10],
        "sensitivity_ord": 100,
        "owner_did": actor,
        "rkey": f"{list_id}_{task_id}",
        "repo": actor,
        "task_id": task_id,
        "list_id": list_id,
        "account_did": _str(token.get("account_did")),
        "title": _str(t.get("title")),
        "notes": _str(t.get("notes")),
        "status": _str(t.get("status")),
        "due_time": _str(t.get("due")),
        "completed_time": _str(t.get("completed")),
        "parent_task_id": _str(t.get("parent")),
        "position": _str(t.get("position")),
        "etag": _str(t.get("etag")),
        "self_link": _str(t.get("selfLink")),
        "web_view_link": _str(t.get("webViewLink")),
        "hidden": "true" if t.get("hidden") else "false",
        "deleted": "true" if t.get("deleted") else "false",
        "links_json": json.dumps(t.get("links") or [], ensure_ascii=False),
        "updated_time": _str(t.get("updated")),
        "created_at": now,
        "org_id": "anon",
        "user_id": _str(token.get("account_did")),
        "actor_id": "tasks-mcp",
    }


def _sync_token(token: dict[str, Any]) -> dict[str, Any]:
    access = _refresh_access_token(_str(token.get("encrypted_refresh_token")))
    if not access:
        return {"ok": False, "error": "access token refresh failed"}

    # cursor stores the last-synced updatedMin timestamp
    updated_min = _str(token.get("cursor"))
    synced = 0

    # Fetch all task lists
    lists_data = _http_json("https://tasks.googleapis.com/tasks/v1/users/@me/lists?maxResults=100", headers={"authorization": f"Bearer {access}"})
    for lst in lists_data.get("items") or []:
        list_id = _str(lst.get("id"))
        if not list_id:
            continue
        get_kotoba_client().insert_row(TASKS_LIST_TABLE, _list_row(token, lst))

        # Fetch tasks in this list
        page_token = ""
        while True:
            params: dict[str, str] = {"maxResults": "100", "showCompleted": "true", "showDeleted": "true", "showHidden": "true"}
            if updated_min:
                params["updatedMin"] = updated_min
            if page_token:
                params["pageToken"] = page_token
            qs = urllib.parse.urlencode(params)
            tasks_data = _http_json(f"https://tasks.googleapis.com/tasks/v1/lists/{list_id}/tasks?{qs}", headers={"authorization": f"Bearer {access}"})
            for t in tasks_data.get("items") or []:
                if t.get("deleted"):
                    vid = f"at://{ACTOR_DID}/com.etzhayyim.apps.tasks.task/{list_id}_{t.get('id')}"
                    # R0: DELETE requires q() Datom log retract.
                    get_kotoba_client().q(f'[:db/retractEntity ["vertex.gtasks-task/id" "{vid}"]]')
                else:
                    get_kotoba_client().insert_row(TASKS_TASK_TABLE, _task_row(token, list_id, t))
                synced += 1
            page_token = _str(tasks_data.get("nextPageToken"))
            if not page_token:
                break

    new_cursor = now_iso()
    client = get_kotoba_client()
    client.insert_row(
        TASKS_TOKEN_TABLE,
        {
            "vertex_id": _str(token.get("vertex_id")),
            "last_sync_at": now_iso(),
            "cursor": new_cursor,
            "updated_at": now_iso(),
        },
    )
    return {"ok": True, "synced": synced, "cursor": new_cursor}


def sync_from_google(email: str = "", **_: Any) -> dict[str, Any]:
    if not email:
        return {"ok": False, "error": "email required"}
    # R0: Multi-predicate select with LIMIT 1 requires q() escape hatch.
    results = get_kotoba_client().q(
        f'[:find (pull ?e [*]) :where [?e :vertex.gtasks-oauth-token/email "{email}"] [?e :vertex.gtasks-oauth-token/status "active"]]',
        graph=TASKS_TOKEN_TABLE,
    )
    token = results[0][0] if results else None
    if not token:
        return {"ok": False, "error": "No active Tasks account. connectAccount first."}
    return _sync_token(token)


def cron_tick(**_: Any) -> dict[str, Any]:
    # R0: ORDER BY COALESCE requires in-Python sorting.
    rows = get_kotoba_client().select_where(TASKS_TOKEN_TABLE, "status", "active")
    # Sort in Python
    rows.sort(key=lambda x: x.get("last_sync_at") or x.get("created_at") or "")
    rows = rows[:10]
    synced = 0
    errors = 0
    for token in rows:
        result = _sync_token(token)
        synced += int(result.get("synced") or 0)
        errors += 0 if result.get("ok") else 1
    return {"ok": errors == 0, "accounts": len(rows), "synced": synced, "errors": errors}
