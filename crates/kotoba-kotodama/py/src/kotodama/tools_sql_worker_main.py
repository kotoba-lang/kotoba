"""Generic-primitive worker for com.etzhayyim.tools.sql.* (ADR-2605082000 §2 follow-up).

Wired into mcp_dispatch via ``register_overrides``.
"""

from __future__ import annotations

import re
from typing import Any
from datetime import datetime, timezone
from kotodama.kotoba_datomic import get_kotoba_client


_RESERVED_KWARGS = {"sql", "params", "limit", "rows", "confirmWrite"}


async def task_sql_query(
    *,
    sql: str = "",
    params: dict[str, Any] | None = None,
    limit: int | None = None,
    **extra_kwargs: Any,
) -> dict[str, Any]:
    """Run a read-only SELECT and return the rows as objects.

    Bind params come from two sources, merged in order:
      1. ``params`` dict (config.args.params or explicit kwarg)
      2. ``extra_kwargs`` — any kwarg other than ``sql`` / ``params`` /
         ``limit`` is treated as a named bind. This is the LangGraph
         input_keys path: ``input_keys=["industry_codes"]`` makes
         ``state["industry_codes"]`` available as ``%(industry_codes)s``
         in the SQL without per-call params dict construction.
      Explicit ``params`` entries win over kwarg-derived ones on conflict.

    Returns ``{"error": ...}`` on rejection / failure. ``limit`` (default
    1000) caps the response payload size to protect callers / hosts.
    """
    # This function now acts as a placeholder returning an error for generic SQL queries.
    return {"error": "com.etzhayyim.tools.sql.query: Generic SQL queries are not supported by the Kotoba Datomic client."}


async def task_sql_exec(
    *,
    sql: str = "",
    params: dict[str, Any] | None = None,
    rows: list[dict[str, Any]] | None = None,
    confirmWrite: bool = False,
    **extra_kwargs: Any,
) -> dict[str, Any]:
    """Run a write SQL (INSERT / UPDATE / UPSERT) and return the rowcount.

    Strict guards:
      - ``confirmWrite`` must be True (defense-in-depth).
      - SQL must start with INSERT / UPDATE / UPSERT / WITH.
      - SQL must NOT contain DELETE / DROP / TRUNCATE / GRANT / REVOKE /
        CREATE / ALTER (case-insensitive substring check).

    Modes:
      - If ``rows`` is supplied → ``sa_executemany`` batch mode.
        Returns ``{"rowCount": <total processed>}``.
      - Else → single ``sa_rowcount`` execute. Returns affected count.
    """
    # This function now acts as a placeholder returning an error for generic SQL execution.
    return {"error": "com.etzhayyim.tools.sql.exec: Generic SQL execution is not supported by the Kotoba Datomic client."}


# ---------------------------------------------------------------------------
# task_sql_insert_row  (ADR-2605082000 Phase E0 — dynamic-column INSERT)
# ---------------------------------------------------------------------------


# Allow only safe identifier shape for `table` (defense-in-depth — even
# though we never interpolate untrusted input directly into SQL, build
# via SQLAlchemy Table reflection-style construction).
_TABLE_NAME_RE = re.compile(r"\A[a-zA-Z_][a-zA-Z0-9_]{0,127}\Z")
_COLUMN_NAME_RE = re.compile(r"\A[a-zA-Z_][a-zA-Z0-9_]{0,127}\Z")


def _render_vertex_id(template: str, owner_did: str, collection: str) -> str:
    """Expand a vertex_id template per the ADR-2605082000 Phase E convention.

    Placeholders:
      {owner_did}  — caller-provided DID, e.g. did:web:bpmn.etzhayyim.com
      {collection} — caller-provided NSID,  e.g. com.etzhayyim.apps.hr.event
      {stamp}      — UTC YYYYMMDDHHMMSS
      {nanoid8}    — 8-char hex nanoid (uuid4 first 8)

    Unknown placeholders pass through unchanged so the caller sees the
    literal `{foo}` if they typoed.
    """
    import uuid as _uuid
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    nanoid8 = _uuid.uuid4().hex[:8]
    return (template
            .replace("{owner_did}", owner_did or "")
            .replace("{collection}", collection or "")
            .replace("{stamp}", stamp)
            .replace("{nanoid8}", nanoid8))


async def task_sql_insert_row(
    *,
    table: str = "",
    row: dict[str, Any] | None = None,
    vertex_id_template: str | None = None,
    owner_did: str = "",
    collection: str = "",
    **_ignored: Any,
) -> dict[str, Any]:
    """Insert a row with runtime-determined columns into ``table``.

    Bridges the ADR-2605082000 Phase E LLM-supervisor decomposition pattern:
    LLM returns ``db_writes: [{"table": "...", "row": {...}}, ...]``, foreach
    iterates, each iteration calls this primitive with one ``{table, row}``
    item. The set of columns is data-driven (LLM picks them) so a fixed
    SQL template (sql.exec) doesn't fit.

    Auto-derive ``vertex_id`` if absent and ``vertex_id_template`` is given.
    Returns ``{"vertexId": <str>, "ok": true}`` or ``{"error": ...}``.

    Safety:
      - ``table`` must match ``^[a-zA-Z_][a-zA-Z0-9_]*$`` (rejects schema
        prefixes / DDL injection / quoted names).
      - Each column key in ``row`` must match the same identifier shape.
      - Values are passed through SQLAlchemy parameter binding — never
        string-interpolated into SQL.
      - No ``DELETE`` / ``UPDATE`` semantics here; only INSERT.
    """
    if not table or not _TABLE_NAME_RE.match(table):
        return {"error": "com.etzhayyim.tools.sql.insert_row: invalid table name"}
    if not isinstance(row, dict) or not row:
        return {"error": "com.etzhayyim.tools.sql.insert_row: 'row' must be a non-empty object"}
    bad_cols = [k for k in row if not _COLUMN_NAME_RE.match(str(k))]
    if bad_cols:
        return {"error": f"com.etzhayyim.tools.sql.insert_row: invalid column names: {bad_cols}"}

    # Derive vertex_id if missing and template given.
    work = dict(row)
    if not work.get("vertex_id") and vertex_id_template:
        work["vertex_id"] = _render_vertex_id(vertex_id_template, owner_did, collection)

    try:
        get_kotoba_client().insert_row(table, work)
    except Exception as exc:  # pragma: no cover — defensive
        return {"error": f"sql_insert_row failed: {exc}"}

    return {"vertexId": work.get("vertex_id", ""), "ok": True}
