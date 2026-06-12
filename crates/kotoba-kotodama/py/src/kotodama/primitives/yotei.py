"""Yotei scheduling XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime
from datetime import timezone
import decimal as _decimal
import json
import time
import uuid
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


YOTEI_DID = "did:web:yotei.etzhayyim.com"

COLLECTION_TABLE = {
    "calendar": "vertex_yotei_calendar",
    "availability": "vertex_yotei_availability",
    "event": "vertex_yotei_event",
    "booking": "vertex_yotei_booking",
}


def _now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today() -> str:
    return _now()[:10]


def _id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000):x}-{uuid.uuid4().hex[:8]}"


def _int(v: Any, default: int, *, min_value: int = 0, max_value: int = 100_000) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = default
    return max(min_value, min(max_value, n))





def _row_text(row: dict[str, Any], key: str) -> str:
    return str(row.get(key) or "")


def _base(kind: str, id_value: str, status: str = "active") -> dict[str, Any]:
    collection = f"com.etzhayyim.apps.yotei.{kind}"
    return {
        "vertex_id": f"at://{YOTEI_DID}/{collection}/{id_value}",
        "created_date": _today(),
        "sensitivity_ord": 1,
        "owner_did": YOTEI_DID,
        "rkey": id_value,
        "repo": YOTEI_DID,
        "did": YOTEI_DID,
        "collection": collection,
        "status": status,
        "id": id_value,
    }


def _insert(table: str, values: dict[str, Any]) -> None:
    get_kotoba_client().insert_row(table, values)


def _query(kind: str, where_sql: str = "", params: tuple[Any, ...] = (), order: str = "", limit: int = 100) -> list[dict[str, Any]]:
    table = COLLECTION_TABLE[kind]

    # R0: _query: Fetching a broader set (max 2000) using `select_where` and applying predicates, ordering, and limits in Python.
    # The `select_where` shim only supports a single equality predicate. We'll use a commonly present column like 'owner_did'.
    all_rows = get_kotoba_client().select_where(table, "owner_did", YOTEI_DID, limit=2000)

    # Apply status filter: "status NOT IN ('deleted','removed','cancelled_tombstone')"
    filtered_rows = [
        row for row in all_rows
        if row.get("status") not in ("deleted", "removed", "cancelled_tombstone")
    ]

    # Apply additional `where_sql` conditions in Python. This is a simplified interpretation.
    # For more complex or performance-critical scenarios, `q()` Datalog escape hatch might be needed.

    # A simple parser for 'col = %s' and basic 'AND' conditions.
    # This might not cover all possible SQL `where_sql` patterns.
    param_idx = 0
    temp_filtered_rows = []
    for row in filtered_rows:
        match = True
        if where_sql:
            # This part needs careful handling of different WHERE clause formats
            # The existing `_query` calls are mostly simple: "id = %s", "calendar_id = %s"
            # Or combined with AND: "calendar_id = %s AND start_at >= %s AND start_at <= %s AND status != %s"

            # Let's break `where_sql` into individual conditions and apply them.
            conditions = where_sql.split(" AND ")
            current_param_idx = 0
            for cond in conditions:
                cond_match = False
                if "=" in cond:
                    col, val_placeholder = cond.split("=", 1)
                    col = col.strip()
                    if "%s" in val_placeholder:
                        if current_param_idx < len(params):
                            if str(row.get(col)) == str(params[current_param_idx]):
                                cond_match = True
                            current_param_idx += 1
                    else: # direct value in SQL, e.g., 'col = "value"'
                        val = val_placeholder.strip().strip("'\"")
                        if str(row.get(col)) == val:
                            cond_match = True
                elif ">=" in cond:
                    col, val_placeholder = cond.split(">=", 1)
                    col = col.strip()
                    if "%s" in val_placeholder:
                        if current_param_idx < len(params):
                            if row.get(col) is not None and str(row.get(col)) >= str(params[current_param_idx]):
                                cond_match = True
                            current_param_idx += 1
                elif "<=" in cond:
                    col, val_placeholder = cond.split("<=", 1)
                    col = col.strip()
                    if "%s" in val_placeholder:
                        if current_param_idx < len(params):
                            if row.get(col) is not None and str(row.get(col)) <= str(params[current_param_idx]):
                                cond_match = True
                            current_param_idx += 1
                elif "!=" in cond:
                    col, val_placeholder = cond.split("!=", 1)
                    col = col.strip()
                    if "%s" in val_placeholder:
                        if current_param_idx < len(params):
                            if str(row.get(col)) != str(params[current_param_idx]):
                                cond_match = True
                            current_param_idx += 1
                elif "IN" in cond:
                    # e.g., `status IN (%s,%s)` -> params would have "proposed", "confirmed"
                    col, in_values_str = cond.split("IN", 1)
                    col = col.strip()
                    # Assuming in_values_str is `(%s,%s)` or `('val1','val2')`
                    # We need to extract the values from params for `%s` cases.

                    # For now, let's assume `IN` will be explicitly converted to `or` in the call site or handled by `q()`.
                    # For the current `task_yotei_analyze_schedule` with `status IN (%s,%s)`, the `params` will contain the values.

                    # This is complex for a generic parser. Let's make an explicit handling for this case.
                    if col == "status" and "IN (%s,%s)" in in_values_str:
                        if current_param_idx + 1 < len(params):
                            if row.get(col) in (params[current_param_idx], params[current_param_idx+1]):
                                cond_match = True
                            current_param_idx += 2 # Consume two parameters
                    else:
                        # Fallback for generic IN, potentially complex
                        cond_match = False # If we can't parse, assume no match
                else:
                    cond_match = False # Unhandled condition type

                if not cond_match:
                    match = False
                    break
        if match:
            temp_filtered_rows.append(row)

    final_rows = temp_filtered_rows

    # Apply ordering
    if order:
        try:
            # Assuming 'order' is like 'col ASC' or 'col DESC'
            col_name = order.split(" ")[0].strip()
            reverse = "DESC" in order.upper()
            final_rows.sort(key=lambda x: x.get(col_name, ""), reverse=reverse)
        except Exception:
            # Fallback if ordering column is not found or type mismatch
            pass

    # Apply limit
    final_rows = final_rows[:max(1, min(limit, 500))]

    return final_rows


def _update(table: str, id_value: str, values: dict[str, Any]) -> None:
    # Determine 'kind' from the table name for _base function
    kind = table.replace("vertex_yotei_", "")
    # Create a base dictionary including the identity column 'vertex_id' and 'id'
    base_dict = _base(kind, id_value, status=values.get("status", "active")) # Assuming status might be in values

    # Merge the new values into the base dictionary
    full_row_dict = {**base_dict, **values}

    # Use insert_row for upsert functionality
    get_kotoba_client().insert_row(table, full_row_dict)


def task_yotei_create_calendar(name: str = "", timezone: str = "Asia/Tokyo", defaultDurationMin: Any = 30, **_: Any) -> dict[str, Any]:
    cal_id = _id("cal")
    now = _now()
    _insert("vertex_yotei_calendar", {
        **_base("calendar", cal_id, "active"),
        "owner_did_ref": YOTEI_DID,
        "name": name,
        "timezone": timezone or "Asia/Tokyo",
        "default_duration_min": _int(defaultDurationMin, 30, min_value=5, max_value=1440),
        "booking_page_enabled": True,
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": YOTEI_DID,
        "created_at": now,
    })
    return {"id": cal_id, "name": name, "status": "created"}


def task_yotei_get_calendar(id: str = "", **_: Any) -> dict[str, Any]:
    rows = _query("calendar", "id = %s", (id,), limit=1)
    return rows[0] if rows else {"error": "not_found"}


def task_yotei_list_calendars(**_: Any) -> dict[str, Any]:
    rows = _query("calendar", order="created_at DESC", limit=50)
    return {"calendars": rows, "total": len(rows)}


def task_yotei_delete_calendar(id: str = "", **_: Any) -> dict[str, Any]:
    _update("vertex_yotei_calendar", id, {"status": "deleted"})
    return {"id": id, "status": "deleted"}


def task_yotei_set_availability(
    calendarId: str = "", dayOfWeek: Any = 0, startTime: str = "", endTime: str = "", specificDate: str = "", **_: Any
) -> dict[str, Any]:
    avl_id = _id("avl")
    recurring = not bool(specificDate)
    day = _int(dayOfWeek, 0, min_value=-1, max_value=6)
    _insert("vertex_yotei_availability", {
        **_base("availability", avl_id, "active"),
        "calendar_id": calendarId,
        "day_of_week": day,
        "start_time": startTime,
        "end_time": endTime,
        "specific_date": specificDate or "",
        "recurring": recurring,
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": YOTEI_DID,
        "created_at": _now(),
    })
    return {"id": avl_id, "day": specificDate or str(day), "startTime": startTime, "endTime": endTime, "status": "set"}


def task_yotei_get_availability(calendarId: str = "", **_: Any) -> dict[str, Any]:
    rows = _query("availability", "calendar_id = %s", (calendarId,), order="day_of_week ASC", limit=100)
    return {"availability": rows, "total": len(rows)}


def task_yotei_remove_availability(id: str = "", **_: Any) -> dict[str, Any]:
    _update("vertex_yotei_availability", id, {"status": "removed"})
    return {"id": id, "status": "removed"}


def task_yotei_get_open_slots(calendarId: str = "", dateFrom: str = "", dateTo: str = "", durationMin: Any = 30, **_: Any) -> dict[str, Any]:
    avails = _query("availability", "calendar_id = %s", (calendarId,), limit=200)
    events = _query(
        "event",
        "calendar_id = %s AND start_at >= %s AND start_at <= %s AND status != %s",
        (calendarId, dateFrom, dateTo, "cancelled"),
        limit=500,
    )
    return {
        "calendarId": calendarId,
        "dateRange": {"from": dateFrom, "to": dateTo},
        "durationMin": _int(durationMin, 30, min_value=5, max_value=1440),
        "availabilityRules": len(avails),
        "existingEvents": len(events),
        "note": "Slot computation: client-side from availability rules minus existing events",
    }


def task_yotei_create_event(calendarId: str = "", title: str = "", startAt: str = "", endAt: str = "", location: str = "", description: str = "", **_: Any) -> dict[str, Any]:
    event_id = _id("evt")
    _insert("vertex_yotei_event", {
        **_base("event", event_id, "confirmed"),
        "calendar_id": calendarId,
        "title": title,
        "start_at": startAt,
        "end_at": endAt,
        "location": location or "",
        "description": description or "",
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": YOTEI_DID,
        "created_at": _now(),
    })
    return {"id": event_id, "title": title, "status": "confirmed"}


def task_yotei_update_event(id: str = "", title: str = "", startAt: str = "", endAt: str = "", location: Any = None, description: Any = None, status: str = "", **_: Any) -> dict[str, Any]:
    rows = _query("event", "id = %s", (id,), limit=1)
    if not rows:
        return {"error": "not_found"}
    updates: dict[str, Any] = {}
    if title:
        updates["title"] = title
    if startAt:
        updates["start_at"] = startAt
    if endAt:
        updates["end_at"] = endAt
    if location is not None:
        updates["location"] = str(location)
    if description is not None:
        updates["description"] = str(description)
    if status:
        updates["status"] = status
    if updates:
        _update("vertex_yotei_event", id, updates)
    return {"id": id, "status": "updated"}


def task_yotei_cancel_event(id: str = "", **_: Any) -> dict[str, Any]:
    _update("vertex_yotei_event", id, {"status": "cancelled"})
    return {"id": id, "status": "cancelled"}


def task_yotei_list_events(calendarId: str = "", dateFrom: str = "", dateTo: str = "", **_: Any) -> dict[str, Any]:
    clauses = ["calendar_id = %s", "status != %s"]
    params: list[Any] = [calendarId, "cancelled"]
    if dateFrom:
        clauses.append("start_at >= %s")
        params.append(dateFrom)
    if dateTo:
        clauses.append("start_at <= %s")
        params.append(dateTo)
    rows = _query("event", " AND ".join(clauses), tuple(params), order="start_at ASC", limit=100)
    return {"events": rows, "total": len(rows)}


def task_yotei_get_event(id: str = "", **_: Any) -> dict[str, Any]:
    rows = _query("event", "id = %s", (id,), limit=1)
    return rows[0] if rows else {"error": "not_found"}


def task_yotei_propose_booking(calendarId: str = "", requesterDid: str = "", durationMin: Any = 30, message: str = "", preferredDates: Any = None, **_: Any) -> dict[str, Any]:
    booking_id = _id("bk")
    duration = _int(durationMin, 30, min_value=5, max_value=1440)
    slots = preferredDates if isinstance(preferredDates, list) else []
    _insert("vertex_yotei_booking", {
        **_base("booking", booking_id, "proposed"),
        "calendar_id": calendarId,
        "event_id": "",
        "requester_did": requesterDid,
        "responder_did": YOTEI_DID,
        "duration_min": duration,
        "proposed_slots": json.dumps(slots, ensure_ascii=False),
        "confirmed_slot": "",
        "message": message or "",
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": YOTEI_DID,
        "created_at": _now(),
    })
    return {"id": booking_id, "status": "proposed", "durationMin": duration}


def task_yotei_confirm_booking(id: str = "", slot: Any = None, **_: Any) -> dict[str, Any]:
    rows = _query("booking", "id = %s", (id,), limit=1)
    if not rows:
        return {"error": "not_found"}
    bk = rows[0]
    slot_obj = slot if isinstance(slot, dict) else {}
    event_id = _id("evt")
    _insert("vertex_yotei_event", {
        **_base("event", event_id, "confirmed"),
        "calendar_id": _row_text(bk, "calendarId"),
        "title": f"Meeting with {_row_text(bk, 'requesterDid')}",
        "start_at": str(slot_obj.get("start") or ""),
        "end_at": str(slot_obj.get("end") or ""),
        "location": "",
        "description": f"Booking {id}",
        "org_id": "anon",
        "user_id": "anon",
        "actor_id": YOTEI_DID,
        "created_at": _now(),
    })
    _update("vertex_yotei_booking", id, {"status": "confirmed", "event_id": event_id, "confirmed_slot": json.dumps(slot_obj)})
    return {"id": id, "eventId": event_id, "status": "confirmed", "slot": slot_obj}


def task_yotei_cancel_booking(id: str = "", **_: Any) -> dict[str, Any]:
    _update("vertex_yotei_booking", id, {"status": "cancelled"})
    return {"id": id, "status": "cancelled"}


def task_yotei_list_bookings(calendarId: str = "", status: str = "", **_: Any) -> dict[str, Any]:
    clauses = ["calendar_id = %s"]
    params: list[Any] = [calendarId]
    if status:
        clauses.append("status = %s")
        params.append(status)
    rows = _query("booking", " AND ".join(clauses), tuple(params), order="created_at DESC", limit=50)
    return {"bookings": rows, "total": len(rows)}


def task_yotei_get_booking(id: str = "", **_: Any) -> dict[str, Any]:
    rows = _query("booking", "id = %s", (id,), limit=1)
    return rows[0] if rows else {"error": "not_found"}


def task_yotei_suggest_slots(calendarId: str = "", requesterDid: str = "", durationMin: Any = 30, purpose: str = "", preferredTimeOfDay: str = "", **_: Any) -> dict[str, Any]:
    avails = _query("availability", "calendar_id = %s", (calendarId,), order="day_of_week ASC", limit=3)
    duration = _int(durationMin, 30, min_value=5, max_value=1440)
    slots = []
    base_date = _dt.datetime.now(tz=_dt.UTC).date()
    for i, av in enumerate(avails or [{"startTime": "09:00", "endTime": "09:30"}]):
        day = base_date + _dt.timedelta(days=i + 1)
        start = f"{day.isoformat()}T{_row_text(av, 'startTime') or '09:00'}:00Z"
        slots.append({"start": start, "end": f"{day.isoformat()}T{_row_text(av, 'endTime') or '09:30'}:00Z", "reason": preferredTimeOfDay or purpose or "available"})
    return {"slots": slots[:3], "note": f"Suggested for {requesterDid}; duration {duration} minutes."}


def task_yotei_auto_reschedule(eventId: str = "", reason: str = "", **_: Any) -> dict[str, Any]:
    rows = _query("event", "id = %s", (eventId,), limit=1)
    if not rows:
        return {"error": "event_not_found"}
    evt = rows[0]
    start = _dt.datetime.now(tz=_dt.UTC) + _dt.timedelta(days=1)
    alternatives = [
        {"start": (start + _dt.timedelta(days=i)).isoformat().replace("+00:00", "Z"), "end": (start + _dt.timedelta(days=i, minutes=30)).isoformat().replace("+00:00", "Z"), "reason": reason or "next available window"}
        for i in range(3)
    ]
    return {"alternatives": alternatives, "originalEvent": {"id": eventId, "title": evt.get("title")}, "advice": "Review availability before confirming."}


def task_yotei_analyze_schedule(calendarId: str = "", **_: Any) -> dict[str, Any]:
    avails = _query("availability", "calendar_id = %s", (calendarId,), limit=100)
    events = _query("event", "calendar_id = %s AND status != %s", (calendarId, "cancelled"), limit=100)
    bookings = _query("booking", "calendar_id = %s AND status IN (%s,%s)", (calendarId, "proposed", "confirmed"), limit=100)
    density = "high" if len(events) > 20 else "medium" if len(events) > 8 else "low"
    risk = "high" if len(bookings) > 10 else "medium" if len(bookings) > 4 else "low"
    return {
        "utilization": f"{min(100, int((len(events) / max(1, len(avails) * 3)) * 100))}%",
        "meetingDensity": density,
        "focusBlocks": max(0, len(avails) - len(events)),
        "overcommitRisk": risk,
        "suggestions": ["Protect focus blocks", "Batch short meetings"] if events else ["Add availability windows"],
        "summary": f"{len(events)} events and {len(bookings)} active bookings.",
    }


def task_yotei_health(**_: Any) -> dict[str, Any]:
    return {"status": "ok", "app": "yotei", "nanoid": "unyrsfan", "timestamp": _now()}


def task_yotei_describe(**_: Any) -> dict[str, Any]:
    return {
        "name": "Yotei Scheduler",
        "description": "Calendar scheduling and availability coordination.",
        "capabilities": ["calendar-scheduling", "availability-management", "meeting-booking", "event-management"],
        "did": YOTEI_DID,
    }


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "xrpc.com.etzhayyim.apps.yotei.analyzeSchedule": task_yotei_analyze_schedule,
        "xrpc.com.etzhayyim.apps.yotei.autoReschedule": task_yotei_auto_reschedule,
        "xrpc.com.etzhayyim.apps.yotei.cancelBooking": task_yotei_cancel_booking,
        "xrpc.com.etzhayyim.apps.yotei.cancelEvent": task_yotei_cancel_event,
        "xrpc.com.etzhayyim.apps.yotei.confirmBooking": task_yotei_confirm_booking,
        "xrpc.com.etzhayyim.apps.yotei.createCalendar": task_yotei_create_calendar,
        "xrpc.com.etzhayyim.apps.yotei.createEvent": task_yotei_create_event,
        "xrpc.com.etzhayyim.apps.yotei.deleteCalendar": task_yotei_delete_calendar,
        "xrpc.com.etzhayyim.apps.yotei.describe": task_yotei_describe,
        "xrpc.com.etzhayyim.apps.yotei.getAvailability": task_yotei_get_availability,
        "xrpc.com.etzhayyim.apps.yotei.getBooking": task_yotei_get_booking,
        "xrpc.com.etzhayyim.apps.yotei.getCalendar": task_yotei_get_calendar,
        "xrpc.com.etzhayyim.apps.yotei.getEvent": task_yotei_get_event,
        "xrpc.com.etzhayyim.apps.yotei.getOpenSlots": task_yotei_get_open_slots,
        "xrpc.com.etzhayyim.apps.yotei.health": task_yotei_health,
        "xrpc.com.etzhayyim.apps.yotei.listBookings": task_yotei_list_bookings,
        "xrpc.com.etzhayyim.apps.yotei.listCalendars": task_yotei_list_calendars,
        "xrpc.com.etzhayyim.apps.yotei.listEvents": task_yotei_list_events,
        "xrpc.com.etzhayyim.apps.yotei.proposeBooking": task_yotei_propose_booking,
        "xrpc.com.etzhayyim.apps.yotei.removeAvailability": task_yotei_remove_availability,
        "xrpc.com.etzhayyim.apps.yotei.setAvailability": task_yotei_set_availability,
        "xrpc.com.etzhayyim.apps.yotei.suggestSlots": task_yotei_suggest_slots,
        "xrpc.com.etzhayyim.apps.yotei.updateEvent": task_yotei_update_event,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
