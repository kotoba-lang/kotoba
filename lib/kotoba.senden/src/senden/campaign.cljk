(ns senden.campaign
  "Marketing campaign model (pure). Campaign{:id :name :channel :status :start
  :end :budget :metrics}. Status: :draft → :scheduled → :running → :paused →
  :completed | :cancelled. Projects onto chobo.ledger as lane :marketing."
  (:require [chobo.ledger :as ledger]))

(defrecord Campaign [id name channel status start end budget metrics])

(def statuses #{:draft :scheduled :running :paused :completed :cancelled})
(def transitions
  {:draft     #{:scheduled :cancelled}
   :scheduled #{:running :cancelled}
   :running   #{:paused :completed :cancelled}
   :paused    #{:running :completed :cancelled}
   :completed #{}
   :cancelled #{}})

(defn campaign [m] (merge {:status :draft :metrics {}} m))

(defn can-transition? [from to] (contains? (get transitions from #{}) to))
(defn transition [c to] (when (can-transition? (:status c :draft) to) (assoc c :status to)))

(defn schedule [c] (transition c :scheduled))
(defn start-campaign [c] (transition c :running))
(defn pause [c] (transition c :paused))
(defn complete [c] (transition c :completed))
(defn cancel [c] (transition c :cancelled))

(defn spend
  "Add `amount` to the campaign's :spend metric (cumulative ad spend)."
  [c amount]
  (update-in c [:metrics :spend] (fnil + 0) (max 0 amount)))

(defn record-conversion
  "Increment the campaign's :conversions metric by n (default 1)."
  ([c] (record-conversion c 1))
  ([c n]
   (update-in c [:metrics :conversions] (fnil + 0) (max 0 n))))

(defn cpa
  "Cost per acquisition = spend / conversions (nil if no conversions)."
  [c]
  (let [spend (get-in c [:metrics :spend] 0)
        conv (get-in c [:metrics :conversions] 0)]
    (when (pos? conv) (/ spend conv))))

(defn marketing-activity
  "Project a campaign event onto chobo.ledger as a :marketing activity."
  [c opts]
  (ledger/activity
   (merge {:lane :marketing :kind :campaign
           :title (:name c) :state (:status c :draft)
           :props {:campaign-id (:id c) :channel (:channel c)
                   :spend (get-in c [:metrics :spend] 0)
                   :conversions (get-in c [:metrics :conversions] 0)}}
          opts)))

;; ---------------------------------------------------------------------------
;; A/B test variants + winner selection
;; ---------------------------------------------------------------------------

(defrecord Variant [id name spend conversions impressions])

(defn variant [m] (merge {:spend 0 :conversions 0 :impressions 0} m))

(defn variant-cvr
  "Conversion rate = conversions / impressions (nil if no impressions)."
  [v]
  (let [i (:impressions v 0)]
    (when (pos? i) (/ (:conversions v 0) i))))

(defn variant-cpa
  "CPA = spend / conversions (nil if no conversions)."
  [v]
  (let [conv (:conversions v 0)]
    (when (pos? conv) (/ (:spend v 0) conv))))

(defn pick-winner
  "Select the winning variant by :conversions (highest). Ties → first. Returns
  nil if no variants have conversions."
  [variants]
  (let [with-conv (filter #(pos? (:conversions % 0)) variants)]
    (when (seq with-conv)
      (first (sort-by #(get-in % [:conversions] 0) > with-conv)))))

(defn pick-winner-by-cpa
  "Select the winning variant by lowest CPA. nil if no variant has conversions."
  [variants]
  (let [with-conv (filter #(pos? (:conversions % 0)) variants)]
    (when (seq with-conv)
      (first (sort-by variant-cpa with-conv)))))

(defn ab-test-activity
  "Project an A/B test winner selection onto chobo.ledger (lane :marketing,
  kind :ab-test)."
  [winner variants opts]
  (ledger/activity
   (merge {:lane :marketing :kind :ab-test
           :title (str "A/B winner: " (:name winner "unknown"))
           :props {:winner-id (:id winner)
                   :variants (count variants)
                   :winner-conversions (:conversions winner 0)}}
          opts)))

;; ---------------------------------------------------------------------------
;; budget management (burn-rate, remaining, overspend detection)
;; ---------------------------------------------------------------------------

(defn budget-remaining
  "Remaining budget = budget - spend. Returns 0 if overspent (clamped)."
  [c]
  (let [budget (get-in c [:budget] 0)
        spend (get-in c [:metrics :spend] 0)]
    (max 0 (- budget spend))))

(defn budget-overspent?
  "True if spend exceeds the campaign's budget."
  [c]
  (> (get-in c [:metrics :spend] 0) (get-in c [:budget] 0)))

(defn burn-rate
  "Fraction of budget consumed = spend / budget (0.0–1.0+). Returns nil if
  budget is 0."
  [c]
  (let [budget (get-in c [:budget] 0)]
    (when (pos? budget)
      (/ (get-in c [:metrics :spend] 0) budget))))

(defn budget-pct
  "Budget consumed as a percentage (0–100+). nil if no budget."
  [c]
  (when-let [r (burn-rate c)]
    (* r 100)))

(defn projected-spend
  "Project total spend at the current rate given elapsed/total days.
  Returns {:projected-spend :would-overspend?}."
  [c elapsed-days total-days]
  (let [spend (get-in c [:metrics :spend] 0)
        daily (if (pos? elapsed-days) (/ spend elapsed-days) 0)
        projected (* daily (max 1 total-days))
        budget (get-in c [:budget] 0)]
    {:projected-spend (long projected)
     :daily-rate (long daily)
     :would-overspend? (> projected budget)}))

(defn budget-activity
  "Build a ledger activity for a budget status check (kind :budget-check)."
  [c opts]
  (ledger/activity
   (merge {:lane :marketing :kind :budget-check
           :title (str "Budget check: " (:name c "campaign"))
           :props {:campaign-id (:id c)
                   :budget (get-in c [:budget] 0)
                   :spend (get-in c [:metrics :spend] 0)
                   :remaining (budget-remaining c)
                   :overspent (budget-overspent? c)}}
          opts)))
