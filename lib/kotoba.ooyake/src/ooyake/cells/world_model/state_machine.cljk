(ns ooyake.cells.world-model.state-machine
  "1:1 port of cells/world_model/cell.py — ooyake cross-actor WORLD-MODEL reconcile
  (ADR-2606021600 §3, depends ADR-2606011000 engi-organism-ontology + ADR-2606011800 tsumugi).

  This is the missing LAYER that joins the two government-facing graphs into one
  world model on the SHARED id-space:

      ooyake :gov.unit/*   (STRUCTURE — who/where/how of public administration)
         ── :gov.unit/organism ──▶  tsumugi :organism/*   (KARMA — 縁/取 power-graph)

  Until now `:gov.unit/organism` was defined in the ontology but populated by no
  unit and joined by no code: ooyake catalogued structure, tsumugi wove karma, and
  nothing reconciled the SAME public body across both. This cell performs that
  reconcile, OFFLINE and deterministically, and emits a world-model artifact.

  Charter shape (read-side, the same discipline as cells/reconcile/cell.py):
    - G9 READ-SIDE — produces a *report* + a *proposed* world-model artifact under
      out/. It NEVER mutates a committed seed; applying a proposed link is a
      separate operator-gated step.
    - G1 POWER-ONLY (tsumugi §D8/§D9) — only power-bearing units (country /
      supranational / cabinet / ministry / agency / bureau / legislature / court)
      are reconciled into the karma graph. Local service surface (prefecture /
      municipality / ward / division / 窓口) is civic-wayfinding, NOT a
      取-concentration node, and is EXCLUDED by construction — never a target-list.
    - G5 SOURCING-HONESTY — confirmed links require an explicit :gov.unit/organism
      whose target organism exists; everything else is a *proposal* tagged
      :representative / :latent. No fabricated reconciliation.
    - mode='live' RAISES (planet-scale ingest + write-back is Council + operator
      gated, exactly like reconcile.py).

  Two graphs in, one world model out. Stdlib only, no network, no LLM."
  (:require [kotoba.lang.edn :as edn]
            [kotoba.lang.text :as str]))

(def POWER_LEVEL_SUBKIND
  {":country" ":state"
   ":supranational" ":state"
   ":cabinet" ":state"
   ":ministry" ":agency"
   ":agency" ":agency"
   ":bureau" ":agency"
   ":legislature" ":legislature"
   ":court" ":court"})

(def GOV_ORGANISM_SUBKINDS #{":state" ":agency" ":legislature" ":court"})

(defn derive-organism-id [gov-unit-id]
  (if (.startsWith gov-unit-id "gov.")
    (str "org.gov." (.substring gov-unit-id 4))
    (str "org.gov." gov-unit-id)))

;; The native kotoba EDN files carry keyword keys (:gov.unit/level) and keyword
;; values (:country). reconcile-world-model + the lookup maps (POWER_LEVEL_SUBKIND,
;; GOV_ORGANISM_SUBKINDS) operate on the Python-faithful STRING-keyed/STRING-valued
;; shape (matching the unit-test fixtures). The loaders normalize EDN→that shape.
(defn- kw->str [v] (if (keyword? v) (str v) v))
(defn- normalize-record [m]
  (reduce-kv (fn [acc k v] (assoc acc (kw->str k) (kw->str v))) {} m))

(defn load-gov-units [reg-dir]
  (let [reg-dir (or reg-dir "registry")
        units (atom {})]
    (try
      (let [files (clojure.java.io/file reg-dir)]
        (if (.isDirectory files)
          (doseq [f (sort (filter #(.endsWith (.getName %) ".edn") (.listFiles files)))]
            (try
              (let [doc (edn/read-string (slurp f))
                    unit-list (get doc :units [])]
                (doseq [u unit-list]
                  (let [uid (get u :gov.unit/id)]
                    (when uid
                      (swap! units assoc uid (normalize-record u))))))
              (catch Exception _)))))
      (catch Exception _))
    @units))

(defn load-organisms [seed-file]
  (let [seed-file (or seed-file "orgs/etzhayyim/com-etzhayyim-tsumugi/data/seed-power-graph.kotoba.edn")
        orgs (atom {})]
    (try
      (let [doc (edn/read-string (slurp seed-file))]
        (doseq [rec doc]
          (when (and (map? rec) (get rec :organism/id))
            (swap! orgs assoc (get rec :organism/id) (normalize-record rec)))))
      (catch Exception _))
    @orgs))

(defn load-edges [seed-file]
  (let [seed-file (or seed-file "orgs/etzhayyim/com-etzhayyim-tsumugi/data/seed-power-graph.kotoba.edn")]
    (try
      (let [doc (edn/read-string (slurp seed-file))]
        (mapv normalize-record (filter #(and (map? %) (get % :en/id)) doc)))
      (catch Exception _
        []))))

(def GOVERNANCE_EN_KINDS #{":tends" ":custodies"})

(defn reconcile-world-model [gov-units organisms edges]
  (let [confirmed (atom [])
        derived (atom [])
        dangling (atom [])
        proposed (atom [])
        proposed-organisms (atom [])
        excluded-non-power (atom 0)
        referenced-org-ids (atom #{})
        orphan-organisms (atom [])
        non-gov-organisms (atom 0)
        stewardship (atom [])]

    ;; Process each gov-unit
    (doseq [uid (sort (keys gov-units))]
      (let [u (get gov-units uid)
            level (get u ":gov.unit/level")
            subkind (get POWER_LEVEL_SUBKIND level)]
        (if (nil? subkind)
          (swap! excluded-non-power inc)
          (let [explicit (get u ":gov.unit/organism")]
            (if explicit
              (if (contains? organisms explicit)
                (do
                  (swap! confirmed conj {"unit" uid "organism" explicit})
                  (swap! referenced-org-ids conj explicit))
                (swap! dangling conj {"unit" uid "organism" explicit}))
              (let [cand (derive-organism-id uid)]
                (if (contains? organisms cand)
                  (do
                    (swap! derived conj {"unit" uid "organism" cand})
                    (swap! referenced-org-ids conj cand))
                  (do
                    (swap! proposed conj {"unit" uid "organism" cand})
                    (swap! proposed-organisms conj
                           {":organism/id" cand
                            ":organism/kind" ":institutional"
                            ":organism/subkind" subkind
                            ":organism/label" (or (get u ":gov.unit/name-en")
                                                  (get u ":gov.unit/name-local")
                                                  uid)
                            ":organism/standing" ":latent"
                            ":organism/claimed?" false
                            ":organism/sourcing" ":representative"})))))))))

    ;; orphan governmental organisms: the karma graph knows them, the atlas does not.
    (doseq [[oid o] (sort organisms)]
      (let [sk (get o ":organism/subkind")
            is-gov (or (contains? GOV_ORGANISM_SUBKINDS sk)
                       (.startsWith oid "org.state."))]
        (if (not is-gov)
          (swap! non-gov-organisms inc)
          (when (not (contains? @referenced-org-ids oid))
            (swap! orphan-organisms conj {"organism" oid "label" (get o ":organism/label")})))))

    ;; cross-graph GOVERNMENT-STEWARDSHIP join
    (let [org-to-unit (into {} (concat
                                (map #(vector (get % "organism") (get % "unit")) @confirmed)
                                (map #(vector (get % "organism") (get % "unit")) @derived)))]
      (doseq [e (or edges [])]
        (let [frm (get e ":en/from")
              unit (get org-to-unit frm)]
          (when (and unit (contains? GOVERNANCE_EN_KINDS (get e ":en/kind")))
            (let [ent (get e ":en/to")]
              (swap! stewardship conj
                     {"gov_unit" unit
                      "gov_organism" frm
                      "kind" (get e ":en/kind")
                      "entity" ent
                      "entity_label" (get (get organisms ent) ":organism/label" ent)}))))))

    ;; Compute and return final report
    (let [stewardship-sorted (sort-by (juxt #(get % "gov_unit") #(get % "entity")) @stewardship)
          power-total (+ (count @confirmed) (count @derived) (count @dangling) (count @proposed))
          reconciled (+ (count @confirmed) (count @derived))]
      {"mode" "bundled"
       "gov_units_total" (count gov-units)
       "organisms_total" (count organisms)
       "power_bearing_units" power-total
       "excluded_non_power_units" @excluded-non-power
       "confirmed_links" @confirmed
       "derived_links" @derived
       "dangling_links" @dangling
       "proposed_links" @proposed
       "proposed_organisms" @proposed-organisms
       "orphan_gov_organisms" @orphan-organisms
       "non_gov_organisms_out_of_atlas" @non-gov-organisms
       "government_stewardship" stewardship-sorted
       "coverage" {"reconciled" reconciled
                   "proposed" (count @proposed)
                   "dangling" (count @dangling)
                   "reconciled_pct" (if (zero? power-total)
                                      0.0
                                      (double (/ (* 100.0 reconciled) power-total)))}})))

(defn stewarded-entities-of [report gov-unit]
  (vec (map #(select-keys % ["entity" "entity_label" "kind"])
            (filter #(= (get % "gov_unit") gov-unit)
                    (get report "government_stewardship" [])))))

(defn regulators-of [report entity]
  (vec (map #(select-keys % ["gov_unit" "gov_organism" "kind"])
            (filter #(= (get % "entity") entity)
                    (get report "government_stewardship" [])))))

(defn- validate-mode [mode]
  (cond
    (= mode "live")
    (throw (ex-info "ooyake world_model LIVE mode not activated (G4/G7). Planet-scale organism reconcile + write-back of :gov.unit/organism links to the committed seed requires Council Lv6+ ratify (ADR-2606021600) + operator enablement. Use mode='bundled' for the offline, deterministic reconcile."
                    {:type ::live-mode-gated}))
    (or (nil? mode) (= mode "bundled"))
    mode
    :else
    (throw (ex-info (str "unknown world_model mode: " (pr-str mode) " (expected 'bundled' or 'live')")
                    {:type ::invalid-mode :mode mode}))))

(defn world-model-cell-solve [state]
  (let [state (or state {})
        mode (get state "mode" "bundled")
        _validated (validate-mode mode)
        gov-units (load-gov-units (get state "reg_dir"))
        organisms (load-organisms (get state "organism_seed"))
        edges (load-edges (get state "organism_seed"))
        report (reconcile-world-model gov-units organisms edges)
        out-dir (get state "out_dir")]
    (when out-dir
      (clojure.java.io/make-parents (str out-dir "/world-model.kotoba.edn"))
      (spit (str out-dir "/world-model.kotoba.edn") (pr-str report)))
    {"status" "ok" "report" report}))
