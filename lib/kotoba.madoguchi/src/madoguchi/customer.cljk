(ns madoguchi.customer
  "Customer / CRM model (pure). Customer{:id :name :email :tags :order-refs
  :lifetime-value :contacts}. Contact log records inbound/outbound interactions."

  (:refer-clojure :exclude [empty])
  (:require [chobo.ledger :as ledger]))

(defrecord Customer [id name email tags order-refs lifetime-value contacts])
(defrecord Contact [id customer channel direction subject timestamp])

(defn customer [m] (merge {:tags #{} :order-refs [] :contacts [] :lifetime-value 0} m))

(defn tag [c t] (update c :tags (fnil conj #{}) t))
(defn untag [c t] (update c :tags disj t))

(defn add-contact [c contact]
  (update c :contacts conj (map->Contact contact)))

(defn contacts-by-channel [c channel] (filterv #(= (:channel %) channel) (:contacts c [])))

(defn add-order-ref [c order-id]
  (update c :order-refs (fnil conj []) order-id))

(defn add-lifetime-value [c amount]
  (update c :lifetime-value (fnil + 0) (max 0 amount)))

;; ---------------------------------------------------------------------------
;; customer 360 stats (derived from the customer record)
;; ---------------------------------------------------------------------------

(defn order-count [c] (count (:order-refs c [])))

(defn last-contact
  "The most recent contact (by :timestamp). nil if no contacts."
  [c]
  (let [contacts (:contacts c [])]
    (when (seq contacts)
      (last (sort-by :timestamp contacts)))))

(defn last-contact-at
  "Timestamp of the most recent contact, or nil."
  [c]
  (:timestamp (last-contact c)))

(defn contact-count [c] (count (:contacts c [])))

(defn avg-order-value
  "Average lifetime value per order. nil if no orders."
  [c]
  (let [n (order-count c)]
    (when (pos? n)
      (/ (:lifetime-value c 0) n))))

(defn customer-360
  "Build a customer 360 snapshot: derived stats from the customer record."
  [c]
  {:id (:id c)
   :name (:name c)
   :email (:email c)
   :tags (:tags c #{})
   :order-count (order-count c)
   :lifetime-value (:lifetime-value c 0)
   :avg-order-value (avg-order-value c)
   :contact-count (contact-count c)
   :last-contact-at (last-contact-at c)})

(defn vip?
  "True if the customer is tagged :vip or has LTV above a threshold (default
  100000)."
  ([c]
   (vip? c 100000))
  ([c threshold]
   (or (contains? (:tags c #{}) :vip)
       (>= (:lifetime-value c 0) threshold))))

;; ---------------------------------------------------------------------------
;; NPS / satisfaction tracking
;; ---------------------------------------------------------------------------

(defn add-survey
  "Record an NPS survey response on the customer. score 0–10. Returns the
  updated customer with :surveys appended."
  [c score opts]
  (let [survey (merge {:score score :at (:at opts)} opts)]
    (update c :surveys (fnil conj []) survey)))

(defn nps-category
  "Classify a score: 0–6 = :detractor, 7–8 = :passive, 9–10 = :promoter."
  [score]
  (cond
    (<= score 6) :detractor
    (<= score 8) :passive
    :else :promoter))

(defn nps-score
  "Compute NPS from a seq of survey scores: %promoters − %detractors. Returns
  an integer in [-100, 100]. nil if no surveys."
  [scores]
  (when (seq scores)
    (let [total (count scores)
          cats (map nps-category scores)
          promoters (count (filter #{:promoter} cats))
          detractors (count (filter #{:detractor} cats))]
      (int (- (* 100 (/ promoters total)) (* 100 (/ detractors total)))))))

(defn customer-nps
  "Compute the NPS from a customer's :surveys. nil if no surveys."
  [c]
  (nps-score (map :score (:surveys c []))))

(defn survey-activity
  "Build a ledger activity for a survey/NPS event (lane :support, kind :nps)."
  [c score opts]
  (ledger/activity
   (merge {:lane :support :kind :nps
           :title (str "NPS survey: " (:id c))
           :props {:customer-id (:id c)
                   :score score
                   :category (nps-category score)}}
          opts)))
