(ns karakuri.cells.command-plan.state-machine
  "Phase state machine for the karakuri command_plan (絡繰) cell.
  1:1 Clojure port of cells/command_plan/state_machine.py (ADR-2606039200 / ADR-2606160842).

  Graph: parse -> classify -> charter-scan -> plan. Wires the Murakumo-only NL planner
  (methods/nl_plan) and the ServiceOp gates (methods/command) into the manifest graph:

    parse        — NL brief -> a `<service> <noun>.<verb>` command (deterministic heuristic at R0;
                   the live Murakumo path is operator-gated, G4).
    classify     — command -> a gated ServiceOp (safety + ToS + mutate gates; G2/G5).
    charter-scan — Charter-Rider §2(a)-(h) scan of the brief + op (N6); a dirty brief plans nothing.
    plan         — assemble the dry-run CommandPlan (G6).

  Conventions: the dataclass PlanState → a plain map with the SAME string field keys the Python
  `cs.__dict__` round-trips; phase enum value identities stay strings; the stored op map carries
  the Python dataclass field names (snake_case string keys), matching `dict(op.__dict__)`."
  (:require [karakuri.methods.command :as command]
            [karakuri.methods.nl-plan :as nl-plan]))

;; ── PlanPhase (enum — Python value identities preserved) ──
(def plan-phases
  {:init       "init"
   :parsed     "parsed"
   :classified "classified"
   :scanned    "scanned"
   :planned    "planned"
   :refused    "refused"})

(def phase-init       (:init plan-phases))
(def phase-parsed     (:parsed plan-phases))
(def phase-classified (:classified plan-phases))
(def phase-scanned    (:scanned plan-phases))
(def phase-planned    (:planned plan-phases))
(def phase-refused    (:refused plan-phases))

;; ── PlanState (dataclass → plain map, string keys + field defaults) ──
(def state-defaults
  {"phase"        phase-init
   "brief"        ""
   "command_line" ""
   "op"           {}
   "payload"      {}})

(defn- cell-state [state]
  (merge state-defaults (get state "cell_state" {})))

;; ── ServiceOp (keyword-kebab map from command/plan) → Python __dict__ (snake_case string keys) ──
(defn op->dict
  "Convert the command/plan ServiceOp map (kebab keyword keys) to the Python `op.__dict__` shape
  (snake_case string keys), so downstream cell access (op['service'] etc.) is faithful."
  [op]
  {"service"       (:service op)
   "noun"          (:noun op)
   "verb"          (:verb op)
   "safety"        (:safety op)
   "destructive"   (:destructive op)
   "adapter_tier"  (:adapter-tier op)
   "args"          (:args op)
   "service_known" (:service-known op)
   "dry_run"       (:dry-run op)
   "tos_gate"      (:tos-gate op)
   "mutate_gate"   (:mutate-gate op)
   "t2_engine"     (:t2-engine op)
   "note"          (:note op)})

(defn transition-parse
  "G4: NL brief -> command (deterministic fallback; live Murakumo path operator-gated elsewhere)."
  [state]
  (let [cs (cell-state state)
        cs (assoc cs "brief" (get state "brief" (get cs "brief")))
        cmd (nl-plan/heuristic-parse (get cs "brief"))]
    (if (not cmd)
      (let [cs (assoc cs "phase" phase-refused
                      ;; G8 — never guesses a service
                      "payload" (assoc (get cs "payload") "outcome" "no-confident-parse"))]
        {"cell_state" cs "next_node" "end"})
      (let [cs (assoc cs "command_line" cmd "phase" phase-parsed)]
        {"cell_state" cs "next_node" "classify"}))))

(defn transition-classify
  "G2/G5: turn the command into a gated ServiceOp (safety + ToS + mutate gates applied)."
  [state]
  (let [cs (cell-state state)
        cs (assoc cs "op" (op->dict (command/plan (get cs "command_line")))
                  "phase" phase-classified)]
    {"cell_state" cs "next_node" "charter_scan"}))

(defn transition-charter-scan
  "N6: scan the brief + resolved op; a dirty brief plans nothing."
  [state]
  (let [cs (cell-state state)
        op (get cs "op")
        [clean hits] (nl-plan/charter-scan
                      (str (get cs "brief") " " (get op "service") " "
                           (get op "noun") " " (get op "verb")))
        cs (assoc cs
                  "payload" (assoc (get cs "payload") "charterClean" clean "charterHits" hits)
                  "phase" phase-scanned)]
    {"cell_state" cs "next_node" "plan"}))

(defn transition-plan
  "G6: assemble the dry-run CommandPlan; a charter-dirty brief yields an empty op list (N6)."
  [state]
  (let [cs (cell-state state)
        payload (get cs "payload")
        ops (if (get payload "charterClean") [(get cs "op")] [])
        cs (assoc cs
                  "payload" (assoc payload
                                   "brief" (get cs "brief")
                                   "ops" ops
                                   "inference" nl-plan/INFERENCE-MURAKUMO   ; G4
                                   "dryRun" true                             ; G6
                                   "mutateGate" (when (seq ops) (get (get cs "op") "mutate_gate")))
                  "phase" phase-planned)]
    {"cell_state" cs "next_node" "end"}))

(defn solve
  "R0 scaffold: .solve() raises until Council activation (ADR-2606039200 §Decision)."
  [_input-state]
  (throw (ex-info "karakuri R0 scaffold: activate command_plan via Council ADR (post-2606039200 ratification)"
                  {:scaffold true})))
