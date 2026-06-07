"""Read-only WebUI for the local artificial-organism agent status."""

from __future__ import annotations

import argparse
import json
import logging
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from kotodama.agent_status_main import load_status_report
from kotodama.local_agent_env import load_env_file, load_keychain_secret

LOG = logging.getLogger("agent_status_web")


STATUS_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Organism Status</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #5f6b7a;
      --line: #d9dee7;
      --good: #17803d;
      --warn: #9a6200;
      --bad: #b3261e;
      --info: #225ea8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1, h2 { margin: 0; font-weight: 650; letter-spacing: 0; }
    h1 { font-size: 18px; }
    h2 { font-size: 13px; color: var(--muted); text-transform: uppercase; }
    main { padding: 20px 24px 28px; }
    .toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    button {
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      height: 34px;
      padding: 0 12px;
      border-radius: 6px;
      cursor: pointer;
    }
    button:hover { border-color: #9ca8b8; }
    .grid {
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 14px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }
    .span-3 { grid-column: span 3; }
    .span-4 { grid-column: span 4; }
    .span-6 { grid-column: span 6; }
    .span-8 { grid-column: span 8; }
    .span-12 { grid-column: span 12; }
    .metric { display: flex; flex-direction: column; gap: 8px; min-height: 108px; }
    .value { font-size: 28px; font-weight: 700; line-height: 1; }
    .subtle { color: var(--muted); }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 3px 9px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #f4f6f8;
      font-weight: 600;
    }
    .ok { color: var(--good); }
    .warn { color: var(--warn); }
    .bad { color: var(--bad); }
    .info { color: var(--info); }
    .rows { display: grid; gap: 8px; }
    .row {
      display: grid;
      grid-template-columns: minmax(150px, 1fr) auto;
      gap: 12px;
      align-items: center;
      padding: 8px 0;
      border-bottom: 1px solid #eef1f5;
    }
    .row:last-child { border-bottom: 0; }
    pre {
      margin: 0;
      max-height: 360px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      background: #111827;
      color: #e5e7eb;
      border-radius: 8px;
      padding: 12px;
    }
    @media (max-width: 900px) {
      header { align-items: flex-start; flex-direction: column; }
      main { padding: 14px; }
      .span-3, .span-4, .span-6, .span-8 { grid-column: span 12; }
      .row { grid-template-columns: 1fr; gap: 4px; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Agent Organism Status</h1>
      <div id="agent" class="subtle">Loading</div>
    </div>
    <div class="toolbar">
      <span id="updated" class="subtle">Not loaded</span>
      <button id="refresh" type="button">Refresh</button>
    </div>
  </header>
  <main>
    <section class="grid">
      <div class="panel metric span-3">
        <h2>Organism</h2>
        <div id="organismState" class="value">--</div>
        <div id="organismScore" class="subtle">score --</div>
      </div>
      <div class="panel metric span-3">
        <h2>Health</h2>
        <div id="healthLevel" class="value">--</div>
        <div id="healthMeta" class="subtle">warnings -- failures --</div>
      </div>
      <div class="panel metric span-3">
        <h2>Homeostasis</h2>
        <div id="viabilityState" class="value">--</div>
        <div id="homeostasisMeta" class="subtle">confidence -- entropy --</div>
      </div>
      <div class="panel metric span-3">
        <h2>Outcome</h2>
        <div id="outcomeState" class="value">--</div>
        <div id="outcomeMeta" class="subtle">success --</div>
      </div>
      <div class="panel metric span-3">
        <h2>Learning</h2>
        <div id="learningState" class="value">--</div>
        <div id="learningMeta" class="subtle">no priors</div>
      </div>
      <div class="panel metric span-3">
        <h2>ERC-8004</h2>
        <div id="erc8004State" class="value">--</div>
        <div id="erc8004Meta" class="subtle">agentId --</div>
      </div>
      <div class="panel metric span-3">
        <h2>Runtime Proof</h2>
        <div id="runtimeProofState" class="value">--</div>
        <div id="runtimeProofMeta" class="subtle">receipt --</div>
      </div>
      <div class="panel metric span-3">
        <h2>Authority</h2>
        <div id="authorityState" class="value">--</div>
        <div id="authorityMeta" class="subtle">policies --</div>
      </div>
      <div class="panel metric span-3">
        <h2>Email Live</h2>
        <div id="emailLiveState" class="value">--</div>
        <div id="emailLiveMeta" class="subtle">blockers --</div>
      </div>
      <div class="panel span-4">
        <h2>Processes</h2>
        <div id="processes" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Real-World Effects</h2>
        <div id="effects" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Dispatch Ledger</h2>
        <div id="dispatch" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Authority Effects</h2>
        <div id="authorityEffects" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Email Outbound</h2>
        <div id="emailOutbound" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Effect Channels</h2>
        <div id="effectChannels" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>On-Chain Runtime</h2>
        <div id="runtimePublication" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Development Memory</h2>
        <div id="developmentMemory" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Memory Edges</h2>
        <div id="developmentEdges" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>KG Fitness</h2>
        <div id="knowledgeGraphFitness" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Policy Adaptation</h2>
        <div id="policyAdaptation" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Active Priors</h2>
        <div id="activePriors" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Counterparties</h2>
        <div id="counterparties" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Protected Assets</h2>
        <div id="protectedAssets" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Minimax</h2>
        <div id="minimaxEvaluations" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Information Height</h2>
        <div id="informationHeight" class="rows"></div>
      </div>
      <div class="panel span-4">
        <h2>Information Flow</h2>
        <div id="informationFlow" class="rows"></div>
      </div>
      <div class="panel span-6">
        <h2>Observations</h2>
        <div id="observations" class="rows"></div>
      </div>
      <div class="panel span-6">
        <h2>Blockers</h2>
        <div id="blockers" class="rows"></div>
      </div>
      <div class="panel span-12">
        <h2>Raw Status</h2>
        <pre id="raw">{}</pre>
      </div>
    </section>
  </main>
  <script>
    const qs = new URLSearchParams(location.search);
    const agentDid = qs.get("agentDid") || "";
    const classify = (state) => {
      if (["active", "normal", "observed", "running"].includes(String(state))) return "ok";
      if (["healthy"].includes(String(state))) return "ok";
      if (["watch", "repairing", "repair", "conserve", "blocked"].includes(String(state))) return "warn";
      if (["degraded", "critical", "halted", "hibernate", "failed", "down"].includes(String(state))) return "bad";
      return "info";
    };
    const row = (name, value, tone) => `<div class="row"><span>${name}</span><span class="pill ${tone || classify(value)}">${value}</span></div>`;
    const empty = (text) => `<div class="row"><span class="subtle">${text}</span><span></span></div>`;
    function renderCounts(id, rows) {
      document.getElementById(id).innerHTML = rows && rows.length
        ? rows.map((item) => row(item.state || "unknown", item.count || 0, classify(item.state))).join("")
        : empty("No rows");
    }
    function render(report) {
      const h = report.homeostasis || {};
      const health = report.healthEvaluation || {};
      const o = report.latestOutcome || {};
      const l = report.learning || {};
      const e = report.erc8004 || {};
      const rp = report.runtimePublication || {};
      const a = report.authority || {};
      const m = report.developmentMemory || {};
      const p = report.policyAdaptation || {};
      const mm = report.counterpartyMinimax || {};
      const inf = report.informationFlow || {};
      const kg = report.knowledgeGraphFitness || {};
      const email = (report.liveChannels || {}).email || {};
      const emailReady = email.readiness || {};
      document.getElementById("agent").textContent = report.agentDid || "";
      document.getElementById("organismState").textContent = report.organismState || "unknown";
      document.getElementById("organismState").className = `value ${classify(report.organismState)}`;
      document.getElementById("organismScore").textContent = `score ${report.organismScore ?? "--"}`;
      document.getElementById("healthLevel").textContent = health.level || "unknown";
      document.getElementById("healthLevel").className = `value ${classify(health.level)}`;
      document.getElementById("healthMeta").textContent = `warnings ${(health.warnings || []).length} failures ${(health.failures || []).length}`;
      document.getElementById("viabilityState").textContent = h.viabilityState || "unknown";
      document.getElementById("viabilityState").className = `value ${classify(h.viabilityState)}`;
      document.getElementById("homeostasisMeta").textContent = `confidence ${h.confidence ?? "--"} entropy ${h.entropy ?? "--"}`;
      document.getElementById("outcomeState").textContent = o.dispatchState || "unknown";
      document.getElementById("outcomeState").className = `value ${classify(o.dispatchState)}`;
      document.getElementById("outcomeMeta").textContent = `success ${o.success ?? "--"}`;
      const priors = Object.keys(l.channelPriors || {}).length;
      document.getElementById("learningState").textContent = priors ? "adapted" : "cold";
      document.getElementById("learningState").className = `value ${priors ? "ok" : "info"}`;
      document.getElementById("learningMeta").textContent = `updated ${l.updatedAt || "--"}`;
      document.getElementById("erc8004State").textContent = e.configured ? "linked" : "pending";
      document.getElementById("erc8004State").className = `value ${e.configured ? "ok" : "warn"}`;
      document.getElementById("erc8004Meta").textContent = `agentId ${e.agentId || "--"}`;
      const runtimeReceipt = rp.runtimeReceipt || {};
      document.getElementById("runtimeProofState").textContent = rp.verified ? "verified" : "pending";
      document.getElementById("runtimeProofState").className = `value ${rp.verified ? "ok" : "warn"}`;
      document.getElementById("runtimeProofMeta").textContent = `receipt ${(runtimeReceipt.job_id || "--").slice(0, 18)}`;
      const authorityPolicies = a.policies || [];
      const activePolicies = authorityPolicies.find((item) => item.state === "active");
      document.getElementById("authorityState").textContent = activePolicies ? "bound" : "pending";
      document.getElementById("authorityState").className = `value ${activePolicies ? "ok" : "warn"}`;
      document.getElementById("authorityMeta").textContent = `policies ${authorityPolicies.length}`;
      document.getElementById("emailLiveState").textContent = emailReady.ready ? "ready" : "blocked";
      document.getElementById("emailLiveState").className = `value ${emailReady.ready ? "ok" : "warn"}`;
      document.getElementById("emailLiveMeta").textContent = `blockers ${(emailReady.blockers || []).length}`;
      document.getElementById("processes").innerHTML = Object.entries(report.processes || {})
        .map(([name, ok]) => row(name, ok ? "running" : "down", ok ? "ok" : "bad")).join("");
      renderCounts("effects", report.realWorldEffects || []);
      renderCounts("dispatch", report.dispatchLedger || []);
      document.getElementById("authorityEffects").innerHTML = (a.recentEffects || []).length
        ? a.recentEffects.map((item) => row(`${item.channel || "--"} ${item.effect_class || ""}`, item.dispatch_state || "--", classify(item.dispatch_state))).join("")
        : empty("No authority-bound effects");
      document.getElementById("emailOutbound").innerHTML = (email.recentOutbound || []).length
        ? email.recentOutbound.map((item) => row(item.subject || item.error || "--", item.status || "--", classify(item.status))).join("")
        : empty("No outbound rows");
      document.getElementById("effectChannels").innerHTML = (report.effectChannels || []).length
        ? report.effectChannels.map((item) => row(item.channel || "--", item.state || "--", classify(item.state))).join("")
        : empty("No channel status");
      const publication = rp.publication || {};
      const artifact = rp.runtimeArtifact || {};
      document.getElementById("runtimePublication").innerHTML = rp.available === false
        ? empty(rp.error || "Runtime publication unavailable")
        : [
            row("ERC-8004 token", publication.token_id || "--", publication.status === "verified" ? "ok" : "warn"),
            row("agent URI", publication.agent_uri || "--", publication.status === "verified" ? "ok" : "info"),
            row("artifact", artifact.artifact_id || "--", artifact.status === "verified" ? "ok" : "warn"),
            row("receipt", runtimeReceipt.job_id || "--", runtimeReceipt.status === "verified" ? "ok" : "warn"),
            row("tx", runtimeReceipt.tx_hash || publication.tx_hash || "--", "info"),
          ].join("");
      document.getElementById("developmentMemory").innerHTML = (m.latestDocuments || []).length
        ? m.latestDocuments.map((item) => row(item.title || item.doc_id || "--", item.status || "--", classify(item.status))).join("")
        : empty(m.available === false ? (m.error || "Development graph unavailable") : "No development documents");
      document.getElementById("developmentEdges").innerHTML = (m.edgeCounts || []).length
        ? m.edgeCounts.map((item) => row(`${item.relation_kind || "--"} / ${item.ref_kind || "--"}`, item.edge_count || 0, "info")).join("")
        : empty("No memory edges");
      document.getElementById("knowledgeGraphFitness").innerHTML = kg.available === false
        ? empty(kg.error || "KG fitness unavailable")
        : [
            row("kgDevelopmentGain", kg.kgDevelopmentGain ?? "--", "ok"),
            row("kgCoverageScore", kg.kgCoverageScore ?? "--", "info"),
            row("missingEdgePenalty", kg.missingEdgePenalty ?? "--", kg.missingEdgePenalty ? "warn" : "ok"),
            row("evolutionFitness", kg.evolutionFitness ?? "--", "ok"),
          ].join("");
      document.getElementById("policyAdaptation").innerHTML = (p.recentProposals || []).length
        ? p.recentProposals.map((item) => row(item.preference_key || "--", item.proposal_state || "--", classify(item.proposal_state))).join("")
        : empty(p.available === false ? (p.error || "Policy adaptation unavailable") : "No adaptation proposals");
      document.getElementById("activePriors").innerHTML = (p.activePriors || []).length
        ? p.activePriors.map((item) => row(item.preference_key || "--", item.weight ?? "--", "info")).join("")
        : empty("No active priors");
      document.getElementById("counterparties").innerHTML = (mm.counterparties || []).length
        ? mm.counterparties.map((item) => row(item.counterparty_ref || "--", item.model_kind || "--", "info")).join("")
        : empty(mm.available === false ? (mm.error || "Counterparty model unavailable") : "No counterparties");
      document.getElementById("protectedAssets").innerHTML = (mm.protectedAssets || []).length
        ? mm.protectedAssets.map((item) => row(item.asset_ref || "--", item.asset_kind || "--", "info")).join("")
        : empty("No protected assets");
      document.getElementById("minimaxEvaluations").innerHTML = (mm.minimaxEvaluations || []).length
        ? mm.minimaxEvaluations.map((item) => row(item.action_id || "--", item.minimax_regret ?? "--", "warn")).join("")
        : empty("No minimax evaluations");
      document.getElementById("informationHeight").innerHTML = (inf.height || []).length
        ? inf.height.map((item) => row(`${item.info_kind || "--"} ${item.counterparty_ref || ""}`, item.max_information_height ?? "--", "info")).join("")
        : empty(inf.available === false ? (inf.error || "Information flow unavailable") : "No information height rows");
      document.getElementById("informationFlow").innerHTML = (inf.flows || []).length
        ? inf.flows.map((item) => row(item.src_vid || "--", item.avg_control_score ?? "--", "info")).join("")
        : empty("No information flow rows");
      document.getElementById("observations").innerHTML = Object.entries(report.latestObservations || {})
        .map(([name, obs]) => row(name, obs.observed_at || "--", classify(name))).join("") || empty("No observations");
      const blockers = [
        ...(h.blockers || []),
        ...((o.blockers || [])),
        ...((emailReady.blockers || [])),
        ...((health.warnings || [])),
        ...((health.failures || [])),
      ];
      document.getElementById("blockers").innerHTML = blockers.length
        ? blockers.map((b) => row(b, "active", "warn")).join("")
        : empty("No blockers");
      document.getElementById("raw").textContent = JSON.stringify(report, null, 2);
      document.getElementById("updated").textContent = new Date().toLocaleString();
    }
    async function refresh() {
      const url = agentDid ? `/api/status?agentDid=${encodeURIComponent(agentDid)}` : "/api/status";
      const res = await fetch(url, { headers: { "Accept": "application/json" } });
      if (!res.ok) throw new Error(`status ${res.status}`);
      render(await res.json());
    }
    document.getElementById("refresh").addEventListener("click", () => refresh().catch(console.error));
    refresh().catch((err) => {
      document.getElementById("raw").textContent = String(err && err.stack || err);
      document.getElementById("organismState").textContent = "error";
      document.getElementById("organismState").className = "value bad";
    });
    setInterval(() => refresh().catch(console.error), 15000);
  </script>
</body>
</html>
"""


def build_status_html() -> str:
    return STATUS_HTML


def status_payload(agent_did: str) -> dict[str, Any]:
    return load_status_report(agent_did)


class StatusWebHandler(BaseHTTPRequestHandler):
    server_version = "KotodamaAgentStatusWeb/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(HTTPStatus.OK, build_status_html().encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/health":
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        if parsed.path == "/api/status":
            query = parse_qs(parsed.query)
            agent_did = str((query.get("agentDid") or [self.server.agent_did])[0])
            try:
                self._send_json(HTTPStatus.OK, status_payload(agent_did))
            except Exception as exc:  # noqa: BLE001
                LOG.exception("status api failed: %s", exc)
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

    def log_message(self, fmt: str, *args: Any) -> None:
        LOG.info("%s - %s", self.address_string(), fmt % args)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        self._send(
            status,
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class StatusWebServer(ThreadingHTTPServer):
    agent_did: str


def serve(host: str, port: int, agent_did: str) -> None:
    server = StatusWebServer((host, port), StatusWebHandler)
    server.agent_did = agent_did
    LOG.info("agent status web listening on http://%s:%d agentDid=%s", host, port, agent_did)
    server.serve_forever()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local agent organism status WebUI")
    parser.add_argument("--host", default=os.environ.get("AGENT_STATUS_WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("AGENT_STATUS_WEB_PORT", "8765")))
    parser.add_argument("--agent-did", default=os.environ.get("AGENT_DID", "did:etzhayyim:agent:local"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    load_env_file()
    if not os.environ.get("RW_URL"):
        rw_url = load_keychain_secret(service="etzhayyim.rw", account="ROOT_URL")
        if rw_url:
            os.environ["RW_URL"] = rw_url
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = parse_args(argv)
    serve(args.host, args.port, args.agent_did)


if __name__ == "__main__":
    main()
