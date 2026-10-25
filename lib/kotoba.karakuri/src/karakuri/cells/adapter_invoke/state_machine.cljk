(ns karakuri.cells.adapter-invoke.state-machine
  "Phase state machine for the karakuri adapter_invoke (絡繰) cell.
  1:1 Clojure port of cells/adapter_invoke/state_machine.py (ADR-2606039200 / ADR-2606160842).

  The cell drives one ServiceOp through the safest adapter, in a dry-run at R0. It wires the offline
  planner (methods/command) and the browser-use T2 plan builder (methods/t2_browser) into the
  manifest state graph:

      tos-gate  ->  mutate-gate  ->  dry-run  ->  execute-gated

  Invariants enforced here as pure transitions (the cell's .solve() raises until Council activation):
    G2 — official-API-first / ToS-honest: a browser-automation-prohibited service (incl. Google +
         Facebook, which are :api-ok but browser-prohibited and resolve to T1) refuses the T2 browser-use
         adapter; the op terminates as :refused without a plan or execution.
    G5 — read-default / mutate-gated: :read ops are read-allowed; any mutating op is marked
         awaiting-member-sig (the dry-run plan is still built; only EXECUTION needs the signature).
    G6 — outward-gated: at R0 the execute-gate ALWAYS reports gated — no live network call.
    G8 — sourcing-honesty: an unknown service degrades to :unknown-service, never a guess.

  Conventions: the dataclass AdapterState → a plain map with the SAME string field keys the Python
  `cs.__dict__` round-trips; the stored op map carries the Python dataclass field names (snake_case
  string keys), matching `dict(op.__dict__)`; the t2_browser plan keeps its string keys."
  (:require [karakuri.methods.command :as command]
            [karakuri.methods.t2-browser :as t2-browser]))

;; ── AdapterPhase (enum — Python value identities preserved) ──
(def adapter-phases
  {:init            "init"
   :tos-checked     "tos_checked"
   :mutate-checked  "mutate_checked"
   :planned         "planned"
   :execute-gated   "execute_gated"
   :refused         "refused"})

(def phase-init           (:init adapter-phases))
(def phase-tos-checked    (:tos-checked adapter-phases))
(def phase-mutate-checked (:mutate-checked adapter-phases))
(def phase-planned        (:planned adapter-phases))
(def phase-execute-gated  (:execute-gated adapter-phases))
(def phase-refused        (:refused adapter-phases))

;; Adapter outcomes recorded on the payload.
(def OUTCOME-REFUSED-TOS "refused-automation-prohibited")   ; G2
(def OUTCOME-UNKNOWN-SERVICE "unknown-service")             ; G8
(def EXECUTE-GATE "gated-council-lv6-operator")             ; G6

;; ── AdapterState (dataclass → plain map, string keys + field defaults) ──
(def state-defaults
  {"phase"       phase-init
   "line"        ""
   "prefer_tier" ""
   "op"          {}
   "payload"     {}})

(defn- cell-state [state]
  (merge state-defaults (get state "cell_state" {})))

;; ── ServiceOp ⇄ Python __dict__ (snake_case string keys) ──
(defn op->dict
  "command/plan ServiceOp (kebab keyword keys) → Python `op.__dict__` shape (snake_case string keys)."
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

(defn dict->op
  "Inverse of op->dict — Python __dict__ (snake string keys) → command ServiceOp (kebab keyword keys),
  reconstructing the op the way Python's `ServiceOp(**cs.op)` does."
  [d]
  {:service       (get d "service")
   :noun          (get d "noun")
   :verb          (get d "verb")
   :safety        (get d "safety")
   :destructive   (get d "destructive")
   :adapter-tier  (get d "adapter_tier")
   :args          (get d "args")
   :service-known (get d "service_known")
   :dry-run       (get d "dry_run")
   :tos-gate      (get d "tos_gate")
   :mutate-gate   (get d "mutate_gate")
   :t2-engine     (get d "t2_engine")
   :note          (get d "note")})

(defn transition-tos-gate
  "Build the ServiceOp and apply the ToS gate (G2 / G8); refuse browser automation up front."
  [state]
  (let [cs (cell-state state)
        cs (assoc cs
                  "line" (get state "line" (get cs "line"))
                  "prefer_tier" (or (get state "prefer_tier" (get cs "prefer_tier")) ""))
        prefer (get cs "prefer_tier")
        op (command/plan (get cs "line") :prefer-tier (if (seq prefer) prefer nil))
        cs (assoc cs "op" (op->dict op))]
    (cond
      (not (:service-known op))
      (let [cs (assoc cs "phase" phase-refused
                      "payload" (assoc (get cs "payload") "adapterOutcome" OUTCOME-UNKNOWN-SERVICE))]  ; G8
        {"cell_state" cs "next_node" "end"})

      (= (:tos-gate op) command/TOS-REFUSED)
      (let [cs (assoc cs "phase" phase-refused
                      "payload" (assoc (get cs "payload")
                                       "adapterOutcome" OUTCOME-REFUSED-TOS    ; G2
                                       "note" (:note op)))]
        {"cell_state" cs "next_node" "end"})

      :else
      (let [cs (assoc cs "phase" phase-tos-checked)]
        {"cell_state" cs "next_node" "mutate_gate"}))))

(defn transition-mutate-gate
  "G5: reads are read-allowed; mutating ops are marked awaiting-member-sig (plan still builds)."
  [state]
  (let [cs (cell-state state)
        safety (get (get cs "op") "safety")
        cs (assoc cs
                  "payload" (assoc (get cs "payload")
                                   "mutateGate" (if (= safety command/SAFETY-READ)
                                                  "read-allowed" "awaiting-member-sig"))
                  "phase" phase-mutate-checked)]
    {"cell_state" cs "next_node" "dry_run"}))

(defn transition-dry-run
  "Build the dry-run adapter plan; for a T2 op, embed the browser-use action plan (G6 dry-run)."
  [state]
  (let [cs (cell-state state)
        op (dict->op (get cs "op"))
        plan-desc {"tier" (:adapter-tier op) "dryRun" true}
        plan-desc (if (= (:adapter-tier op) command/TIER-T2)
                    (let [bp (t2-browser/build-browser-plan op)]   ; browser-use steps; raises if not eligible
                      (assoc plan-desc
                             "engine" (get bp "engine")              ; "browser-use"
                             "runtime" (get bp "runtime")            ; langgraph->wasm
                             "detectionEvasion" (get bp "detection_evasion")  ; False — unrepresentable (G2/N2)
                             "steps" (get bp "steps")))
                    plan-desc)
        cs (assoc cs "payload" (assoc (get cs "payload") "plan" plan-desc)
                  "phase" phase-planned)]
    {"cell_state" cs "next_node" "execute_gated"}))

(defn transition-execute-gated
  "G6: at R0 there is no live execution; the execute-gate always reports gated (operator+Council)."
  [state]
  (let [cs (cell-state state)
        cs (assoc cs
                  "payload" (assoc (get cs "payload")
                                   "executeGate" EXECUTE-GATE   ; G6 — Council Lv6+ + operator
                                   "executed" false)            ; R0 invariant: never executed
                  "phase" phase-execute-gated)]
    {"cell_state" cs "next_node" "end"}))

(defn solve
  "R0 scaffold: .solve() raises until Council activation (ADR-2606039200 §Decision)."
  [_input-state]
  (throw (ex-info "karakuri R0 scaffold: activate adapter_invoke via Council ADR (post-2606039200 ratification)"
                  {:scaffold true})))
