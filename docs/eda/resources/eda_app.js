(() => {
  const stages = [
    ["spec", "Spec", "requirements, IO, clocks, power, test intent"],
    ["arch", "Architecture", "IP blocks, buses, memories, analog boundaries"],
    ["source", "Source", ".kotoba, .cljc, RTL, SPICE, constraints"],
    ["sim", "Simulation", "unit, mixed-signal, waveform, formal checks"],
    ["synth", "Synthesis", "netlist, timing constraints, area and power"],
    ["pnr", "Floorplan/P&R", "placement, routing, congestion, clocks"],
    ["signoff", "Signoff", "DRC, LVS, STA, IR, EM, SPICE reports"],
    ["tapeout", "Tapeout", "GDS/OASIS, LEF/DEF, netlist and waiver bundle"],
    ["mask", "Mask order", "reticle plan, mask shop package, release gate"],
    ["wafer", "Wafer lot", "process traveller, PCM, lot sampling"],
    ["probe", "Probe", "wafer sort, binning, known-good die data"],
    ["package", "Package", "assembly, substrate, wirebond/flip-chip, thermal"],
    ["final", "Final test", "ATE vectors, QA, yield ramp, ship release"]
  ];
  const gates = [
    ["pdk-license", "PDK license", "PDK と rule deck の利用権"],
    ["nda-export", "NDA / export", "外部推論と foundry 送信の可否"],
    ["mask-budget", "Mask budget", "有償 mask order の承認"],
    ["foundry-slot", "Foundry slot", "lot 予約と upload window"],
    ["human-signoff", "Human signoff", "LLM ではない責任者承認"]
  ];
  const state = {
    stage: 0,
    view: "layout",
    issue: null,
    approvals: new Set(["pdk-license"]),
    datoms: [],
    llm: [],
    co: null,
    maturity: null,
    artifacts: [],
    runnerPlan: null,
    murakumoPayload: null,
    runnerResults: [],
    signoffEvidence: [],
    renderIR: null
  };
  const $ = (id) => document.getElementById(id);
  const canvas = $("eda-canvas");
  const ctx = canvas.getContext("2d");

  function cfg() {
    const ip = ["cpu", "sram", "analog", "serdes", "ml", "otp"].filter((x) => $("ip-" + x).checked);
    return {
      target: $("target").value,
      process: $("process").value,
      die: Number($("die").value),
      volume: Number($("volume").value),
      ip
    };
  }
  function hash(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
    return "bafyeda" + (h >>> 0).toString(36).padStart(7, "0");
  }
  const bareKeywords = new Set([
    "ready", "missing-inputs", "dry-run", "dry-run-until-host-approved", "requires-approval",
    "deny", "deny-by-default", "workspace-only", "required", "required-before-exec",
    "open-source", "passed", "failed", "pending", "not-applicable"
  ]);
  function ednKeyword(s) {
    return ":" + s;
  }
  function shouldKeyword(s) {
    return bareKeywords.has(s) || /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(s);
  }
  function ednString(s) {
    return JSON.stringify(String(s));
  }
  function toEdn(value, keyContext = "") {
    if (value === null || value === undefined) return "nil";
    if (typeof value === "number" || typeof value === "boolean") return String(value);
    if (typeof value === "string") return shouldKeyword(value) ? ednKeyword(value) : ednString(value);
    if (Array.isArray(value)) return "[" + value.map((x) => toEdn(x, keyContext)).join(" ") + "]";
    if (typeof value === "object") {
      return "{" + Object.entries(value).map(([k, v]) => {
        const ek = k.includes("/") || k.includes(".") ? ednKeyword(k) : ednKeyword(k);
        return ek + " " + toEdn(v, k);
      }).join(" ") + "}";
    }
    return ednString(value);
  }
  function downloadText(filename, text, type = "application/edn") {
    const blob = new Blob([text], { type });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: filename });
    a.click(); URL.revokeObjectURL(a.href);
  }
  const formatRegistry = [
    ["rtl/systemverilog", [".sv", ".svh"], "source", ["design/source-frozen", "simulation/rtl"]],
    ["rtl/verilog", [".v"], "source", ["design/source-frozen", "simulation/rtl"]],
    ["rtl/vhdl", [".vhd", ".vhdl"], "source", ["design/source-frozen", "simulation/rtl"]],
    ["analog/spice", [".sp", ".spi", ".cir", ".ckt"], "netlist", ["design/source-frozen", "simulation/mixed-signal"]],
    ["analog/cdl", [".cdl"], "netlist", ["simulation/mixed-signal", "signoff/drc-lvs-sta"]],
    ["constraint/sdc", [".sdc"], "constraint", ["design/spec-reviewed", "implementation/synthesis"]],
    ["constraint/upf", [".upf"], "constraint", ["design/spec-reviewed"]],
    ["library/liberty", [".lib"], "library", ["implementation/synthesis", "signoff/drc-lvs-sta"]],
    ["physical/lef", [".lef"], "physical", ["implementation/pnr"]],
    ["physical/def", [".def"], "physical", ["implementation/pnr"]],
    ["layout/gdsii", [".gds", ".gdsii"], "layout", ["release/tapeout-bundle", "manufacturing/mask-gated"]],
    ["layout/oasis", [".oas", ".oasis"], "layout", ["release/tapeout-bundle", "manufacturing/mask-gated"]],
    ["wave/vcd", [".vcd"], "waveform", ["simulation/rtl"]],
    ["wave/fst", [".fst"], "waveform", ["simulation/rtl"]],
    ["timing/sdf", [".sdf"], "timing", ["signoff/drc-lvs-sta"]],
    ["power/saif", [".saif"], "power", ["signoff/drc-lvs-sta"]],
    ["test/stil", [".stil"], "test", ["manufacturing/probe-package-ate"]],
    ["test/wgl", [".wgl"], "test", ["manufacturing/probe-package-ate"]],
    ["report/generic", [".rpt", ".log", ".drc", ".lvs"], "report", ["signoff/drc-lvs-sta"]],
    ["pdk/rule-deck", [".rule", ".rules", ".deck"], "pdk", ["signoff/drc-lvs-sta"]]
  ];
  const runnerAdapters = [
    { id: "runner/verilator-lint", name: "Verilator lint", software: "sw/verilator", formats: ["rtl/verilog", "rtl/systemverilog"], operation: "op/lint", command: ["verilator", "--lint-only", "--Wall", "$inputs"] },
    { id: "runner/verilator-vcd", name: "Verilator simulation scaffold", software: "sw/verilator", formats: ["rtl/verilog", "rtl/systemverilog"], operation: "op/simulate", command: ["verilator", "--cc", "--trace", "$inputs"] },
    { id: "runner/yosys-synth", name: "Yosys synthesis", software: "sw/yosys", formats: ["rtl/verilog", "rtl/systemverilog"], operation: "op/synthesize", command: ["yosys", "-p", "read_verilog -sv $inputs; synth; stat; write_json out/netlist.json"] },
    { id: "runner/opensta-timing", name: "OpenSTA timing", software: "sw/opensta", formats: ["constraint/sdc", "library/liberty", "timing/sdf"], operation: "op/analyze-timing", command: ["sta", "-exit", "flow.tcl"] },
    { id: "runner/openroad-pnr", name: "OpenROAD place and route", software: "sw/openroad", formats: ["physical/lef", "physical/def", "constraint/sdc", "library/liberty"], operation: "op/route", command: ["openroad", "flow.tcl"] },
    { id: "runner/klayout-drc", name: "KLayout DRC/layout summary", software: "sw/klayout", formats: ["layout/gdsii", "layout/oasis", "pdk/rule-deck"], operation: "op/drc", command: ["klayout", "-b", "-r", "$rule_deck", "$layout"] },
    { id: "runner/netgen-lvs", name: "Netgen LVS", software: "sw/netgen", formats: ["analog/spice", "analog/cdl", "layout/gdsii"], operation: "op/lvs", command: ["netgen", "-batch", "lvs", "$layout_netlist", "$source_netlist", "setup.tcl"] },
    { id: "runner/ngspice", name: "ngspice simulation", software: "sw/ngspice", formats: ["analog/spice"], operation: "op/simulate", command: ["ngspice", "-b", "$inputs", "-o", "out/ngspice.log"] }
  ];
  const signoffRequirements = [
    { type: "signoff/timing-pvt", coverage: "coverage/timing-corners", tool: "sw/opensta", operation: "op/analyze-timing", label: "OpenSTA PVT timing", minCorners: 3 },
    { type: "signoff/route", coverage: "coverage/power-activity", tool: "sw/openroad", operation: "op/route", label: "OpenROAD route", maxOverflow: 0 },
    { type: "signoff/drc", coverage: "coverage/drc-lvs", tool: "sw/klayout", operation: "op/drc", label: "KLayout DRC", maxViolations: 0 },
    { type: "signoff/lvs", coverage: "coverage/drc-lvs", tool: "sw/netgen", operation: "op/lvs", label: "Netgen LVS", maxMismatches: 0 },
    { type: "signoff/spice-corner", coverage: "coverage/mixed-signal", tool: "sw/ngspice", operation: "op/simulate", label: "ngspice corners" },
    { type: "signoff/ate-pattern", coverage: "coverage/ate-pattern", tool: "sw/ate-adapter", operation: "op/ate", label: "ATE pattern", minCoverage: 95 }
  ];
  function signoffEvidenceTemplate() {
    return [
      { type: "signoff/timing-pvt", tool: "sw/opensta", operation: "op/analyze-timing", status: "passed", coverage: 96, corners: 4, corner: "ss_0p72v_125c", pvt: "ss/0.72V/125C", slackNs: 0.041, outputCid: hash("opensta-pvt") },
      { type: "signoff/route", tool: "sw/openroad", operation: "op/route", status: "passed", coverage: 92, overflow: 0, outputCid: hash("openroad-route") },
      { type: "signoff/drc", tool: "sw/klayout", operation: "op/drc", status: "passed", coverage: 100, violations: 0, ruleDeckCid: hash("klayout-deck"), outputCid: hash("klayout-drc") },
      { type: "signoff/lvs", tool: "sw/netgen", operation: "op/lvs", status: "passed", coverage: 100, mismatches: 0, outputCid: hash("netgen-lvs") },
      { type: "signoff/spice-corner", tool: "sw/ngspice", operation: "op/simulate", status: "passed", coverage: 88, corner: "tt_1p8v_25c", outputCid: hash("ngspice-corner") },
      { type: "signoff/ate-pattern", tool: "sw/ate-adapter", operation: "op/ate", status: "passed", coverage: 97, vectorCoverage: 97, outputCid: hash("ate-pattern") }
    ];
  }
  function extension(path) {
    const i = path.lastIndexOf(".");
    return i >= 0 ? path.slice(i).toLowerCase() : "";
  }
  function formatForFile(name) {
    const ext = extension(name);
    const hit = formatRegistry.find(([, exts]) => exts.includes(ext));
    return hit ? { id: hit[0], kind: hit[2], evidence: hit[3], ext } : { id: "unknown", kind: "unknown", evidence: [], ext };
  }
  function countMatches(text, re) {
    return (text.match(re) || []).length;
  }
  function parseArtifact(name, text, bytes) {
    const fmt = formatForFile(name);
    const lower = text.toLowerCase();
    const summary = { format: fmt.id, kind: fmt.kind, bytes };
    const findings = [];
    if (fmt.id.startsWith("rtl/")) {
      summary.modules = countMatches(text, /\bmodule\b/g);
      summary.alwaysBlocks = countMatches(text, /\balways(_ff|_comb|_latch)?\b/g);
      summary.assigns = countMatches(text, /\bassign\b/g);
      if (!summary.modules) findings.push(["high", "RTL source has no module declaration."]);
    } else if (fmt.id === "constraint/sdc") {
      summary.clocks = countMatches(text, /\bcreate_clock\b/g);
      summary.falsePaths = countMatches(text, /\bset_false_path\b/g);
      if (!summary.clocks) findings.push(["medium", "SDC has no create_clock constraint."]);
    } else if (fmt.id.startsWith("analog/")) {
      summary.subckts = countMatches(text, /^\.subckt\b/gim);
      summary.devices = countMatches(text, /^[xmrcdlq]\w*/gim);
      if (!summary.subckts) findings.push(["medium", "Netlist has no .subckt boundary."]);
    } else if (fmt.id === "library/liberty") {
      summary.cells = countMatches(text, /\bcell\s*\(/g);
      summary.pins = countMatches(text, /\bpin\s*\(/g);
    } else if (fmt.id === "physical/def") {
      summary.components = countMatches(text, /\bCOMPONENTS\b/g);
      summary.nets = countMatches(text, /\bNETS\b/g);
    } else if (fmt.id === "wave/vcd") {
      summary.signals = countMatches(text, /\$var\b/g);
      summary.timestamps = countMatches(text, /^#\d+/gm);
    } else if (fmt.kind === "report") {
      summary.errors = countMatches(lower, /\berror\b/g);
      summary.warnings = countMatches(lower, /\bwarning\b/g);
      summary.violations = countMatches(lower, /\b(violation|violated|drc|lvs|slack)\b/g);
      if (summary.errors || summary.violations) findings.push(["high", `${summary.errors + summary.violations} report risk markers found.`]);
    } else if (fmt.kind === "layout") {
      summary.binaryLayout = true;
      summary.note = "Binary layout accepted as CID evidence; deep GDS/OASIS parse requires server adapter.";
    }
    return { ...fmt, summary, findings };
  }
  function evidenceFor(checkId) {
    return state.artifacts.some((a) => a.evidence.includes(checkId));
  }
  function score(c) {
    const complexity = c.die / 144 + c.ip.length * 0.055 + (c.process === "cmos28" ? 0.18 : 0) + (c.process === "bcd180" ? 0.1 : 0);
    const issuePenalty = state.issue ? 0.08 : 0;
    const signoff = Math.max(0, Math.min(1, state.stage / (stages.length - 1) - issuePenalty));
    const yieldPct = Math.max(42, Math.min(98, 96 - complexity * 18 - issuePenalty * 100 + signoff * 4));
    const cost = Math.round((c.die * 2.8 + c.volume * 0.18 + c.ip.length * 8) * (c.process === "cmos28" ? 4.5 : c.process === "bcd180" ? 2.2 : 1));
    return { complexity, signoff, yieldPct, cost };
  }
  function coSientistReview() {
    const c = cfg();
    const s = score(c);
    const gateCoverage = state.approvals.size / gates.length;
    const quality = Math.max(0, Math.min(100, Math.round(s.signoff * 55 + gateCoverage * 25 + (state.issue ? -18 : 10) + (c.die >= 100 ? -4 : 6))));
    const uiux = Math.max(0, Math.min(100, Math.round(72 + gateCoverage * 8 + (state.issue ? -10 : 4) + (s.signoff >= 0.5 ? 6 : 0))));
    const findings = [];
    if (quality < 70) findings.push(["high", "Add missing evidence CIDs before release or foundry handoff."]);
    if (state.issue) findings.push(["high", "Resolve timing/DRC correlation before tapeout."]);
    if (gateCoverage < 0.8) findings.push(["medium", "Approve remaining policy gates or keep vendor actions disabled."]);
    if (uiux < 82) findings.push(["medium", "Promote next action, blocking gate and artifact status in the primary scan path."]);
    if (!findings.length) findings.push(["info", "Quality and UIUX review is clean enough to continue to the next EDA stage."]);
    return { quality, uiux, gateCoverage, findings };
  }
  function readinessChecks() {
    return [
      ["design/spec-reviewed", "design", 1, "requirements, interfaces and power/timing intent reviewed"],
      ["design/source-frozen", "design", 2, ".kotoba/.cljc/RTL/SPICE sources have CIDs"],
      ["simulation/rtl", "simulation", 3, "RTL/unit regression and waveform summary available"],
      ["simulation/mixed-signal", "simulation", 3, "SPICE or mixed-signal corner smoke tests available"],
      ["implementation/synthesis", "implementation", 4, "synthesis reports, netlist and constraints are reproducible"],
      ["implementation/pnr", "implementation", 5, "DEF, congestion, clock and route reports are reproducible"],
      ["signoff/drc-lvs-sta", "signoff", 6, "DRC/LVS/STA evidence CIDs are present and current"],
      ["release/tapeout-bundle", "release", 7, "GDS/OASIS, waiver manifest and release packet exist"],
      ["manufacturing/mask-gated", "manufacturing", 8, "mask order is explicit, budgeted and human-approved"],
      ["manufacturing/probe-package-ate", "manufacturing", 12, "probe, package and final ATE plans are traceable"]
    ];
  }
  function simulationMatrix() {
    const c = cfg();
    const s = score(c);
    const simReached = state.stage >= 3;
    const signoffReached = state.stage >= 6;
    return [
      ["RTL unit regression", "Verilator", simReached ? "pass" : "pending", simReached ? Math.min(98, Math.round(72 + s.signoff * 20)) : 0],
      ["Formal smoke", "Yosys", simReached ? "pass" : "pending", simReached ? 68 : 0],
      ["Mixed-signal corners", "ngspice", c.ip.includes("analog") ? (simReached ? "pass" : "pending") : "not-applicable", c.ip.includes("analog") ? (simReached ? 61 : 0) : 100],
      ["Timing corners", "OpenSTA", signoffReached ? "pass" : "pending", signoffReached ? 84 : 0],
      ["Power activity", "OpenSTA + SAIF", signoffReached ? "pass" : "pending", signoffReached ? 76 : 0]
    ];
  }
  function resultFor(tool, operation) {
    return state.runnerResults.find((r) => r.tool === tool && r.operation === operation);
  }
  function normalizeEvidence(row) {
    const metrics = row.metrics || row["eda.signoff/metrics"] || {};
    const evidence = {
      type: row.type || row.evidenceType || row["eda.signoff/type"],
      tool: row.tool || row["eda.signoff/tool"] || row["eda.run/tool"],
      operation: row.operation || row["eda.signoff/operation"] || row["eda.run/operation"],
      status: row.status || row["eda.signoff/status"] || row["eda.run/status"] || "passed",
      coverage: Number(row.coverage ?? row["eda.signoff/coverage"] ?? row["eda.run/coverage"] ?? 0),
      corners: Number(row.corners ?? row["eda.signoff/corners"] ?? metrics.corners ?? (row.corner ? 1 : 0)),
      corner: row.corner || row["eda.signoff/corner"] || "",
      pvt: row.pvt || row["eda.signoff/pvt"] || "",
      slackNs: Number(row.slackNs ?? row["slack-ns"] ?? row["eda.signoff/slack-ns"] ?? metrics.slackNs ?? -9999),
      overflow: Number(row.overflow ?? row["eda.signoff/overflow"] ?? metrics.overflow ?? 0),
      violations: Number(row.violations ?? row["eda.signoff/violations"] ?? metrics.violations ?? 0),
      mismatches: Number(row.mismatches ?? row["eda.signoff/mismatches"] ?? metrics.mismatches ?? 0),
      vectorCoverage: Number(row.vectorCoverage ?? row["vector-coverage"] ?? row["eda.signoff/vector-coverage"] ?? row.coverage ?? 0),
      outputCid: row.outputCid || row.evidenceCid || row["eda.signoff/evidence-cid"] || row["eda.run/output-cid"] || hash(JSON.stringify(row)),
      waiverCid: row.waiverCid || row["eda.signoff/waiver-cid"] || ""
    };
    if (!evidence.type) {
      const req = signoffRequirements.find((r) => r.tool === evidence.tool && r.operation === evidence.operation);
      evidence.type = req?.type || "signoff/unknown";
    }
    return evidence;
  }
  function signoffEvidenceFor(type) {
    return state.signoffEvidence.find((e) => e.type === type);
  }
  function signoffEvidenceAssessment() {
    const rows = signoffRequirements.map((req) => {
      const e = signoffEvidenceFor(req.type);
      let pass = false;
      if (e) {
        if (req.type === "signoff/timing-pvt") pass = e.status === "passed" && e.corners >= req.minCorners && e.slackNs >= 0;
        else if (req.type === "signoff/route") pass = e.status === "passed" && e.overflow <= req.maxOverflow;
        else if (req.type === "signoff/drc") pass = e.status === "passed" && e.violations <= req.maxViolations;
        else if (req.type === "signoff/lvs") pass = e.status === "passed" && e.mismatches <= req.maxMismatches;
        else if (req.type === "signoff/ate-pattern") pass = e.status === "passed" && e.vectorCoverage >= req.minCoverage;
        else pass = e.status === "passed";
      }
      return {
        ...req,
        status: pass ? "passed" : "blocked",
        source: e ? "signoff-evidence" : "missing",
        score: pass ? Math.max(e.coverage || 0, req.minCoverage || 95) : (e?.coverage || 0),
        evidence: e?.outputCid || "",
        blocker: pass ? "" : (e ? "metric-threshold-not-met" : "evidence-missing")
      };
    });
    const passed = rows.filter((r) => r.status === "passed").length;
    return { source: state.signoffEvidence.length ? "signoff-evidence" : "missing", rows, passed, total: rows.length, score: Math.round(rows.reduce((n, r) => n + r.score, 0) / rows.length) };
  }
  function signoffCoverageFor(id) {
    const rows = signoffEvidenceAssessment().rows.filter((r) => r.coverage === id);
    if (!rows.length) return null;
    return {
      source: "signoff-evidence",
      status: rows.every((r) => r.status === "passed") ? "pass" : "blocked",
      score: Math.round(rows.reduce((n, r) => n + r.score, 0) / rows.length),
      evidence: rows.map((r) => r.evidence).filter(Boolean).join(",")
    };
  }
  function coverageAssessment() {
    const base = simulationMatrix();
    const source = state.signoffEvidence.length ? "signoff-evidence" : state.runnerResults.length ? "runner-result" : "stage-model";
    const rows = [
      ["coverage/rtl-unit", "Verilator", "sw/verilator", "op/simulate", base[0]],
      ["coverage/formal-smoke", "Yosys", "sw/yosys", "op/synthesize", base[1]],
      ["coverage/mixed-signal", "ngspice", "sw/ngspice", "op/simulate", base[2]],
      ["coverage/timing-corners", "OpenSTA", "sw/opensta", "op/analyze-timing", base[3]],
      ["coverage/power-activity", "OpenSTA", "sw/opensta", "op/analyze-power", base[4]],
      ["coverage/drc-lvs", "KLayout/Netgen", "sw/klayout", "op/drc", ["DRC/LVS", "KLayout/Netgen", state.stage >= 6 ? "pending" : "pending", state.stage >= 6 ? 40 : 0]],
      ["coverage/ate-pattern", "ATE", "sw/ate-adapter", "op/ate", ["ATE pattern", "ATE", state.stage >= 12 ? "pending" : "pending", state.stage >= 12 ? 35 : 0]]
    ].map(([id, label, tool, op, fallback]) => {
      const rr = resultFor(tool, op);
      const sr = signoffCoverageFor(id);
      return {
        id,
        label,
        source: sr ? sr.source : rr ? "runner-result" : source,
        status: sr?.status || rr?.status || fallback[2],
        score: sr?.score ?? rr?.coverage ?? fallback[3],
        evidence: sr?.evidence || rr?.outputCid || rr?.adapter || ""
      };
    });
    return { source, rows, score: Math.round(rows.reduce((n, x) => n + x.score, 0) / rows.length) };
  }
  function maturityAssessment() {
    const signoff = signoffEvidenceAssessment();
    const checks = readinessChecks().map(([id, category, requiredStage, role]) => {
      const stageOk = state.stage >= requiredStage;
      const artifactOk = evidenceFor(id);
      const signoffOk = id === "signoff/drc-lvs-sta"
        ? ["signoff/timing-pvt", "signoff/drc", "signoff/lvs"].every((type) => signoff.rows.find((r) => r.type === type && r.status === "passed"))
        : id === "manufacturing/probe-package-ate"
          ? signoff.rows.some((r) => r.type === "signoff/ate-pattern" && r.status === "passed")
          : false;
      const gateOk = id === "manufacturing/mask-gated" ? state.approvals.has("mask-budget") && state.approvals.has("human-signoff") : true;
      const pass = (stageOk || artifactOk || signoffOk) && gateOk && !state.issue;
      return {
        id,
        category,
        role,
        status: pass ? "pass" : "block",
        blocker: state.issue ? "blocked-by-signoff-issue" : !(stageOk || artifactOk || signoffOk) ? "stage-or-evidence-missing" : !gateOk ? "policy-gate-missing" : "",
        cid: pass ? (state.artifacts.find((a) => a.evidence.includes(id))?.cid || signoff.rows.find((r) => r.evidence)?.evidence || hash("readiness" + id + JSON.stringify(cfg()))) : ""
      };
    });
    const passed = checks.filter((x) => x.status === "pass").length;
    const readiness = Math.round((passed / checks.length) * 100);
    const sims = simulationMatrix();
    const coverage = coverageAssessment();
    const simCoverage = coverage.score;
    const level = passed === checks.length && simCoverage >= 85 && signoff.passed === signoff.total && state.approvals.has("foundry-slot") && state.approvals.has("human-signoff")
      ? "MRL release-ready"
      : readiness >= 80 && simCoverage >= 75
        ? "MRL pilot-ready"
        : readiness >= 55 && simCoverage >= 50
          ? "MRL engineering-ready"
          : readiness >= 30
            ? "MRL prototype"
            : "MRL concept";
    const useableFor = level === "MRL release-ready"
      ? ["foundry handoff", "mask order", "pilot lot", "ATE release"]
      : level === "MRL pilot-ready"
        ? ["internal tapeout review", "MPW precheck", "package planning"]
        : level === "MRL engineering-ready"
          ? ["design review", "simulation regression", "P&R iteration"]
          : level === "MRL prototype"
            ? ["architecture review", "source bringup", "testbench work"]
            : ["requirements work"];
    return { level, readiness, simCoverage, passed, total: checks.length, checks, sims, coverage, signoff, useableFor };
  }
  function transact(kind, body) {
    const time = new Date().toISOString();
    const datom = { time, kind, stage: stages[state.stage][0], ...body };
    state.datoms.unshift(datom);
    return datom;
  }
  async function ingestArtifacts(files) {
    for (const file of files) {
      const fmt = formatForFile(file.name);
      const text = fmt.kind === "layout" || fmt.id === "wave/fst" ? "" : await file.text();
      const cid = hash(file.name + ":" + file.size + ":" + text.slice(0, 4096));
      const parsed = parseArtifact(file.name, text, file.size);
      const artifact = {
        name: file.name,
        cid,
        format: parsed.id,
        kind: parsed.kind,
        evidence: parsed.evidence,
        summary: parsed.summary,
        findings: parsed.findings
      };
      state.artifacts.unshift(artifact);
      transact(":eda.artifact/ingest", {
        path: artifact.name,
        cid,
        format: artifact.format,
        bytes: file.size,
        evidence: artifact.evidence
      });
      transact(":eda.parser/summary", {
        cid,
        format: artifact.format,
        summary: artifact.summary
      });
      artifact.findings.forEach(([severity, text]) => {
        transact(":eda.report/finding", { cid, severity, text });
      });
    }
    proposal(`${files.length} artifact(s) ingested and converted to EDN manifest summaries in-browser. External EDA execution still requires a runner adapter.`, "info");
    refresh();
  }
  async function importRunnerResults(files) {
    for (const file of files) {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const rows = Array.isArray(parsed) ? parsed : parsed.results || parsed["eda.runner/results"] || [parsed];
      rows.forEach((row) => {
        const result = {
          adapter: row.adapter || row["eda.run/adapter"],
          tool: row.tool || row["eda.run/tool"],
          operation: row.operation || row["eda.run/operation"],
          status: row.status || row["eda.run/status"] || "passed",
          coverage: Number(row.coverage ?? row["eda.run/coverage"] ?? (row.status === "failed" ? 20 : 80)),
          outputCid: row.outputCid || row["eda.run/output-cid"] || hash(JSON.stringify(row))
        };
        state.runnerResults.unshift(result);
        transact(":eda.run/result", result);
        transact(":eda.coverage/sample", {
          tool: result.tool,
          operation: result.operation,
          status: result.status,
          coverage: result.coverage,
          evidenceCid: result.outputCid
        });
      });
    }
    proposal(`${files.length} runner result file(s) imported; coverage now prefers runner-result evidence over stage fallback.`, "info");
    refresh();
  }
  async function importSignoffEvidence(files) {
    for (const file of files) {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const rows = Array.isArray(parsed) ? parsed : parsed.results || parsed.evidence || parsed["eda.signoff/evidence"] || [parsed];
      rows.forEach((row) => {
        const evidence = normalizeEvidence(row);
        state.signoffEvidence.unshift(evidence);
        state.runnerResults.unshift({
          adapter: evidence.type,
          tool: evidence.tool,
          operation: evidence.operation,
          status: evidence.status,
          coverage: evidence.coverage,
          outputCid: evidence.outputCid
        });
        transact(":eda.signoff/evidence", evidence);
        transact(":eda.coverage/sample", {
          tool: evidence.tool,
          operation: evidence.operation,
          status: evidence.status,
          coverage: evidence.coverage,
          evidenceCid: evidence.outputCid
        });
      });
    }
    proposal(`${files.length} signoff evidence file(s) imported; release readiness now requires PVT/DRC/LVS/ATE evidence thresholds.`, "info");
    refresh();
  }
  function buildPreviewRunnerPlan() {
    return {
      "eda.job/id": "preview",
      "eda.job/adapters": runnerAdapters.map((adapter) => {
        const inputs = state.artifacts.filter((a) => adapter.formats.includes(a.format));
        return {
          "eda.job.adapter/id": adapter.id,
          "eda.job.adapter/name": adapter.name,
          "eda.job.adapter/software": adapter.software,
          "eda.job.adapter/status": inputs.length ? "ready" : "missing-inputs"
        };
      })
    };
  }
  function buildRunnerPlan() {
    const job = {
      "eda.job/schema": 1,
      "eda.job/kind": "eda.runner/job-plan",
      "eda.job/id": "eda-job-" + hash(JSON.stringify(state.artifacts)).slice(-8),
      "eda.job/mode": "dry-run-until-host-approved",
      "eda.job/adapters": runnerAdapters.map((adapter) => {
        const inputs = state.artifacts.filter((a) => adapter.formats.includes(a.format));
        return {
          "eda.job.adapter/id": adapter.id,
          "eda.job.adapter/name": adapter.name,
          "eda.job.adapter/software": adapter.software,
          "eda.job.adapter/operation": adapter.operation,
          "eda.job.adapter/status": inputs.length ? "ready" : "missing-inputs",
          "eda.job.adapter/inputs": inputs.map((a) => ({ path: a.name, cid: a.cid, format: a.format })),
          "eda.job.adapter/command": {
            "eda.command/argv": adapter.command,
            "eda.command/input-cids": inputs.map((a) => a.cid),
            "eda.command/input-paths": inputs.map((a) => a.name),
            "eda.command/policy": { network: "deny", filesystem: "workspace-only", approval: "required-before-exec" }
          }
        };
      })
    };
    state.runnerPlan = job;
    transact(":eda.runner/plan", {
      id: job["eda.job/id"],
      ready: job["eda.job/adapters"].filter((a) => a["eda.job.adapter/status"] === "ready").length,
      total: job["eda.job/adapters"].length
    });
    proposal("Runner adapter plan built. Download it and execute with host/murakumo runner after policy approval.", "info");
    refresh();
  }
  function buildMurakumoPayload() {
    const runnerPlan = state.runnerPlan || buildPreviewRunnerPlan();
    const runId = "eda-run-" + hash(JSON.stringify({ runnerPlan, artifacts: state.artifacts, gates: Array.from(state.approvals) })).slice(-8);
    const payload = {
      "eda.murakumo/schema": 1,
      "eda.murakumo/run-id": runId,
      "eda.murakumo/kind": "eda.runner/job",
      "eda.murakumo/project": "kotoba-eda-" + cfg().target,
      "eda.murakumo/mode": "dry-run",
      "eda.murakumo/placement": {
        reach: ["tailnet", "local-workspace"],
        class: ["mac-mini", "linux-workstation", "licensed-runner"],
        requires: ["cpu", "workspace-fs"],
        forbids: ["public-internet-egress"]
      },
      "eda.murakumo/policy": {
        network: "deny-by-default",
        filesystem: "workspace-only",
        licenseCheck: "required",
        pdkExport: "deny-by-default",
        paidAction: "approval-required",
        humanSignoff: "required-for-vendor-upload",
        approvals: Object.fromEntries(gates.map(([id]) => [id, state.approvals.has(id)]))
      },
      "eda.murakumo/runner-plan": runnerPlan,
      "eda.murakumo/artifacts": state.artifacts,
      "eda.murakumo/ready-adapters": runnerPlan["eda.job/adapters"].filter((a) => a["eda.job.adapter/status"] === "ready").map((a) => a["eda.job.adapter/id"]),
      "eda.murakumo/events-path": `/v1/eda/runs/${runId}/events`
    };
    state.murakumoPayload = payload;
    transact(":eda.murakumo/submit-payload", {
      runId,
      readyAdapters: payload["eda.murakumo/ready-adapters"].length,
      mode: payload["eda.murakumo/mode"]
    });
    proposal("Murakumo submit payload built. This is a dry-run payload until a host runner receives policy approval.", "info");
    refresh();
  }
  function proposal(text, severity = "info") {
    state.llm.unshift({ time: new Date().toISOString(), severity, text });
  }
  function runCoSientistReview() {
    state.co = coSientistReview();
    transact(":eda.review/co-sientist", {
      quality: state.co.quality,
      uiux: state.co.uiux,
      gateCoverage: Number((state.co.gateCoverage * 100).toFixed(1)),
      findings: state.co.findings.length
    });
    proposal("Co-sientist reviewed quality and UIUX. Results are proposal-only and cannot approve signoff.", "info");
    refresh();
  }
  function runMaturityAudit() {
    state.maturity = maturityAssessment();
    transact(":eda.maturity/audit", {
      level: state.maturity.level,
      readiness: state.maturity.readiness,
      simulationCoverage: state.maturity.simCoverage,
      blockers: state.maturity.checks.filter((x) => x.status === "block").length
    });
    proposal("Maturity audit updated manufacturing readiness, simulation coverage, evidence CIDs and blockers.", "info");
    refresh();
  }
  function runStage() {
    const c = cfg();
    const [id, name] = stages[state.stage];
    const cid = hash(JSON.stringify({ id, c, stage: state.stage, issue: state.issue }));
    const status = state.issue && state.stage >= 6 && state.stage < 8 ? "blocked" : "passed";
    transact(":eda.run/complete", { tool: "murakumo." + id, status, cid });
    if (status === "blocked") {
      transact(":eda.report/finding", { severity: "high", rule: "timing-drc-correlation", cid: hash("finding" + cid) });
      proposal("STA と DRC overlay の相関から、clock spine 近傍の keepout と buffer sizing を見直す proposal を生成しました。", "warn");
    } else {
      proposal(name + " completed. LLM は report 要約と次工程 plan の proposal のみを保存しました。");
      if (state.stage < stages.length - 1) state.stage += 1;
    }
    refresh();
  }
  function runAll() {
    let guard = 0;
    while (state.stage < stages.length - 1 && guard < 20) {
      runStage();
      if (state.issue && state.stage >= 6 && state.stage < 8) break;
      guard += 1;
    }
  }
  function renderStages() {
    $("stages").innerHTML = stages.map(([id, name, desc], i) => {
      const klass = i < state.stage ? "stage done" : i === state.stage ? "stage active" : "stage";
      const fail = state.issue && i === state.stage && i >= 6 ? " fail" : "";
      return `<div class="${klass}${fail}"><b>${i + 1}. ${name}</b><span>${desc}</span><span class="mono">${id}</span></div>`;
    }).join("");
  }
  function renderGates() {
    $("gates").innerHTML = gates.map(([id, name, desc]) => {
      const ok = state.approvals.has(id);
      return `<div class="gate"><div><strong>${name}</strong><span>${desc}</span></div><button data-gate="${id}">${ok ? "approved" : "approve"}</button></div>`;
    }).join("");
    document.querySelectorAll("[data-gate]").forEach((b) => b.onclick = () => {
      state.approvals.add(b.dataset.gate);
      transact(":eda.policy/approve", { gate: b.dataset.gate, approver: "human" });
      refresh();
    });
  }
  function renderLogs() {
    $("datom-log").innerHTML = state.datoms.slice(0, 80).map((d) => `<div class="log-row"><b>${d.kind}</b><small>${d.time} · ${d.stage} · ${d.status || d.gate || d.cid || ""}</small></div>`).join("");
    $("llm-log").innerHTML = state.llm.slice(0, 30).map((d) => `<div class="log-row"><b>${d.severity}</b><small>${d.time}</small>${d.text}</div>`).join("");
  }
  function renderArtifacts() {
    $("artifact-log").innerHTML = state.artifacts.slice(0, 30).map((a) => {
      const fields = Object.entries(a.summary).slice(0, 5).map(([k, v]) => `${k}:${v}`).join(" ");
      return `<div class="log-row"><b>${a.format}</b><small>${a.name} · ${a.cid}</small>${fields}</div>`;
    }).join("") || `<div class="log-row"><b>empty</b><small>Upload .sv, .sdc, .sp, .lib, .def, .gds, .vcd, .rpt and related EDA files.</small>No artifacts ingested yet.</div>`;
  }
  function renderRunnerPlan() {
    const plan = state.runnerPlan || buildPreviewRunnerPlan();
    $("runner-log").innerHTML = plan["eda.job/adapters"].map((a) => `<div class="log-row"><b>${a["eda.job.adapter/status"]}</b><small>${a["eda.job.adapter/id"]} · ${a["eda.job.adapter/software"]}</small>${a["eda.job.adapter/name"]}</div>`).join("");
    const payload = state.murakumoPayload;
    $("murakumo-log").innerHTML = payload
      ? `<div class="log-row"><b>${payload["eda.murakumo/mode"]}</b><small>${payload["eda.murakumo/run-id"]} · ${payload["eda.murakumo/events-path"]}</small>${payload["eda.murakumo/ready-adapters"].length} ready adapter(s)</div>`
      : `<div class="log-row"><b>empty</b><small>Build a runner plan first, then build murakumo payload.</small>No submit payload yet.</div>`;
  }
  function renderCoSientist() {
    const co = state.co || coSientistReview();
    $("co-scores").innerHTML = [
      ["Quality", co.quality],
      ["UIUX", co.uiux],
      ["Gates", Math.round(co.gateCoverage * 100)]
    ].map(([label, value]) => `<div class="score-row"><b>${label}</b><div class="bar"><span style="width:${value}%"></span></div><span>${value}%</span></div>`).join("");
    $("co-findings").innerHTML = co.findings.map(([severity, text]) => `<div class="log-row"><b>${severity}</b><small>co-sientist proposal</small>${text}</div>`).join("");
  }
  function renderMaturity() {
    const m = state.maturity || maturityAssessment();
    $("maturity-cards").innerHTML = [
      ["Maturity", m.level],
      ["Readiness", m.readiness + "%"],
      ["Simulation", m.simCoverage + "%"]
    ].map(([label, value]) => `<div class="maturity-card"><span>${label}</span><b>${value}</b></div>`).join("");
    $("maturity-use").innerHTML = `<div class="badges">${m.useableFor.map((x) => `<span class="badge ok">${x}</span>`).join("")}</div>`;
    $("sim-matrix").innerHTML = m.sims.map(([name, tool, status, coverage]) => `<tr><td>${name}</td><td>${tool}</td><td>${status}</td><td>${coverage}%</td></tr>`).join("");
    $("readiness-log").innerHTML = m.checks.map((x) => `<div class="log-row"><b>${x.status}</b><small>${x.category} · ${x.id} · ${x.cid || x.blocker}</small>${x.role}</div>`).join("");
  }
  function renderCoverage() {
    const c = coverageAssessment();
    const signoff = signoffEvidenceAssessment();
    $("coverage-cards").innerHTML = [
      ["Coverage", c.score + "%"],
      ["Source", c.source],
      ["Samples", String(state.runnerResults.length)],
      ["Signoff", `${signoff.passed}/${signoff.total}`]
    ].map(([label, value]) => `<div class="maturity-card"><span>${label}</span><b>${value}</b></div>`).join("");
    $("coverage-matrix").innerHTML = c.rows.map((r) => `<tr><td>${r.id}</td><td>${r.source}</td><td>${r.status}</td><td>${r.score}%</td></tr>`).join("");
    $("signoff-evidence-matrix").innerHTML = signoff.rows.map((r) => `<tr><td>${r.label}</td><td>${r.tool}</td><td>${r.status}</td><td>${r.evidence || r.blocker}</td></tr>`).join("");
    $("runner-result-log").innerHTML = state.runnerResults.slice(0, 20).map((r) => `<div class="log-row"><b>${r.status}</b><small>${r.tool} · ${r.operation} · ${r.outputCid}</small>${r.coverage}% coverage</div>`).join("")
      || `<div class="log-row"><b>fallback</b><small>stage-model</small>No runner result imported yet.</div>`;
  }
  function makeRenderIR(c, s) {
    const dies = c.ip.map((ip, i) => ({
      id: "macro-" + ip,
      layer: i % 3 === 0 ? "M1" : i % 3 === 1 ? "M4" : "Mtop",
      x: 90 + (i % 3) * 210,
      y: 90 + Math.floor(i / 3) * 140,
      w: 140 + (ip === "ml" ? 70 : 0),
      h: 80 + (ip === "sram" ? 45 : 0),
      color: ["#2563eb", "#16825d", "#c2410c", "#0891b2", "#6d28d9", "#b45309"][i % 6]
    }));
    return {
      "frame/n": state.stage,
      "frame/clear": [0.97, 0.98, 0.99, 1.0],
      "frame/kami-engine": "render-ir-compatible",
      "eda/project": c.target,
      "eda/process": c.process,
      "eda/stage": stages[state.stage][0],
      "eda/signoff": Number((s.signoff * 100).toFixed(1)),
      "eda/yield": Number(s.yieldPct.toFixed(1)),
      "eda/co-sientist": state.co || coSientistReview(),
      "eda/maturity": state.maturity || maturityAssessment(),
      "eda/coverage": coverageAssessment(),
      "frame/passes": [{
        "pass/id": "eda-main",
        "pass/target": "canvas",
        "pass/draws": dies.map((d) => ({
          "draw/pipeline": "eda-layer-rect",
          "draw/mesh": "rect",
          "draw/material": d.layer,
          "draw/instances": { count: 1, rect: [d.x, d.y, d.w, d.h], tint: d.color, label: d.id }
        }))
      }]
    };
  }
  function drawLayout(ir) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#e5eaf2"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#f8fafc"; ctx.strokeStyle = "#334155"; ctx.lineWidth = 2;
    ctx.fillRect(60, 60, 700, 430); ctx.strokeRect(60, 60, 700, 430);
    const draws = ir["frame/passes"][0]["pass/draws"];
    draws.forEach((draw) => {
      const r = draw["draw/instances"].rect;
      ctx.fillStyle = draw["draw/instances"].tint;
      ctx.globalAlpha = 0.82;
      ctx.fillRect(r[0], r[1], r[2], r[3]);
      ctx.globalAlpha = 1;
      ctx.strokeStyle = "#0f172a"; ctx.strokeRect(r[0], r[1], r[2], r[3]);
      ctx.fillStyle = "#fff"; ctx.font = "18px " + getComputedStyle(document.body).fontFamily;
      ctx.fillText(draw["draw/instances"].label, r[0] + 10, r[1] + 28);
    });
    ctx.fillStyle = "#172033"; ctx.font = "24px " + getComputedStyle(document.body).fontFamily;
    ctx.fillText("GDS/OASIS layout view · " + cfg().process, 60, 535);
  }
  function drawFlow() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#f8fafc"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    stages.forEach((st, i) => {
      const col = i % 5, row = Math.floor(i / 5);
      const x = 55 + col * 200, y = 70 + row * 155;
      ctx.fillStyle = i < state.stage ? "#dcfce7" : i === state.stage ? "#dbeafe" : "#fff";
      ctx.strokeStyle = i === state.stage ? "#2563eb" : "#cbd5e1";
      ctx.lineWidth = i === state.stage ? 3 : 1;
      ctx.fillRect(x, y, 155, 74); ctx.strokeRect(x, y, 155, 74);
      ctx.fillStyle = "#172033"; ctx.font = "17px " + getComputedStyle(document.body).fontFamily;
      ctx.fillText(st[1], x + 12, y + 32);
      ctx.fillStyle = "#667085"; ctx.font = "12px " + getComputedStyle(document.body).fontFamily;
      ctx.fillText(st[0], x + 12, y + 54);
    });
  }
  function drawWafer() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#eef2f7"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.beginPath(); ctx.arc(360, 310, 230, 0, Math.PI * 2); ctx.fillStyle = "#f8fafc"; ctx.fill(); ctx.strokeStyle = "#334155"; ctx.stroke();
    const c = cfg(), s = score(c);
    for (let y = -7; y <= 7; y++) for (let x = -7; x <= 7; x++) {
      if (x*x + y*y < 49) {
        const pass = ((x * 13 + y * 17 + state.stage * 11) % 100 + 100) % 100 < s.yieldPct;
        ctx.fillStyle = pass ? "#16a34a" : "#dc2626";
        ctx.fillRect(360 + x * 27 - 10, 310 + y * 27 - 10, 20, 20);
      }
    }
    ctx.fillStyle = "#172033"; ctx.font = "26px " + getComputedStyle(document.body).fontFamily;
    ctx.fillText("Wafer sort yield " + s.yieldPct.toFixed(1) + "%", 650, 210);
    ctx.font = "16px " + getComputedStyle(document.body).fontFamily;
    ctx.fillText("Probe map and binning become :eda.manufacturing/probe datoms.", 650, 245);
  }
  function drawPackage() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#f8fafc"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#dbeafe"; ctx.strokeStyle = "#1d4ed8"; ctx.lineWidth = 3;
    ctx.fillRect(250, 210, 520, 230); ctx.strokeRect(250, 210, 520, 230);
    ctx.fillStyle = "#172033"; ctx.fillRect(410, 280, 200, 95);
    ctx.fillStyle = "#fff"; ctx.font = "22px " + getComputedStyle(document.body).fontFamily; ctx.fillText("DIE", 488, 335);
    ctx.strokeStyle = "#b45309"; ctx.lineWidth = 2;
    for (let i = 0; i < 18; i++) {
      ctx.beginPath(); ctx.moveTo(420 + i * 10, 280); ctx.lineTo(280 + i * 28, 210); ctx.stroke();
    }
    ctx.fillStyle = "#172033"; ctx.font = "24px " + getComputedStyle(document.body).fontFamily;
    ctx.fillText("Package / assembly / thermal view", 250, 500);
  }
  function draw() {
    const c = cfg(), s = score(c);
    const ir = makeRenderIR(c, s);
    state.renderIR = ir;
    if (state.view === "layout") drawLayout(ir);
    if (state.view === "flow") drawFlow();
    if (state.view === "wafer") drawWafer();
    if (state.view === "package") drawPackage();
    $("render-ir").textContent = JSON.stringify(ir, null, 2);
  }
  function packet() {
    const c = cfg(), s = score(c);
    return {
      project: "kotoba-eda-" + c.target,
      process: c.process,
      stage: stages[state.stage][0],
      gates: gates.map(([id]) => [id, state.approvals.has(id)]),
      artifactCount: state.artifacts.length,
      artifacts: {
        source: hash("source" + JSON.stringify(c)),
        netlist: hash("netlist" + JSON.stringify(c)),
        gds: hash("gds" + JSON.stringify(c)),
        reports: hash("reports" + state.datoms.length),
        waivers: hash("waivers" + (state.issue || "none"))
      },
      manufacturing: {
        maskOrder: state.approvals.has("mask-budget") && state.approvals.has("human-signoff") ? "ready" : "gated",
        foundryUpload: state.approvals.has("foundry-slot") ? "ready" : "gated",
        waferTraveller: ["lot-start", "implant", "metallization", "pcm", "probe"],
        packageBom: ["substrate", "die-attach", "bond", "mold", "mark"],
        ateCoverage: Math.round(s.signoff * 100),
        expectedYield: Number(s.yieldPct.toFixed(1))
      },
      maturity: state.maturity || maturityAssessment(),
      signoffEvidence: signoffEvidenceAssessment(),
      signoffEvidenceDatoms: state.signoffEvidence,
      artifactManifests: state.artifacts
    };
  }
  function refresh() {
    const c = cfg(), s = score(c);
    state.maturity = maturityAssessment();
    $("die-label").textContent = c.die + " mm²";
    $("volume-label").textContent = c.volume + "k units";
    $("metric-stage").textContent = stages[state.stage][1];
    $("metric-signoff").textContent = Math.round(s.signoff * 100) + "%";
    $("metric-yield").textContent = s.yieldPct.toFixed(1) + "%";
    $("metric-cost").textContent = "$" + s.cost + "k";
    $("mfg-summary").textContent = JSON.stringify(packet().manufacturing);
    renderStages(); renderGates(); renderLogs(); renderArtifacts(); renderRunnerPlan(); renderCoSientist(); renderMaturity(); renderCoverage(); draw();
  }
  document.querySelectorAll("select,input").forEach((el) => el.addEventListener("input", () => {
    transact(":eda.project/update", cfg());
    refresh();
  }));
  document.querySelectorAll(".canvas-tabs button").forEach((b) => b.onclick = () => {
    document.querySelectorAll(".canvas-tabs button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    state.view = b.dataset.view;
    draw();
  });
  $("advance").onclick = runStage;
  $("run-all").onclick = runAll;
  $("co-review").onclick = runCoSientistReview;
  $("maturity-audit").onclick = runMaturityAudit;
  $("runner-plan").onclick = buildRunnerPlan;
  $("murakumo-submit").onclick = buildMurakumoPayload;
  $("inject").onclick = () => {
    state.issue = state.issue ? null : "timing-drc-correlation";
    transact(":eda.issue/toggle", { issue: state.issue || "cleared" });
    proposal(state.issue ? "意図的な signoff issue を追加しました。DRC/LVS/STA の gate で止まります。" : "issue を解除しました。", state.issue ? "warn" : "info");
    refresh();
  };
  $("export-json").onclick = () => {
    const blob = new Blob([JSON.stringify(state.datoms, null, 2)], { type: "application/json" });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "kotoba-eda-datoms.json" });
    a.click(); URL.revokeObjectURL(a.href);
  };
  $("download-packet").onclick = () => {
    const blob = new Blob([JSON.stringify(packet(), null, 2)], { type: "application/json" });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: "kotoba-eda-manufacturing-packet.json" });
    a.click(); URL.revokeObjectURL(a.href);
  };
  $("download-runner-plan").onclick = () => {
    const plan = state.runnerPlan || buildPreviewRunnerPlan();
    downloadText("kotoba-eda-runner-plan.edn", toEdn(plan) + "\n");
  };
  $("download-murakumo-payload").onclick = () => {
    const payload = state.murakumoPayload || buildMurakumoPayload() || state.murakumoPayload;
    downloadText("kotoba-eda-murakumo-submit.edn", toEdn(payload) + "\n");
  };
  $("download-signoff-template").onclick = () => {
    downloadText("kotoba-eda-signoff-evidence-template.json", JSON.stringify(signoffEvidenceTemplate(), null, 2) + "\n", "application/json");
  };
  $("load-sample-signoff").onclick = () => {
    signoffEvidenceTemplate().forEach((row) => {
      const evidence = normalizeEvidence(row);
      state.signoffEvidence.unshift(evidence);
      state.runnerResults.unshift({
        adapter: evidence.type,
        tool: evidence.tool,
        operation: evidence.operation,
        status: evidence.status,
        coverage: evidence.coverage,
        outputCid: evidence.outputCid
      });
      transact(":eda.signoff/evidence", evidence);
    });
    proposal("Sample OpenSTA/OpenROAD/KLayout/Netgen/ngspice/ATE signoff evidence loaded. Release-ready still requires foundry-slot and human-signoff approvals.", "info");
    refresh();
  };
  $("artifact-files").addEventListener("change", (event) => {
    ingestArtifacts(Array.from(event.target.files || []));
    event.target.value = "";
  });
  $("runner-result-files").addEventListener("change", (event) => {
    importRunnerResults(Array.from(event.target.files || []));
    event.target.value = "";
  });
  $("signoff-evidence-files").addEventListener("change", (event) => {
    importSignoffEvidence(Array.from(event.target.files || []));
    event.target.value = "";
  });
  window.__kotobaEda = { state, buildRunnerPlan, buildMurakumoPayload, buildPreviewRunnerPlan, packet, toEdn, signoffEvidenceAssessment, signoffEvidenceTemplate };
  transact(":eda.project/create", cfg());
  proposal("murakumo inference queue is ready. LLM output is stored as :eda.review/* proposal data, not as signoff authority.");
  refresh();
})();
