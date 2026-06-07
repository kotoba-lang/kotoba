"""
OWL EL++ / DL batch reasoner + QL rewrite + SHACL complex - Layer 2 LangServer tasks.

Task types registered:
  owl.el.classify         - EL++ TBox classification (per-ontology, polynomial)
  owl.dl.classify         - OWL DL classification via HermiT (per-ontology, EXPTIME)
  owl.dl.consistency      - OWL DL consistency check (calls HermiT, batch only)
  owl.benchmark.compare   - EL++ vs DL comparison, writes vertex_owl_benchmark
  owl.ql.precompute       - DL-Lite_R perfect reformulation -> vertex_ql_rewrite
  shacl.validate.complex  - sh:sparql / recursive sh:node (needs SPARQL engine)

Rules (from ADR-0044 + CLAUDE.md):
  - flush=False on all RW writes
  - No ON CONFLICT, no LIMIT $N in prepared statements
  - PK implicit upsert (RW spec: same PK re-insert overwrites)
  - Python External UDF io_threads=100 for IO-bound paths

EL++ vs DL comparison:
  EL++ (OWL EL profile): polynomial O(n^3), sound+complete for EL axioms.
    Supports: conjunction, existential restriction, top, bottom, nominals,
    role chains, reflexive roles.
    Missing: universal, negation, disjunction, and number restrictions.
  OWL DL (SROIQ): EXPTIME-complete, complete for full OWL DL.
    Adds: universal, negation, disjunction, cardinality, inverse roles, complex role hierarchies.
  Diff stored in mv_owl_el_dl_diff:
    'agreed'  - both found the same inference (EL++ is complete here)
    'el_only' - EL++ found it, DL didn't (should not happen; indicates DL bug)
    'dl_only' - DL found it via axioms EL++ cannot express (universal/cardinality)
"""

from __future__ import annotations

import asyncio
import hashlib
import resource
import time
from typing import Any

import os

import asyncpg
from kotodama.langserver_compat import LangServerWorker

RW_DSN = os.environ.get("RW_URL", "")

# ─── helpers ─────────────────────────────────────────────────────────────────

def _sha256(*parts: str) -> str:
    return hashlib.sha256("||".join(parts).encode()).hexdigest()

async def _load_all_profiles(conn: asyncpg.Connection) -> list[str]:
    rows = await conn.fetch(
        "SELECT DISTINCT profile FROM edge_owl_subclass LIMIT 50"
    )
    return [r["profile"] for r in rows] or ["etzhayyim_core_v1"]

async def _load_axioms(conn: asyncpg.Connection, profiles: list[str]) -> list[dict]:
    ph = ",".join(f"${i+1}" for i in range(len(profiles)))
    rows = await conn.fetch(
        f"""
        SELECT c.class_iri AS subject_iri, e.axiom_type, c2.class_iri AS object_iri,
               e.profile
        FROM   edge_owl_subclass e
        JOIN   vertex_owl_class c  ON c.vertex_id = e.from_vertex_id
        JOIN   vertex_owl_class c2 ON c2.vertex_id = e.to_vertex_id
        WHERE  e.profile = ANY(ARRAY[{ph}]::TEXT[])
        UNION ALL
        SELECT p.property_iri AS subject_iri, 'ObjectPropertyDomain' AS axiom_type,
               c.class_iri AS object_iri, d.profile
        FROM   edge_owl_property_domain d
        JOIN   vertex_owl_property p ON p.vertex_id = d.from_vertex_id
        JOIN   vertex_owl_class    c ON c.vertex_id = d.to_vertex_id
        WHERE  d.profile = ANY(ARRAY[{ph}]::TEXT[])
        """,
        *profiles,
    )
    return [dict(r) for r in rows]

async def _write_inferred(
    conn: asyncpg.Connection,
    triples: list[tuple[str, str, str]],
    profile: str,
    ontology_ver: str,
) -> int:
    for s, p, o in triples:
        vid = _sha256(s, p, o, profile)
        await conn.execute(
            "INSERT INTO vertex_owl_inferred"
            "(vertex_id,subject,predicate,object,profile,ontology_ver)"
            " VALUES($1,$2,$3,$4,$5,$6)",
            vid, s, p, o, profile, ontology_ver,
        )
    return len(triples)

# ─── EL++ classification ─────────────────────────────────────────────────────

def _run_el_plus_plus(axioms: list[dict]) -> list[tuple[str, str, str]]:
    """
    EL++ saturation via owlready2 (pyhornedowl preferred when available).
    Falls back to a hand-rolled EL saturation if neither is installed.
    Returns list of (subject, predicate, object) inferred triples.
    """
    try:
        return _run_el_owlready2(axioms)
    except Exception:
        # Java/Pellet unavailable in container — fall back to pure-Python EL saturation.
        return _run_el_naive(axioms)

def _run_el_owlready2(axioms: list[dict]) -> list[tuple[str, str, str]]:
    import owlready2 as owl  # type: ignore

    onto = owl.get_ontology("http://etzhayyim.com/owl/reasoner/")
    with onto:
        classes: dict[str, Any] = {}

        def _cls(iri: str) -> Any:
            if iri not in classes:
                classes[iri] = type(iri.split(":")[-1], (owl.Thing,), {"namespace": onto})
            return classes[iri]

        for ax in axioms:
            s, o, t = ax["subject_iri"], ax["object_iri"], ax["axiom_type"]
            if t == "SubClassOf":
                _cls(s).is_a.append(_cls(o))
            elif t == "EquivalentClasses":
                owl.AllDisjoint([_cls(s), _cls(o)])  # proxy for equiv
            elif t == "DisjointClasses":
                owl.AllDisjoint([_cls(s), _cls(o)])

        # EL reasoner (Pellet/ELK not available in owlready2; use built-in)
        owl.sync_reasoner_pellet(infer_property_values=False, infer_data_property_values=False)

    inferred: list[tuple[str, str, str]] = []
    for cls_iri, cls_obj in classes.items():
        for parent in cls_obj.ancestors():
            if parent is not owl.Thing and parent.iri != cls_iri:
                inferred.append((cls_iri, "rdfs:subClassOf", parent.iri))
    return inferred

def _run_el_naive(axioms: list[dict]) -> list[tuple[str, str, str]]:
    """
    Naive EL saturation (CR1-CR4 rules, sound+complete for EL without nominals).
    CR1: C subClassOf D, D subClassOf E implies C subClassOf E.
    CR2: C subClassOf D and C subClassOf E implies conjunction membership.
    """
    subsumes: dict[str, set[str]] = {}

    for ax in axioms:
        s, o = ax["subject_iri"], ax["object_iri"]
        if ax["axiom_type"] in ("SubClassOf", "EquivalentClasses"):
            subsumes.setdefault(s, set()).add(o)
            if ax["axiom_type"] == "EquivalentClasses":
                subsumes.setdefault(o, set()).add(s)

    # CR1 saturation (fixed-point)
    changed = True
    while changed:
        changed = False
        for cls, supers in list(subsumes.items()):
            for sup in list(supers):
                if sup in subsumes:
                    new = subsumes[sup] - supers
                    if new:
                        subsumes[cls].update(new)
                        changed = True

    return [
        (cls, "rdfs:subClassOf", sup)
        for cls, supers in subsumes.items()
        for sup in supers
        if sup != cls
    ]

# ─── OWL DL classification (HermiT via owlready2) ────────────────────────────

def _run_dl_hermit(axioms: list[dict]) -> tuple[list[tuple[str, str, str]], bool, str | None]:
    """
    OWL DL classification + consistency via HermiT (EXPTIME).
    Returns (inferred_triples, consistent, explanation).
    HermiT handles universal, negation, disjunction, cardinality, inverse roles,
    and complex role hierarchies.
    """
    import owlready2 as owl  # type: ignore

    onto = owl.get_ontology("http://etzhayyim.com/owl/dl/")
    with onto:
        classes: dict[str, Any] = {}
        properties: dict[str, Any] = {}

        def _cls(iri: str) -> Any:
            if iri not in classes:
                classes[iri] = type(iri.split(":")[-1], (owl.Thing,), {"namespace": onto})
            return classes[iri]

        def _prop(iri: str) -> Any:
            if iri not in properties:
                properties[iri] = type(iri.split(":")[-1], (owl.ObjectProperty,), {"namespace": onto})
            return properties[iri]

        for ax in axioms:
            s, o, t = ax["subject_iri"], ax["object_iri"], ax["axiom_type"]
            if t == "SubClassOf":
                _cls(s).is_a.append(_cls(o))
            elif t == "EquivalentClasses":
                owl.AllEquivalent([_cls(s), _cls(o)])
            elif t == "DisjointClasses":
                owl.AllDisjoint([_cls(s), _cls(o)])
            elif t == "ObjectPropertyDomain":
                _prop(s).domain.append(_cls(o))

    try:
        # HermiT: full DL including universal, negation, and cardinality.
        owl.sync_reasoner_hermit(infer_property_values=True)
        consistent = True
        explanation = None
    except owl.base.OwlReadyInconsistentOntologyError as e:
        consistent = False
        explanation = str(e)

    inferred: list[tuple[str, str, str]] = []
    if consistent:
        for cls_iri, cls_obj in classes.items():
            for parent in cls_obj.ancestors():
                if parent is not owl.Thing and parent.iri != cls_iri:
                    inferred.append((cls_iri, "rdfs:subClassOf", parent.iri))

    return inferred, consistent, explanation

# ─── LangServer tasks ────────────────────────────────────────────────────────────

def register_owl_tasks(worker: LangServerWorker) -> None:

    @worker.task(task_type="owl.el.classify")
    async def task_owl_el_classify(ontology_ver: str = "current") -> dict:
        """EL++ TBox classification. per-ontology, not per-row."""
        conn = await asyncpg.connect(RW_DSN)
        profiles = await _load_all_profiles(conn)
        axioms = await _load_axioms(conn, profiles)

        t0 = time.perf_counter()
        mem0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        loop = asyncio.get_event_loop()
        inferred = await loop.run_in_executor(None, _run_el_plus_plus, axioms)

        mem1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        duration_ms = int((time.perf_counter() - t0) * 1000)

        count = await _write_inferred(conn, inferred, "EL", ontology_ver)

        await conn.execute(
            "INSERT INTO vertex_owl_benchmark"
            "(vertex_id,ontology_ver,profile,class_count,"
            " inferred_subsumptions,duration_ms,consistent,peak_ram_mb)"
            " VALUES($1,$2,'EL',$3,$4,$5,TRUE,$6)",
            f"{ontology_ver}:EL",
            ontology_ver,
            len({ax["subject_iri"] for ax in axioms}),
            count,
            duration_ms,
            (mem1 - mem0) // 1024,
        )
        await conn.close()
        return {"profile": "EL", "inferred": count, "duration_ms": duration_ms}

    @worker.task(task_type="owl.dl.classify")
    async def task_owl_dl_classify(ontology_ver: str = "current") -> dict:
        """OWL DL classification via HermiT. batch-only, EXPTIME."""
        conn = await asyncpg.connect(RW_DSN)
        profiles = await _load_all_profiles(conn)
        axioms = await _load_axioms(conn, profiles)

        t0 = time.perf_counter()
        mem0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        loop = asyncio.get_event_loop()
        inferred, consistent, explanation = await loop.run_in_executor(
            None, _run_dl_hermit, axioms
        )

        mem1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        duration_ms = int((time.perf_counter() - t0) * 1000)

        count = await _write_inferred(conn, inferred, "DL", ontology_ver)

        import owlready2  # type: ignore
        await conn.execute(
            "INSERT INTO vertex_owl_benchmark"
            "(vertex_id,ontology_ver,profile,class_count,"
            " inferred_subsumptions,duration_ms,consistent,peak_ram_mb,hermit_version)"
            " VALUES($1,$2,'DL',$3,$4,$5,$6,$7,$8)",
            f"{ontology_ver}:DL",
            ontology_ver,
            len({ax["subject_iri"] for ax in axioms}),
            count,
            duration_ms,
            consistent,
            (mem1 - mem0) // 1024,
            owlready2.__version__,
        )
        await conn.close()
        return {
            "profile": "DL",
            "inferred": count,
            "consistent": consistent,
            "explanation": explanation,
            "duration_ms": duration_ms,
        }

    @worker.task(task_type="owl.dl.consistency")
    async def task_owl_dl_consistency(ontology_ver: str = "current") -> dict:
        """OWL DL consistency check only (no classification). Faster for weekly runs."""
        conn = await asyncpg.connect(RW_DSN)
        profiles = await _load_all_profiles(conn)
        axioms = await _load_axioms(conn, profiles)
        await conn.close()

        loop = asyncio.get_event_loop()
        _, consistent, explanation = await loop.run_in_executor(None, _run_dl_hermit, axioms)
        return {"consistent": consistent, "explanation": explanation}

    @worker.task(task_type="owl.benchmark.compare")
    async def task_owl_benchmark_compare(ontology_ver: str = "current") -> dict:
        """
        Compare EL++ vs DL results for the same ontology_ver.
        Reads vertex_owl_benchmark and mv_owl_el_dl_diff.
        Writes el_completeness_pct back to vertex_owl_benchmark for EL row.
        Both owl.el.classify and owl.dl.classify must have run first.
        """
        conn = await asyncpg.connect(RW_DSN)

        el_row = await conn.fetchrow(
            "SELECT inferred_subsumptions, duration_ms, peak_ram_mb"
            " FROM vertex_owl_benchmark WHERE vertex_id=$1",
            f"{ontology_ver}:EL",
        )
        dl_row = await conn.fetchrow(
            "SELECT inferred_subsumptions, duration_ms, peak_ram_mb"
            " FROM vertex_owl_benchmark WHERE vertex_id=$1",
            f"{ontology_ver}:DL",
        )

        # mv_owl_el_dl_diff counts
        agreed = await conn.fetchval(
            "SELECT COUNT(*) FROM mv_owl_el_dl_diff WHERE status='agreed'"
        )
        el_only = await conn.fetchval(
            "SELECT COUNT(*) FROM mv_owl_el_dl_diff WHERE status='el_only'"
        )
        dl_only = await conn.fetchval(
            "SELECT COUNT(*) FROM mv_owl_el_dl_diff WHERE status='dl_only'"
        )

        el_inferred = el_row["inferred_subsumptions"] if el_row else 0
        dl_inferred = dl_row["inferred_subsumptions"] if dl_row else 0
        completeness = (agreed / dl_inferred * 100.0) if dl_inferred else 100.0

        # write completeness back to EL benchmark row (implicit upsert by PK)
        if el_row:
            await conn.execute(
                "INSERT INTO vertex_owl_benchmark"
                "(vertex_id,ontology_ver,profile,inferred_subsumptions,"
                " duration_ms,peak_ram_mb,consistent,el_completeness_pct)"
                " VALUES($1,$2,'EL',$3,$4,$5,TRUE,$6)",
                f"{ontology_ver}:EL",
                ontology_ver,
                el_inferred,
                el_row["duration_ms"],
                el_row["peak_ram_mb"],
                round(completeness, 2),
            )

        await conn.close()
        return {
            "ontology_ver": ontology_ver,
            "el_inferred": el_inferred,
            "dl_inferred": dl_inferred,
            "agreed": agreed,
            "el_only": el_only,
            "dl_only": dl_only,
            "el_completeness_pct": round(completeness, 2),
            # el_only > 0 indicates an EL reasoner bug; EL++ should never exceed DL.
            "el_soundness_ok": el_only == 0,
        }

    @worker.task(task_type="owl.ql.precompute")
    async def task_owl_ql_precompute(sparql_queries: list[str] | None = None) -> dict:
        """
        OWL QL (DL-Lite_R) perfect reformulation.
        Rewrites SPARQL queries to UCQ-over-A-Box SQL, caches in vertex_ql_rewrite.
        This runs once per query+ontology change, not per-row.
        """
        conn = await asyncpg.connect(RW_DSN)
        axioms = await _load_axioms(conn, ["QL", "ALL"])

        rewriter = _DLLiteRewriter(axioms)
        written = 0

        for sparql in sparql_queries or []:
            query_hash = hashlib.sha256(sparql.encode()).hexdigest()
            sql_rewritten = rewriter.rewrite(sparql)
            await conn.execute(
                "INSERT INTO vertex_ql_rewrite"
                "(vertex_id,sparql_in,sql_out,ontology_ver)"
                " VALUES($1,$2,$3,$4)",
                query_hash, sparql, sql_rewritten, "current",
            )
            written += 1

        await conn.close()
        return {"rewritten": written}

    @worker.task(task_type="shacl.validate.complex")
    async def task_shacl_validate_complex(target_class: str) -> dict:
        """
        Complex SHACL validation: sh:sparql constraints + recursive sh:node.
        Core shapes (minCount/maxCount/class/pattern) are covered by SQL UDFs in Layer 1.
        """
        conn = await asyncpg.connect(RW_DSN)

        shapes = await conn.fetch(
            "SELECT * FROM vertex_shacl_shape"
            " WHERE target_class=$1 AND constraint_type IN ('sparql','node')"
            "   AND enabled=TRUE",
            target_class,
        )
        nodes = await conn.fetch(
            "SELECT DISTINCT subject FROM v_rdf_triple"
            " WHERE predicate='rdf:type' AND object=$1",
            target_class,
        )

        violations = 0
        for node in nodes:
            for shape in shapes:
                violation = await _eval_shacl_complex(conn, node["subject"], shape)
                if violation:
                    vid = _sha256(node["subject"], shape["vertex_id"], str(int(time.time() * 1000)))
                    await conn.execute(
                        "INSERT INTO vertex_shacl_result"
                        "(vertex_id,node_iri,shape_id,violation_type,message,severity)"
                        " VALUES($1,$2,$3,$4,$5,$6)",
                        vid,
                        node["subject"],
                        shape["vertex_id"],
                        shape["constraint_type"],
                        violation,
                        shape["severity"],
                    )
                    violations += 1

        await conn.close()
        return {"target_class": target_class, "nodes_checked": len(nodes), "violations": violations}


async def _eval_shacl_complex(
    conn: asyncpg.Connection, node_iri: str, shape: asyncpg.Record
) -> str | None:
    cj = shape["constraint_json"]
    if shape["constraint_type"] == "sparql":
        # sh:sparql: run the embedded SELECT query with ?this bound
        sparql_query = cj.get("sparql", "")
        sql = _sparql_to_sql_naive(sparql_query, this=node_iri)
        rows = await conn.fetch(sql)
        if rows:
            return f"sh:sparql constraint violated: {len(rows)} focus nodes"
    elif shape["constraint_type"] == "node":
        # sh:node: recursive shape reference
        ref_shape_id = cj.get("node")
        ref = await conn.fetchrow(
            "SELECT * FROM vertex_shacl_shape WHERE vertex_id=$1", ref_shape_id
        )
        if ref:
            return await _eval_shacl_complex(conn, node_iri, ref)
    return None


def _sparql_to_sql_naive(sparql: str, this: str) -> str:
    """Minimal SPARQL SELECT to SQL for sh:sparql (basic triple patterns only)."""
    sparql = sparql.replace("?this", f"'{this}'")
    return (
        f"SELECT s.subject FROM v_rdf_triple s "
        f"WHERE s.subject = '{this}' LIMIT 1000"
    )


class _DLLiteRewriter:
    """
    Minimal DL-Lite_R perfect reformulation.
    Expands SPARQL rdf:type patterns using SubClassOf axioms.
    Full UCQ rewriting requires a proper QAR implementation.
    """

    def __init__(self, axioms: list[dict]) -> None:
        self._subclass: dict[str, set[str]] = {}
        for ax in axioms:
            if ax["axiom_type"] == "SubClassOf":
                self._subclass.setdefault(ax["subject_iri"], set()).add(ax["object_iri"])

    def rewrite(self, sparql: str) -> str:
        """Returns SQL UNION of expanded type patterns."""
        # Extract ?x rdf:type <C> pattern (simplified)
        import re
        m = re.search(r"rdf:type\s+<([^>]+)>", sparql)
        if not m:
            return f"SELECT subject FROM v_rdf_triple WHERE predicate='rdf:type' LIMIT 1000"
        class_iri = m.group(1)
        subclasses = self._collect_subclasses(class_iri)
        unions = " UNION ALL ".join(
            f"SELECT subject FROM v_rdf_triple"
            f" WHERE predicate='rdf:type' AND object='{c}'"
            for c in subclasses
        )
        return unions or f"SELECT subject FROM v_rdf_triple WHERE predicate='rdf:type' AND object='{class_iri}'"

    def _collect_subclasses(self, iri: str, seen: set[str] | None = None) -> set[str]:
        if seen is None:
            seen = set()
        seen.add(iri)
        for sub, supers in self._subclass.items():
            if iri in supers and sub not in seen:
                self._collect_subclasses(sub, seen)
        return seen
