// =======================================
// Bulk ingest: UNWIND $runs AS run
// Input param: $runs = [ SignoffReportJson, ... ]
// =======================================

// Optional constraints for run-layer entities
CREATE CONSTRAINT flowrun_id IF NOT EXISTS FOR (n:FlowRun) REQUIRE n.run_id IS UNIQUE;
CREATE CONSTRAINT runmetrics_id IF NOT EXISTS FOR (n:RunMetrics) REQUIRE n.run_id IS UNIQUE;
CREATE CONSTRAINT stage_status_id IF NOT EXISTS FOR (n:StageStatus) REQUIRE (n.run_id, n.stage_id) IS UNIQUE;
CREATE CONSTRAINT check_id IF NOT EXISTS FOR (n:CheckResult) REQUIRE (n.run_id, n.check_name) IS UNIQUE;
CREATE CONSTRAINT artifact_id IF NOT EXISTS FOR (n:Artifact) REQUIRE (n.run_id, n.name) IS UNIQUE;

// ---------- 1) FlowRun ----------
UNWIND $runs AS run
MERGE (r:FlowRun {run_id: run.run_id})
SET r += {
  input_hash_fnv1a64: run.input_hash_fnv1a64,
  policy_version: run.policy_version,
  policy_profile: run.policy_profile,
  top_module: run.top_module,
  signoff_pass: run.signoff_pass,
  created_at: coalesce(run.created_at, datetime().toString())
};

// ---------- 2) Run -> Capability(flow) ----------
UNWIND $runs AS run
MATCH (r:FlowRun {run_id: run.run_id})
MATCH (c:Capability {id:'flow'})
MERGE (r)-[:EXECUTES]->(c);

// ---------- 3) Metrics ----------
UNWIND $runs AS run
MERGE (m:RunMetrics {run_id: run.run_id})
SET m += {
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
  lvs_mismatches: run.lvs_mismatches
}
WITH run
MATCH (r:FlowRun {run_id: run.run_id})
MATCH (m:RunMetrics {run_id: run.run_id})
MERGE (r)-[:HAS_METRICS]->(m);

// ---------- 4) Checks ----------
UNWIND $runs AS run
UNWIND coalesce(run.checks, []) AS chk
MERGE (k:CheckResult {run_id: run.run_id, check_name: chk[0]})
SET k.pass = chk[1]
WITH run
MATCH (r:FlowRun {run_id: run.run_id})
MATCH (k:CheckResult {run_id: run.run_id})
MERGE (r)-[:HAS_CHECK]->(k);

// ---------- 5) Artifacts ----------
UNWIND $runs AS run
UNWIND coalesce(run.artifacts, []) AS a
MERGE (af:Artifact {run_id: run.run_id, name: a.name})
SET af += {
  kind: a.kind,
  bytes: a.bytes,
  hash_fnv1a64: a.hash_fnv1a64
}
WITH run, a
MATCH (r:FlowRun {run_id: run.run_id})
MATCH (af:Artifact {run_id: run.run_id, name: a.name})
MERGE (r)-[:HAS_ARTIFACT]->(af)
WITH run, a
WHERE a.kind = 'gdsii'
MATCH (r:FlowRun {run_id: run.run_id})
MATCH (res:Resource {id:'r_gds'})
MERGE (r)-[:PRODUCED_RESOURCE {bytes: a.bytes, hash_fnv1a64: a.hash_fnv1a64}]->(res);

// ---------- 6) Stage status ----------
UNWIND $runs AS run
UNWIND [
  {stage:'design',       pass: coalesce(run.rtl_parse_ok,false) AND size(coalesce(run.floorplan_violations,[])) = 0},
  {stage:'verification', pass: run.equivalence_status = 'Pass' AND coalesce(run.dft_atpg_coverage,0.0) >= 0.95},
  {stage:'signoff',      pass: coalesce(run.sta_setup_slack_ps,-1e9) >= 0 AND coalesce(run.sta_hold_slack_ps,-1e9) >= 0 AND coalesce(run.drc_violations,999999)=0 AND coalesce(run.lvs_mismatches,999999)=0},
  {stage:'tapeout',      pass: coalesce(run.signoff_pass,false)}
] AS s
MERGE (ss:StageStatus {run_id: run.run_id, stage_id: s.stage})
SET ss.pass = s.pass
WITH run, ss, s
MATCH (st:Stage {id:s.stage})
MERGE (ss)-[:FOR_STAGE]->(st)
WITH run, ss
MATCH (r:FlowRun {run_id: run.run_id})
MERGE (r)-[:HAS_STAGE_STATUS]->(ss);
