(ns haishin.receipt
  "What actually happened for one target, as an append-only record.

  A receipt is produced for every attempted entry, including failures and
  skips. A syndication run that posted to four platforms and failed on two must
  leave six records, not four — otherwise the ledger reads as a clean run and
  the two failures are invisible to anyone auditing later.

  Receipts are plain maps so they can be transacted straight into the workspace
  EDN plane (`:source/dataset` joins them to the rest of the fleet's facts)."
  (:require [haishin.artifact :as artifact]))

(def statuses
  "  :sent    the sender reported success and returned a remote id
     :failed  the sender threw; :receipt/error carries why
     :skipped the target was planned but not granted, or had no sender"
  #{:sent :failed :skipped})

(defn receipt
  [{:keys [artifact-id target status remote-id url error at]}]
  (cond-> {:receipt/artifact-id artifact-id
           :receipt/target target
           :receipt/status status
           :source/dataset "haishin-receipts"}
    remote-id (assoc :receipt/remote-id remote-id)
    url (assoc :receipt/url url)
    at (assoc :receipt/at at)
    error (assoc :receipt/error error)))

(defn sent [artifact-id target {:keys [remote-id url at]}]
  (receipt {:artifact-id artifact-id :target target :status :sent
            :remote-id remote-id :url url :at at}))

(defn failed [artifact-id target error at]
  (receipt {:artifact-id artifact-id :target target :status :failed
            :error error :at at}))

(defn skipped [artifact-id target reason at]
  (receipt {:artifact-id artifact-id :target target :status :skipped
            :error reason :at at}))

(defn ok? [r] (= :sent (:receipt/status r)))

(defn tally
  "status -> count, over a run's receipts."
  [receipts]
  (reduce (fn [acc r] (update acc (:receipt/status r) (fnil inc 0))) {} receipts))

(defn from-artifact
  "Seed the fields every receipt for `artifact` shares."
  [artifact]
  {:receipt/artifact-id (:artifact/id artifact)
   :receipt/source-url (artifact/attribution-url artifact)})
