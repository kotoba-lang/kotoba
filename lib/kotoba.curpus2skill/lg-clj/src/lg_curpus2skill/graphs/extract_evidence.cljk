(ns lg-curpus2skill.graphs.extract-evidence
  "curpus2skill `extractEvidence` graph — wraps the corpus→skill evidence task.

  NSID: com.etzhayyim.apps.curpus2skill.extractEvidence
  Faithful clj port of the Python `_make_single_node_graph(
  task_curpus2skill_extract_evidence, \"extractEvidence\")` in
  `lg/lg_curpus2skill/server.py` (ADR-2606280030).

  Topology (identical to the Python single-node graph): START → execute → END.
  The `execute` node reads `{:input <camelCase-params>}` from state, calls the
  injectable handler, and returns `{:result ...}` on success or `{:error ...}`
  (clipped to 300 chars) on failure — byte-for-byte the Python `_node` contract.

  DEVIATION (noted): the Python handler queried RisingWave; per the substrate
  boundary (ADR-2605262130) the default handler here is the in-process store
  seam (`lg-curpus2skill.store/extract-evidence`), whose corpus read + skill
  write edges are injectable (kotoba Datom-log target). camelCase params
  (source/limit/skillLimit/minScore/topK/dryRun) are passed through as-is."
  (:require [kotoba.lang.text :as str]
            [langgraph.graph :as g]
            [lg-curpus2skill.store :as store]))

(defn- clip [s n] (let [s (str s)] (subs s 0 (min n (count s)))))

;; Injectable handler edge — defaults to the store-seam task. Tests / the kotoba
;; adapter rebind this; the Python `handler` argument is what this var stands in
;; for.
(def ^:dynamic *handler* store/extract-evidence)

(defn node-execute
  "Single execute node — mirrors the Python async `_node`: pull kwargs from
  `:input`, invoke the handler, return `{:result ...}` | `{:error <=300 chars>}`."
  [state]
  (let [kwargs (or (:input state) {})]
    (try
      {:result (*handler* kwargs)}
      (catch Exception e
        {:error (clip (.getMessage e) 300)}))))

(defn build
  "Compile the extractEvidence StateGraph (START → execute → END)."
  []
  (-> (g/state-graph)
      (g/add-node :execute node-execute)
      (g/set-entry-point :execute)
      (g/set-finish-point :execute)
      (g/compile-graph)))

(def GRAPH (build))
