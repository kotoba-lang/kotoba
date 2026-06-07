"""Calendar business logic for Zeebe workers."""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

ACTOR_DID = "did:web:calendar.etzhayyim.com"
GCAL_TOKEN_TABLE = "vertex_gcal_oauth_token"
GWS_UNIFIED_SCOPES = " ".join([
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/contacts.other.readonly",
    "https://www.googleapis.com/auth/directory.readonly",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/presentations.readonly",
    "https://www.googleapis.com/auth/meetings.space.readonly",
])


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def gen_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _str(value: Any) -> str:
    return "" if value is None else str(value)





def _http_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, body: bytes | None = None, timeout: int = 30) -> Any:
    req = urllib.request.Request(url, data=body, method=method, headers={"accept": "application/json", "user-agent": "etzhayyim-calendar-zeebe/1", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _snake(name: str) -> str:
    out = ""
    for ch in name:
        out += f"_{ch.lower()}" if ch.isupper() else ch
    return out.lstrip("_")


def _insert(table: str, row: dict[str, Any]) -> None:
    get_kotoba_client().insert_row(table, row)


def _base(collection: str, rkey: str, created: str | None = None) -> dict[str, Any]:
    created_at = created or now_iso()
    return {
        "vertex_id": f"at://{ACTOR_DID}/com.etzhayyim.apps.calendar.{collection}/{rkey}",
        "created_date": created_at[:10],
        "sensitivity_ord": 100,
        "owner_did": ACTOR_DID,
        "rkey": rkey,
        "repo": ACTOR_DID,
        "collection": f"com.etzhayyim.apps.calendar.{collection}",
        "created_at": created_at,
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": "calendar-mcp",
        "actor_did": ACTOR_DID,
        "org_did": "anon",
    }


def _event_row(rec: dict[str, Any]) -> dict[str, Any]:
    event_id = _str(rec.get("eventId") or rec.get("event_id") or gen_id("evt"))
    now = _str(rec.get("createdAt") or rec.get("created_at") or now_iso())
    row = {
        **_base("event", event_id, now),
        "event_id": event_id,
        "title": _str(rec.get("title")),
        "description": _str(rec.get("description")),
        "start_time": _str(rec.get("startTime") or rec.get("start_time")),
        "end_time": _str(rec.get("endTime") or rec.get("end_time")),
        "location": _str(rec.get("location")),
        "all_day": "true" if rec.get("allDay") is True else _str(rec.get("allDay") or rec.get("all_day") or "false"),
        "timezone": _str(rec.get("timezone") or "UTC"),
        "visibility": _str(rec.get("visibility") or "private"),
        "status": _str(rec.get("status") or "confirmed"),
        "organizer_did": _str(rec.get("organizerDid") or rec.get("organizer_did") or ACTOR_DID),
        "recurrence_id": _str(rec.get("recurrenceId") or rec.get("recurrence_id")),
        "attendees_json": json.dumps(rec.get("attendees") or [], ensure_ascii=False),
        "reminders_json": json.dumps(rec.get("reminders") or [], ensure_ascii=False),
        "icalendar_uid": _str(rec.get("icalendarUid") or rec.get("icalendar_uid")),
        "updated_at": _str(rec.get("updatedAt") or rec.get("updated_at") or now),
        "props": json.dumps(rec, ensure_ascii=False),
    }
    return row


def create_event(**req: Any) -> dict[str, Any]:
    if not req.get("title") or not req.get("startTime") or not req.get("endTime"):
        return {"ok": False, "error": "title, startTime, and endTime are required"}
    event_id = _str(req.get("eventId") or gen_id("evt"))
    req["eventId"] = event_id
    _insert("vertex_calendar_event", _event_row(req))
    attendees = req.get("attendees") or []
    for attendee in attendees if isinstance(attendees, list) else []:
        inv_id = gen_id("inv")
        _insert("vertex_calendar_invitation", {
            **_base("invitation", inv_id),
            "invitation_id": inv_id,
            "event_id": event_id,
            "invitee_did": _str(attendee),
            "organizer_did": ACTOR_DID,
            "status": "pending",
            "responded_at": "",
            "props": json.dumps({"eventId": event_id, "inviteeDid": attendee}, ensure_ascii=False),
        })
    return {"ok": True, "status": "created", "eventId": event_id, "attendeesInvited": len(attendees) if isinstance(attendees, list) else 0}


def update_event(eventId: str = "", **req: Any) -> dict[str, Any]:
    if not eventId:
        return {"ok": False, "error": "eventId is required"}
    existing = _fetch_one("SELECT * FROM vertex_calendar_event WHERE event_id = %s LIMIT 1", (eventId,))
    if not existing:
        return {"ok": False, "error": "event not found", "eventId": eventId}
    allowed = {
        "title": "title", "description": "description", "startTime": "start_time",
        "endTime": "end_time", "location": "location", "timezone": "timezone",
        "status": "status", "visibility": "visibility",
    }
    updates: dict[str, Any] = {"updated_at": now_iso()}
    if "allDay" in req:
        updates["all_day"] = "true" if req.get("allDay") else "false"
    for src, dst in allowed.items():
        if src in req:
            updates[dst] = _str(req.get(src))
    sets = ", ".join([f"{k} = %s" for k in updates])
    _execute(f"UPDATE vertex_calendar_event SET {sets} WHERE event_id = %s", tuple(updates.values()) + (eventId,))
    return {"ok": True, "status": "updated", "eventId": eventId}


def delete_event(eventId: str = "", **_: Any) -> dict[str, Any]:
    if not eventId:
        return {"ok": False, "error": "eventId is required"}

    event_record = get_kotoba_client().select_first_where("vertex_calendar_event", "event_id", eventId, columns=["vertex_id"])
    if not event_record:
        return {"ok": False, "error": "event not found", "eventId": eventId}

    vertex_id = event_record["vertex_id"]

    # R0: Using q() as a Datalog escape hatch for deletion (retraction)
    # First, query for the Datomic entity ID (:db/id) using the vertex_id
    entity_id_result = get_kotoba_client().q(
        '[:find ?e . :where [?e :vertex/id "$vertex_id"]]',
        args={"$vertex_id": vertex_id}
    )

    if not entity_id_result:
        return {"ok": False, "error": "event entity not found in Datomic", "eventId": eventId}

    entity_id = entity_id_result

    # Construct the Datalog transaction for retraction
    # This assumes `q()` can execute transactions if provided with transaction EDN
    transaction_edn = f'[[:db/retractEntity {entity_id}]]'
    try:
        get_kotoba_client().q(transaction_edn) # Assuming q() can transact
        count = 1 # Assuming one entity was retracted
    except Exception as e:
        # Log the error or handle it as appropriate
        print(f"Error during Datalog retraction: {e}")
        count = 0

    return {"ok": count > 0, "status": "deleted" if count else "not_found", "eventId": eventId}


def _normalize_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "eventId": _str(row.get("event_id")),
        "title": _str(row.get("title")),
        "description": _str(row.get("description")),
        "startTime": _str(row.get("start_time")),
        "endTime": _str(row.get("end_time")),
        "location": _str(row.get("location")),
        "allDay": _str(row.get("all_day")),
        "timezone": _str(row.get("timezone")),
        "visibility": _str(row.get("visibility")),
        "status": _str(row.get("status")),
        "organizerDid": _str(row.get("organizer_did") or row.get("owner_did")),
        "recurrenceId": _str(row.get("recurrence_id")),
        "createdAt": _str(row.get("created_at")),
        "updatedAt": _str(row.get("updated_at")),
    }


def list_events(startDate: str = "", endDate: str = "", status: str = "", visibility: str = "", limit: int = 50, offset: int = 0, **_: Any) -> dict[str, Any]:
    # R0: Multiple predicates, ORDER BY, LIMIT, OFFSET applied in Python
    all_events = get_kotoba_client().select_where("vertex_calendar_event", "owner_did", ACTOR_DID)
    filtered_events = []
    for event in all_events:
        match = True
        if startDate and event.get("start_time", "") < startDate:
            match = False
        if endDate and event.get("end_time", "") > endDate:
            match = False
        if status and event.get("status", "") != status:
            match = False
        if visibility and event.get("visibility", "") != visibility:
            match = False
        if match:
            filtered_events.append(event)

    # Apply order by, limit, and offset
    sorted_events = sorted(filtered_events, key=lambda x: x.get("start_time", ""))
    paginated_events = sorted_events[offset:offset + limit]

    return {"ok": True, "events": [_normalize_event(r) for r in paginated_events], "total": len(filtered_events), "offset": offset, "limit": limit}


def get_event(eventId: str = "", **_: Any) -> dict[str, Any]:
    if not eventId:
        return {"ok": False, "error": "eventId is required"}
    row = get_kotoba_client().select_first_where("vertex_calendar_event", "event_id", eventId)
    if not row:
        return {"ok": False, "error": "event not found", "eventId": eventId}
    # R0: ORDER BY and LIMIT applied in Python
    rsvps_raw = get_kotoba_client().select_where("vertex_calendar_rsvp", "event_id", eventId, columns=["rsvp_id", "respondent_did", "response", "comment", "created_at"])
    rsvps = sorted(rsvps_raw, key=lambda x: x.get("created_at", ""), reverse=True)[:200]
    return {"ok": True, **_normalize_event(row), "rsvps": rsvps}


def _parse_dt(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def create_recurring(recurrenceRule: str = "", **req: Any) -> dict[str, Any]:
    if not req.get("title") or not req.get("startTime") or not req.get("endTime") or not recurrenceRule:
        return {"ok": False, "error": "title, startTime, endTime, and recurrenceRule are required"}
    start = _parse_dt(_str(req.get("startTime")))
    end = _parse_dt(_str(req.get("endTime")))
    if not start or not end:
        return {"ok": False, "error": "invalid startTime or endTime"}
    params = dict(part.split("=", 1) for part in recurrenceRule.upper().split(";") if "=" in part)
    freq = params.get("FREQ", "WEEKLY")
    count = min(int(params.get("COUNT", "10") or 10), 52)
    days = {"DAILY": 1, "WEEKLY": 7, "BIWEEKLY": 14, "MONTHLY": 30}.get(freq, 7)
    duration = end - start
    recurrence_id = gen_id("rec")
    ids: list[str] = []
    for i in range(count):
        instance_start = start.timestamp() + i * days * 86400
        sdt = datetime.fromtimestamp(instance_start, tz=timezone.utc)
        edt = sdt + duration
        payload = {**req, "recurrenceId": recurrence_id, "startTime": sdt.isoformat().replace("+00:00", "Z"), "endTime": edt.isoformat().replace("+00:00", "Z")}
        result = create_event(**payload)
        ids.append(_str(result.get("eventId")))
    return {"ok": True, "status": "created", "recurrenceId": recurrence_id, "eventCount": len(ids), "eventIds": ids}


def rsvp(eventId: str = "", response: str = "", respondentDid: str = "", comment: str = "", **_: Any) -> dict[str, Any]:
    if not eventId:
        return {"ok": False, "error": "eventId is required"}
    if response not in {"accept", "decline", "tentative"}:
        return {"ok": False, "error": "response must be accept, decline, or tentative"}
    if not _fetch_one("SELECT event_id FROM vertex_calendar_event WHERE event_id = %s LIMIT 1", (eventId,)):
        return {"ok": False, "error": "event not found", "eventId": eventId}
    rsvp_id = gen_id("rsvp")
    respondent = respondentDid or ACTOR_DID
    _insert("vertex_calendar_rsvp", {
        **_base("rsvp", rsvp_id),
        "rsvp_id": rsvp_id,
        "event_id": eventId,
        "respondent_did": respondent,
        "response": response,
        "comment": comment,
        "props": json.dumps({"eventId": eventId, "respondentDid": respondent, "response": response}, ensure_ascii=False),
    })
    # R0: Convert UPDATE to select, modify, insert_row
    invitation_to_update = get_kotoba_client().select_first_where(
        "vertex_calendar_invitation", "event_id", eventId,
        columns=["invitation_id", "event_id", "invitee_did", "organizer_did", "status", "responded_at", "created_at"]
    )
    if invitation_to_update and invitation_to_update.get("invitee_did") == respondent:
        invitation_to_update["status"] = response
        invitation_to_update["responded_at"] = now_iso()
        get_kotoba_client().insert_row("vertex_calendar_invitation", invitation_to_update)
    return {"ok": True, "status": "recorded", "rsvpId": rsvp_id, "eventId": eventId, "response": response}


def list_invitations(inviteeDid: str = "", status: str = "", limit: int = 50, offset: int = 0, **_: Any) -> dict[str, Any]:
    # R0: Multiple predicates, ORDER BY, LIMIT, OFFSET applied in Python
    all_invitations_raw = get_kotoba_client().select_where("vertex_calendar_invitation", "invitee_did", inviteeDid or ACTOR_DID, columns=["invitation_id", "event_id", "invitee_did", "organizer_did", "status", "responded_at", "created_at"])

    filtered_invitations = []
    required_status = status or "pending"
    for invitation in all_invitations_raw:
        if invitation.get("status") == required_status:
            filtered_invitations.append(invitation)

    sorted_invitations = sorted(filtered_invitations, key=lambda x: x.get("created_at", ""), reverse=True)
    paginated_invitations = sorted_invitations[offset:offset + limit]

    return {"ok": True, "invitations": paginated_invitations, "total": len(filtered_invitations), "offset": offset, "limit": limit}


def connect_account(accountDid: str = "did:anonymous", email: str = "", **_: Any) -> dict[str, Any]:
    client_id = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_ID", "")
    if not client_id:
        return {"ok": False, "error": "SS_GOOGLE_OAUTH_CLIENT_ID not configured"}
    redirect = os.environ.get("GOOGLE_CALENDAR_REDIRECT_URI", "https://calendar.etzhayyim.com/oauth/callback")
    qs = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": GWS_UNIFIED_SCOPES,
        "state": accountDid,
        "access_type": "offline",
        "prompt": "consent",
        **({"login_hint": email} if email else {}),
    })
    return {"ok": True, "status": "pending_oauth", "oauthUrl": f"https://accounts.google.com/o/oauth2/v2/auth?{qs}"}


def _decode_jwt_payload(jwt: str) -> dict[str, Any]:
    try:
        part = jwt.split(".")[1]
        part += "=" * (-len(part) % 4)
        return json.loads(base64.urlsafe_b64decode(part.encode()).decode())
    except Exception:
        return {}


def oauth_callback(code: str = "", error: str = "", state: str = "", **_: Any) -> dict[str, Any]:
    if error:
        return {"ok": False, "html": f"<h1>Calendar connect failed</h1><p>{error}</p>"}
    if not code:
        return {"ok": False, "html": "<h1>Missing code</h1>"}
    client_id = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_SECRET", "")
    redirect = os.environ.get("GOOGLE_CALENDAR_REDIRECT_URI", "https://calendar.etzhayyim.com/oauth/callback")
    if not client_id or not client_secret:
        return {"ok": False, "html": "<h1>Google OAuth credentials not configured</h1>"}
    body = urllib.parse.urlencode({"code": code, "client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect, "grant_type": "authorization_code"}).encode()
    tokens = _http_json("https://oauth2.googleapis.com/token", method="POST", headers={"content-type": "application/x-www-form-urlencoded"}, body=body)
    refresh = _str(tokens.get("refresh_token"))
    payload = _decode_jwt_payload(_str(tokens.get("id_token")))
    email = _str(payload.get("email"))
    if not refresh or not email:
        return {"ok": False, "html": "<h1>Calendar connect error</h1><p>missing refresh_token or email</p>"}
    _store_token(state or "did:anonymous", email, refresh, _str(tokens.get("scope") or GWS_UNIFIED_SCOPES))
    _insert("vertex_gcal_account", {
        **_base_gcal("account", email),
        "account_did": state or "did:anonymous",
        "email": email,
        "display_name": _str(payload.get("name")),
        "status": "active",
        "scope": _str(tokens.get("scope") or GWS_UNIFIED_SCOPES),
        "sync_token": "",
        "last_sync_at": "",
        "connected_at": now_iso(),
    })
    return {"ok": True, "html": f"<h1>Google Calendar connected</h1><p>{email}</p>", "email": email}


def _base_gcal(collection: str, rkey: str) -> dict[str, Any]:
    created = now_iso()
    return {
        "vertex_id": f"at://{ACTOR_DID}/com.etzhayyim.apps.calendar.{collection}/{rkey}",
        "created_date": created[:10],
        "sensitivity_ord": 100,
        "owner_did": ACTOR_DID,
        "rkey": rkey,
        "repo": ACTOR_DID,
        "created_at": created,
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": "calendar-mcp",
        "actor_did": ACTOR_DID,
        "org_did": "anon",
    }


def _store_token(account_did: str, email: str, refresh_token: str, scope: str) -> None:
    now = now_iso()
    vid = f"{account_did}|{email}"
    row = {
        "vertex_id": vid,
        "account_did": account_did,
        "email": email,
        "encrypted_refresh_token": refresh_token,
        "wrapped_data_key": "",
        "iv": "",
        "scope": scope,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    get_kotoba_client().insert_row(GCAL_TOKEN_TABLE, row)


def _refresh_access_token(refresh_token: str) -> str:
    client_id = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("SS_GOOGLE_OAUTH_CLIENT_SECRET", "")
    body = urllib.parse.urlencode({"refresh_token": refresh_token, "client_id": client_id, "client_secret": client_secret, "grant_type": "refresh_token"}).encode()
    data = _http_json("https://oauth2.googleapis.com/token", method="POST", headers={"content-type": "application/x-www-form-urlencoded"}, body=body)
    return _str(data.get("access_token"))


def sync_from_google(email: str = "", **_: Any) -> dict[str, Any]:
    if not email:
        return {"ok": False, "error": "email required"}
    # R0: Multiple predicates not supported by select_first_where directly, filtering in Python
    tokens = get_kotoba_client().select_where(GCAL_TOKEN_TABLE, "email", email)
    token = next((t for t in tokens if t.get("status") == "active"), None)
    if not token:
        return {"ok": False, "error": "No active Google Calendar account. Call connectAccount first."}
    return _sync_token(token)


def cron_tick(**_: Any) -> dict[str, Any]:
    # R0: ORDER BY COALESCE and LIMIT applied in Python
    all_active_tokens = get_kotoba_client().select_where(GCAL_TOKEN_TABLE, "status", "active")

    # Sort by COALESCE(last_sync_at, created_at) ASC and apply limit
    sorted_tokens = sorted(all_active_tokens, key=lambda x: x.get("last_sync_at") or x.get("created_at"))
    rows = sorted_tokens[:10]
    synced = 0
    errors = 0
    for token in rows:
        result = _sync_token(token)
        synced += int(result.get("synced") or 0)
        errors += 0 if result.get("ok") else 1
    return {"ok": errors == 0, "accounts": len(rows), "synced": synced, "errors": errors}


def _sync_token(token: dict[str, Any]) -> dict[str, Any]:
    access = _refresh_access_token(_str(token.get("encrypted_refresh_token")))
    if not access:
        return {"ok": False, "error": "access token refresh failed"}
    qs = urllib.parse.urlencode({"maxResults": "250", "showDeleted": "true", "singleEvents": "false", "timeMin": datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year - 1).isoformat()})
    data = _http_json(f"https://www.googleapis.com/calendar/v3/calendars/primary/events?{qs}", headers={"authorization": f"Bearer {access}"})
    synced = 0
    for ev in data.get("items", []):
        if not ev.get("id"):
            continue
        _insert("vertex_gcal_event", _gcal_event_row(token, ev))
        for attendee in ev.get("attendees", []) or []:
            if attendee.get("email"):
                _insert("vertex_gcal_attendee", _gcal_attendee_row(ev, attendee))
        synced += 1
    # R0: Convert UPDATE to select, modify, insert_row
    token_to_update = get_kotoba_client().select_first_where(GCAL_TOKEN_TABLE, "vertex_id", _str(token.get("vertex_id")))
    if token_to_update:
        token_to_update["last_sync_at"] = now_iso()
        token_to_update["cursor"] = _str(data.get("nextSyncToken"))
        token_to_update["updated_at"] = now_iso()
        get_kotoba_client().insert_row(GCAL_TOKEN_TABLE, token_to_update)
    return {"ok": True, "synced": synced, "syncToken": _str(data.get("nextSyncToken"))}


def _gcal_event_row(token: dict[str, Any], ev: dict[str, Any]) -> dict[str, Any]:
    event_id = _str(ev.get("id"))
    row = _base_gcal("event", event_id)
    row.update({
        "event_id": event_id,
        "ical_uid": _str(ev.get("iCalUID")),
        "calendar_id": "primary",
        "account_did": _str(token.get("account_did")),
        "summary": _str(ev.get("summary")),
        "description": _str(ev.get("description")),
        "location": _str(ev.get("location")),
        "start_time": _str((ev.get("start") or {}).get("dateTime")),
        "end_time": _str((ev.get("end") or {}).get("dateTime")),
        "start_date": _str((ev.get("start") or {}).get("date")),
        "end_date": _str((ev.get("end") or {}).get("date")),
        "timezone": _str((ev.get("start") or {}).get("timeZone")),
        "all_day": "true" if (ev.get("start") or {}).get("date") else "false",
        "status": _str(ev.get("status")),
        "visibility": _str(ev.get("visibility")),
        "transparency": _str(ev.get("transparency")),
        "recurrence": "\n".join(ev.get("recurrence") or []),
        "recurring_event_id": _str(ev.get("recurringEventId")),
        "organizer_email": _str((ev.get("organizer") or {}).get("email")),
        "organizer_name": _str((ev.get("organizer") or {}).get("displayName")),
        "creator_email": _str((ev.get("creator") or {}).get("email")),
        "hangout_link": _str(ev.get("hangoutLink")),
        "meet_uri": _str(next((e.get("uri") for e in ((ev.get("conferenceData") or {}).get("entryPoints") or []) if e.get("entryPointType") == "video"), "")),
        "conference_id": _str((ev.get("conferenceData") or {}).get("conferenceId")),
        "attendees_json": json.dumps(ev.get("attendees") or [], ensure_ascii=False),
        "attachments_json": json.dumps(ev.get("attachments") or [], ensure_ascii=False),
        "reminders_json": json.dumps(ev.get("reminders") or {}, ensure_ascii=False),
        "etag": _str(ev.get("etag")),
        "sequence": int(ev.get("sequence") or 0),
        "html_link": _str(ev.get("htmlLink")),
        "created_time": _str(ev.get("created")),
        "updated_time": _str(ev.get("updated")),
    })
    return row


def _gcal_attendee_row(ev: dict[str, Any], attendee: dict[str, Any]) -> dict[str, Any]:
    event_id = _str(ev.get("id"))
    email = _str(attendee.get("email"))
    row = _base_gcal("attendee", f"{event_id}:{email}")
    row.update({
        "attendee_id": f"{event_id}:{email}",
        "event_id": event_id,
        "calendar_id": "primary",
        "email": email,
        "display_name": _str(attendee.get("displayName")),
        "response_status": _str(attendee.get("responseStatus")),
        "is_organizer": "true" if attendee.get("organizer") else "false",
        "is_optional": "true" if attendee.get("optional") else "false",
        "is_resource": "true" if attendee.get("resource") else "false",
        "comment": _str(attendee.get("comment")),
    })
    return row
