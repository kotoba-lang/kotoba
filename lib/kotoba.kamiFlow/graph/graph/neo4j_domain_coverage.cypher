// =============================================================
// Domain coverage / supply chain / actor integration
// Input params:
//   $entries = [
//     {
//       domain: "semiconductor_design",
//       tool: "kami-flow",
//       layer: "verification",
//       actor: { id: "actor_fabless_design_house", name: "Fabless Design House", type: "organization" },
//       isco: ["2152"],
//       isic: ["2610"],
//       cpc:  ["G06F1/00"],
//       dsm:  ["front_end_design", "signoff"],
//       resources_in:  [{ id:"r_pdk",   name:"PDK", kind:"artifact" }],
//       resources_out: [{ id:"r_gds",   name:"GDSII", kind:"artifact" }],
//       suppliers:     [{ id:"supplier_foundry_tsmc", name:"Foundry", role:"foundry" }],
//       consumers:     [{ id:"consumer_osat", name:"OSAT", role:"packaging_test" }]
//     }
//   ]
// =============================================================

CREATE CONSTRAINT actor_id IF NOT EXISTS FOR (n:Actor) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT taxonomy_code IF NOT EXISTS FOR (n:TaxonomyCode) REQUIRE (n.scheme, n.code) IS UNIQUE;
CREATE CONSTRAINT domain_id IF NOT EXISTS FOR (n:Domain) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT tool_id IF NOT EXISTS FOR (n:Tool) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT layer_id IF NOT EXISTS FOR (n:Layer) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT cov_key IF NOT EXISTS FOR (n:Coverage) REQUIRE (n.domain_id, n.tool_id, n.layer_id) IS UNIQUE;

UNWIND $entries AS e

MERGE (d:Domain {id: e.domain})
SET d.name = coalesce(e.domain_name, e.domain)

MERGE (t:Tool {id: e.tool})
SET t.name = coalesce(e.tool_name, e.tool)

MERGE (l:Layer {id: e.layer})
SET l.name = coalesce(e.layer_name, e.layer)

MERGE (cv:Coverage {domain_id: e.domain, tool_id: e.tool, layer_id: e.layer})
SET cv.updated_at = datetime().toString()

MERGE (d)-[:HAS_COVERAGE]->(cv)
MERGE (cv)-[:BY_TOOL]->(t)
MERGE (cv)-[:AT_LAYER]->(l)

WITH e, cv, t
WHERE e.actor IS NOT NULL
MERGE (a:Actor {id: e.actor.id})
SET a.name = coalesce(e.actor.name, e.actor.id),
    a.type = coalesce(e.actor.type, "unknown")
MERGE (a)-[:OPERATES]->(t)
MERGE (a)-[:CONTRIBUTES_TO]->(cv);

UNWIND $entries AS e
UNWIND coalesce(e.isco, []) AS code
MERGE (x:TaxonomyCode {scheme: "ISCO", code: code})
MERGE (cv:Coverage {domain_id: e.domain, tool_id: e.tool, layer_id: e.layer})
MERGE (cv)-[:CLASSIFIED_AS]->(x);

UNWIND $entries AS e
UNWIND coalesce(e.isic, []) AS code
MERGE (x:TaxonomyCode {scheme: "ISIC", code: code})
MERGE (cv:Coverage {domain_id: e.domain, tool_id: e.tool, layer_id: e.layer})
MERGE (cv)-[:CLASSIFIED_AS]->(x);

UNWIND $entries AS e
UNWIND coalesce(e.cpc, []) AS code
MERGE (x:TaxonomyCode {scheme: "CPC", code: code})
MERGE (cv:Coverage {domain_id: e.domain, tool_id: e.tool, layer_id: e.layer})
MERGE (cv)-[:CLASSIFIED_AS]->(x);

UNWIND $entries AS e
UNWIND coalesce(e.dsm, []) AS code
MERGE (x:TaxonomyCode {scheme: "DSM", code: code})
MERGE (cv:Coverage {domain_id: e.domain, tool_id: e.tool, layer_id: e.layer})
MERGE (cv)-[:CLASSIFIED_AS]->(x);

UNWIND $entries AS e
UNWIND coalesce(e.resources_in, []) AS r
MERGE (res:Resource {id: r.id})
SET res.name = coalesce(r.name, r.id),
    res.kind = coalesce(r.kind, "unknown")
MERGE (cv:Coverage {domain_id: e.domain, tool_id: e.tool, layer_id: e.layer})
MERGE (res)-[:INPUT_TO]->(cv);

UNWIND $entries AS e
UNWIND coalesce(e.resources_out, []) AS r
MERGE (res:Resource {id: r.id})
SET res.name = coalesce(r.name, r.id),
    res.kind = coalesce(r.kind, "unknown")
MERGE (cv:Coverage {domain_id: e.domain, tool_id: e.tool, layer_id: e.layer})
MERGE (cv)-[:OUTPUT_OF]->(res);

UNWIND $entries AS e
UNWIND coalesce(e.suppliers, []) AS s
MERGE (sup:Actor {id: s.id})
SET sup.name = coalesce(s.name, s.id),
    sup.type = coalesce(s.role, "supplier")
MERGE (cv:Coverage {domain_id: e.domain, tool_id: e.tool, layer_id: e.layer})
MERGE (sup)-[:SUPPLIES]->(cv);

UNWIND $entries AS e
UNWIND coalesce(e.consumers, []) AS c
MERGE (con:Actor {id: c.id})
SET con.name = coalesce(c.name, c.id),
    con.type = coalesce(c.role, "consumer")
MERGE (cv:Coverage {domain_id: e.domain, tool_id: e.tool, layer_id: e.layer})
MERGE (cv)-[:DELIVERS_TO]->(con);
