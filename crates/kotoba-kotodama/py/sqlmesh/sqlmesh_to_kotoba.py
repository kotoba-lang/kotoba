#!/usr/bin/env python3
"""Convert sqlmesh RisingWave materialized-view models → kotoba view registry (EDN).

ADR-2605262130 + ADR-2605312345: the kotoba Datom log is first-class canonical
state and the read path is ``kotoba-kqe`` arrangements **directly over the log** —
there is no separate projection layer. The 610 ``mv_*.sql`` RisingWave materialized
views are therefore not state; they are *derived read definitions*. Each becomes a
kotoba **view** = a Datalog ``[:find … :where …]`` query run on demand by kqe.

This converter parses every model's ``MODEL(...)`` header (preserving lineage
metadata: name / kind / grain / tags / description / source deps) and emits a single
``kotoba/views.edn`` registry. For genuinely simple shapes — a single-source
projection or single-source group-by count/sum with no JOIN and no computed
expression — it auto-emits the Datalog query (``:translation :auto``). Anything with
JOINs, multi-table aggregates, UNION, DISTINCT ON, subqueries or computed SELECT
expressions is cataloged with its metadata, source attributes, and the original SQL
preserved under ``:sql-source`` and flagged ``:translation :manual`` with a reason —
nothing is silently dropped or pretended-translated.

stdlib only. Usage:
    python3 sqlmesh/sqlmesh_to_kotoba.py            # writes sqlmesh/kotoba/views.edn + prints coverage
    python3 sqlmesh/sqlmesh_to_kotoba.py --print     # print EDN to stdout, no write
"""
from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
MODELS = HERE / "models"
OUT = HERE / "kotoba" / "views.edn"


# ── EDN emission (minimal, mirrors kotoba_datomic.edn_val) ──
def edn_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip() + '"'


def edn_kw_vec(items: list[str]) -> str:
    return "[" + " ".join(items) + "]"


# ── parse MODEL() header ──
def parse_model_header(sql: str) -> dict:
    m = re.search(r"MODEL\s*\((.*?)\)\s*;", sql, re.S | re.I)
    block = m.group(1) if m else ""
    def field(name: str) -> str | None:
        mm = re.search(rf"\b{name}\s+([^\n,]+)", block, re.I)
        return mm.group(1).strip().rstrip(",").strip() if mm else None
    def listfield(name: str) -> list[str]:
        mm = re.search(rf"\b{name}\s*\[([^\]]*)\]", block, re.I)
        if not mm:
            return []
        return [x.strip() for x in mm.group(1).split(",") if x.strip()]
    name = field("name") or ""
    name = name.split(".")[-1]  # strip dev. schema prefix
    desc = None
    md = re.search(r"description\s+'([^']*)'", block, re.I)
    if md:
        desc = md.group(1)
    return {
        "name": name,
        "kind": (field("kind") or "FULL").upper(),
        "grain": listfield("grain"),
        "tags": listfield("tags"),
        "description": desc,
    }


# ── table → kotoba attribute namespace (matches kotoba_datomic.table_attr_namespace) ──
def table_ns(table: str) -> str:
    t = table.split(".")[-1]
    if t.startswith("vertex_"):
        return "vertex." + t[len("vertex_"):].replace("_", "-")
    if t.startswith("edge_"):
        return "edge." + t[len("edge_"):].replace("_", "-")
    return "ent." + t.replace("_", "-")


def id_attr_for(table: str) -> str:
    """The ``:db.unique/identity`` keyword for a table (``vertex_*``→vertex-id,
    ``edge_*``→edge-id, else vertex-id)."""
    ns = table_ns(table)
    id_col = "edge-id" if ns.startswith("edge.") else "vertex-id"
    return f":{ns}/{id_col}"


def source_tables(sql: str) -> list[str]:
    body = re.sub(r"MODEL\s*\(.*?\)\s*;", "", sql, flags=re.S | re.I)
    found = []
    for m in re.findall(r"(?:FROM|JOIN)\s+([a-z_][a-z0-9_.]*)", body, re.I):
        t = m.split(".")[-1]
        if t not in found:
            found.append(t)
    return found


# ── classify + (where simple) auto-translate ──
def _try_simple_join(body: str, up: str) -> tuple[str, str | None, str | None] | None:
    """Auto-translate the single equi-join graph-traversal shape:

        SELECT a1.c, a2.c AS x, …
        FROM <t1> a1 JOIN <t2> a2 ON a2.<jc2> = a1.<jc1>
        [WHERE a.col = 'literal']

    → ``[:find ?c ?x … :where [?a1 :ns1/jc1 ?j] [?a2 :ns2/jc2 ?j] [?a1 :ns1/c ?c] …]``

    Returns None (caller keeps it :manual) unless every clause is supported:
    exactly one INNER JOIN, no GROUP BY / aggregate / computed projection / UNION,
    and any WHERE is a single ``alias.col = 'literal'`` equality.
    """
    if up.count(" JOIN ") != 1 or " LEFT " in up or " RIGHT " in up or " OUTER " in up:
        return None
    if "GROUP BY" in up or "UNION" in up:
        return None
    m = re.search(
        r"SELECT\s+(.*?)\s+FROM\s+([a-z_][\w.]*)\s+(\w+)\s+JOIN\s+([a-z_][\w.]*)\s+(\w+)\s+ON\s+(.*?)(?:\s+WHERE\s+(.*))?$",
        body, re.S | re.I,
    )
    if not m:
        return None
    select_list, t1, a1, t2, a2, on_clause, where = m.groups()
    # parse ON  aA.cA = aB.cB
    on = re.fullmatch(r"\s*(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)\s*", on_clause)
    if not on:
        return None
    alias_tbl = {a1: t1, a2: t2}
    alias_ns = {a1: table_ns(t1), a2: table_ns(t2)}
    jaA, jcA, jaB, jcB = on.groups()
    if jaA not in alias_tbl or jaB not in alias_tbl:
        return None
    # projections: each "alias.col" or "alias.col AS name" — all must be bare
    clauses: list[str] = []
    findvars: list[str] = []
    seen_out: set[str] = set()
    for raw in re.split(r",(?![^()]*\))", select_list):
        c = raw.strip()
        mm = re.fullmatch(r"(\w+)\.(\w+)(?:\s+AS\s+(\w+))?", c, re.I)
        if not mm:
            return None  # computed/aliased expr → manual
        al, col, outname = mm.group(1), mm.group(2), mm.group(3)
        if al not in alias_ns:
            return None
        out = (outname or col).replace("_", "-")
        var = f"?{out}"
        if out not in seen_out:
            seen_out.add(out)
            findvars.append(var)
        clauses.append(f"[?{al} :{alias_ns[al]}/{col.replace('_','-')} {var}]")
    # join clause: shared var ?j binds aA.cA and aB.cB
    clauses.insert(0, f"[?{jaB} :{alias_ns[jaB]}/{jcB.replace('_','-')} ?__j]")
    clauses.insert(0, f"[?{jaA} :{alias_ns[jaA]}/{jcA.replace('_','-')} ?__j]")
    # optional single equality WHERE
    if where:
        w = where.strip().rstrip(";").strip()
        wm = re.fullmatch(r"(\w+)\.(\w+)\s*=\s*'([^']*)'", w)
        if not wm:
            return None  # LIKE / IN / AND / complex → manual
        wa, wc, wv = wm.groups()
        if wa not in alias_ns:
            return None
        clauses.append(f'[?{wa} :{alias_ns[wa]}/{wc.replace("_","-")} {edn_str(wv)}]')
    return "auto", f"[:find {' '.join(findvars)} :where {' '.join(clauses)}]", None


def _strip_casts(body: str) -> str:
    """Drop PostgreSQL ``::TYPE`` casts — pure annotations, no semantic effect on
    attribute binding (``COUNT(*)::BIGINT`` ≡ ``COUNT(*)``, ``col::INT`` ≡ ``col``).

    The two-word forms (``double precision`` / ``timestamp …``) are matched
    explicitly so the single-word rule does NOT swallow a following ``AS`` alias.
    """
    body = re.sub(r"::\s*double\s+precision", "", body, flags=re.I)
    body = re.sub(r"::\s*timestamp(\s+with(out)?\s+time\s+zone)?", "", body, flags=re.I)
    return re.sub(r"::\s*[A-Za-z][A-Za-z0-9_]*", "", body)


def classify(sql: str) -> tuple[str, str | None, str | None]:
    """Returns (translation, datalog_or_None, manual_reason_or_None)."""
    body = re.sub(r"MODEL\s*\(.*?\)\s*;", "", sql, flags=re.S | re.I).strip()
    body = _strip_casts(body)
    up = body.upper()
    if " JOIN " in up:
        joined = _try_simple_join(body, up)
        if joined:
            return joined
        return "manual", None, "multi-source JOIN — needs kqe rule / explicit join clause"
    if "UNION" in up:
        return "manual", None, "UNION — needs kqe rule disjunction"
    if "DISTINCT ON" in up:
        return "manual", None, "DISTINCT ON — needs latest-per-grain aggregate idiom"
    if up.count("SELECT") > 1:
        return "manual", None, "subquery — needs decomposed kqe rule"

    # single-source. Extract SELECT list + FROM table.
    sel = re.search(r"SELECT\s+(.*?)\s+FROM\s+([a-z_][a-z0-9_.]*)", body, re.S | re.I)
    if not sel:
        return "manual", None, "could not parse single SELECT…FROM"
    select_list, table = sel.group(1), sel.group(2)
    cols = [c.strip() for c in re.split(r",(?![^()]*\))", select_list)]
    # reject computed expressions / functions in the projection (except a plain GROUP-BY agg handled below)
    has_group = "GROUP BY" in up
    has_agg = bool(re.search(r"\b(COUNT|SUM|MAX|MIN|AVG)\s*\(", select_list, re.I))
    ns = table_ns(table)

    # scalar/grouped aggregate (with or without GROUP BY) → aggregate find-form
    if has_group or has_agg:
        agg = emit_aggregate(ns, cols, body, id_attr_for(table))
        if agg:
            return "auto", agg, None
        return "manual", None, "single-source aggregate with computed/distinct/where expr — kqe rule"

    # simple projection: every selected col must be a bare column (optional alias)
    plain = []
    for c in cols:
        cc = re.sub(r"\s+AS\s+\w+$", "", c, flags=re.I).strip()
        cc = cc.split(".")[-1]
        if re.fullmatch(r"[a-z_][a-z0-9_]*", cc):
            plain.append(cc)
        else:
            return "manual", None, f"computed/aliased projection expr: {c.strip()[:40]}"
    return "auto", emit_projection(ns, plain), None


def _var(col: str) -> str:
    return "?" + col.replace("_", "-")


def emit_projection(ns: str, cols: list[str]) -> str:
    """``[:find ?c1 ?c2 … :where [?e :ns/c1 ?c1] …]`` (first col anchors the entity)."""
    findvars = " ".join(_var(c) for c in cols)
    where = " ".join(f"[?e :{ns}/{c.replace('_','-')} {_var(c)}]" for c in cols)
    return f"[:find {findvars} :where {where}]"


_AGG = {"COUNT": "count", "SUM": "sum", "MAX": "max", "MIN": "min", "AVG": "avg"}


def emit_aggregate(ns: str, cols: list[str], body: str, id_attr: str | None = None) -> str | None:
    """Single-source aggregate → ``[:find ?g (count ?e) … :where …]``.

    Supports the bare grouping columns plus simple aggregates over ``*`` or a bare
    column: COUNT(*) → ``(count ?e)``, COUNT(DISTINCT c) → ``(count-distinct ?c)``,
    SUM/MAX/MIN/AVG(c) → ``(sum ?c)`` … Works with or without GROUP BY (a bare
    ``SELECT COUNT(*)`` is a scalar aggregate anchored on ``id_attr``). Returns None
    (→ stays manual) if any SELECT item is a computed expression (arithmetic, nested
    fn, CASE, ``||``) or has a WHERE/HAVING filter.
    """
    if re.search(r"\bHAVING\b", body, re.I):
        return None  # post-aggregate filter → kqe rule
    # A WHERE filter must be reflected in the :where clauses or the count is wrong.
    # Support only a conjunction of simple ``col = 'literal'`` equalities; anything
    # else (LIKE / IN / OR / range / function) stays :manual rather than silently
    # dropping the filter.
    where_eqs: list[tuple[str, str]] = []
    wm = re.search(r"\bWHERE\b(.*?)(?:\bGROUP\s+BY\b|$)", body, re.S | re.I)
    if wm and wm.group(1).strip():
        wtext = wm.group(1).strip()
        parts = re.split(r"\bAND\b", wtext, flags=re.I)
        for part in parts:
            pm = re.fullmatch(r"\s*(\w+)\s*=\s*'([^']*)'\s*", part)
            if not pm:
                return None  # non-equality predicate → keep honest, stay manual
            where_eqs.append((pm.group(1), pm.group(2)))
    find_parts: list[str] = []
    where: dict[str, str] = {}  # col → binding (dedup)
    for raw in cols:
        c = re.sub(r"\s+AS\s+\w+$", "", raw, flags=re.I).strip()
        cu = c.upper()
        m = re.fullmatch(r"(COUNT|SUM|MAX|MIN|AVG)\s*\(\s*(DISTINCT\s+)?([*]|[a-z_][a-z0-9_.]*)\s*\)", c, re.I)
        if m:
            fn, distinct, arg = m.group(1).upper(), m.group(2), m.group(3)
            arg = arg.split(".")[-1]
            if arg == "*":
                if fn != "COUNT":
                    return None
                find_parts.append("(count ?e)")
            else:
                v = _var(arg)
                where[arg] = f"[?e :{ns}/{arg.replace('_','-')} {v}]"
                if distinct:
                    find_parts.append(f"(count-distinct {v})" if fn == "COUNT" else None)  # type: ignore
                    if find_parts[-1] is None:
                        return None
                else:
                    find_parts.append(f"({_AGG[fn]} {v})")
            continue
        # bare grouping column?
        cc = c.split(".")[-1]
        if re.fullmatch(r"[a-z_][a-z0-9_]*", cc):
            v = _var(cc)
            where[cc] = f"[?e :{ns}/{cc.replace('_','-')} {v}]"
            find_parts.append(v)
            continue
        return None  # computed expression → stays manual
    where_clauses = [w for w in where.values() if w]
    # reflect the WHERE equalities so the aggregate is correct
    for col, val in where_eqs:
        where_clauses.append(f'[?e :{ns}/{col.replace("_", "-")} {edn_str(val)}]')
    if not where_clauses:
        # pure scalar aggregate (e.g. SELECT COUNT(*)) — anchor ?e on the table identity
        if id_attr:
            where_clauses = [f"[?e {id_attr} _]"]
        else:
            return None
    return f"[:find {' '.join(find_parts)} :where {' '.join(where_clauses)}]"


def model_to_edn(meta: dict, srcs: list[str], translation: str, datalog: str | None,
                 reason: str | None, raw_sql: str) -> str:
    lines = ["  {"]
    lines.append(f"   :view/name {edn_str(meta['name'])}")
    lines.append(f"   :view/kind :{meta['kind'].lower()}")
    if meta["grain"]:
        lines.append(f"   :view/grain {edn_kw_vec([edn_str(g) for g in meta['grain']])}")
    if meta["tags"]:
        lines.append(f"   :view/tags {edn_kw_vec([edn_str(t) for t in meta['tags']])}")
    if meta["description"]:
        lines.append(f"   :view/description {edn_str(meta['description'])}")
    src_ns = [table_ns(s) for s in srcs]
    lines.append(f"   :view/sources {edn_kw_vec([edn_str(s) for s in src_ns])}")
    lines.append(f"   :view/translation :{translation}")
    if translation == "auto" and datalog:
        lines.append(f"   :view/query {edn_str(datalog)}")
    else:
        lines.append(f"   :view/manual-reason {edn_str(reason or 'unclassified')}")
        # preserve the original SELECT body for the human translator (single line)
        body = re.sub(r"MODEL\s*\(.*?\)\s*;", "", raw_sql, flags=re.S | re.I).strip()
        lines.append(f"   :view/sql-source {edn_str(body)}")
    lines.append("  }")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    files = sorted(MODELS.glob("*.sql"))
    entries, stats = [], {"auto": 0, "manual": 0}
    reasons: dict[str, int] = {}
    for f in files:
        sql = f.read_text()
        meta = parse_model_header(sql)
        if not meta["name"]:
            meta["name"] = f.stem
        srcs = source_tables(sql)
        translation, datalog, reason = classify(sql)
        stats[translation] += 1
        if reason:
            key = reason.split("—")[0].strip()
            reasons[key] = reasons.get(key, 0) + 1
        entries.append(model_to_edn(meta, srcs, translation, datalog, reason, sql))

    header = [
        ";; GENERATED by sqlmesh/sqlmesh_to_kotoba.py — DO NOT EDIT auto entries by hand.",
        ";; kotoba view registry: 610 RisingWave materialized views → kqe Datalog views.",
        ";; ADR-2605262130 (no projection layer) + ADR-2605312345 (Datom log = canonical state).",
        f";; coverage: {stats['auto']} auto-translated · {stats['manual']} :manual (SQL preserved, R1 targets).",
        ";; A :manual view keeps :view/sql-source verbatim — honest, never a pretended translation.",
    ]
    edn = "\n".join(f";; {h[3:]}" if h.startswith(';; ') else h for h in header)
    edn = "\n".join(header) + "\n[\n" + "\n\n".join(entries) + "\n]\n"

    if "--print" in argv:
        print(edn)
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(edn, encoding="utf-8")
        print(f"wrote {OUT.relative_to(HERE.parent)} — {len(entries)} views")
    print(f"\ncoverage: {stats['auto']} auto · {stats['manual']} manual (of {len(files)})")
    print("manual reasons:")
    for r, n in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  {n:4d}  {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
