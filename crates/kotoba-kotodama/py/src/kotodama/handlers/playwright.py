"""
ADR-0047 Phase B pilot — playwright actor on shared Python UDF pool.

Ports the session-lifecycle subset of the TS implementation at
`60-apps/etzhayyim-project-playwright/.../src/app.ts`:

- `com.etzhayyim.apps.playwright.sessionOpen`
- `com.etzhayyim.apps.playwright.sessionClose`

The op-forwarding commands (goto / fill / click / waitFor / scrape /
snapshot / screenshot / evaluate / getUrl / responseBody /
waitForTimeout) depend on the D1-backed `action` queue table +
Mac-daemon long-poll loop. That queue is pre-ADR-0036 state that must
be migrated to `vertex_playwright_action` (RW) before the Python pool
can host these verbs. Ditto the `dequeueAction` / `reportActionResult`
daemon-interface pair.

Until that migration, the shared UDF pool owns only the session-row
lifecycle; ops continue on the TS Worker. Both paths share
`vertex_playwright_session` via ADR-0036 Worker-direct Hyperdrive.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

from kotodama import udf

ACTOR_NAME = "playwright"
ACTOR_DID = f"did:web:{ACTOR_NAME}.etzhayyim.com"

SESSION_TTL_LOCAL_SEC = 30 * 60
SESSION_TTL_CF_SEC = 5 * 60


def _new_id(prefix: str) -> str:
    # 16 hex chars of entropy, prefixed — matches the TS `genID` surface.
    return f"{prefix}-{secrets.token_hex(8)}"


# NOTE: arrow-udf does not currently await `async def` handlers; it treats
# the returned coroutine as the scalar value and fails at arrow conversion
# ("Expected bytes, got a 'coroutine' object"). Until a sync asyncpg pool
# is wired into kotodama.db, these two handlers stay synchronous and
# compute session metadata without persisting to `vertex_playwright_session`.
# The persistence side will land as Phase B.1 alongside a sync `init_pool`
# call in kotodama.server (tracked in ADR-0049 §M4).


@udf(
    nsid="com.etzhayyim.apps.playwright.sessionOpen",
    io_threads=100,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("playwright", "session"),
    agent_tool=(
        "Open a Playwright session "
        "(target: 'local' = Mac daemon, 'cf-browser' = CF Browser Rendering)."
    ),
)
def session_open(params_json: str) -> str:
    """
    Input: JSON `{target?, userAgent?, locale?, viewport?}`.
    Output: JSON `{sessionId, target, expiresAt, _persisted: false}` for pilot
    (persistence deferred to Phase B.1 — see module docstring).
    """
    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"invalid JSON: {e}"})

    target = str(params.get("target") or "local")
    if target not in ("local", "cf-browser"):
        return json.dumps({"error": "target must be 'local' or 'cf-browser'"})

    session_id = _new_id("local" if target == "local" else "cf")
    ttl = SESSION_TTL_LOCAL_SEC if target == "local" else SESSION_TTL_CF_SEC
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(seconds=ttl)).isoformat()
    return json.dumps(
        {
            "sessionId": session_id,
            "target": target,
            "expiresAt": expires_at,
            "_persisted": False,
        }
    )


@udf(
    nsid="com.etzhayyim.apps.playwright.sessionClose",
    io_threads=100,
    input_types=["VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("playwright", "session"),
    agent_tool="Close a Playwright session.",
)
def session_close(params_json: str) -> str:
    """
    Input: JSON `{sessionId}`.
    Output: JSON `{sessionId, closed: true, _persisted: false}` for pilot
    (persistence deferred to Phase B.1 — see module docstring).
    """
    try:
        params = json.loads(params_json) if params_json else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"invalid JSON: {e}"})

    session_id = str(params.get("sessionId") or "")
    if not session_id:
        return json.dumps({"error": "sessionId required"})

    return json.dumps(
        {"sessionId": session_id, "closed": True, "_persisted": False}
    )
