"""Google Drive ingest Zeebe worker — changes.list cursor-based sync."""

from __future__ import annotations

import json
import os

import urllib.parse
import urllib.request
from typing import Any
from datetime import datetime, timezone

from kotodama.kotoba_datomic import get_kotoba_client


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _http_json(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, method=method, data=body, headers={"accept": "application/json", "user-agent": "etzhayyim-drive-zeebe/1", **(headers or {})})
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


def _file_row(token: dict[str, Any], f: dict[str, Any], is_removed: bool = False) -> dict[str, Any]:
    file_id = _str(f.get("id"))
    actor = ACTOR_DID
    now = now_iso()
    base_row = {
        "vertex_id": f"at://{actor}/com.etzhayyim.apps.drive.file/{file_id}",
        "_seq": int(datetime.now(timezone.utc).timestamp() * 1000),
        "created_date": now[:10],
        "sensitivity_ord": 100,
        "owner_did": actor,
        "rkey": file_id,
        "repo": actor,
        "file_id": file_id,
        "account_did": _str(token.get("account_did")),
        "created_at": now,
        "org_id": "anon",
        "user_id": _str(token.get("account_did")),
        "actor_id": "drive-mcp",
    }
    if is_removed:
        base_row.update({
            "name": "",
            "mime_type": "",
            "kind": "",
            "size_bytes": 0,
            "md5_checksum": "",
            "sha256_checksum": "",
            "description": "",
            "starred": "false",
            "trashed": "true",
            "explicitly_trashed": "true",
            "shared": "false",
            "owners_json": "[]",
            "parents_json": "[]",
            "spaces_json": "[]",
            "web_view_link": "",
            "web_content_link": "",
            "icon_link": "",
            "thumbnail_link": "",
            "original_filename": "",
            "file_extension": "",
            "full_file_extension": "",
            "head_revision_id": "",
            "version_num": 0,
            "view_count": 0,
            "capabilities_json": "{}",
            "export_links_json": "{}",
            "drive_id": "",
            "team_drive_id": "",
            "created_time": "",
            "modified_time": "",
            "viewed_by_me_time": "",
            "shared_with_me_time": "",
        })
    else:
        base_row.update({
            "name": _str(f.get("name")),
            "mime_type": _str(f.get("mimeType")),
            "kind": _str(f.get("kind")),
            "size_bytes": int(f.get("size") or 0),
            "md5_checksum": _str(f.get("md5Checksum")),
            "sha256_checksum": _str(f.get("sha256Checksum")),
            "description": _str(f.get("description")),
            "starred": "true" if f.get("starred") else "false",
            "trashed": "true" if f.get("trashed") else "false",
            "explicitly_trashed": "true" if f.get("explicitlyTrashed") else "false",
            "shared": "true" if f.get("shared") else "false",
            "owners_json": json.dumps(f.get("owners") or [], ensure_ascii=False),
            "parents_json": json.dumps(f.get("parents") or [], ensure_ascii=False),
            "spaces_json": json.dumps(f.get("spaces") or [], ensure_ascii=False),
            "web_view_link": _str(f.get("webViewLink")),
            "web_content_link": _str(f.get("webContentLink")),
            "icon_link": _str(f.get("iconLink")),
            "thumbnail_link": _str(f.get("thumbnailLink")),
            "original_filename": _str(f.get("originalFilename")),
            "file_extension": _str(f.get("fileExtension")),
            "full_file_extension": _str(f.get("fullFileExtension")),
            "head_revision_id": _str(f.get("headRevisionId")),
            "version_num": int(f.get("version") or 0),
            "view_count": int((f.get("fileViewerAccess") or {}).get("viewCount") or 0),
            "capabilities_json": json.dumps(f.get("capabilities") or {}, ensure_ascii=False),
            "export_links_json": json.dumps(f.get("exportLinks") or {}, ensure_ascii=False),
            "drive_id": _str(f.get("driveId")),
            "team_drive_id": _str(f.get("teamDriveId")),
            "created_time": _str(f.get("createdTime")),
            "modified_time": _str(f.get("modifiedTime")),
            "viewed_by_me_time": _str(f.get("viewedByMeTime")),
            "shared_with_me_time": _str(f.get("sharedWithMeTime")),
        })
    return base_row


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
        fields = "newStartPageToken,nextPageToken,changes(type,removed,fileId,file(id,name,mimeType,kind,size,md5Checksum,sha256Checksum,description,starred,trashed,explicitlyTrashed,shared,owners,parents,spaces,webViewLink,webContentLink,iconLink,thumbnailLink,originalFilename,fileExtension,fullFileExtension,headRevisionId,version,capabilities,exportLinks,driveId,teamDriveId,createdTime,modifiedTime,viewedByMeTime,sharedWithMeTime))"
        qs = urllib.parse.urlencode({"pageToken": page_token, "fields": fields, "pageSize": "1000", "includeItemsFromAllDrives": "true", "supportsAllDrives": "true"})
        data = _http_json(f"https://www.googleapis.com/drive/v3/changes?{qs}", headers={"authorization": f"Bearer {access}"})

        for change in data.get("changes", []):
            if change.get("type") != "file":
                continue
            f = change.get("file")
            if not f or not f.get("id"):
                continue
            if change.get("removed"):
                # Instead of DELETE, insert a row reflecting the removed status.
                _insert(DRIVE_FILE_TABLE, _file_row(token, f, is_removed=True))
            else:
                _insert(DRIVE_FILE_TABLE, _file_row(token, f))
            synced += 1

        new_cursor = _str(data.get("newStartPageToken") or data.get("nextPageToken") or page_token)
        page_token = _str(data.get("nextPageToken"))

    # Update the token in kotoba Datom log
    current_token_data = get_kotoba_client().select_first_where(
        DRIVE_TOKEN_TABLE, "vertex_id", _str(token.get("vertex_id"))
    )
    if current_token_data:
        current_token_data["last_sync_at"] = now_iso()
        current_token_data["cursor"] = new_cursor
        current_token_data["updated_at"] = now_iso()
        get_kotoba_client().insert_row(DRIVE_TOKEN_TABLE, current_token_data)
    return {"ok": True, "synced": synced, "cursor": new_cursor}


def sync_from_google(email: str = "", **_: Any) -> dict[str, Any]:
    if not email:
        return {"ok": False, "error": "email required"}
    # R0: status filter applied in Python
    token = get_kotoba_client().select_first_where(DRIVE_TOKEN_TABLE, "email", email, columns=["*"])
    if token and token.get("status") != "active":
        token = None
    if not token:
        return {"ok": False, "error": "No active Drive account. connectAccount first."}
    return _sync_token(token)


def cron_tick(**_: Any) -> dict[str, Any]:
    # R0: ORDER BY and LIMIT applied in Python
    rows = get_kotoba_client().select_where(DRIVE_TOKEN_TABLE, "status", "active", columns=["*"], limit=100) # Fetch more than needed
    rows.sort(key=lambda x: x.get("last_sync_at") or x.get("created_at") or "", reverse=False)
    rows = rows[:10]
    synced = 0
    errors = 0
    for token in rows:
        result = _sync_token(token)
        synced += int(result.get("synced") or 0)
        errors += 0 if result.get("ok") else 1
    return {"ok": errors == 0, "accounts": len(rows), "synced": synced, "errors": errors}
