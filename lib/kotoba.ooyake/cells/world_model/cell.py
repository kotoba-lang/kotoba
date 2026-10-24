"""WorldModelCell — ooyake cross-actor WORLD-MODEL reconcile (ADR-2606021600 §3,
depends ADR-2606011000 engi-organism-ontology + ADR-2606011800 tsumugi).

This is the missing LAYER that joins the two government-facing graphs into one
world model on the SHARED id-space:

    ooyake :gov.unit/*   (STRUCTURE — who/where/how of public administration)
       ── :gov.unit/organism ──▶  tsumugi :organism/*   (KARMA — 縁/取 power-graph)

Until now `:gov.unit/organism` was defined in the ontology but populated by no
unit and joined by no code: ooyake catalogued structure, tsumugi wove karma, and
nothing reconciled the SAME public body across both. This cell performs that
reconcile, OFFLINE and deterministically, and emits a world-model artifact.

Charter shape (read-side, the same discipline as cells/reconcile/cell.py):
  - G9 READ-SIDE — produces a *report* + a *proposed* world-model artifact under
    out/. It NEVER mutates a committed seed; applying a proposed link is a
    separate operator-gated step.
  - G1 POWER-ONLY (tsumugi §D8/§D9) — only power-bearing units (country /
    supranational / cabinet / ministry / agency / bureau / legislature / court)
    are reconciled into the karma graph. Local service surface (prefecture /
    municipality / ward / division / 窓口) is civic-wayfinding, NOT a
    取-concentration node, and is EXCLUDED by construction — never a target-list.
  - G5 SOURCING-HONESTY — confirmed links require an explicit :gov.unit/organism
    whose target organism exists; everything else is a *proposal* tagged
    :representative / :latent. No fabricated reconciliation.
  - mode="live" RAISES (planet-scale ingest + write-back is Council + operator
    gated, exactly like reconcile.py).

Two graphs in, one world model out. Stdlib only, no network, no LLM.
"""

from __future__ import annotations

import glob
import os
from typing import Any

# reuse the single-source EDN reader from the reconcile cell (load by path under a
# unique module name — both modules are named `cell`, so a plain import would clash)
import importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_RECONCILE_CELL = os.path.normpath(os.path.join(_HERE, "..", "reconcile", "cell.py"))
_spec = importlib.util.spec_from_file_location("ooyake_reconcile_cell", _RECONCILE_CELL)
_recon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_recon)
parse_edn = _recon.parse_edn

_REG = os.path.normpath(os.path.join(_HERE, "..", "..", "registry"))
_TSUMUGI_SEED = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "tsumugi", "data", "seed-power-graph.kotoba.edn")
)

# ── level → organism subkind. The keys are the power-bearing levels admitted into
# the engi karma graph (tsumugi G1). Everything else is civic service surface.
POWER_LEVEL_SUBKIND: dict[str, str] = {
    ":country": ":state",
    ":supranational": ":state",
    ":cabinet": ":state",
    ":ministry": ":agency",
    ":agency": ":agency",
    ":bureau": ":agency",
    ":legislature": ":legislature",
    ":court": ":court",
}
# governmental organism subkinds — used to detect orphans (a state body the karma
# graph knows but the structural atlas does not carry). Corps (org.corp.*) and
# corporate role nodes (org.role.*) are out of the atlas by design (they belong to
# kabuto/kanjo/tsumugi), so they are NOT orphans.
GOV_ORGANISM_SUBKINDS = {":state", ":agency", ":legislature", ":court"}


def derive_organism_id(gov_unit_id: str) -> str:
    """Deterministic, collision-free mapping of a gov-unit into the organism
    id-space: gov.jpn.meti → org.gov.jpn.meti. Honestly distinct from tsumugi's
    hand-curated org.state.* / org.corp.* ids (those match only via an explicit
    :gov.unit/organism link)."""
    if gov_unit_id.startswith("gov."):
        return "org.gov." + gov_unit_id[len("gov.") :]
    return "org.gov." + gov_unit_id


def load_gov_units(reg_dir: str | None = None) -> dict[str, dict]:
    units: dict[str, dict] = {}
    for f in sorted(glob.glob(os.path.join(reg_dir or _REG, "gov-units*.edn"))):
        doc = parse_edn(open(f, encoding="utf-8").read())
        for u in doc.get(":units", []):
            uid = u.get(":gov.unit/id")
            if uid:
                units[uid] = u
    return units


def load_organisms(seed_file: str | None = None) -> dict[str, dict]:
    """tsumugi seed-power-graph is a top-level vector of organism + 縁 records."""
    doc = parse_edn(open(seed_file or _TSUMUGI_SEED, encoding="utf-8").read())
    orgs: dict[str, dict] = {}
    for rec in doc:
        if isinstance(rec, dict) and rec.get(":organism/id"):
            orgs[rec[":organism/id"]] = rec
    return orgs


def load_edges(seed_file: str | None = None) -> list[dict]:
    """the 縁 (:en/*) edges of the tsumugi power-graph (same file, mixed vector)."""
    doc = parse_edn(open(seed_file or _TSUMUGI_SEED, encoding="utf-8").read())
    return [rec for rec in doc if isinstance(rec, dict) and rec.get(":en/id")]


# governance 縁: a government body STEWARDING/holding an entity (vs :depends-on, the
# entity's reverse dependency). These are the gov→entity paths the world model joins.
GOVERNANCE_EN_KINDS = {":tends", ":custodies"}


def reconcile_world_model(
    gov_units: dict[str, dict],
    organisms: dict[str, dict],
    edges: list[dict] | None = None,
) -> dict[str, Any]:
    """Pure function — join the structural atlas to the karma graph.

    Returns a report with, for every POWER-BEARING gov-unit, one of:
      confirmed  — explicit :gov.unit/organism → target organism exists
      derived    — no explicit link, but the derived organism id already exists
      dangling   — explicit :gov.unit/organism → target organism MISSING (G5 flag)
      proposed   — power-bearing, no counterpart → propose a latent organism + link
    plus orphan governmental organisms (in the karma graph, absent from the atlas).

    When `edges` (the tsumugi 縁) are supplied, also resolves the cross-graph
    GOVERNMENT-STEWARDSHIP join: each reconciled gov-unit → its organism → the
    entities it :tends/:custodies → the concrete "this gov body stewards that
    entity" path. This is the payload the world model exists to produce — the
    queryable join of structure (ooyake) and karma (tsumugi), not just matched nodes.
    """
    confirmed: list[dict] = []
    derived: list[dict] = []
    dangling: list[dict] = []
    proposed: list[dict] = []
    proposed_organisms: list[dict] = []
    excluded_non_power = 0
    referenced_org_ids: set[str] = set()

    for uid in sorted(gov_units):
        u = gov_units[uid]
        level = u.get(":gov.unit/level")
        subkind = POWER_LEVEL_SUBKIND.get(level)
        if subkind is None:
            excluded_non_power += 1
            continue

        explicit = u.get(":gov.unit/organism")
        if explicit:
            if explicit in organisms:
                confirmed.append({"unit": uid, "organism": explicit})
                referenced_org_ids.add(explicit)
            else:
                dangling.append({"unit": uid, "organism": explicit})
            continue

        cand = derive_organism_id(uid)
        if cand in organisms:
            derived.append({"unit": uid, "organism": cand})
            referenced_org_ids.add(cand)
            continue

        # propose: a latent organism stub + a proposed :gov.unit/organism link
        proposed.append({"unit": uid, "organism": cand})
        proposed_organisms.append(
            {
                ":organism/id": cand,
                ":organism/kind": ":institutional",
                ":organism/subkind": subkind,
                ":organism/label": u.get(":gov.unit/name-en") or u.get(":gov.unit/name-local") or uid,
                ":organism/standing": ":latent",
                ":organism/claimed?": False,
                ":organism/sourcing": ":representative",
            }
        )

    # orphan governmental organisms: the karma graph knows them, the atlas does not.
    orphan_organisms: list[dict] = []
    non_gov_organisms = 0
    for oid, o in sorted(organisms.items()):
        sk = o.get(":organism/subkind")
        is_gov = sk in GOV_ORGANISM_SUBKINDS or oid.startswith("org.state.")
        if not is_gov:
            non_gov_organisms += 1
            continue
        if oid not in referenced_org_ids:
            orphan_organisms.append({"organism": oid, "label": o.get(":organism/label")})

    # cross-graph GOVERNMENT-STEWARDSHIP join: reconciled gov-unit → organism →
    # (:tends/:custodies) → entity. The whole point of reconciling the two graphs.
    org_to_unit = {c["organism"]: c["unit"] for c in (confirmed + derived)}
    stewardship: list[dict] = []
    for e in edges or []:
        frm = e.get(":en/from")
        unit = org_to_unit.get(frm)
        if unit is None or e.get(":en/kind") not in GOVERNANCE_EN_KINDS:
            continue
        ent = e.get(":en/to")
        stewardship.append({
            "gov_unit": unit,
            "gov_organism": frm,
            "kind": e.get(":en/kind"),
            "entity": ent,
            "entity_label": (organisms.get(ent) or {}).get(":organism/label", ent),
        })
    stewardship.sort(key=lambda s: (s["gov_unit"], s["entity"]))

    power_total = len(confirmed) + len(derived) + len(dangling) + len(proposed)
    reconciled = len(confirmed) + len(derived)
    return {
        "mode": "bundled",
        "gov_units_total": len(gov_units),
        "organisms_total": len(organisms),
        "power_bearing_units": power_total,
        "excluded_non_power_units": excluded_non_power,
        "confirmed_links": confirmed,
        "derived_links": derived,
        "dangling_links": dangling,
        "proposed_links": proposed,
        "proposed_organisms": proposed_organisms,
        "orphan_gov_organisms": orphan_organisms,
        "non_gov_organisms_out_of_atlas": non_gov_organisms,
        "government_stewardship": stewardship,
        "coverage": {
            "reconciled": reconciled,
            "proposed": len(proposed),
            "dangling": len(dangling),
            "reconciled_pct": round(100.0 * reconciled / power_total, 2) if power_total else 0.0,
        },
    }


# ── world-model QUERIES (the consumable cross-graph join) ────────────────────
# Both directions over a reconcile_world_model(...) report's government_stewardship:
#   stewarded_entities_of(report, gov_unit) → what this government body stewards
#   regulators_of(report, entity)           → which government bodies steward an entity
# Pure, offline; the read surface danjo/kanae/tsumugi/himotoki consume.

def stewarded_entities_of(report: dict[str, Any], gov_unit: str) -> list[dict]:
    """forward: the entities a given (reconciled) gov-unit :tends/:custodies."""
    return [
        {"entity": s["entity"], "entity_label": s["entity_label"], "kind": s["kind"]}
        for s in report.get("government_stewardship", [])
        if s["gov_unit"] == gov_unit
    ]


def regulators_of(report: dict[str, Any], entity: str) -> list[dict]:
    """reverse: the government bodies that steward a given entity (its regulators).

    e.g. regulators_of(report, "org.corp.us.apple") → EU + US SEC. This is the
    cross-actor question the world model answers for tsumugi/danjo/kanae."""
    return [
        {"gov_unit": s["gov_unit"], "gov_organism": s["gov_organism"], "kind": s["kind"]}
        for s in report.get("government_stewardship", [])
        if s["entity"] == entity
    ]


# ── minimal EDN writer for the world-model artifact ──────────────────────────
def _edn_val(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        if v.startswith(":"):
            return v
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if v is None:
        return "nil"
    return str(v)


def _edn_map(m: dict) -> str:
    return "{" + " ".join(f"{k} {_edn_val(v)}" for k, v in m.items()) + "}"


def render_world_model_edn(report: dict[str, Any]) -> str:
    def block(title: str, key: str, rows: list[dict]) -> str:
        body = "\n  ".join(_edn_map(r) for r in rows) if rows else ""
        return f" ;; {title}\n {key}\n [{body}]\n"

    confirmed_rows = [
        {":gov.unit/id": r["unit"], ":gov.unit/organism": r["organism"], ":match": ":confirmed"}
        for r in report["confirmed_links"]
    ] + [
        {":gov.unit/id": r["unit"], ":gov.unit/organism": r["organism"], ":match": ":derived"}
        for r in report["derived_links"]
    ]
    proposed_link_rows = [
        {
            ":gov.unit/id": r["unit"],
            ":gov.unit/organism": r["organism"],
            ":proposed?": True,
            ":sourcing": ":representative",
        }
        for r in report["proposed_links"]
    ]
    head = (
        ";; world-model-v1 — ooyake↔tsumugi reconcile artifact (GENERATED; do not hand-edit)\n"
        ";; ADR-2606021600 §3 · cells/world_model/cell.py · read-side proposal (G9):\n"
        ";; :reconciled = real gov.unit↔organism joins; :proposed-* are :representative/\n"
        ";; :latent candidates the operator may apply to a seed in a separate gated step.\n"
        '{:graph {:name "world-model-v1" :cid :derived :visibility :public}\n'
    )
    stewardship_rows = [
        {
            ":gov.unit/id": s["gov_unit"],
            ":gov.unit/organism": s["gov_organism"],
            ":en/kind": s["kind"],
            ":entity": s["entity"],
        }
        for s in report.get("government_stewardship", [])
    ]
    return (
        head
        + block("RECONCILED links (gov.unit ↔ organism)", ":reconciled", confirmed_rows)
        + block("GOVERNMENT STEWARDSHIP (reconciled gov.unit → organism → :tends/:custodies → entity)",
                ":government-stewardship", stewardship_rows)
        + block("PROPOSED links (power-bearing units with no organism yet)", ":proposed-links", proposed_link_rows)
        + block("PROPOSED latent organisms (atlas-derived, claimed?=false)", ":proposed-organisms", report["proposed_organisms"])
        + block("DANGLING links (explicit :gov.unit/organism whose target is MISSING — G5)", ":dangling-links",
                [{":gov.unit/id": r["unit"], ":gov.unit/organism": r["organism"]} for r in report["dangling_links"]])
        + "}\n"
    )


class WorldModelCell:
    """ooyake world-model reconcile cell. solve(state) → world-model report (G9)."""

    def solve(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = state or {}
        mode = state.get("mode", "bundled")
        if mode == "live":
            raise RuntimeError(
                "ooyake world_model LIVE mode not activated (G4/G7). Planet-scale "
                "organism reconcile + write-back of :gov.unit/organism links to the "
                "committed seed requires Council Lv6+ ratify (ADR-2606021600) + operator "
                "enablement. Use mode='bundled' for the offline, deterministic reconcile."
            )
        if mode != "bundled":
            raise ValueError(f"unknown world_model mode: {mode!r} (expected 'bundled' or 'live')")
        gov_units = load_gov_units(state.get("reg_dir"))
        organisms = load_organisms(state.get("organism_seed"))
        edges = load_edges(state.get("organism_seed"))
        report = reconcile_world_model(gov_units, organisms, edges)
        out_dir = state.get("out_dir")
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "world-model.kotoba.edn"), "w", encoding="utf-8") as fh:
                fh.write(render_world_model_edn(report))
        return {"status": "ok", "report": report}
