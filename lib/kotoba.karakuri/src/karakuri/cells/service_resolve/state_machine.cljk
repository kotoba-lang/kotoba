(ns karakuri.cells.service-resolve.state-machine
  "Phase state machine for the karakuri service_resolve (絡繰) cell.
  1:1 Clojure port of cells/service_resolve/state_machine.py (ADR-2606039200 / ADR-2606160842).

  Graph: lookup -> tier-select -> tos-stance. Resolves a service against the :representative registry
  (methods/command), selects the safest adapter tier, and reports both stance axes. G2 (tier choice
  respects the browser-automation stance), G6 (no network), G8 (unknown service degrades honestly).

  Conventions: the dataclass ResolveState → a plain map with the SAME string field keys the Python
  `cs.__dict__` round-trips; the registry record keeps its string keys; phase enum values stay strings."
  (:require [karakuri.methods.command :as command]))

(def OUTCOME-UNKNOWN-SERVICE "unknown-service")   ; G8

;; ── ResolvePhase (enum — Python value identities preserved) ──
(def resolve-phases
  {:init          "init"
   :looked-up     "looked_up"
   :tier-selected "tier_selected"
   :resolved      "resolved"
   :refused       "refused"})

(def phase-init          (:init resolve-phases))
(def phase-looked-up     (:looked-up resolve-phases))
(def phase-tier-selected (:tier-selected resolve-phases))
(def phase-resolved      (:resolved resolve-phases))
(def phase-refused       (:refused resolve-phases))

;; ── ResolveState (dataclass → plain map, string keys + field defaults) ──
(def state-defaults
  {"phase"   phase-init
   "service" ""
   "rec"     {}
   "payload" {}})

(defn- cell-state [state]
  (merge state-defaults (get state "cell_state" {})))

(defn transition-lookup
  "G8: resolve the service; an unknown service degrades honestly with no guess."
  [state]
  (let [cs (cell-state state)
        cs (assoc cs "service" (get state "service" (get cs "service")))
        rec (command/resolve-service (get cs "service"))]
    (if (nil? rec)
      (let [cs (assoc cs "phase" phase-refused
                      "payload" (assoc (get cs "payload") "outcome" OUTCOME-UNKNOWN-SERVICE))]
        {"cell_state" cs "next_node" "end"})
      (let [cs (assoc cs "rec" rec "phase" phase-looked-up)]
        {"cell_state" cs "next_node" "tier_select"}))))

(defn transition-tier-select
  "G2: pick the safest adapter tier (official API > permitted browser-use > export)."
  [state]
  (let [cs (cell-state state)
        cs (assoc cs
                  "payload" (assoc (get cs "payload") "tier" (command/select-tier (get cs "rec")))
                  "phase" phase-tier-selected)]
    {"cell_state" cs "next_node" "tos_stance"}))

(defn transition-tos-stance
  "Report both stance axes (official-API + browser-automation) and the T2 engine if permitted."
  [state]
  (let [cs (cell-state state)
        rec (get cs "rec")
        stance (command/t2-stance rec)
        payload (assoc (get cs "payload")
                       "officialApi" (boolean (get rec "official_api"))
                       "tosStance" (get rec "tos")           ; official-API axis
                       "t2Stance" stance)                    ; browser-automation axis (G2)
        payload (if (and (= (get payload "tier") command/TIER-T2)
                         (contains? #{"permitted" "restricted"} stance))
                  (assoc payload "t2Engine" command/T2-ENGINE)   ; browser-use
                  payload)
        cs (assoc cs "payload" payload "phase" phase-resolved)]
    {"cell_state" cs "next_node" "end"}))

(defn solve
  "R0 scaffold: .solve() raises until Council activation (ADR-2606039200 §Decision)."
  [_input-state]
  (throw (ex-info "karakuri R0 scaffold: activate service_resolve via Council ADR (post-2606039200 ratification)"
                  {:scaffold true})))
