"""Google Contacts ingest Zeebe worker — People API syncToken cursor."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

CONTACTS_TOKEN_TABLE = "vertex_gcontacts_oauth_token"
CONTACTS_TABLE = "vertex_gcontacts_contact"
ACTOR_DID = "did:web:contacts.etzhayyim.com"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _str(v: Any) -> str:
    return "" if v is None else str(v)


def _http_json(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, method=method, data=body, headers={"accept": "application/json", "user-agent": "etzhayyim-contacts-zeebe/1", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))




def _refresh_access_token(refresh_token: str) -> str:
    client_id = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_SECRET", "")
    body = urllib.parse.urlencode({"refresh_token": refresh_token, "client_id": client_id, "client_secret": client_secret, "grant_type": "refresh_token"}).encode()
    data = _http_json("https://oauth2.googleapis.com/token", method="POST", headers={"content-type": "application/x-www-form-urlencoded"}, body=body)
    return _str(data.get("access_token"))


def _name_field(names: list[dict]) -> tuple[str, str, str, str, str, str]:
    n = names[0] if names else {}
    return (
        _str(n.get("displayName")),
        _str(n.get("givenName")),
        _str(n.get("familyName")),
        _str(n.get("middleName")),
        _str(n.get("honorificPrefix")),
        _str(n.get("honorificSuffix")),
    )


def _contact_row(token: dict[str, Any], p: dict[str, Any]) -> dict[str, Any]:
    resource_name = _str(p.get("resourceName"))
    rkey = resource_name.replace("/", "_")
    actor = ACTOR_DID
    now = now_iso()
    names = p.get("names") or []
    display_name, given_name, family_name, middle_name, honorific_prefix, honorific_suffix = _name_field(names)
    nicknames = p.get("nicknames") or []
    metadata = p.get("metadata") or {}
    updated_time = _str((metadata.get("sources") or [{}])[0].get("updateTime"))
    return {
        "vertex_id": f"at://{actor}/com.etzhayyim.apps.contacts.contact/{rkey}",
        "_seq": int(datetime.now(timezone.utc).timestamp() * 1000),
        "created_date": now[:10],
        "sensitivity_ord": 100,
        "owner_did": actor,
        "rkey": rkey,
        "repo": actor,
        "resource_name": resource_name,
        "account_did": _str(token.get("account_did")),
        "etag": _str(p.get("etag")),
        "display_name": display_name,
        "given_name": given_name,
        "family_name": family_name,
        "middle_name": middle_name,
        "honorific_prefix": honorific_prefix,
        "honorific_suffix": honorific_suffix,
        "nickname": _str(nicknames[0].get("value") if nicknames else ""),
        "emails_json": json.dumps(p.get("emailAddresses") or [], ensure_ascii=False),
        "phones_json": json.dumps(p.get("phoneNumbers") or [], ensure_ascii=False),
        "addresses_json": json.dumps(p.get("addresses") or [], ensure_ascii=False),
        "organizations_json": json.dumps(p.get("organizations") or [], ensure_ascii=False),
        "biographies_json": json.dumps(p.get("biographies") or [], ensure_ascii=False),
        "birthdays_json": json.dumps(p.get("birthdays") or [], ensure_ascii=False),
        "urls_json": json.dumps(p.get("urls") or [], ensure_ascii=False),
        "photos_json": json.dumps(p.get("photos") or [], ensure_ascii=False),
        "memberships_json": json.dumps(p.get("memberships") or [], ensure_ascii=False),
        "user_defined_json": json.dumps(p.get("userDefined") or [], ensure_ascii=False),
        "metadata_json": json.dumps(metadata, ensure_ascii=False),
        "updated_time": updated_time,
        "created_at": now,
        "org_id": "anon",
        "user_id": _str(token.get("account_did")),
        "actor_id": "contacts-mcp",
    }


def _sync_token(token: dict[str, Any]) -> dict[str, Any]:
    access = _refresh_access_token(_str(token.get("encrypted_refresh_token")))
    if not access:
        return {"ok": False, "error": "access token refresh failed"}

    sync_token = _str(token.get("cursor"))
    person_fields = "names,emailAddresses,phoneNumbers,addresses,organizations,biographies,birthdays,urls,photos,memberships,userDefined,metadata,nicknames"
    synced = 0
    new_cursor = sync_token

    page_token = ""
    while True:
        params: dict[str, str] = {"personFields": person_fields, "pageSize": "1000"}
        if sync_token:
            params["syncToken"] = sync_token
        if page_token:
            params["pageToken"] = page_token
        qs = urllib.parse.urlencode(params)
        try:
            data = _http_json(f"https://people.googleapis.com/v1/people/me/connections?{qs}", headers={"authorization": f"Bearer {access}"})
        except Exception as exc:
            # 410 Gone means syncToken expired — fall back to full sync
            if "410" in str(exc):
                sync_token = ""
                page_token = ""
                continue
            raise

        for p in data.get("connections") or []:
            if p.get("metadata", {}).get("deleted"):
                rkey = _str(p.get("resourceName")).replace("/", "_")
                vid = f"at://{ACTOR_DID}/com.etzhayyim.apps.contacts.contact/{rkey}"
                # R0: Deleting contact entity via Datalog transaction
                db_id_result = get_kotoba_client().q(f'[:find ?dbid . :where [?dbid :vertex/vertex_id "{vid}"]]')
                if db_id_result:
                    db_id = db_id_result[0][0]
                    get_kotoba_client().q(f'[:db/retractEntity {db_id}]')
            else:
                get_kotoba_client().insert_row(CONTACTS_TABLE, _contact_row(token, p))
            synced += 1

        new_cursor = _str(data.get("nextSyncToken") or new_cursor)
        page_token = _str(data.get("nextPageToken"))
        if not page_token:
            break

    # Upserting contact token status
    update_row_dict = {
        "vertex_id": _str(token.get("vertex_id")),
        "last_sync_at": now_iso(),
        "cursor": new_cursor,
        "updated_at": now_iso(),
    }
    get_kotoba_client().insert_row(CONTACTS_TOKEN_TABLE, update_row_dict)
    return {"ok": True, "synced": synced, "cursor": new_cursor}


def sync_from_google(email: str = "", **_: Any) -> dict[str, Any]:
    if not email:
        return {"ok": False, "error": "email required"}
    # R0: Filtering by status in Python
    all_tokens_by_email = get_kotoba_client().select_where(CONTACTS_TOKEN_TABLE, "email", email)
    token = next((t for t in all_tokens_by_email if t.get("status") == "active"), None)
    if not token:
        return {"ok": False, "error": "No active Contacts account. connectAccount first."}
    return _sync_token(token)


def cron_tick(**_: Any) -> dict[str, Any]:
    # R0: Filtering, ordering, and limiting in Python
    all_active_tokens = get_kotoba_client().select_where(CONTACTS_TOKEN_TABLE, "status", "active")
    # Sort by COALESCE(last_sync_at, created_at) ASC
    def sort_key(t):
        last_sync = t.get("last_sync_at")
        created = t.get("created_at")
        if last_sync:
            return datetime.strptime(last_sync, "%Y-%m-%dT%H:%M:%SZ")
        elif created:
            return datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ")
        return datetime.min # fallback for missing dates

    sorted_tokens = sorted(all_active_tokens, key=sort_key)
    rows = sorted_tokens[:10]
    synced = 0
    errors = 0
    for token in rows:
        result = _sync_token(token)
        synced += int(result.get("synced") or 0)
        errors += 0 if result.get("ok") else 1
    return {"ok": errors == 0, "accounts": len(rows), "synced": synced, "errors": errors}
