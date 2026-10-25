(ns lg-curpus2skill.store
  "Corpus → skill evidence store seam — the charter-clean replacement for the
  Python RisingWave / psycopg persistence the kotodama
  `task_curpus2skill_extract_evidence` handler used (substrate boundary
  ADR-2605262130 / 2605312345: NO RisingWave/Postgres; corpus + extracted skills
  belong on the kotoba Datom log).

  This namespace is the SWAP SEAM (the actor injection pattern): the corpus READ
  edge (`*query-corpus*`) and the skill WRITE edge (`*persist-skills*`) are
  dynamic vars the graph calls; the default backend is an in-process append-only
  atom keyed by skill, which the kotoba Datom-log adapter can replace without
  touching the graph. Tests rebind these to stubs.

  Faithful-default gate: like the Python (which is a no-op when the RisingWave
  connection / RW_URL is unset), the store is INERT unless C2S_STORE_ENABLED=1
  (or RW_URL is set as a legacy signal). Inert, `query-corpus` yields no rows and
  `persist-skills!` stores nothing — exactly the unconfigured Python path."
  (:require [kotoba.lang.text :as str]))

(def ^:dynamic *enabled?*
  "Host-controlled store gate. Portable execution is inert by default."
  false)

(defn enabled?
  "True when the store should read/persist (faithful analogue of the Python's
  RisingWave-connection gate)."
  []
  (true? *enabled?*))

;; append-only in-process skill backend: skill-string -> evidence row map
(defonce ^:private skill-db (atom {}))
;; in-process corpus rows (a kotoba Datom-log adapter replaces this): vector of
;; {:doc-id <str> :candidates [{:skill <str> :score <double>} ...]}
(defonce ^:private corpus-db (atom {}))

(defn reset-store! [] (reset! skill-db {}) (reset! corpus-db {}))

(defn seed-corpus!
  "Test/dev helper — seed the in-process corpus for a source key."
  [source rows]
  (swap! corpus-db assoc source (vec rows)))

;; ── injectable edges (rebound in tests / by the kotoba adapter) ─────────────

(def ^:dynamic *query-corpus*
  "Default corpus read: returns up to `limit` document rows for `source` from the
  in-process corpus, or [] when the store is disabled (unconfigured Python path)."
  (fn [source limit]
    (if-not (enabled?)
      []
      (->> (get @corpus-db source []) (take (max 0 (long limit))) vec))))

(def ^:dynamic *persist-skills*
  "Default skill write: append the extracted skill rows to the in-process store
  (no-op when disabled). Returns {:persisted <n>}."
  (fn [skills]
    (if-not (enabled?)
      {:persisted 0}
      (do (doseq [{:keys [skill] :as row} skills]
            (swap! skill-db assoc skill row))
          {:persisted (count skills)}))))

(defn query-corpus [source limit] (*query-corpus* source limit))
(defn persist-skills! [skills] (*persist-skills* skills))

;; ── pure extraction core (no I/O — same semantics as the kotodama handler) ──

(defn extract
  "Pure corpus→skill evidence extraction over already-fetched `docs`.

  Mirrors the camelCase handler params:
    minScore   — keep only candidates with score >= minScore
    topK       — keep at most topK candidates per document
    skillLimit — cap the total number of extracted skills

  Returns a sorted (score desc) deduped-by-skill vector of evidence rows."
  [docs {:keys [minScore topK skillLimit]
         :or   {minScore 0.97 topK 5 skillLimit 2000}}]
  (let [per-doc (mapcat
                 (fn [doc]
                   (->> (:candidates doc)
                        (filter #(>= (double (or (:score %) 0)) (double minScore)))
                        (sort-by :score #(compare %2 %1))
                        (take (max 0 (long topK)))
                        (map #(assoc % :doc-id (:doc-id doc)))))
                 docs)
        deduped (->> per-doc
                     (reduce (fn [acc {:keys [skill] :as row}]
                               (if (contains? acc skill) acc (assoc acc skill row)))
                             {})
                     vals
                     (sort-by :score #(compare %2 %1))
                     vec)]
    (vec (take (max 0 (long skillLimit)) deduped))))

(defn extract-evidence
  "Full corpus→skill task: read the corpus, extract evidence, persist unless
  dryRun. The clj analogue of `task_curpus2skill_extract_evidence` — same
  camelCase params, same return shape (a JSON-able dict).

  Reads via `query-corpus` (limit documents) and writes via `persist-skills!`,
  both injectable (the substrate boundary). Returns a result map."
  [{:keys [source limit skillLimit minScore topK dryRun]
    :or   {source "legal-corpus" limit 10 skillLimit 2000
           minScore 0.97 topK 5 dryRun false}}]
  (let [docs    (query-corpus source limit)
        skills  (extract docs {:minScore minScore :topK topK :skillLimit skillLimit})
        persist (if (and (seq skills) (not dryRun))
                  (:persisted (persist-skills! skills))
                  0)]
    {:source       source
     :scanned      (count docs)
     :extracted    (count skills)
     :persisted    persist
     :dryRun       (boolean dryRun)
     :minScore     minScore
     :topK         topK
     :skillLimit   skillLimit
     :skills       (mapv #(select-keys % [:skill :score :doc-id]) skills)}))

(defn store-summary
  "Diagnostic — current in-process store sizes (not part of the handler API)."
  []
  {:enabled (enabled?)
   :corpus-sources (vec (keys @corpus-db))
   :skills-held (count @skill-db)
   :note (str "in-process seam — kotoba Datom-log adapter replaces this "
              (when-not (enabled?) (str/trim "(currently INERT)")))})
