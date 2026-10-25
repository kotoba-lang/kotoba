(ns senden.channel
  "Marketing channel model (pure). Channel{:id :name :reach :cost-per-1k-impressions
  :conversion-rate}. Reach = estimated audience size; cost-per-1k = CPM; conversion-rate
  = historical click→purchase rate. campaign-cost computes expected spend for a campaign's
  channel given an impression target."
  (:require [chobo.ledger :as ledger]))

(defrecord Channel [id name reach cost-per-1k-impressions conversion-rate])

(defn channel [m] (merge {:reach 0 :cost-per-1k-impressions 0 :conversion-rate 0} m))

(defn campaign-cost
  "Expected spend = (impressions / 1000) * CPM. Returns 0 if no CPM."
  [channel' impressions]
  (let [cpm (:cost-per-1k-impressions channel' 0)]
    (* (/ (max 0 impressions) 1000) cpm)))

(defn expected-conversions
  "Expected conversions = impressions * conversion-rate (click→purchase)."
  [channel' impressions]
  (* (max 0 impressions) (:conversion-rate channel' 0)))

(defn expected-cpa
  "Expected cost-per-acquisition = cost / conversions. nil if no conversions expected."
  [channel' impressions]
  (let [cost (campaign-cost channel' impressions)
        conv (expected-conversions channel' impressions)]
    (when (pos? conv) (/ cost conv))))

(defn best-channel
  "Pick the channel with the lowest expected CPA. nil if no channel expects
  conversions."
  [channels impressions]
  (->> channels
       (map #(vector (or (expected-cpa % impressions) ##Inf) %))
       (filter #(not= (first %) ##Inf))
       (sort-by first)
       first
       second))

(defn channel-activity
  "Project a channel selection/spend event onto chobo.ledger (lane :marketing,
  kind :channel-selection)."
  [channel' opts]
  (ledger/activity
   (merge {:lane :marketing :kind :channel-selection
           :title (:name channel' "channel")
           :props {:channel-id (:id channel')
                   :reach (:reach channel' 0)
                   :cpm (:cost-per-1k-impressions channel' 0)}} opts)))
