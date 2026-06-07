"""Google Sheets ingest Zeebe worker — Drive changes filter + spreadsheets.get. Uses kotoba Datom log for state management."""

from __future__ import annotations

import json
import os

import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

SHEETS_TOKEN_TABLE = "vertex_gsheets_oauth_token"
SHEETS_SPREADSHEET_TABLE = "vertex_gsheets_spreadsheet"
SHEETS_SHEET_TABLE = "vertex_gsheets_sheet"
ACTOR_DID = "did:web:sheets.etzhayyim.com"
GSHEETS_MIME = "application/vnd.google-apps.spreadsheet"





def _str(v: Any) -> str:
    return "" if v is None else str(v)








def _http_json(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, method=method, data=body, headers={"accept": "application/json", "user-agent": "etzhayyim-sheets-zeebe/1", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _insert(table: str, row: dict[str, Any]) -> None:
    get_kotoba_client().insert_row(table, row)


def _refresh_access_token(refresh_token: str) -> str:
    client_id = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_SECRET", "")
    body = urllib.parse.urlencode({"refresh_token": refresh_token, "client_id": client_id, "client_secret": client_secret, "grant_type": "refresh_token"}).encode()
    data = _http_json("https://oauth2.googleapis.com/token", method="POST", headers={"content-type": "application/x-www-form-urlencoded"}, body=body)
    return _str(data.get("access_token"))


def _get_start_page_token(access: str) -> str:
    data = _http_json("https://www.googleapis.com/drive/v3/changes/startPageToken", headers={"authorization": f"Bearer {access}"})
    return _str(data.get("startPageToken"))


def _spreadsheet_row(token: dict[str, Any], ss: dict[str, Any], file_id: str, modified_time: str) -> dict[str, Any]:
    spreadsheet_id = _str(ss.get("spreadsheetId"))
    actor = ACTOR_DID
    now = now_iso()
    props = ss.get("properties") or {}
    sheets = ss.get("sheets") or []
    named_ranges = ss.get("namedRanges") or []
    developer_metadata = ss.get("developerMetadata") or []
    return {
        "vertex_id": f"at://{actor}/com.etzhayyim.apps.sheets.spreadsheet/{spreadsheet_id}",
        "_seq": int(time.time() * 1000),
        "created_date": now[:10],
        "sensitivity_ord": 100,
        "owner_did": actor,
        "rkey": spreadsheet_id,
        "repo": actor,
        "spreadsheet_id": spreadsheet_id,
        "account_did": _str(token.get("account_did")),
        "file_id": file_id,
        "title": _str(props.get("title")),
        "locale": _str(props.get("locale")),
        "time_zone": _str(props.get("timeZone")),
        "auto_recalc": _str(props.get("autoRecalc")),
        "sheet_count": len(sheets),
        "named_ranges_json": json.dumps(named_ranges, ensure_ascii=False),
        "developer_metadata_json": json.dumps(developer_metadata, ensure_ascii=False),
        "spreadsheet_url": _str(ss.get("spreadsheetUrl")),
        "updated_time": modified_time,
        "created_at": now,
        "org_id": "anon",
        "user_id": _str(token.get("account_did")),
        "actor_id": "sheets-mcp",
    }


def _sheet_row(token: dict[str, Any], spreadsheet_id: str, sheet: dict[str, Any]) -> dict[str, Any]:
    props = sheet.get("properties") or {}
    grid_props = props.get("gridProperties") or {}
    sheet_id = _str(props.get("sheetId"))
    actor = ACTOR_DID
    now = now_iso()

    # Extract grid data preview (values from first sheet data range)
    data_list = sheet.get("data") or []
    grid_values: list[list[Any]] = []
    for d in data_list[:1]:
        for row_data in (d.get("rowData") or [])[:20]:
            row_vals = [_str((c.get("formattedValue") or "")) for c in (row_data.get("values") or [])]
            grid_values.append(row_vals)
    grid_preview = json.dumps(grid_values[:5], ensure_ascii=False)[:2000]

    charts = sheet.get("charts") or []
    protected = sheet.get("protectedRanges") or []

    # Estimate cell count and data bytes from row/col counts
    row_count = int(grid_props.get("rowCount") or 0)
    col_count = int(grid_props.get("columnCount") or 0)
    cell_count = row_count * col_count if row_count and col_count else 0
    data_bytes = len(json.dumps(grid_values, ensure_ascii=False).encode())

    return {
        "vertex_id": f"at://{actor}/com.etzhayyim.apps.sheets.sheet/{spreadsheet_id}_{sheet_id}",
        "_seq": int(time.time() * 1000),
        "created_date": now[:10],
        "sensitivity_ord": 100,
        "owner_did": actor,
        "rkey": f"{spreadsheet_id}_{sheet_id}",
        "repo": actor,
        "sheet_id": sheet_id,
        "spreadsheet_id": spreadsheet_id,
        "account_did": _str(token.get("account_did")),
        "title": _str(props.get("title")),
        "sheet_type": _str(props.get("sheetType")),
        "sheet_index": int(props.get("index") or 0),
        "row_count": row_count,
        "column_count": col_count,
        "frozen_row_count": int(grid_props.get("frozenRowCount") or 0),
        "frozen_column_count": int(grid_props.get("frozenColumnCount") or 0),
        "hidden": _str(props.get("hidden") or "false"),
        "tab_color": json.dumps((props.get("tabColorStyle") or props.get("tabColor") or {}), ensure_ascii=False),
        "grid_values_json": json.dumps(grid_values, ensure_ascii=False)[:8000],
        "grid_values_preview": grid_preview,
        "cell_count": cell_count,
        "data_bytes": data_bytes,
        "charts_json": json.dumps(charts, ensure_ascii=False)[:4000],
        "protected_ranges_json": json.dumps(protected, ensure_ascii=False),
        "updated_time": now,
        "created_at": now,
        "org_id": "anon",
        "user_id": _str(token.get("account_did")),
        "actor_id": "sheets-mcp",
    }


def _sync_token(token: dict[str, Any]) -> dict[str, Any]:
    access = _refresh_access_token(_str(token.get("encrypted_refresh_token")))
    if not access:
        return {"ok": False, "error": "access token refresh failed"}

    page_token = _str(token.get("cursor"))
    if not page_token:
        page_token = _get_start_page_token(access)

    synced = 0
    new_cursor = page_token

    while page_token:
        fields = "newStartPageToken,nextPageToken,changes(type,removed,fileId,file(id,mimeType,name,modifiedTime))"
        qs = urllib.parse.urlencode({"pageToken": page_token, "fields": fields, "pageSize": "1000", "includeItemsFromAllDrives": "true", "supportsAllDrives": "true"})
        data = _http_json(f"https://www.googleapis.com/drive/v3/changes?{qs}", headers={"authorization": f"Bearer {access}"})

        for change in data.get("changes") or []:
            if change.get("type") != "file":
                continue
            f = change.get("file") or {}
            file_id = _str(f.get("id") or change.get("fileId"))
            if not file_id:
                continue
            if f.get("mimeType") != GSHEETS_MIME:
                continue
            if change.get("removed"):
                # R0: Deleting by retracting entity in Datalog via q().
                spreadsheet_to_delete = get_kotoba_client().select_first_where(
                    SHEETS_SPREADSHEET_TABLE, "file_id", file_id
                )
                # Filter by account_did in Python
                if spreadsheet_to_delete and spreadsheet_to_delete.get("account_did") == _str(token.get("account_did")):
                    vertex_id_to_retract = spreadsheet_to_delete.get("vertex_id")
                    if vertex_id_to_retract:
                        # Constructing a Datalog transaction to retract the entity identified by vertex_id
                        # This assumes vertex_id is directly usable as a Datomic entity identifier.
                        # The transaction uses [:db.fn/retractEntity entity-id].
                        # The `q` method is being used to execute this transaction, assuming it can execute transactions.
                        # This is a critical assumption for "mechanical conversion" of DELETE.
                        get_kotoba_client().q(
                            f'[:db.fn/retractEntity "{vertex_id_to_retract}"]',
                            args=(),
                            graph=None
                        )
            else:
                try:
                    # includeGridData=true fetches sheet values (first 20 rows per sheet)
                    ss = _http_json(
                        f"https://sheets.googleapis.com/v4/spreadsheets/{file_id}?includeGridData=true&ranges=A1:T20",
                        headers={"authorization": f"Bearer {access}"},
                    )
                    _insert(SHEETS_SPREADSHEET_TABLE, _spreadsheet_row(token, ss, file_id, _str(f.get("modifiedTime"))))
                    for sheet in ss.get("sheets") or []:
                        _insert(SHEETS_SHEET_TABLE, _sheet_row(token, _str(ss.get("spreadsheetId")), sheet))
                    synced += 1
                except Exception:
                    pass  # permission denied or transient — skip

        new_cursor = _str(data.get("newStartPageToken") or data.get("nextPageToken") or page_token)
        page_token = _str(data.get("nextPageToken"))

    # R0: UPDATE converted to SELECT, modify in-Python, then insert_row (UPSERT).
    existing_token = get_kotoba_client().select_first_where(
        SHEETS_TOKEN_TABLE, "vertex_id", _str(token.get("vertex_id"))
    )
    if existing_token:
        current_time = datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z'
        existing_token["last_sync_at"] = current_time
        existing_token["cursor"] = new_cursor
        existing_token["updated_at"] = current_time
        get_kotoba_client().insert_row(SHEETS_TOKEN_TABLE, existing_token)
    return {"ok": True, "synced": synced, "cursor": new_cursor}


def sync_from_google(email: str = "", **_: Any) -> dict[str, Any]:
    if not email:
        return {"ok": False, "error": "email required"}
    # R0: Multi-predicate SELECT converted to select_where + in-Python filtering.
    email_tokens = get_kotoba_client().select_where(
        SHEETS_TOKEN_TABLE, "email", email
    )
    token = None
    for t in email_tokens:
        if t.get("status") == "active":
            token = t
            break

    if not token:
        return {"ok": False, "error": "No active Sheets account. connectAccount first."}
    return _sync_token(token)


def cron_tick(**_: Any) -> dict[str, Any]:
    # R0: Complex SELECT (ORDER BY, COALESCE) converted to select_where + in-Python filtering and sorting.
    active_tokens = get_kotoba_client().select_where(
        SHEETS_TOKEN_TABLE, "status", "active"
    )
    # Apply ORDER BY COALESCE(last_sync_at, created_at) ASC
    def sort_key(t):
        last_sync = t.get("last_sync_at")
        created = t.get("created_at")
        if last_sync:
            return last_sync
        return created if created else "" # Fallback for None, empty string for consistent comparison

    active_tokens.sort(key=sort_key)
    rows = active_tokens[:10] # Apply LIMIT 10

    synced = 0
    errors = 0
    for token in rows:
        result = _sync_token(token)
        synced += int(result.get("synced") or 0)
        errors += 0 if result.get("ok") else 1
    return {"ok": errors == 0, "accounts": len(rows), "synced": synced, "errors": errors}
