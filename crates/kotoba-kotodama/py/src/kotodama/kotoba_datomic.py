"""kotoba Datomic substrate client for the kotodama worker layer.

This is the **RW-free substrate replacement** for ``kotodama.rw_async_pool`` +
``kotodama.rw_sql`` (ADR-2605262130 + ADR-2605312345: kotoba Datom log is the
first-class canonical state; no RisingWave / Postgres / Kysely). It speaks the
kotoba Datomic XRPC surface against a running kotoba node:

    POST /xrpc/com.etzhayyim.apps.kotoba.datomic.transact   {graph, tx_edn}
    POST /xrpc/com.etzhayyim.apps.kotoba.datomic.q          {graph, query, args}
    POST /xrpc/com.etzhayyim.apps.kotoba.datomic.pull       {graph, selector, eid}

stdlib only (urllib + json) — same dependency-free posture as the migrated actor
``methods/transact.py`` (ipaddress / yabai / tadori). No psycopg, no SQLAlchemy,
no connection pool.

## Vertex/edge row → Datom entity mapping

The legacy schema modelled the graph as ``vertex_<type>`` / ``edge_<type>`` SQL
tables keyed by a ``vertex_id`` (an ``at://`` URI) PK. Under kotoba each row is an
entity map whose attributes are namespaced by the table:

    table  ``vertex_employee``  column ``vertex_id``  →  ``:vertex.employee/vertex-id``  (:db.unique/identity)
                                 column ``name``       →  ``:vertex.employee/name``
                                 column ``hired_at``   →  ``:vertex.employee/hired-at``

``vertex-id`` carries ``:db.unique/identity`` so a re-transact upserts — preserving
the RisingWave "PK implicit overwrite" semantics the old pool relied on. Schema
install (declaring the identity attributes) is a separate transact; ``ensure_schema``
helps emit it.

## Auth (ADR-2605231525 — no platform-held key)

Live writes require an operator credential in ``KOTOBA_SESSION_POP`` (verified via
``com.etzhayyim.pds.session.verify``) or ``KOTOBA_TOKEN`` bearer. Without one the
client raises on write so nothing silently no-ops; reads are open against a local
node. Set ``KOTODAMA_KOTOBA_DRYRUN=1`` to make ``transact`` print + skip instead.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Iterable, Mapping, Sequence

NSID_TRANSACT = "com.etzhayyim.apps.kotoba.datomic.transact"
NSID_Q = "com.etzhayyim.apps.kotoba.datomic.q"
NSID_PULL = "com.etzhayyim.apps.kotoba.datomic.pull"
NSID_SESSION_VERIFY = "com.etzhayyim.pds.session.verify"

DEFAULT_URL = "http://127.0.0.1:8077"
DEFAULT_GRAPH = "etzhayyim/kotoba-kotodama/graph"


# ─────────────────────────── EDN serialization ───────────────────────────
# Minimal EDN value writer (mirrors the per-actor *_edn.py helpers). Only the
# value shapes a Datom tx-data / query needs: nil, bool, int, float, string,
# keyword, vector, map.

def edn_str(s: str) -> str:
    """Serialize a Python str as an EDN string literal (quoted, escaped)."""
    out = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return f'"{out}"'


def edn_val(x: Any) -> str:
    """Serialize a Python value to EDN source text.

    A str that already looks like a keyword (``:ns/name``) is emitted verbatim so
    callers can pass attribute keywords directly; any other str is quoted.
    """
    if x is None:
        return "nil"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, (int, float)):
        return str(x)
    if isinstance(x, str):
        if x.startswith(":") and " " not in x and '"' not in x:
            return x  # keyword passthrough
        return edn_str(x)
    if isinstance(x, Mapping):
        inner = " ".join(f"{edn_val(k)} {edn_val(v)}" for k, v in x.items())
        return "{" + inner + "}"
    if isinstance(x, (list, tuple)):
        return "[" + " ".join(edn_val(v) for v in x) + "]"
    if isinstance(x, set):
        return "#{" + " ".join(edn_val(v) for v in x) + "}"
    # fallback: stringify
    return edn_str(str(x))


def to_tx_edn(entities: Iterable[Mapping[str, Any]], header_lines: Sequence[str] = ()) -> str:
    """Frame a sequence of entity maps as a Datomic map-form tx-data vector."""
    head = "".join(f";; {ln}\n" for ln in header_lines)
    body = "\n ".join(edn_val(dict(e)) for e in entities)
    return f"{head}[{body}]" if body else f"{head}[]"


# ─────────────────────────── row → entity mapping ───────────────────────────

def _kebab(name: str) -> str:
    return name.replace("_", "-")


def table_attr_namespace(table_name: str) -> str:
    """``vertex_employee`` → ``vertex.employee`` ; ``edge_actor_has_role`` → ``edge.actor-has-role``.

    The leading ``vertex_`` / ``edge_`` becomes the namespace head; the remainder
    is kebab-cased into a single segment so the attribute keyword reads
    ``:vertex.employee/<col>``.
    """
    if table_name.startswith("vertex_"):
        head, rest = "vertex", table_name[len("vertex_"):]
    elif table_name.startswith("edge_"):
        head, rest = "edge", table_name[len("edge_"):]
    else:
        head, rest = "ent", table_name
    return f"{head}.{_kebab(rest)}" if rest else head


def row_to_entity(table_name: str, row: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a ``vertex_*`` / ``edge_*`` SQL-shaped row into a kotoba entity map.

    Column ``vertex_id`` (or ``edge_id``) becomes the ``:db.unique/identity`` key.
    ``None`` values are dropped (kotoba has no NULL column; absence = no datom).
    """
    ns = table_attr_namespace(table_name)
    ent: dict[str, Any] = {}
    for col, val in row.items():
        if val is None:
            continue
        ent[f":{ns}/{_kebab(str(col))}"] = val
    return ent


def identity_attr(table_name: str, id_column: str = "vertex_id") -> str:
    """The ``:db.unique/identity`` keyword for a table's id column."""
    return f":{table_attr_namespace(table_name)}/{_kebab(id_column)}"


def schema_install_edn(table_name: str, columns: Sequence[str], id_column: str = "vertex_id") -> str:
    """Emit a schema-install tx declaring the table's identity attribute.

    Other columns are open (kotoba is schemaless on value type by default); only
    the unique-identity attribute must be declared so upsert works.
    """
    ns = table_attr_namespace(table_name)
    attrs = [{
        ":db/ident": f":{ns}/{_kebab(id_column)}",
        ":db/unique": ":db.unique/identity",
        ":db/cardinality": ":db.cardinality/one",
    }]
    return to_tx_edn(attrs, [f"{table_name} identity attr install"])


# ─────────────────────────── client ───────────────────────────

class KotobaTransactError(RuntimeError):
    pass


class KotobaDatomicClient:
    """Synchronous kotoba Datomic client (urllib, stdlib only).

    Replaces ``ensure_rw_async_pool()`` — there is no pool because each call is a
    stateless XRPC POST to the local kotoba node.
    """

    def __init__(
        self,
        url: str | None = None,
        graph: str | None = None,
        token: str | None = None,
        session_pop: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.url = (url or os.environ.get("KOTOBA_URL") or DEFAULT_URL).rstrip("/")
        self.graph = graph or os.environ.get("KOTODAMA_KOTOBA_GRAPH") or DEFAULT_GRAPH
        self.token = token or os.environ.get("KOTOBA_TOKEN")
        self.session_pop = session_pop or os.environ.get("KOTOBA_SESSION_POP")
        self.timeout = timeout
        self._session_verified = False

    # -- low level --
    def _post(self, nsid: str, body: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(f"{self.url}/xrpc/{nsid}", data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        tok = self.token or self.session_pop
        if tok:
            req.add_header("Authorization", f"Bearer {tok}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 (own node)
                return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read().decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return exc.code, {"error": "non-json"}

    def _verify_session(self) -> None:
        if self._session_verified or not self.session_pop:
            return
        st, info = self._post(NSID_SESSION_VERIFY, {"token": self.session_pop})
        if st != 200 or not info.get("valid"):
            raise KotobaTransactError(f"session PoP rejected: {info}")
        self._session_verified = True

    def _require_write_credential(self) -> None:
        if not (self.token or self.session_pop):
            raise KotobaTransactError(
                "no write credential — set KOTOBA_SESSION_POP or KOTOBA_TOKEN "
                "(ADR-2605231525: no platform-held key). Set KOTODAMA_KOTOBA_DRYRUN=1 to dry-run."
            )

    # -- public Datomic surface --
    def transact(self, tx_edn: str, *, graph: str | None = None) -> dict[str, Any]:
        """Transact raw tx-data EDN into the Datom log. Returns the node response."""
        g = graph or self.graph
        if os.environ.get("KOTODAMA_KOTOBA_DRYRUN") == "1":
            print(f"[kotoba dry-run] transact graph={g} ({len(tx_edn.encode()):,} bytes)\n{tx_edn[:400]}")
            return {"dry_run": True, "graph": g}
        self._require_write_credential()
        self._verify_session()
        st, body = self._post(NSID_TRANSACT, {"graph": g, "tx_edn": tx_edn})
        if st != 200:
            raise KotobaTransactError(f"transact failed: {st} {body}")
        return body

    def q(self, query_edn: str, args: Sequence[Any] = (), *, graph: str | None = None) -> list[Any]:
        """Run a Datalog query (EDN ``[:find … :where …]``). Returns result rows."""
        g = graph or self.graph
        st, body = self._post(NSID_Q, {"graph": g, "query_edn": query_edn, "inputs_edn": [edn_val(a) for a in args]})
        if st != 200:
            raise KotobaTransactError(f"query failed: {st} {body}")
        return body.get("result", body.get("rows", []))

    def pull(self, selector: str, eid: Any, *, graph: str | None = None) -> dict[str, Any]:
        """Pull an entity tree by selector + entity id (or lookup-ref)."""
        g = graph or self.graph
        st, body = self._post(NSID_PULL, {"graph": g, "entity": str(eid), "pattern_edn": selector})
        if st != 200:
            raise KotobaTransactError(f"pull failed: {st} {body}")
        return body.get("entity", body)

    # -- rw_sql-compatible shims (low-friction caller migration) --
    def ensure_schema(self, table_name: str, columns: Sequence[str], id_column: str = "vertex_id") -> dict[str, Any]:
        """RW DDL analog — declare the table's unique-identity attribute (idempotent)."""
        return self.transact(schema_install_edn(table_name, columns, id_column))

    def insert_row(self, table_name: str, row: Mapping[str, Any]) -> dict[str, Any]:
        """Replacement for ``rw_sql.insert_projected_row`` — upsert one entity."""
        ent = row_to_entity(table_name, row)
        if not ent:
            return {"datom_count": 0}
        return self.transact(to_tx_edn([ent], [f"{table_name} row"]))

    def insert_rows(self, table_name: str, rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        """Batch upsert — one transaction for many rows."""
        ents = [row_to_entity(table_name, r) for r in rows]
        ents = [e for e in ents if e]
        if not ents:
            return {"datom_count": 0}
        return self.transact(to_tx_edn(ents, [f"{table_name} rows ({len(ents)})"]))

    def select_rows(
        self,
        table_name: str,
        columns: Sequence[str] = (),
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Replacement for ``rw_sql.select_projected`` — Datalog SELECT over a table.

        Builds ``[:find (pull ?e [<attrs>]) :where [?e <identity-attr> _]]`` so every
        entity of the table is returned, then projects the requested columns back to
        plain ``{column: value}`` dicts (the RW row shape callers expect).
        """
        return self._select_by_clause(table_name, f"[?e {identity_attr(table_name)} _]", columns, limit)

    def select_where(
        self,
        table_name: str,
        column: str,
        value: Any,
        columns: Sequence[str] = (),
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Replacement for ``…selectFrom(t).where(col,'=',val).execute()``."""
        ns = table_attr_namespace(table_name)
        clause = f"[?e :{ns}/{_kebab(column)} {edn_val(value)}]"
        return self._select_by_clause(table_name, clause, columns, limit)

    def select_first_where(
        self, table_name: str, column: str, value: Any, columns: Sequence[str] = (),
    ) -> dict[str, Any] | None:
        """Replacement for ``…where(col,'=',val).limit(1).executeTakeFirst()``."""
        rows = self.select_where(table_name, column, value, columns, limit=1)
        return rows[0] if rows else None

    def aggregate_where(
        self,
        table_name: str,
        fn: str,
        column: str,
        where_column: str | None = None,
        where_value: Any = None,
    ) -> float:
        """Replacement for ``…select(fn(col)).where(w,'=',v).executeTakeFirst()``.

        ``fn`` ∈ count|sum|max|min|avg. Returns the scalar (0 when no rows).
        """
        ns = table_attr_namespace(table_name)
        clauses: list[str] = []
        agg_expr = "(count ?e)" if (fn == "count" and column == "*") else f"({fn} ?v)"
        if column != "*":
            clauses.append(f"[?e :{ns}/{_kebab(column)} ?v]")
        if where_column is not None:
            clauses.append(f"[?e :{ns}/{_kebab(where_column)} {edn_val(where_value)}]")
        if not clauses:
            clauses.append(f"[?e {identity_attr(table_name)} _]")
        query = f"[:find {agg_expr} :where {' '.join(clauses)}]"
        raw = self.q(query, graph=self.graph)
        first = raw[0] if isinstance(raw, list) and raw else None
        scalar = first[0] if isinstance(first, (list, tuple)) and first else first
        try:
            return float(scalar) if scalar is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _select_by_clause(
        self, table_name: str, where_clause: str, columns: Sequence[str], limit: int,
    ) -> list[dict[str, Any]]:
        ns = table_attr_namespace(table_name)
        sel_attrs = [f":{ns}/{_kebab(c)}" for c in columns] if columns else ["*"]
        selector = "[" + " ".join(sel_attrs) + "]"
        query = f"[:find (pull ?e {selector}) :where {where_clause}]"
        raw = self.q(query, graph=self.graph)
        rows: list[dict[str, Any]] = []
        prefix = f":{ns}/"
        for item in raw[: max(1, min(int(limit or 100), 1000))]:
            ent = item[0] if isinstance(item, (list, tuple)) and item else item
            if not isinstance(ent, Mapping):
                continue
            row = {}
            for k, v in ent.items():
                key = str(k)
                col = key[len(prefix):] if key.startswith(prefix) else key.lstrip(":")
                row[col.replace("-", "_")] = v
            rows.append(row)
        return rows


_DEFAULT_CLIENT: KotobaDatomicClient | None = None


def get_kotoba_client() -> KotobaDatomicClient:
    """Process-wide default client (lazy). Mirrors ``ensure_rw_async_pool`` ergonomics."""
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = KotobaDatomicClient()
    return _DEFAULT_CLIENT
