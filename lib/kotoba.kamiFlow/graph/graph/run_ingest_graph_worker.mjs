#!/usr/bin/env node
import { readFile } from 'node:fs/promises';

const GRAPH_BASE = process.env.GRAPH_BASE || 'https://graph.etzhayyim.com';
const NSID = 'app.etzhayyim.kagami.graph.query';
const GRAPH_REPO_DID = process.env.GRAPH_REPO_DID || 'did:web:kami.etzhayyim.com';
const COLLECTION = process.env.GRAPH_COLLECTION || 'app.etzhayyim.apps.kami.flow.graph';
const VERTEX_TABLE = 'vertex_kami_flow_node';
const EDGE_TABLE = 'edge_kami_flow_relation';
const runsPath = process.env.RUNS_JSON || new URL('./data/runs.json', import.meta.url);
const entriesPath = process.env.ENTRIES_JSON || new URL('./data/entries_semiconductor.json', import.meta.url);

function nowMs() {
  return Date.now();
}

function lit(v) {
  if (v === null || v === undefined) return 'NULL';
  if (typeof v === 'number') return Number.isFinite(v) ? String(v) : 'NULL';
  if (typeof v === 'boolean') return v ? 'TRUE' : 'FALSE';
  const s = String(v).replace(/\\/g, '\\\\').replace(/'/g, "''");
  return `'${s}'`;
}

function mkRkey(id) {
  const s = String(id);
  return s.length <= 512 ? s : s.slice(-512);
}

async function jget(path) {
  const r = await fetch(`${GRAPH_BASE}${path}`);
  const j = await r.json().catch((error) => {
    console.warn("[silent-fail] run_ingest_graph_worker.mjs: jget json parse failed", error);
    return {};
  });
  return { status: r.status, json: j };
}

async function graphStatement(statement) {
  const r = await fetch(`${GRAPH_BASE}/xrpc/${NSID}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ statement }),
  });
  const j = await r.json().catch((error) => {
    console.warn("[silent-fail] run_ingest_graph_worker.mjs: graphStatement json parse failed", error);
    return {};
  });
  if (!r.ok || j?.error) {
    const msg = j?.message || `${r.status} ${r.statusText}`;
    throw new Error(`graph_statement_failed: ${msg}`);
  }
  return j;
}

async function ensureReady() {
  const h = await jget('/_worker/health');
  if (!h.json?.ok) throw new Error(`health_check_failed: ${JSON.stringify(h.json)}`);

  // Schema managed by Alembic — no version gate needed.
}

function makeVertexInsert(v, seq) {
  const ts = nowMs();
  return `INSERT INTO graphar.${VERTEX_TABLE} (vertex_id, rkey, repo, node_label, did, collection, status, props, _alive, _seq, timestamp_ms, owner_did, actor_did, org_did, sensitivity_ord) VALUES (${lit(v.vertex_id)}, ${lit(mkRkey(v.vertex_id))}, ${lit(GRAPH_REPO_DID)}, ${lit(v.label)}, ${lit(GRAPH_REPO_DID)}, ${lit(COLLECTION)}, 'active', ${lit(JSON.stringify(v.props || {}))}, TRUE, ${lit(seq)}, ${lit(ts)}, ${lit(GRAPH_REPO_DID)}, ${lit(GRAPH_REPO_DID)}, 'anon', 2)`;
}

function makeEdgeInsert(e, seq) {
  const ts = nowMs();
  return `INSERT INTO graphar.${EDGE_TABLE} (edge_id, relation_label, rkey, repo, src_vid, dst_vid, src_label, dst_label, weight, props, _alive, _seq, timestamp_ms, owner_did, actor_did, org_did, sensitivity_ord) VALUES (${lit(e.edge_id)}, ${lit(e.label)}, ${lit(mkRkey(e.edge_id))}, ${lit(GRAPH_REPO_DID)}, ${lit(e.src_vid)}, ${lit(e.dst_vid)}, ${lit(e.src_label)}, ${lit(e.dst_label)}, 1.0, ${lit(JSON.stringify(e.props || {}))}, TRUE, ${lit(seq)}, ${lit(ts)}, ${lit(GRAPH_REPO_DID)}, ${lit(GRAPH_REPO_DID)}, 'anon', 2)`;
}

function edgeId(label, src, dst, key = '') {
  return `${label}:${src}->${dst}${key ? ':' + key : ''}`;
}

function buildGraphObjects(runs, entries) {
  const vertices = new Map();
  const edges = new Map();

  const addV = (vertex_id, label, props) => {
    vertices.set(vertex_id, { vertex_id, label, props });
  };
  const addE = (eid, label, src_vid, dst_vid, src_label, dst_label, props = {}) => {
    edges.set(eid, { edge_id: eid, label, src_vid, dst_vid, src_label, dst_label, props });
  };

  for (const run of runs) {
    const runId = `flowrun:${run.run_id}`;
    addV(runId, 'FlowRun', run);

    const metricsId = `runmetrics:${run.run_id}`;
    addV(metricsId, 'RunMetrics', {
      rtl_port_count: run.rtl_port_count,
      floorplan_utilization: run.floorplan_utilization,
      gdsii_size_bytes: run.gdsii_size_bytes,
      equivalence_status: run.equivalence_status,
      equivalence_mismatch_count: run.equivalence_mismatch_count,
      dynamic_power_mw: run.dynamic_power_mw,
      ir_max_drop_mv: run.ir_max_drop_mv,
      dft_scan_chain_count: run.dft_scan_chain_count,
      dft_atpg_coverage: run.dft_atpg_coverage,
      si_z0_ohm: run.si_z0_ohm,
      si_eye_height_mv: run.si_eye_height_mv,
      yield_pass_ratio: run.yield_pass_ratio,
      pvt_corner_count: run.pvt_corner_count,
      sta_setup_slack_ps: run.sta_setup_slack_ps,
      sta_hold_slack_ps: run.sta_hold_slack_ps,
      drc_violations: run.drc_violations,
      lvs_mismatches: run.lvs_mismatches,
    });
    addE(edgeId('HAS_METRICS', runId, metricsId), 'HAS_METRICS', runId, metricsId, 'FlowRun', 'RunMetrics');

    for (const [checkName, pass] of (run.checks || [])) {
      const cid = `check:${run.run_id}:${checkName}`;
      addV(cid, 'CheckResult', { run_id: run.run_id, check_name: checkName, pass: Boolean(pass) });
      addE(edgeId('HAS_CHECK', runId, cid), 'HAS_CHECK', runId, cid, 'FlowRun', 'CheckResult');
    }

    for (const a of (run.artifacts || [])) {
      const aid = `artifact:${run.run_id}:${a.name}`;
      addV(aid, 'Artifact', { run_id: run.run_id, ...a });
      addE(edgeId('HAS_ARTIFACT', runId, aid), 'HAS_ARTIFACT', runId, aid, 'FlowRun', 'Artifact');
      if (a.kind === 'gdsii') {
        const rid = 'resource:r_gds';
        addV(rid, 'Resource', { id: 'r_gds', name: 'GDSII', kind: 'artifact' });
        addE(edgeId('PRODUCED_RESOURCE', runId, rid, a.name), 'PRODUCED_RESOURCE', runId, rid, 'FlowRun', 'Resource', { bytes: a.bytes, hash_fnv1a64: a.hash_fnv1a64 });
      }
    }
  }

  for (const e of entries) {
    const domainId = `domain:${e.domain}`;
    const toolId = `tool:${e.tool}`;
    const layerId = `layer:${e.layer}`;
    const coverageId = `coverage:${e.domain}:${e.tool}:${e.layer}`;

    addV(domainId, 'Domain', { id: e.domain, name: e.domain_name || e.domain });
    addV(toolId, 'Tool', { id: e.tool, name: e.tool_name || e.tool });
    addV(layerId, 'Layer', { id: e.layer, name: e.layer_name || e.layer });
    addV(coverageId, 'Coverage', { domain_id: e.domain, tool_id: e.tool, layer_id: e.layer });

    addE(edgeId('HAS_COVERAGE', domainId, coverageId), 'HAS_COVERAGE', domainId, coverageId, 'Domain', 'Coverage');
    addE(edgeId('BY_TOOL', coverageId, toolId), 'BY_TOOL', coverageId, toolId, 'Coverage', 'Tool');
    addE(edgeId('AT_LAYER', coverageId, layerId), 'AT_LAYER', coverageId, layerId, 'Coverage', 'Layer');

    if (e.actor?.id) {
      const actorId = `actor:${e.actor.id}`;
      addV(actorId, 'Actor', e.actor);
      addE(edgeId('OPERATES', actorId, toolId), 'OPERATES', actorId, toolId, 'Actor', 'Tool');
      addE(edgeId('CONTRIBUTES_TO', actorId, coverageId), 'CONTRIBUTES_TO', actorId, coverageId, 'Actor', 'Coverage');
    }

    const taxonomySpecs = [
      ['ISCO', e.isco || []],
      ['ISIC', e.isic || []],
      ['CPC', e.cpc || []],
      ['DSM', e.dsm || []],
    ];
    for (const [scheme, codes] of taxonomySpecs) {
      for (const code of codes) {
        const taxId = `taxonomy:${scheme}:${code}`;
        addV(taxId, 'TaxonomyCode', { scheme, code });
        addE(edgeId('CLASSIFIED_AS', coverageId, taxId), 'CLASSIFIED_AS', coverageId, taxId, 'Coverage', 'TaxonomyCode');
      }
    }

    for (const r of (e.resources_in || [])) {
      const rid = `resource:${r.id}`;
      addV(rid, 'Resource', r);
      addE(edgeId('INPUT_TO', rid, coverageId), 'INPUT_TO', rid, coverageId, 'Resource', 'Coverage');
    }

    for (const r of (e.resources_out || [])) {
      const rid = `resource:${r.id}`;
      addV(rid, 'Resource', r);
      addE(edgeId('OUTPUT_OF', coverageId, rid), 'OUTPUT_OF', coverageId, rid, 'Coverage', 'Resource');
    }

    for (const s of (e.suppliers || [])) {
      const sid = `actor:${s.id}`;
      addV(sid, 'Actor', { id: s.id, name: s.name, type: s.role || 'supplier' });
      addE(edgeId('SUPPLIES', sid, coverageId), 'SUPPLIES', sid, coverageId, 'Actor', 'Coverage');
    }

    for (const c of (e.consumers || [])) {
      const cid = `actor:${c.id}`;
      addV(cid, 'Actor', { id: c.id, name: c.name, type: c.role || 'consumer' });
      addE(edgeId('DELIVERS_TO', coverageId, cid), 'DELIVERS_TO', coverageId, cid, 'Coverage', 'Actor');
    }
  }

  return { vertices: [...vertices.values()], edges: [...edges.values()] };
}

async function main() {
  await ensureReady();

  const runsObj = JSON.parse(await readFile(runsPath, 'utf8'));
  const entriesObj = JSON.parse(await readFile(entriesPath, 'utf8'));
  const runs = Array.isArray(runsObj.runs) ? runsObj.runs : [];
  const entries = Array.isArray(entriesObj.entries) ? entriesObj.entries : [];

  const { vertices, edges } = buildGraphObjects(runs, entries);
  console.log(`[ingest] base=${GRAPH_BASE} vertices=${vertices.length} edges=${edges.length}`);

  let seq = Date.now() * 1000;
  for (const v of vertices) {
    await graphStatement(makeVertexInsert(v, ++seq));
  }
  for (const e of edges) {
    await graphStatement(makeEdgeInsert(e, ++seq));
  }

  const verifyV = await graphStatement(
    `SELECT node_label AS label, COUNT(*) AS cnt FROM graphar.${VERTEX_TABLE} WHERE repo = ${lit(GRAPH_REPO_DID)} GROUP BY node_label ORDER BY cnt DESC LIMIT 20`
  );
  const verifyE = await graphStatement(
    `SELECT relation_label AS label, COUNT(*) AS cnt FROM graphar.${EDGE_TABLE} WHERE repo = ${lit(GRAPH_REPO_DID)} GROUP BY relation_label ORDER BY cnt DESC LIMIT 20`
  );

  console.log('[verify] vertex labels:', JSON.stringify(verifyV.rows || []));
  console.log('[verify] edge labels:', JSON.stringify(verifyE.rows || []));
  console.log('[ingest] completed');
}

main().catch((e) => {
  console.error(String(e?.message || e));
  process.exit(1);
});
