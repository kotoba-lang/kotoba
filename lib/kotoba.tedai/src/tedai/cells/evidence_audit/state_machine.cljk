(ns tedai.cells.evidence-audit.state-machine
  "Phase state machine for the tedai 手代 evidence_audit cell.
  1:1 port of cells/evidence_audit/state_machine.py (ADR-2606101400). hash-evidence → project-datoms
  → assemble-batch. G9: screen evidence enters ONLY as a sha256 hash (raw frame stays on-device);
  G7: every DesktopOp becomes a kotoba Datom entity; the batch is dry-run (live ingest G6-gated in datom)."
  (:require [tedai.methods.datom :as datom]))

(def state-defaults {"phase" "init" "ops" [] "planned_at" "" "evidence_sha256" "" "payload" {}})
(defn- cell-state [state] (merge state-defaults (get state "cell_state" {})))

(defn transition-hash-evidence [state]
  (let [cs (cell-state state)
        cs (assoc cs "ops" (vec (get state "ops" (get cs "ops")))
                  "planned_at" (get state "planned_at" (get cs "planned_at")))]
    (when (empty? (get cs "ops"))
      (throw (ex-info "evidence_audit: no ops supplied" {})))
    (when-not (seq (get cs "planned_at"))
      (throw (ex-info "evidence_audit: planned_at must be caller-stamped (no clock reads here)" {})))
    (let [frame (get state "frame_bytes")
          cs (if (some? frame) (assoc cs "evidence_sha256" (datom/evidence-hash frame)) cs)]
      {"cell_state" (assoc cs "phase" "evidence_hashed") "next_node" "project_datoms"})))

(defn transition-project-datoms [state]
  (let [cs (cell-state state)
        sha (get cs "evidence_sha256")
        entities (mapv (fn [op] (datom/op-entity op (get cs "planned_at")
                                                 :evidence-sha256 (when (seq sha) sha)))
                       (get cs "ops"))]
    {"cell_state" (assoc cs "payload" (assoc (get cs "payload") "entities" entities) "phase" "projected")
     "next_node" "assemble_batch"}))

(defn transition-assemble-batch [state]
  (let [cs (cell-state state)]
    {"cell_state" (assoc cs "phase" "assembled"
                         "payload" (assoc (get cs "payload")
                                          "batch" (datom/ingest-batch (get-in cs ["payload" "entities"]))
                                          "liveIngest" false))
     "next_node" "end"}))

(defn solve [_input-state]
  (throw (ex-info "tedai R0 scaffold: activate evidence_audit via Council ADR (post-2606101400 ratification)" {:scaffold true})))
