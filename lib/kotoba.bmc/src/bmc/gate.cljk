(ns bmc.gate
  "Gate evaluator: turn collected metrics into hypothesis progression so a
   portfolio BMC actually *cycles* on a schedule instead of going dry.
   Extracted from 70-tools/bmc's gftd.gate (ADR-2607022100) into a reusable
   library (ADR-260719XXXX) — the evaluator half only. The concrete per-
   hypothesis `gate-specs` table (product/metric-path literals) is NOT part
   of this library; it stays in the consumer (e.g. 70-tools/bmc's gftd.cli)
   as config data and is passed into `proposals` explicitly.

   Per riskiest hypothesis, a gate-spec is either:
   - machine-measurable — {:metric [path...] :op :>= :threshold N} over the
     product's metrics edn. When satisfied → propose `hyp/status :validated`
     with the measured value as evidence (auto-advance). When measurable but
     not yet met → promote hyp to :measuring once + emit a 'gate distance'
     observation (hyp no longer stays untested when the instrument is live).
   - instrument-blocked — {:needs [\"missing instrument\" ...]}. The gate can't be
     measured until those are prepared, so propose a concrete '準備:' item into
     the solution block (actionable to-do) and record the gate as :blocked.

   Pure .cljc; io stays in the consumer's cli/collect layer."
  (:require [kotoba.lang.text :as str]
            [bmc.canvas :as canvas]))

;; ---- predicate evaluation ---------------------------------------------------

(defn- num [x] (cond (number? x) x (string? x) (parse-double x) :else nil))

(defn- op-fn [op] (case op :>= >= :> > :<= <= :< < := == :== ==))

(defn- eval-clause
  "→ {:measurable bool :met bool :value v} for one {:metric :op :threshold} clause."
  [metrics {:keys [metric op threshold]}]
  (let [v (num (get-in metrics metric))]
    (if (nil? v)
      {:measurable false}
      {:measurable true :met ((op-fn op) v threshold) :value v})))

(defn evaluate-hyp
  "Evaluate one hypothesis' gate against the product's metrics. `spec` is a
   single hypothesis' gate-spec (one value out of the caller's gate-specs
   map) — this fn has no notion of the whole table.
   → {:status :validated|:measuring|:blocked :evidence str :needs [..] :distance str}"
  [metrics spec]
  (cond
    (nil? spec) {:status :blocked :needs ["gate-spec 未定義"]}

    ;; conjunction of clauses (:all)
    (:all spec)
    (let [rs (map #(eval-clause metrics %) (:all spec))]
      (cond
        (some #(not (:measurable %)) rs)
        {:status :blocked :needs (:needs-when-unmeasurable spec)}
        (every? :met rs)
        {:status :validated
         :evidence (str (:evidence-label spec) " gate 到達: "
                        (str/join " / " (map :value rs)))}
        :else
        {:status :measuring
         :distance (str (:evidence-label spec) " 現在 "
                        (str/join " / " (map :value rs)) " (gate 未到達)")}))

    ;; cross-metric comparison (lhs op rhs)
    (:compare spec)
    (let [{:keys [lhs op rhs]} (:compare spec)
          l (num (get-in metrics lhs)) r (num (get-in metrics rhs))]
      (cond
        (or (nil? l) (nil? r)) {:status :blocked :needs (:needs-when-unmeasurable spec)}
        ((op-fn op) l r) {:status :validated
                          :evidence (str (:evidence-label spec) " gate 到達: " l " vs " r)}
        :else {:status :measuring
               :distance (str (:evidence-label spec) " 現在 " l " vs " r " (gate 未到達)")}))

    ;; single measurable clause
    (:metric spec)
    (let [r (eval-clause metrics spec)]
      (cond
        (not (:measurable r)) {:status :blocked :needs (:needs-when-unmeasurable spec)}
        (:met r) {:status :validated
                  :evidence (str (:evidence-label spec) " = " (:value r) " (gate 到達)")}
        :else {:status :measuring
               :distance (str (:evidence-label spec) " = " (:value r) " (gate 未到達)")}))

    ;; instrument-blocked
    (:needs spec) {:status :blocked :needs (:needs spec)}

    :else {:status :blocked :needs ["gate-spec 不明"]}))

;; ---- proposals ---------------------------------------------------------------

(defn- block-id [product suffix] (keyword (str (name product) "." suffix)))

(defn- block-items-set [idx block-id]
  "Get current canvas items for a block as a set for dedup."
  (let [block (get-in idx [:blocks block-id])]
    (if block (set (:canvas/items block)) #{})))

(defn proposals
  "Given the caller's `gate-specs` map (hyp-id → spec), the folded index, a
   product, and its metrics, return governor-ready proposals that advance the
   BMC cycle:
   - :validated → hyp/status :validated (evidence attached)
   - :blocked   → 準備 to-do item into the solution block (dedup'd)
   - :measuring → hyp/status :measuring once (instrument live) + gate-distance
                  observation into key-metrics (dedup'd)"
  [gate-specs idx product metrics]
  (let [hyps (canvas/product-hyps idx product)]
    (mapcat
     (fn [h]
       (let [hid (:hyp/id h)
             spec (get gate-specs hid)]
        (if (nil? spec)
          []                                  ; gate-spec の無い仮説はスキップ（no-op）
          (let [r (evaluate-hyp metrics spec)]
           (case (:status r)
           :validated
           ;; 既に :validated の仮説は再提案しない — これが無いと gate 到達後の
           ;; 毎 tick/毎日 run が同じ昇格 event を ledger に積み続け、loop が
           ;; 収束 (dry) しない (2026-07-15 cloud-murakumo 実測で発見)。
           (when (not= :validated (:hyp/status h))
             [{:proposal/action :hyp/status :hyp/id hid :event/value :validated
               :event/evidence (:evidence r)
               :proposal/reason "gate 到達 (機械測定) — 仮説を validated に昇格"}])
           :blocked
           (let [solution-items (block-items-set idx (block-id product "solution"))]
             (for [need (:needs r)
                   :let [txt (str "準備 (" (name hid) "): " need)]
                   :when (not (contains? solution-items txt))]
               {:proposal/action :canvas/add-item
                :canvas/id (block-id product "solution")
                :event/value txt
                :proposal/reason "gate 測定に必要な計器/前提が未整備 — 準備項目として提案"}))
           :measuring
           ;; 計器が読めて未到達なら hyp を :measuring に昇格（一度きり）し、
           ;; gate 距離を key-metrics に載せる。:validated と同様に既に
           ;; :measuring の hyp は status 再提案しない。
           (let [metrics-items (block-items-set idx (block-id product "metrics"))
                 txt (str "gate 距離 (" (name hid) "): " (:distance r))
                 status-up (when (and (not= :measuring (:hyp/status h))
                                      (not= :validated (:hyp/status h)))
                             [{:proposal/action :hyp/status :hyp/id hid
                               :event/value :measuring
                               :event/evidence (or (:distance r) (:evidence r)
                                                   "gate instrumented, threshold not met")
                               :proposal/reason "gate 計器稼働・未到達 — measuring に昇格"}])
                 dist-item (if (contains? metrics-items txt)
                             []
                             [{:proposal/action :canvas/add-item
                               :canvas/id (block-id product "metrics")
                               :event/value txt
                               :proposal/reason "gate は機械測定可能・未到達 — 距離を運用指標に反映"}])]
             (concat status-up dist-item))
           [])))))
     hyps)))
