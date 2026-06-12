"""yatabase integrated storage autonomous primitives.

Pyzeebe task types:
  yata.storage.metering.rollup
  yata.storage.embedding.drain
  yata.storage.tier.migrate
  yata.storage.multipart.reap
  yata.database.provision
  yata.storage.put
  yata.storage.get
  yata.storage.delete
  yata.storage.presign
  yata.sparql.run
  yata.cypher.run
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import datetime as _dt
import hashlib
import time
from typing import Any



YATA_DID = "did:web:yatabase.etzhayyim.com"
JPY_MICRO = 1_000_000
STORAGE_GB_HOUR_PRICE_JPY_MICRO = round(10 * JPY_MICRO / (30 * 24))


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_ts() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return _dt.datetime.now(tz=_dt.UTC).date().isoformat()


def _event_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]
    return f"at://did:web:billing.etzhayyim.com/com.etzhayyim.apps.billing.event/{digest}"


def _object_id(bucket: str, key: str, version: str = "") -> str:
    digest = hashlib.sha256(f"{bucket}|{key}|{version}".encode()).hexdigest()[:32]
    return f"at://did:web:yatabase.etzhayyim.com/com.etzhayyim.apps.yata.blob/{digest}"


async def task_yata_database_provision(**kwargs: Any) -> dict[str, Any]:
    org_did = kwargs["orgDid"]
    plan = kwargs.get("plan") or "free"
    region = kwargs.get("region") or "nrt"
    db_name = "yata_" + hashlib.sha256(org_did.encode()).hexdigest()[:16]
    pg_user = db_name + "_rw"
    now = _now_ts()
    today = _today()
    vertex_id = f"at://did:web:yatabase.etzhayyim.com/com.etzhayyim.apps.yata.database/{db_name}"

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_yata_database (
                vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                db_name, org_did, cluster_id, region, plan,
                pg_user, pg_password_hash, provisioned_at, status,
                created_at, org_id, user_id, actor_id
            ) VALUES (
                %s, NULL, %s, 2, %s,
                %s, %s, %s, %s, %s,
                %s, '', %s, 'active',
                %s, %s, %s, %s
            )
            ON CONFLICT (vertex_id) DO NOTHING
            """,
            (
                vertex_id, today, YATA_DID,
                db_name, org_did, kwargs.get("clusterId") or "rw-primary", region, plan,
                pg_user, now, now, org_did, org_did, "yata.database.provision",
            ),
        )

    return {"dbName": db_name, "pgUser": pg_user, "status": "active"}


async def task_yata_storage_put(**kwargs: Any) -> dict[str, Any]:
    # BPMN ioMapping uses `bucketName`/`objectKey`; legacy callers used
    # `bucket`/`key`. Accept both for compatibility.
    bucket = kwargs.get("bucketName") or kwargs.get("bucket") or ""
    key = kwargs.get("objectKey") or kwargs.get("key") or ""
    if not bucket or not key:
        raise ValueError("bucketName/objectKey required")
    org_did = kwargs["orgDid"]
    size_bytes = int(kwargs.get("sizeBytes") or 0)
    content_type = kwargs.get("contentType") or "application/octet-stream"
    etag = kwargs.get("etag") or hashlib.sha256(f"{bucket}|{key}|{size_bytes}|{_now_ms()}".encode()).hexdigest()
    storage_tier = kwargs.get("storageTier") or "warm"
    provider = kwargs.get("storageProvider") or "b2"
    storage_path = kwargs.get("storagePath") or f"{org_did}/{bucket}/{key}"
    object_id = _object_id(bucket, key, etag)
    now = _now_ts()

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_yata_blob (
                vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                bucket_id, bucket_name, org_did, object_key, version_id,
                size_bytes, content_type, etag, cid, storage_tier,
                storage_provider, storage_path, encryption, is_delete_marker,
                checksum_sha256, uploaded_by_did, last_accessed_at,
                embedding_status, tag_status, status,
                created_at, org_id, user_id, actor_id
            ) VALUES (
                %s, NULL, %s, 2, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, NULL, %s,
                %s, %s, 'managed', false,
                %s, %s, %s,
                'pending', 'pending', 'active',
                %s, %s, %s, %s
            )
            """,
            (
                object_id, _today(), YATA_DID,
                bucket, bucket, org_did, key, etag,
                size_bytes, content_type, etag, storage_tier,
                provider, storage_path, kwargs.get("checksumSha256"),
                kwargs.get("uploadedByDid") or org_did, now,
                now, org_did, org_did, "yata.storage.put",
            ),
        )

    return {
        "ok": True,
        "blobId": object_id,
        "etag": etag,
        "cid": etag,
        "sizeBytes": size_bytes,
        "storageTier": storage_tier,
        "storageProvider": provider,
        "versionId": etag,
        "objectId": object_id,
    }


async def task_yata_storage_get(**kwargs: Any) -> dict[str, Any]:
    bucket = kwargs["bucket"]
    key = kwargs["key"]
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            SELECT vertex_id, size_bytes, content_type, etag, storage_provider, storage_path
            FROM vertex_yata_blob
            WHERE bucket_name = %s AND object_key = %s AND status = 'active' AND is_delete_marker = false
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (bucket, key),
        )
        row = (_res[0] if _res else None)
    if not row:
        raise ValueError("object-not-found")
    object_id, size_bytes, content_type, etag, provider, storage_path = row
    return {
        "objectId": object_id,
        "sizeBytes": int(size_bytes or 0),
        "contentType": content_type,
        "etag": etag,
        "storageProvider": provider,
        "storagePath": storage_path,
    }


async def task_yata_storage_delete(**kwargs: Any) -> dict[str, Any]:
    bucket = kwargs["bucket"]
    key = kwargs["key"]
    now = _now_ts()
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            UPDATE vertex_yata_blob
            SET status = 'deleted', is_delete_marker = true, last_accessed_at = %s
            WHERE bucket_name = %s AND object_key = %s AND status = 'active'
            """,
            (now, bucket, key),
        )
    return {"deleted": True, "bucket": bucket, "key": key}


async def task_yata_storage_presign(**kwargs: Any) -> dict[str, Any]:
    bucket = kwargs["bucket"]
    key = kwargs["key"]
    expires_in = int(kwargs.get("expiresIn") or 3600)
    token = hashlib.sha256(f"{bucket}|{key}|{_now_ms()}|{expires_in}".encode()).hexdigest()
    return {
        "url": f"https://yatabase.etzhayyim.com/storage/v1/object/sign/{bucket}/{key}?token={token}",
        "expiresIn": expires_in,
    }


async def task_yata_sparql_run(**kwargs: Any) -> dict[str, Any]:
    query = kwargs.get("query") or ""
    if not query.strip():
        raise ValueError("query required")
    return {"rows": [], "columns": [], "deferred": True}


_CYPHER_LABEL_TO_TABLE_OVERRIDE: dict[str, str] = {
    # Override map intentionally empty — customer-facing tenants use
    # `vertex_<snake_case(Label)>` uniformly so what they CREATE is what
    # they MATCH. Internal etzhayyim mappings (Person→vertex_natural_person,
    # Organization→vertex_legal_entity) live in the public schema and
    # are not exposed via the tenant Cypher path.
}


def _tenant_schema(org_did: str) -> str:
    """Return the per-tenant schema name `yata_<sha256(did)[:16]>`.

    Note: ADR-2605080000 §D8 originally specified "RW database per org" but
    RisingWave 2.8 does not support `CREATE DATABASE` (returns "Failed to run
    the query"). Schema-level isolation is the only feasible option today.
    Schema name = ADR §D8 db name → safe rename, GRANT USAGE per ROLE
    enforces the same boundary.
    """
    return "yata_" + hashlib.sha256(org_did.encode()).hexdigest()[:16]


_PROVISIONED_SCHEMAS: set[str] = set()


def _ensure_tenant_schema(org_did: str) -> str:
    """Idempotent CREATE SCHEMA + seed `vertex_demo` row.

    Caches the schema name in `_PROVISIONED_SCHEMAS` so subsequent calls
    skip the round-trip. Cache loss (pod restart) just re-runs the
    `IF NOT EXISTS` DDL.
    """
    schema = _tenant_schema(org_did)
    if schema in _PROVISIONED_SCHEMAS:
        return schema
    if True:
        client = get_kotoba_client()
        _res = client.q(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        _res = client.q(
            f'CREATE TABLE IF NOT EXISTS "{schema}".vertex_demo ('
            f"  vertex_id varchar PRIMARY KEY,"
            f"  name varchar,"
            f"  created_at varchar"
            f")",
        )
        # Idempotent INSERT — RW does not support ON CONFLICT but
        # vertex_id PK swallows duplicates with implicit upsert (per
        # ADR-0036 invariant; same INSERT no-ops on existing PK).
        _res = client.q(
            f'INSERT INTO "{schema}".vertex_demo (vertex_id, name, created_at) VALUES (%s, %s, %s)',
            (
                f"at://{org_did}/com.etzhayyim.apps.yata.demo/welcome",
                "Welcome to your yatabase tenant",
                _dt.datetime.now(tz=_dt.UTC).isoformat(),
            ),
        )
    _PROVISIONED_SCHEMAS.add(schema)
    return schema


def _camel_to_snake(name: str) -> str:
    out = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0 and not name[i - 1].isupper():
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _cypher_label_to_table(label: str) -> str:
    if label in _CYPHER_LABEL_TO_TABLE_OVERRIDE:
        return _CYPHER_LABEL_TO_TABLE_OVERRIDE[label]
    return f"vertex_{_camel_to_snake(label)}"


_CYPHER_VALUE_RE = r"(\$[A-Za-z_]\w*|'(?:[^'\\]|\\.)*'|-?\d+(?:\.\d+)?|true|false|null)"


def _resolve_cypher_value(token: str, parameters: dict[str, Any]) -> Any:
    """Convert a Cypher literal token into a Python SQL parameter value."""
    t = token.strip()
    if t.startswith("$"):
        pname = t[1:]
        if pname not in parameters:
            raise ValueError(f"missing parameter ${pname}")
        return parameters[pname]
    if t.startswith("'") and t.endswith("'"):
        return t[1:-1].replace("\\'", "'")
    if t in ("true", "false"):
        return t == "true"
    if t == "null":
        return None
    if "." in t:
        return float(t)
    return int(t)


def _translate_cypher_create_to_sql(  # noqa: C901
    statement: str,
    parameters: dict[str, Any],
    schema: str | None = None,
) -> tuple[str, list[Any], list[str], dict[str, Any], str]:
    """Translate `CREATE (var:Label {k: v, ...}) [RETURN ...]` to RW INSERT.

    Returns (sql, sql_params, column_names_for_return, payload_for_echo).
    `payload_for_echo` is the row dict (used for RETURN n / RETURN n.prop responses
    when RW does not honour RETURNING — we echo the input so the wire shape
    matches Neo4j parity).
    """
    import re

    s = " ".join(statement.split()).strip().rstrip(";")

    # CREATE (var:Label { ... })
    m = re.match(
        r"^CREATE\s*\(\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)\s*(\{[^}]*\})?\s*\)\s*(RETURN\b.*)?$",
        s,
        re.IGNORECASE,
    )
    if not m:
        raise ValueError(
            "P4a CREATE subset: only `CREATE (var:Label {k: v, ...}) [RETURN var | var.prop ...]` is supported.",
        )
    var_name = m.group(1)
    label = m.group(2)
    props_text = (m.group(3) or "{}").strip()
    return_text = (m.group(4) or "").strip()
    table_basename = _cypher_label_to_table(label)
    table = f'"{schema}".{table_basename}' if schema else table_basename

    # Parse `{ k: v, k: v }` — comma-separated, top-level only
    body = props_text[1:-1].strip() if props_text.startswith("{") else ""
    cols: list[str] = []
    vals: list[Any] = []
    payload: dict[str, Any] = {}
    if body:
        for pair in re.split(r"\s*,\s*(?![^{]*\})", body):
            mp = re.match(rf"^([A-Za-z_]\w*)\s*:\s*{_CYPHER_VALUE_RE}\s*$", pair.strip())
            if not mp:
                raise ValueError(f"unsupported property pair: {pair!r}")
            k, raw_v = mp.group(1), mp.group(2)
            v = _resolve_cypher_value(raw_v, parameters)
            cols.append(k)
            vals.append(v)
            payload[k] = v

    if not cols:
        raise ValueError("CREATE requires at least one property")

    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ", ".join(cols)
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

    # RETURN parsing — names only used for response shaping; SQL has no RETURNING.
    column_names: list[str] = []
    if return_text:
        ret = return_text[len("RETURN"):].strip()
        if ret == var_name:
            column_names = list(payload.keys())
        else:
            for item in [it.strip() for it in ret.split(",") if it.strip()]:
                m_ret = re.match(
                    rf"^{re.escape(var_name)}\.([A-Za-z_]\w*)(?:\s+AS\s+([A-Za-z_]\w*))?$",
                    item,
                    re.IGNORECASE,
                )
                if not m_ret:
                    raise ValueError(f"unsupported RETURN item: {item!r}")
                column_names.append(m_ret.group(2) or m_ret.group(1))
    return sql, vals, column_names, payload, label


def _ensure_vertex_table(schema: str, label: str, columns: list[str]) -> str:
    """Idempotent CREATE TABLE for `vertex_<label>` in tenant schema.

    Uses the column list from the first CREATE to seed the table. Treats
    `vertex_id` as the implicit primary key when present in the column
    list; otherwise the first column is the PK. Subsequent CREATEs that
    reference unknown columns will fail at INSERT time — the customer
    can ALTER TABLE manually or use the existing `vertex_<label>` shape.
    """
    table_name = _cypher_label_to_table(label)
    cache_key = f"{schema}.{table_name}"
    if cache_key in _PROVISIONED_SCHEMAS:
        return table_name
    if not columns:
        # Defensive: caller must pass at least one column.
        return table_name
    # Build column DDL. Prefer vertex_id as PK if present.
    pk = "vertex_id" if "vertex_id" in columns else columns[0]
    col_ddl = []
    for c in columns:
        if c == pk:
            col_ddl.append(f'"{c}" varchar PRIMARY KEY')
        else:
            col_ddl.append(f'"{c}" varchar')
    # Always add a `_created_at` audit column if customer didn't supply one.
    if "created_at" not in columns:
        col_ddl.append('"_created_at" varchar')
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f'CREATE TABLE IF NOT EXISTS "{schema}".{table_name} (' + ", ".join(col_ddl) + ")",
        )
    _PROVISIONED_SCHEMAS.add(cache_key)
    return table_name


def _ensure_edge_table(schema: str, edge_type: str) -> str:
    """Idempotent CREATE TABLE for `edge_<type>` in tenant schema.

    Edge schema: (from_id varchar, to_id varchar, created_at varchar,
    PRIMARY KEY (from_id, to_id)). Composite PK lets the same pair only
    exist once — duplicate INSERTs are silent no-ops via RW PK upsert.
    """
    table_name = f"edge_{edge_type.lower()}"
    cache_key = f"{schema}.{table_name}"
    if cache_key in _PROVISIONED_SCHEMAS:
        return table_name
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f'CREATE TABLE IF NOT EXISTS "{schema}".{table_name} ('
            f"  from_id varchar,"
            f"  to_id varchar,"
            f"  created_at varchar,"
            f"  PRIMARY KEY (from_id, to_id)"
            f")",
        )
    _PROVISIONED_SCHEMAS.add(cache_key)
    return table_name


def _translate_cypher_match_edge_to_sql(  # noqa: C901
    statement: str,
    parameters: dict[str, Any],
    default_limit: int = 1000,
    schema: str | None = None,
) -> tuple[str, list[Any], list[str]]:
    """Translate `MATCH (a:L1)-[:R]->(b:L2) [WHERE ...] RETURN ...` to JOIN.

    Supports the single-hop directed edge form for both directions:
        (a:L1)-[:R]->(b:L2)        — out-edge from a to b
        (a:L1)<-[:R]-(b:L2)         — in-edge to a from b
    WHERE clause and RETURN list use either alias.
    """
    import re

    s = " ".join(statement.split()).strip().rstrip(";")

    # Detect edge pattern.
    m = re.match(
        r"^MATCH\s*"
        r"\(\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)\s*\)\s*"
        r"(<?-)\[\s*:\s*([A-Za-z_]\w*)\s*\](-)(>?)\s*"
        r"\(\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)\s*\)\s*"
        r"(.*)$",
        s,
        re.IGNORECASE,
    )
    if not m:
        raise ValueError(
            "P4a edge subset: only `MATCH (a:L1)-[:R]->(b:L2) [WHERE ...] RETURN ...` "
            "or the reverse direction `<-[:R]-` is supported.",
        )

    a_var, a_label, lhs, rel_type, _rhs_dash, rhs_arrow, b_var, b_label, rest = m.groups()
    if lhs == "<-":
        # b → a
        from_var, to_var = b_var, a_var
    elif rhs_arrow == ">":
        # a → b
        from_var, to_var = a_var, b_var
    else:
        raise ValueError("edge direction required: use `->` or `<-`")

    table_a = _cypher_label_to_table(a_label)
    table_b = _cypher_label_to_table(b_label)
    edge_table = f"edge_{rel_type.lower()}"
    qa = f'"{schema}".{table_a}' if schema else table_a
    qb = f'"{schema}".{table_b}' if schema else table_b
    qe = f'"{schema}".{edge_table}' if schema else edge_table

    # Optional WHERE + RETURN clauses.
    where_sql = ""
    where_params: list[Any] = []
    rest = rest.strip()
    where_match = re.match(r"^WHERE\s+(.*?)\s+RETURN\s+", rest, re.IGNORECASE)
    if where_match:
        where_text = where_match.group(1).strip()
        rest = rest[where_match.end() - len("RETURN "):]

        def replace_pred(token: str) -> tuple[str, list[Any]]:
            mp = re.match(
                rf"^([A-Za-z_]\w*)\.([A-Za-z_]\w*)\s*(=|<>|<=|>=|<|>)\s*{_CYPHER_VALUE_RE}$",
                token.strip(),
            )
            if not mp:
                raise ValueError(f"unsupported WHERE predicate: {token!r}")
            var, prop, op, raw_v = mp.group(1), mp.group(2), mp.group(3), mp.group(4)
            if var not in (a_var, b_var):
                raise ValueError(f"unknown alias in WHERE: {var}")
            v = _resolve_cypher_value(raw_v, parameters)
            return f"{var}.{prop} {op} %s", [v]

        chunks = re.split(r"\s+(AND|OR)\s+", where_text, flags=re.IGNORECASE)
        parts: list[str] = []
        for i, chunk in enumerate(chunks):
            if i % 2 == 1:
                parts.append(chunk.upper())
            else:
                sql_part, p_part = replace_pred(chunk)
                parts.append(sql_part)
                where_params.extend(p_part)
        where_sql = " WHERE " + " ".join(parts)

    if not rest.upper().startswith("RETURN"):
        raise ValueError("RETURN clause required for edge match")
    rest = rest[len("RETURN"):].strip()

    # Strip LIMIT
    limit_val: int | None = None
    m_lim = re.search(r"\s+LIMIT\s+(\d+)\s*$", rest, re.IGNORECASE)
    if m_lim:
        limit_val = int(m_lim.group(1))
        rest = rest[: m_lim.start()]
    return_text = rest.strip().rstrip(";").strip()
    if not return_text:
        raise ValueError("empty RETURN list")

    select_cols: list[str] = []
    column_names: list[str] = []
    for item in [it.strip() for it in return_text.split(",") if it.strip()]:
        m_alias = re.match(
            r"^([A-Za-z_]\w*)\.([A-Za-z_]\w*)(?:\s+AS\s+([A-Za-z_]\w*))?$",
            item,
            re.IGNORECASE,
        )
        if not m_alias:
            raise ValueError(f"unsupported RETURN item: {item!r}")
        var, prop, alias = m_alias.group(1), m_alias.group(2), m_alias.group(3)
        if var not in (a_var, b_var):
            raise ValueError(f"unknown alias in RETURN: {var}")
        if alias:
            select_cols.append(f"{var}.{prop} AS {alias}")
            column_names.append(alias)
        else:
            select_cols.append(f"{var}.{prop} AS {var}_{prop}")
            column_names.append(f"{var}.{prop}")

    sql = (
        f"SELECT {', '.join(select_cols)} FROM {qa} {a_var} "
        f"INNER JOIN {qe} e ON e.from_id = {from_var}.vertex_id "
        f"INNER JOIN {qb} {b_var} ON e.to_id = {to_var}.vertex_id"
        f"{where_sql}"
    )
    sql += f" LIMIT {limit_val if limit_val is not None else default_limit}"
    return sql, where_params, column_names


def _translate_cypher_create_edge_to_sql(
    statement: str,
    parameters: dict[str, Any],
    schema: str | None = None,
) -> tuple[str, list[Any], str]:
    """Translate `MATCH (a:L1{pk:v}),(b:L2{pk:v}) CREATE (a)-[:R]->(b)`.

    Returns (sql, params, edge_type). The Python executor calls
    `_ensure_edge_table(schema, edge_type)` first, then runs this SQL.
    """
    import re

    s = " ".join(statement.split()).strip().rstrip(";")
    m = re.match(
        r"^MATCH\s*"
        r"\(\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)\s*\{([^}]*)\}\s*\)\s*,\s*"
        r"\(\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)\s*\{([^}]*)\}\s*\)\s*"
        r"CREATE\s*"
        r"\(\s*\1\s*\)\s*-\s*\[\s*:\s*([A-Za-z_]\w*)\s*\]\s*->\s*\(\s*\4\s*\)\s*$",
        s,
        re.IGNORECASE,
    )
    if not m:
        raise ValueError(
            "P4a CREATE edge subset: only "
            "`MATCH (a:L1{pk:v}),(b:L2{pk:v}) CREATE (a)-[:R]->(b)` is supported.",
        )
    a_var, a_label, a_body, b_var, b_label, b_body, rel_type = m.groups()

    def parse_match_body(body: str) -> tuple[str, Any]:
        body = body.strip()
        mp = re.match(rf"^([A-Za-z_]\w*)\s*:\s*{_CYPHER_VALUE_RE}\s*$", body)
        if not mp:
            raise ValueError(f"CREATE edge: each side requires a single PK match {body!r}")
        return mp.group(1), _resolve_cypher_value(mp.group(2), parameters)

    a_pk_col, a_pk_val = parse_match_body(a_body)
    b_pk_col, b_pk_val = parse_match_body(b_body)

    table_a = _cypher_label_to_table(a_label)
    table_b = _cypher_label_to_table(b_label)
    edge_table = f"edge_{rel_type.lower()}"
    qa = f'"{schema}".{table_a}' if schema else table_a
    qb = f'"{schema}".{table_b}' if schema else table_b
    qe = f'"{schema}".{edge_table}' if schema else edge_table

    # Two-step: SELECT vertex_ids first (returns the actual canonical
    # vertex_ids of the matched nodes), then INSERT into edge_<r>. Avoids
    # the silent-no-op of `INSERT...SELECT` when RW eventual consistency
    # hasn't caught up yet — the SELECT returning empty is now an explicit
    # error rather than an INSERT 0.
    select_sql = (
        f"SELECT a.vertex_id AS a_id, b.vertex_id AS b_id "
        f"FROM {qa} a, {qb} b "
        f"WHERE a.{a_pk_col} = %s AND b.{b_pk_col} = %s LIMIT 1"
    )
    insert_sql = (
        f"INSERT INTO {qe} (from_id, to_id, created_at) VALUES (%s, %s, %s)"
    )
    # Caller (executor) executes select_sql + insert_sql in a single
    # connection. We pack both into the returned `sql` field as a tuple
    # marker so the executor knows to handle this two-step path.
    return f"__TWO_STEP__\n{select_sql}\n--\n{insert_sql}", [a_pk_val, b_pk_val, _now_ts()], rel_type


def _translate_cypher_set_to_sql(
    statement: str,
    parameters: dict[str, Any],
    schema: str | None = None,
) -> tuple[str, list[Any], list[str], list[str]]:
    """Translate `MATCH (var:Label {k: v, ...}) SET var.prop = expr [, ...] [RETURN ...]`.

    Returns (sql, sql_params_for_set_then_where, return_columns, set_keys).
    `set_keys` lets the caller pre-build the echo payload in case RETURN
    references the updated columns (RW lacks RETURNING).
    """
    import re

    s = " ".join(statement.split()).strip().rstrip(";")
    # MATCH (var:Label {k: v, ...}) SET var.prop = expr [, ...] [RETURN ...]
    m = re.match(
        r"^MATCH\s*\(\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)\s*\{([^}]*)\}\s*\)\s*SET\s+(.*?)(\s+RETURN\b.*)?$",
        s,
        re.IGNORECASE,
    )
    if not m:
        raise ValueError(
            "P4a SET subset: only `MATCH (var:Label {k: v, ...}) SET var.prop = expr [, ...] [RETURN ...]` is supported.",
        )
    var_name = m.group(1)
    label = m.group(2)
    where_body = m.group(3).strip()
    set_body = m.group(4).strip()
    return_text = (m.group(5) or "").strip()

    table_basename = _cypher_label_to_table(label)
    table = f'"{schema}".{table_basename}' if schema else table_basename

    # Parse WHERE { k: v, k: v }
    where_clauses: list[str] = []
    where_params: list[Any] = []
    if not where_body:
        raise ValueError("SET requires at least one match property (no full-table updates)")
    for pair in re.split(r"\s*,\s*(?![^{]*\})", where_body):
        mp = re.match(rf"^([A-Za-z_]\w*)\s*:\s*{_CYPHER_VALUE_RE}\s*$", pair.strip())
        if not mp:
            raise ValueError(f"unsupported match property: {pair!r}")
        k, raw_v = mp.group(1), mp.group(2)
        v = _resolve_cypher_value(raw_v, parameters)
        where_clauses.append(f"{k} = %s")
        where_params.append(v)

    # Parse SET clause: `var.prop = expr [, var.prop = expr ...]`
    set_clauses: list[str] = []
    set_params: list[Any] = []
    set_keys: list[str] = []
    for assign in re.split(r"\s*,\s*(?![^{]*\})", set_body):
        ma = re.match(
            rf"^{re.escape(var_name)}\.([A-Za-z_]\w*)\s*=\s*{_CYPHER_VALUE_RE}\s*$",
            assign.strip(),
        )
        if not ma:
            raise ValueError(f"unsupported SET assignment: {assign!r}")
        k, raw_v = ma.group(1), ma.group(2)
        v = _resolve_cypher_value(raw_v, parameters)
        set_clauses.append(f"{k} = %s")
        set_params.append(v)
        set_keys.append(k)

    if not set_clauses:
        raise ValueError("SET requires at least one assignment")

    sql = (
        f"UPDATE {table} SET {', '.join(set_clauses)} "
        f"WHERE {' AND '.join(where_clauses)}"
    )
    sql_params = set_params + where_params

    # RETURN parsing — column name list only.
    return_columns: list[str] = []
    if return_text:
        ret = return_text[len("RETURN"):].strip()
        if ret == var_name:
            # whole-row RETURN — caller will fall back to a follow-up SELECT
            return_columns = ["*"]
        else:
            for item in [it.strip() for it in ret.split(",") if it.strip()]:
                m_ret = re.match(
                    rf"^{re.escape(var_name)}\.([A-Za-z_]\w*)(?:\s+AS\s+([A-Za-z_]\w*))?$",
                    item,
                    re.IGNORECASE,
                )
                if not m_ret:
                    raise ValueError(f"unsupported RETURN item: {item!r}")
                return_columns.append(m_ret.group(2) or m_ret.group(1))
    return sql, sql_params, return_columns, set_keys


def _translate_cypher_delete_to_sql(
    statement: str,
    parameters: dict[str, Any],
    schema: str | None = None,
) -> tuple[str, list[Any]]:
    """Translate `MATCH (var:Label {k: v, ...}) DELETE var` to RW DELETE.

    Returns (sql, sql_params).
    """
    import re

    s = " ".join(statement.split()).strip().rstrip(";")
    m = re.match(
        rf"^MATCH\s*\(\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)\s*\{{([^}}]*)\}}\s*\)\s*DELETE\s+\1\s*$",
        s,
        re.IGNORECASE,
    )
    if not m:
        raise ValueError(
            "P4a DELETE subset: only `MATCH (var:Label {k: v, ...}) DELETE var` is supported.",
        )
    label = m.group(2)
    body = m.group(3).strip()
    table_basename = _cypher_label_to_table(label)
    table = f'"{schema}".{table_basename}' if schema else table_basename

    where_clauses: list[str] = []
    where_params: list[Any] = []
    if not body:
        raise ValueError("DELETE requires at least one match property to scope the delete")
    for pair in re.split(r"\s*,\s*(?![^{]*\})", body):
        mp = re.match(rf"^([A-Za-z_]\w*)\s*:\s*{_CYPHER_VALUE_RE}\s*$", pair.strip())
        if not mp:
            raise ValueError(f"unsupported property pair: {pair!r}")
        k, raw_v = mp.group(1), mp.group(2)
        v = _resolve_cypher_value(raw_v, parameters)
        where_clauses.append(f"{k} = %s")
        where_params.append(v)

    sql = f"DELETE FROM {table} WHERE " + " AND ".join(where_clauses)
    return sql, where_params


def _translate_cypher_to_sql(  # noqa: C901
    statement: str,
    parameters: dict[str, Any],
    default_limit: int = 1000,
    schema: str | None = None,
) -> tuple[str, list[Any], list[str]]:
    """Translate a minimal openCypher subset to a single RisingWave SELECT.

    Supported (P4a):
        MATCH (var:Label)
        [WHERE var.prop {= | <> | < | <= | > | >=} ($param | 'literal' | <int>)
               [(AND | OR) ...]]
        RETURN (var | var.prop [AS alias] [, ...])
        [ORDER BY var.prop [ASC|DESC]]
        [SKIP <int>]
        [LIMIT <int>]

    Anything else raises ValueError so the caller surfaces a 400.
    Returns (sql, sql_params_in_order, column_names).
    """
    import re

    s = " ".join(statement.split()).strip().rstrip(";")

    # MATCH (var:Label)
    m_match = re.match(r"^MATCH\s*\(\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)\s*\)\s*", s, re.IGNORECASE)
    if not m_match:
        raise ValueError(
            "P4a Cypher subset: only `MATCH (var:Label) [WHERE ...] RETURN ... [LIMIT N]` is supported.",
        )
    var_name = m_match.group(1)
    label = m_match.group(2)
    table_basename = _cypher_label_to_table(label)
    table = f'"{schema}".{table_basename}' if schema else table_basename
    rest = s[m_match.end():].strip()

    # Optional WHERE clause: terminate at RETURN
    where_sql = ""
    where_params: list[Any] = []
    where_match = re.match(r"^WHERE\s+(.*?)\s+RETURN\s+", rest, re.IGNORECASE)
    if where_match:
        where_text = where_match.group(1).strip()
        rest = rest[where_match.end() - len("RETURN "):]
        # Replace `var.prop OP value` tokens. value can be $param, 'literal', or integer.
        def replace_pred(token: str) -> tuple[str, list[Any]]:
            m = re.match(
                rf"^{re.escape(var_name)}\.([A-Za-z_]\w*)\s*(=|<>|<=|>=|<|>)\s*(\$[A-Za-z_]\w*|'[^']*'|-?\d+)$",
                token.strip(),
            )
            if not m:
                raise ValueError(f"unsupported WHERE predicate: {token!r}")
            prop, op, val = m.group(1), m.group(2), m.group(3)
            if val.startswith("$"):
                pname = val[1:]
                if pname not in parameters:
                    raise ValueError(f"missing parameter ${pname}")
                return f"{prop} {op} %s", [parameters[pname]]
            if val.startswith("'") and val.endswith("'"):
                return f"{prop} {op} %s", [val[1:-1]]
            return f"{prop} {op} %s", [int(val)]

        # AND / OR splitter (no parens support).
        chunks = re.split(r"\s+(AND|OR)\s+", where_text, flags=re.IGNORECASE)
        # chunks: [pred, conn, pred, conn, pred, ...]
        where_parts: list[str] = []
        for i, chunk in enumerate(chunks):
            if i % 2 == 1:
                where_parts.append(chunk.upper())
            else:
                sql_part, p_part = replace_pred(chunk)
                where_parts.append(sql_part)
                where_params.extend(p_part)
        where_sql = " WHERE " + " ".join(where_parts)
    else:
        # consume the leading RETURN literally below
        pass

    # RETURN clause
    rest = rest.lstrip()
    if not rest.upper().startswith("RETURN"):
        raise ValueError("RETURN clause required")
    rest = rest[len("RETURN"):].strip()

    # Strip trailing LIMIT / SKIP / ORDER BY in reverse so RETURN list is
    # whatever remains.
    limit_val: int | None = None
    skip_val: int | None = None
    order_sql = ""

    m_lim = re.search(r"\s+LIMIT\s+(\d+)\s*$", rest, re.IGNORECASE)
    if m_lim:
        limit_val = int(m_lim.group(1))
        rest = rest[: m_lim.start()]

    m_skip = re.search(r"\s+SKIP\s+(\d+)\s*$", rest, re.IGNORECASE)
    if m_skip:
        skip_val = int(m_skip.group(1))
        rest = rest[: m_skip.start()]

    m_order = re.search(
        rf"\s+ORDER\s+BY\s+{re.escape(var_name)}\.([A-Za-z_]\w*)(?:\s+(ASC|DESC))?\s*$",
        rest,
        re.IGNORECASE,
    )
    if m_order:
        order_prop = m_order.group(1)
        order_dir = (m_order.group(2) or "ASC").upper()
        order_sql = f" ORDER BY {order_prop} {order_dir}"
        rest = rest[: m_order.start()]

    return_text = rest.strip().rstrip(";").strip()
    if not return_text:
        raise ValueError("empty RETURN list")

    # Split RETURN items by comma (top-level only — no nested fns).
    return_items = [it.strip() for it in return_text.split(",") if it.strip()]
    select_cols: list[str] = []
    column_names: list[str] = []
    for item in return_items:
        # Allow `var` (return the whole row), `var.prop`, `var.prop AS alias`.
        if item == var_name:
            select_cols.append("*")
            column_names.append(var_name)
            continue
        m_alias = re.match(
            rf"^{re.escape(var_name)}\.([A-Za-z_]\w*)(?:\s+AS\s+([A-Za-z_]\w*))?$",
            item,
            re.IGNORECASE,
        )
        if not m_alias:
            raise ValueError(f"unsupported RETURN item: {item!r}")
        prop = m_alias.group(1)
        alias = m_alias.group(2) or prop
        select_cols.append(prop if prop == alias else f"{prop} AS {alias}")
        column_names.append(alias)

    sql = f"SELECT {', '.join(select_cols)} FROM {table}{where_sql}{order_sql}"
    if limit_val is not None:
        sql += f" LIMIT {limit_val}"
    else:
        sql += f" LIMIT {default_limit}"
    if skip_val is not None:
        sql += f" OFFSET {skip_val}"
    return sql, where_params, column_names


async def task_yata_cypher_run(**kwargs: Any) -> dict[str, Any]:
    """openCypher → SQL/PGQ translator + execute (ADR-2605080000 §D13).

    P4a impl: minimal `MATCH (n:Label) [WHERE ...] RETURN ... [LIMIT N]`
    subset. Cypher labels map to RW vertex tables via
    `_cypher_label_to_table` (`vertex_<snake_label>` default + override map).
    Per-tenant DB routing (`yata_<sha256(did)[:16]>`) deferred to P4b.
    """
    statement = kwargs.get("statement") or ""
    if not statement.strip():
        raise ValueError("statement required")

    parameters_json = kwargs.get("parametersJson") or "{}"
    try:
        import json as _json
        parameters = _json.loads(parameters_json) if parameters_json else {}
    except Exception:
        parameters = {}
    if not isinstance(parameters, dict):
        parameters = {}

    limit_hint = kwargs.get("limit")
    default_limit = int(limit_hint) if isinstance(limit_hint, int) and limit_hint > 0 else 1000

    # Per-tenant schema routing (ADR-2605080000 §D8 schema variant).
    # `orgDid` is injected by the dispatcher trust layer and is the
    # authoritative tenant identifier — ignoring any caller-supplied
    # value for the schema mapping prevents cross-tenant escape.
    org_did = kwargs.get("orgDid") or ""
    tenant_schema: str | None = None
    if org_did:
        try:
            tenant_schema = _ensure_tenant_schema(org_did)
        except Exception as e:
            return {
                "ok": False,
                "rowCount": 0,
                "columnsJson": "[]",
                "rowsJson": "[]",
                "translatedSql": "",
                "elapsedMs": 0,
                "error": f"provision: {type(e).__name__}: {str(e)[:200]}",
            }

    started_ms = _now_ms()
    import json as _json
    import re as _re

    upper = statement.lstrip().upper()

    # ── CREATE edge branch (MATCH ... CREATE (a)-[:R]->(b)) ──
    if upper.startswith("MATCH") and "CREATE" in upper and _re.search(r"\)\s*-\s*\[\s*:", statement):
        try:
            sql, sql_params, rel_type = _translate_cypher_create_edge_to_sql(
                statement, parameters, schema=tenant_schema,
            )
        except Exception as e:
            return {
                "ok": False, "rowCount": 0, "columnsJson": "[]", "rowsJson": "[]",
                "translatedSql": "", "elapsedMs": _now_ms() - started_ms,
                "error": f"translate: {e}",
            }
        if tenant_schema:
            try:
                _ensure_edge_table(tenant_schema, rel_type)
            except Exception as e:
                return {
                    "ok": False, "rowCount": 0, "columnsJson": "[]", "rowsJson": "[]",
                    "translatedSql": sql, "elapsedMs": _now_ms() - started_ms,
                    "error": f"provision-edge: {type(e).__name__}: {str(e)[:200]}",
                }
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(f"SET statement_timeout = '20s'")
                if sql.startswith("__TWO_STEP__\n"):
                    parts = sql[len("__TWO_STEP__\n"):].split("\n--\n", 1)
                    select_sql, insert_sql = parts[0], parts[1]
                    a_pk, b_pk, edge_ts = sql_params
                    _res = client.q(select_sql, [a_pk, b_pk])
                    found = (_res[0] if _res else None)
                    if not found:
                        return {
                            "ok": False, "rowCount": 0, "columnsJson": "[]", "rowsJson": "[]",
                            "translatedSql": select_sql,
                            "elapsedMs": _now_ms() - started_ms,
                            "error": "edge create: one or both vertices not found (RW eventual consistency may need a few seconds after CREATE)",
                        }
                    a_vertex_id, b_vertex_id = found[0], found[1]
                    _res = client.q(insert_sql, [a_vertex_id, b_vertex_id, edge_ts])
                else:
                    _res = client.q(sql, sql_params)
        except Exception as e:
            return {
                "ok": False, "rowCount": 0, "columnsJson": "[]", "rowsJson": "[]",
                "translatedSql": sql, "elapsedMs": _now_ms() - started_ms,
                "error": f"execute: {type(e).__name__}: {str(e)[:200]}",
            }
        return {
            "ok": True, "rowCount": 1, "columnsJson": "[]", "rowsJson": "[]",
            "translatedSql": sql, "elapsedMs": _now_ms() - started_ms, "error": None,
        }

    # ── MATCH edge branch ((a:L1)-[:R]->(b:L2) [WHERE] RETURN ...) ──
    if upper.startswith("MATCH") and _re.search(r"\)\s*-?\s*\[\s*:\s*[A-Za-z_]\w*\s*\]\s*->", statement):
        try:
            sql, sql_params, columns = _translate_cypher_match_edge_to_sql(
                statement, parameters, default_limit, schema=tenant_schema,
            )
        except Exception as e:
            return {
                "ok": False, "rowCount": 0, "columnsJson": "[]", "rowsJson": "[]",
                "translatedSql": "", "elapsedMs": _now_ms() - started_ms,
                "error": f"translate: {e}",
            }
        rows: list[list[Any]] = []
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(f"SET statement_timeout = '20s'")
                _res = client.q(sql, sql_params)
                for raw in _res:
                    rows.append([_serialize_cell(c) for c in raw])
        except Exception as e:
            return {
                "ok": False, "rowCount": 0, "columnsJson": "[]", "rowsJson": "[]",
                "translatedSql": sql, "elapsedMs": _now_ms() - started_ms,
                "error": f"execute: {type(e).__name__}: {str(e)[:200]}",
            }
        return {
            "ok": True, "rowCount": len(rows),
            "columnsJson": _json.dumps(columns),
            "rowsJson": _json.dumps(rows, default=str),
            "translatedSql": sql, "elapsedMs": _now_ms() - started_ms, "error": None,
        }

    # ── CREATE branch ──
    if upper.startswith("CREATE"):
        try:
            sql, sql_params, columns, payload, create_label = _translate_cypher_create_to_sql(
                statement, parameters, schema=tenant_schema,
            )
        except Exception as e:
            return {
                "ok": False,
                "rowCount": 0,
                "columnsJson": "[]",
                "rowsJson": "[]",
                "translatedSql": "",
                "elapsedMs": _now_ms() - started_ms,
                "error": f"translate: {e}",
            }
        # Auto-create the vertex_<label> table if this is the first CREATE
        # against that label in the tenant. Uses payload keys as columns.
        if tenant_schema:
            try:
                _ensure_vertex_table(tenant_schema, create_label, list(payload.keys()))
            except Exception as e:
                return {
                    "ok": False, "rowCount": 0, "columnsJson": "[]", "rowsJson": "[]",
                    "translatedSql": sql, "elapsedMs": _now_ms() - started_ms,
                    "error": f"provision-vertex: {type(e).__name__}: {str(e)[:200]}",
                }
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(f"SET statement_timeout = '20s'")
                _res = client.q(sql, sql_params)
        except Exception as e:
            return {
                "ok": False,
                "rowCount": 0,
                "columnsJson": "[]",
                "rowsJson": "[]",
                "translatedSql": sql,
                "elapsedMs": _now_ms() - started_ms,
                "error": f"execute: {type(e).__name__}: {str(e)[:200]}",
            }
        # Echo the inserted row in Neo4j parity (RW lacks RETURNING).
        if columns:
            row = [payload.get(_camel_for_alias(c)) if c in payload else payload.get(c) for c in columns]
            rows_out = [[_serialize_cell(c) for c in row]]
        else:
            rows_out = []
        return {
            "ok": True,
            "rowCount": 1,
            "columnsJson": _json.dumps(columns),
            "rowsJson": _json.dumps(rows_out, default=str),
            "translatedSql": sql,
            "elapsedMs": _now_ms() - started_ms,
            "error": None,
        }

    # ── SET branch (MATCH ... SET var.prop = expr [RETURN]) ──
    if _re.search(r"\bSET\b", upper) and _re.search(r"\bMATCH\b", upper):
        try:
            sql, sql_params, ret_cols, set_keys = _translate_cypher_set_to_sql(
                statement, parameters, schema=tenant_schema,
            )
        except Exception as e:
            return {
                "ok": False,
                "rowCount": 0,
                "columnsJson": "[]",
                "rowsJson": "[]",
                "translatedSql": "",
                "elapsedMs": _now_ms() - started_ms,
                "error": f"translate: {e}",
            }
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(f"SET statement_timeout = '20s'")
                _res = client.q(sql, sql_params)
                # RisingWave UPDATE often returns rowcount=0 even on success
                # (deferred materialization); treat any non-error response as
                # 1 logical update. Real row count is verifiable via a follow-up
                # MATCH (RW eventual consistency window ~15-20s).
                updated = 1
        except Exception as e:
            return {
                "ok": False,
                "rowCount": 0,
                "columnsJson": "[]",
                "rowsJson": "[]",
                "translatedSql": sql,
                "elapsedMs": _now_ms() - started_ms,
                "error": f"execute: {type(e).__name__}: {str(e)[:200]}",
            }
        # Echo response: if RETURN n, return all set keys + their new values.
        # If RETURN n.prop, only those.
        rows_out: list[list[Any]] = []
        if ret_cols == ["*"]:
            ret_cols = list(set_keys)
        if ret_cols:
            payload = dict(zip(set_keys, sql_params[: len(set_keys)]))
            row = [_serialize_cell(payload.get(c)) for c in ret_cols]
            rows_out = [row]
        return {
            "ok": True,
            "rowCount": updated,
            "columnsJson": _json.dumps(ret_cols),
            "rowsJson": _json.dumps(rows_out, default=str),
            "translatedSql": sql,
            "elapsedMs": _now_ms() - started_ms,
            "error": None,
        }

    # ── DELETE branch (MATCH ... DELETE var) ──
    if _re.search(r"\bDELETE\b", upper):
        try:
            sql, sql_params = _translate_cypher_delete_to_sql(
                statement, parameters, schema=tenant_schema,
            )
        except Exception as e:
            return {
                "ok": False,
                "rowCount": 0,
                "columnsJson": "[]",
                "rowsJson": "[]",
                "translatedSql": "",
                "elapsedMs": _now_ms() - started_ms,
                "error": f"translate: {e}",
            }
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(f"SET statement_timeout = '20s'")
                _res = client.q(sql, sql_params)
                deleted = (len(_res) if isinstance(_res, list) else 1) if (len(_res) if isinstance(_res, list) else 1) and (len(_res) if isinstance(_res, list) else 1) > 0 else 0
        except Exception as e:
            return {
                "ok": False,
                "rowCount": 0,
                "columnsJson": "[]",
                "rowsJson": "[]",
                "translatedSql": sql,
                "elapsedMs": _now_ms() - started_ms,
                "error": f"execute: {type(e).__name__}: {str(e)[:200]}",
            }
        return {
            "ok": True,
            "rowCount": deleted,
            "columnsJson": "[]",
            "rowsJson": "[]",
            "translatedSql": sql,
            "elapsedMs": _now_ms() - started_ms,
            "error": None,
        }

    # ── default: read MATCH ... RETURN ──
    try:
        sql, sql_params, columns = _translate_cypher_to_sql(
            statement, parameters, default_limit, schema=tenant_schema,
        )
    except Exception as e:
        return {
            "ok": False,
            "rowCount": 0,
            "columnsJson": "[]",
            "rowsJson": "[]",
            "translatedSql": "",
            "elapsedMs": _now_ms() - started_ms,
            "error": f"translate: {e}",
        }

    rows: list[list[Any]] = []
    err: str | None = None
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(f"SET statement_timeout = '20s'")
            _res = client.q(sql, sql_params)
            for raw in _res:
                rows.append([_serialize_cell(cell) for cell in raw])
            if [] and (len(columns) == 1 and columns[0] != [][0].name):
                if "*" in sql.split("FROM", 1)[0]:
                    columns = [d.name for d in []]
    except Exception as e:
        err = f"execute: {type(e).__name__}: {str(e)[:200]}"

    elapsed = _now_ms() - started_ms
    if err is not None:
        return {
            "ok": False,
            "rowCount": 0,
            "columnsJson": "[]",
            "rowsJson": "[]",
            "translatedSql": sql,
            "elapsedMs": elapsed,
            "error": err,
        }

    return {
        "ok": True,
        "rowCount": len(rows),
        "columnsJson": _json.dumps(columns),
        "rowsJson": _json.dumps(rows, default=str),
        "translatedSql": sql,
        "elapsedMs": elapsed,
        "error": None,
    }


def _camel_for_alias(alias: str) -> str:
    """No-op pass-through for now — kept for future RETURN aliasing."""
    return alias


def _serialize_cell(cell: Any) -> Any:
    """Best-effort JSON-friendly cast for RW row cells."""
    if cell is None:
        return None
    if isinstance(cell, (str, int, float, bool)):
        return cell
    if isinstance(cell, (list, tuple)):
        return [_serialize_cell(c) for c in cell]
    if isinstance(cell, dict):
        return {str(k): _serialize_cell(v) for k, v in cell.items()}
    if isinstance(cell, _dt.datetime):
        return cell.isoformat()
    if isinstance(cell, _dt.date):
        return cell.isoformat()
    return str(cell)


async def task_yata_storage_metering_rollup(**kwargs: Any) -> dict[str, Any]:
    ts_ms = _now_ms()
    today = _today()
    created_at = _now_ts()
    events_emitted = 0
    total_bytes_hour = 0

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            SELECT org_did, bucket_name, storage_tier, bytes_stored
            FROM mv_yata_storage_by_org
            WHERE bytes_stored > 0
            LIMIT 10000
            """
        )
        rows = _res
        for org_did, bucket_name, storage_tier, bytes_stored in rows:
            bytes_hour = int(bytes_stored or 0)
            if bytes_hour <= 0:
                continue
            gb_hour = bytes_hour / (1024 ** 3)
            billed = round(STORAGE_GB_HOUR_PRICE_JPY_MICRO * gb_hour)
            vertex_id = _event_id(str(org_did), "storage_gb_hour", str(ts_ms), str(bucket_name), str(storage_tier))
            _res = client.q(
                """
                INSERT INTO vertex_billing_event (
                    vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    org_did, actor_did, ts_ms, metric, qty, product,
                    ref_resource, unit_cost_jpy_micro, list_price_jpy_micro,
                    applied_discount_pct, billed_amount_jpy_micro,
                    created_at, org_id, user_id, actor_id
                ) VALUES (
                    %s, NULL, %s, 2, %s,
                    %s, NULL, %s, 'storage_gb_hour', %s, 'yata',
                    %s, NULL, %s,
                    0, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (vertex_id) DO NOTHING
                """,
                (
                    vertex_id, today, YATA_DID,
                    org_did, ts_ms, gb_hour,
                    f"{bucket_name}:{storage_tier}", STORAGE_GB_HOUR_PRICE_JPY_MICRO,
                    billed, created_at, org_did, org_did, "yata.storage.metering.rollup",
                ),
            )
            events_emitted += 1
            total_bytes_hour += bytes_hour

    return {"eventsEmitted": events_emitted, "totalBytesHour": total_bytes_hour}


async def task_yata_storage_embedding_drain(**kwargs: Any) -> dict[str, Any]:
    batch_size = int(kwargs.get("batchSize") or 32)
    processed = 0
    failed = 0
    now = _now_ts()

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            SELECT blob_id
            FROM mv_yata_blob_embedding_queue
            LIMIT %s
            """,
            (batch_size,),
        )
        blob_ids = [r[0] for r in _res]
        for blob_id in blob_ids:
            try:
                _res = client.q(
                    """
                    UPDATE vertex_yata_blob
                    SET embedding_status = 'inflight', last_accessed_at = %s
                    WHERE vertex_id = %s AND embedding_status = 'pending'
                    """,
                    (now, blob_id),
                )
                processed += 1
            except Exception:
                failed += 1

    return {"processed": processed, "failed": failed}


async def task_yata_storage_tier_migrate(**kwargs: Any) -> dict[str, Any]:
    batch_size = int(kwargs.get("batchSize") or 200)
    now = _now_ts()
    hot_to_warm = 0
    warm_to_cold = 0
    bytes_migrated = 0

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            SELECT b.vertex_id, b.storage_tier, b.size_bytes
            FROM vertex_yata_blob b
            JOIN vertex_yata_bucket bk ON bk.bucket_name = b.bucket_name AND bk.org_did = b.org_did
            WHERE b.status = 'active'
              AND b.is_delete_marker = false
              AND bk.tier_policy = 'auto'
              AND (
                (b.storage_tier = 'hot' AND b.last_accessed_at < CAST(now() - INTERVAL '90 days' AS varchar))
                OR
                (b.storage_tier = 'warm' AND b.last_accessed_at < CAST(now() - INTERVAL '30 days' AS varchar))
              )
            LIMIT %s
            """,
            (batch_size,),
        )
        rows = _res
        for blob_id, tier, size_bytes in rows:
            next_tier = "warm" if tier == "hot" else "cold"
            _res = client.q(
                """
                UPDATE vertex_yata_blob
                SET storage_tier = %s, last_accessed_at = %s
                WHERE vertex_id = %s
                """,
                (next_tier, now, blob_id),
            )
            if tier == "hot":
                hot_to_warm += 1
            else:
                warm_to_cold += 1
            bytes_migrated += int(size_bytes or 0)

    return {"hotToWarm": hot_to_warm, "warmToCold": warm_to_cold, "bytesMigrated": bytes_migrated}


async def task_yata_storage_multipart_reap(**kwargs: Any) -> dict[str, Any]:
    now = _now_ts()
    aborted = 0
    bytes_freed = 0

    if True:

        client = get_kotoba_client()
        _res = client.q(
            """
            SELECT vertex_id, total_bytes
            FROM vertex_yata_multipart
            WHERE status = 'active' AND expires_at < %s
            LIMIT 500
            """,
            (now,),
        )
        rows = _res
        for vertex_id, total_bytes in rows:
            _res = client.q(
                """
                UPDATE vertex_yata_multipart
                SET status = 'aborted'
                WHERE vertex_id = %s AND status = 'active'
                """,
                (vertex_id,),
            )
            aborted += 1
            bytes_freed += int(total_bytes or 0)

    return {"aborted": aborted, "bytesFreed": bytes_freed}


# ──────────────────────────────────────────────────────────────────────
# P3.2.5 — Multipart upload + ListObjectsV2 (skeleton primitives)
# ──────────────────────────────────────────────────────────────────────
#
# These primitives are the v0 contract that the yatabase CF Worker calls
# via bpmn-dispatcher when handling /s3/{bucket}/{key}?uploads etc. The
# byte-buffering + provider-side InitiateMultipartUpload / UploadPart /
# CompleteMultipartUpload SigV4 calls are deferred to a follow-up
# (P3.2.6) — at this stage we only persist enough state in
# vertex_yata_multipart for the Worker to validate the upload session
# and return a stable uploadId.


async def task_yata_storage_multipart_init(
    bucketName: str = "",
    objectKey: str = "",
    contentType: str | None = None,
    encryption: str | None = None,
    orgDid: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Open a multipart upload session.  v0 inserts the row only; the
    provider-side InitiateMultipartUpload SigV4 lands in P3.2.6 alongside
    the byte-streaming proxy."""
    if not bucketName or not objectKey:
        return {"ok": False, "error": "bucketName + objectKey required"}
    if not orgDid:
        return {"ok": False, "error": "orgDid required"}
    upload_id = "mu-" + hashlib.sha256(
        f"{orgDid}|{bucketName}|{objectKey}|{_now_ms()}".encode()
    ).hexdigest()[:24]
    expires_at = _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0)
    expires_at += _dt.timedelta(hours=24)
    vid = "at://did:web:yatabase.etzhayyim.com/com.etzhayyim.apps.yata.multipart/" + upload_id
    if True:
        client = get_kotoba_client()
        _res = client.q(
            """
            INSERT INTO vertex_yata_multipart (
              vertex_id, _seq, created_date, sensitivity_ord, owner_did,
              upload_id, bucket_name, object_key, org_did, content_type,
              parts_received, total_bytes, storage_provider, provider_upload_id,
              parts_json, initiated_at, expires_at, status,
              created_at, org_id, user_id, actor_id
            ) VALUES (
              %s, NULL, %s, 2, %s,
              %s, %s, %s, %s, %s,
              0, 0, %s, %s,
              %s, %s, %s, 'active',
              %s, %s, %s, %s
            )
            """,
            (
                vid, _today(), YATA_DID,
                upload_id, bucketName, objectKey, orgDid, contentType or "application/octet-stream",
                "b2", upload_id,
                "[]", _now_ts(), expires_at.strftime("%Y-%m-%d %H:%M:%S"),
                _now_ts(), orgDid, orgDid, "sys.yata.multipart.init",
            ),
        )
    return {"ok": True, "uploadId": upload_id, "expiresAt": expires_at.isoformat()}


async def task_yata_storage_multipart_part(
    uploadId: str = "",
    partNumber: int = 0,
    data: str = "",
    orgDid: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Buffer one part body in vertex_yata_multipart.parts_json (v0)."""
    if not uploadId or partNumber < 1 or partNumber > 10_000 or not data:
        return {"ok": False, "error": "uploadId + partNumber (1..10000) + data required"}
    # Compute etag without holding the bytes longer than necessary.
    digest = hashlib.sha256(data.encode()).hexdigest()
    size = (len(data) // 4) * 3  # base64 → byte estimate
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT parts_json, total_bytes FROM vertex_yata_multipart "
            "WHERE upload_id = %s AND status = 'active' LIMIT 1",
            (uploadId,),
        )
        row = (_res[0] if _res else None)
        if not row:
            return {"ok": False, "error": "uploadId not active"}
        # parts_json is small JSON; manipulate via Python.
        import json as _json
        try:
            parts = _json.loads(row[0] or "[]")
        except Exception:
            parts = []
        parts = [p for p in parts if p.get("partNumber") != partNumber]
        parts.append({"partNumber": partNumber, "etag": digest, "sizeBytes": size, "data": data})
        parts.sort(key=lambda p: p.get("partNumber") or 0)
        _res = client.q(
            "UPDATE vertex_yata_multipart "
            "SET parts_json = %s, parts_received = parts_received + 1, total_bytes = %s "
            "WHERE upload_id = %s",
            (_json.dumps(parts), int(row[1] or 0) + size, uploadId),
        )
    return {"partNumber": partNumber, "etag": digest, "sizeBytes": size}


async def task_yata_storage_multipart_complete(
    uploadId: str = "",
    parts: list | None = None,
    orgDid: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Finalise — emit a vertex_yata_blob row + close multipart row.

    P3.2.5 v0 stub: accepts the submitted parts list, marks the row
    'completed', and surfaces enough metadata for the client. Provider
    PUT happens in P3.2.6 once the byte-streaming path lands.
    """
    if not uploadId:
        return {"ok": False, "error": "uploadId required"}
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT bucket_name, object_key, org_did, content_type, total_bytes "
            "FROM vertex_yata_multipart WHERE upload_id = %s AND status = 'active' LIMIT 1",
            (uploadId,),
        )
        row = (_res[0] if _res else None)
        if not row:
            return {"ok": False, "error": "uploadId not active"}
        bucket_name, object_key, upload_org, content_type, total_bytes = row
        agg_etag = hashlib.sha256(uploadId.encode()).hexdigest()
        blob_id = _object_id(bucket_name, object_key, agg_etag)
        _res = client.q(
            "UPDATE vertex_yata_multipart SET status = 'completed' WHERE upload_id = %s",
            (uploadId,),
        )
    return {
        "ok": True,
        "bucketName": bucket_name,
        "objectKey": object_key,
        "blobId": blob_id,
        "etag": agg_etag,
        "cid": "",
        "sizeBytes": int(total_bytes or 0),
    }


async def task_yata_storage_multipart_abort(
    uploadId: str = "",
    orgDid: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    if not uploadId:
        return {"ok": False, "error": "uploadId required"}
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "UPDATE vertex_yata_multipart SET status = 'aborted' "
            "WHERE upload_id = %s AND status = 'active'",
            (uploadId,),
        )
    return {"ok": True, "partsAborted": 0}


async def task_yata_storage_list_objects(
    bucketName: str = "",
    prefix: str = "",
    delimiter: str = "",
    limit: int = 100,
    cursor: str | None = None,
    orgDid: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """SELECT vertex_yata_blob WHERE bucket_name + prefix. delimiter
    folding is computed in Python on the cursor page (small set)."""
    if not bucketName:
        return {"ok": False, "error": "bucketName required"}
    safe = min(max(int(limit or 100), 1), 1000)
    if True:
        client = get_kotoba_client()
        sql = (
            "SELECT vertex_id, object_key, version_id, size_bytes, etag, "
            "content_type, storage_tier, created_at "
            "FROM vertex_yata_blob "
            "WHERE org_did = %s AND bucket_name = %s "
            "AND status = 'active' AND is_delete_marker = false "
        )
        params: list[Any] = [orgDid, bucketName]
        if prefix:
            sql += "AND object_key LIKE %s "
            params.append(prefix + "%")
        if cursor:
            sql += "AND object_key > %s "
            params.append(cursor)
        sql += f"ORDER BY object_key ASC LIMIT {safe + 1}"
        _res = client.q(sql, tuple(params))
        rows = _res
    has_more = len(rows) > safe
    rows = rows[:safe]

    objects: list[dict[str, Any]] = []
    common_prefixes: list[str] = []
    seen: set[str] = set()
    for r in rows:
        key = str(r[1] or "")
        if delimiter:
            after = key[len(prefix):] if (prefix and key.startswith(prefix)) else key
            sep = after.find(delimiter)
            if sep >= 0:
                cp = key[: len(prefix or "") + sep + len(delimiter)]
                if cp not in seen:
                    seen.add(cp)
                    common_prefixes.append(cp)
                continue
        objects.append({
            "objectKey": key,
            "blobId": str(r[0] or ""),
            "versionId": (str(r[2]) if r[2] else None),
            "sizeBytes": int(r[3] or 0),
            "etag": str(r[4] or ""),
            "contentType": str(r[5] or ""),
            "storageTier": str(r[6] or ""),
            "createdAt": str(r[7] or ""),
        })
    next_cursor = objects[-1]["objectKey"] if has_more and objects else ""
    return {
        "bucketName": bucketName,
        "objects": objects,
        "commonPrefixes": common_prefixes,
        "nextCursor": next_cursor,
    }


# ──────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("yata.storage.metering.rollup", task_yata_storage_metering_rollup, ms=60_000)
    t("yata.storage.embedding.drain", task_yata_storage_embedding_drain, ms=180_000)
    t("yata.storage.tier.migrate", task_yata_storage_tier_migrate, ms=180_000)
    t("yata.storage.multipart.reap", task_yata_storage_multipart_reap, ms=60_000)
    t("yata.database.provision", task_yata_database_provision, ms=60_000)
    t("yata.storage.put", task_yata_storage_put, ms=60_000)
    t("yata.storage.get", task_yata_storage_get, ms=30_000)
    t("yata.storage.delete", task_yata_storage_delete, ms=30_000)
    t("yata.storage.presign", task_yata_storage_presign, ms=15_000)
    t("yata.sparql.run", task_yata_sparql_run, ms=30_000)
    t("yata.cypher.run", task_yata_cypher_run, ms=30_000)
    # P3.2.5
    t("yata.storage.multipart.init",     task_yata_storage_multipart_init,     ms=30_000)
    t("yata.storage.multipart.part",     task_yata_storage_multipart_part,     ms=60_000)
    t("yata.storage.multipart.complete", task_yata_storage_multipart_complete, ms=120_000)
    t("yata.storage.multipart.abort",    task_yata_storage_multipart_abort,    ms=30_000)
    t("yata.storage.list.objects",       task_yata_storage_list_objects,       ms=30_000)


__all__ = [
    "register",
    "task_yata_storage_metering_rollup",
    "task_yata_storage_embedding_drain",
    "task_yata_storage_tier_migrate",
    "task_yata_storage_multipart_reap",
    "task_yata_database_provision",
    "task_yata_storage_put",
    "task_yata_storage_get",
    "task_yata_storage_delete",
    "task_yata_storage_presign",
    "task_yata_sparql_run",
    "task_yata_storage_multipart_init",
    "task_yata_storage_multipart_part",
    "task_yata_storage_multipart_complete",
    "task_yata_storage_multipart_abort",
    "task_yata_storage_list_objects",
]
