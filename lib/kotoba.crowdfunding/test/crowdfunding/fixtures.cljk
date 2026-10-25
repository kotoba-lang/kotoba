(ns crowdfunding.fixtures
  "Shared fixtures. Deliberately concrete — a campaign with a real goal, a
  limited tier, an add-on and per-destination shipping, because every bug
  this library is shaped around only appears once those exist."
  (:require [crowdfunding.campaign :as campaign]
            [crowdfunding.pledge :as pledge]
            [crowdfunding.reward :as reward]))

(def risks
  "A risks disclosure long enough to clear the substance floor in
  `crowdfunding.trust`."
  (str "Tooling for the split chassis is not finalised and the injection "
       "moulder has quoted a six week lead time that could slip. The FIDO2 "
       "controller is a single-source part; a shortage would delay every "
       "tier. We have built three prototypes but no production run."))

(def story "A split mechanical keyboard with an on-board FIDO2 authenticator.")

(defn a-campaign
  ([] (a-campaign nil))
  ([overrides]
   (merge (campaign/campaign
           {:id            "kb-split"
            :creator       "did:web:kawasaki.example"
            :title         "KB-SPLIT 60 FIDO"
            :currency      "JPY"
            :goal-minor    5000000
            :funding-model :all-or-nothing
            :category      :technology
            :duration-days 60
            :launched-at   "2026-08-01T00:00:00Z"
            :deadline      "2026-09-30T00:00:00Z"
            :story         story
            :risks         risks
            :ships-to      #{:jp :rest-of-world}})
          overrides)))

(def early-bird
  (reward/reward {:id "early-bird" :title "Early Bird" :minimum-minor 19800
                  :limit 50 :estimated-delivery "2027-03-01"
                  :shipping {:jp 800 :rest-of-world 3000}
                  :ships-to #{:jp :rest-of-world}}))

(def standard
  (reward/reward {:id "standard" :title "Standard" :minimum-minor 24800
                  :estimated-delivery "2027-04-01"
                  :shipping {:jp 800 :rest-of-world 3000}
                  :ships-to #{:jp :rest-of-world}}))

(def premium
  (reward/reward {:id "premium" :title "Premium CNC" :minimum-minor 32800
                  :limit 20 :estimated-delivery "2027-06-01"
                  :shipping {:jp 800}
                  :ships-to #{:jp}}))

(def wrist-rest
  (reward/reward {:id "wrist-rest" :title "Magnetic wrist rest" :minimum-minor 3000
                  :add-on? true :estimated-delivery "2027-04-01"
                  :ships-to #{:jp :rest-of-world}}))

(def rewards [early-bird standard premium wrist-rest])

(defn a-pledge
  ([id] (a-pledge id nil))
  ([id overrides]
   (merge (pledge/pledge {:id       id
                          :campaign "kb-split"
                          :backer   (str "did:web:backer-" id ".example")
                          :amount-minor 24800
                          :reward   "standard"
                          :ship-to  :jp
                          :placed-at "2026-08-10T00:00:00Z"})
          overrides)))

(def during-window "2026-09-01T00:00:00Z")
(def after-deadline "2026-10-01T00:00:00Z")

(defn live [] (-> (a-campaign) (assoc :campaign/state :in-review) (campaign/advance :live)))
