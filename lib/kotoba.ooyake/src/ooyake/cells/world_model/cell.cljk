(ns ooyake.cells.world-model.cell
  "LangGraph Pregel wrapper for the ooyake (公) world_model cell — R0 scaffold.
  1:1 port of cells/world_model/cell.py (ADR-2606021600 §3, depends ADR-2606011000
  engi-organism-ontology + ADR-2606011800 tsumugi).

  WorldModelCell joins the two government-facing graphs into one world model on the SHARED
  id-space — ooyake :gov.unit/* (STRUCTURE) ── :gov.unit/organism ──▶ tsumugi :organism/* (KARMA):
  it classifies every POWER-BEARING gov-unit as confirmed / derived / dangling / proposed against
  the tsumugi karma graph and emits a world-model artifact. Read-side (G9): it produces a *report*
  + a *proposed* artifact; it NEVER mutates a committed seed. G1 power-only — local service surface
  (prefecture / municipality / ward / division / 窓口) is EXCLUDED by construction, never a
  target-list. Two graphs in, one world model out. Stdlib only, no network, no LLM.

  The offline, deterministic bundled-mode reconcile (parse-edn / derive-organism-id /
  load-gov-units / load-organisms / reconcile-world-model / render-world-model-edn / queries) is
  ported to cells/world_model/state_machine.cljc. .solve() stays Council-gated at R0; live mode
  (planet-scale ingest + write-back of :gov.unit/organism links) is Council Lv6+ + operator gated.")

(defn solve
  [_input-state]
  (throw (ex-info (str "ooyake world_model R0 cljc scaffold: cell .solve() disabled "
                       "(offline bundled-mode reconcile is ported to cells/world_model/state_machine.cljc; "
                       "live planet-scale ingest + write-back is Council Lv6+ + operator gated, ADR-2606021600)")
                  {:scaffold true :cell :world-model})))
