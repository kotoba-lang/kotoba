(ns apn.provision
  "Pure lightpath lifecycle transitions: request -> RWA -> commit, and
  teardown. No I/O — a host applies the returned :apn/system' and reacts
  to :apn/event (e.g. writes it to an audit ledger, as
  cloud-itonami-isic-6110 does)."
  (:require [apn.model :as m]
            [apn.rwa :as rwa]))

(defn request
  "Attempt to provision a lightpath id from src to dst. On success, adds an
  :apn/state :active lightpath to the topology and occupies its assigned
  wavelength on every hop. On failure, returns the unchanged system and a
  :blocked event carrying the RWA rejection reason — nothing is mutated on
  failure."
  ([sys id src dst] (request sys id src dst {}))
  ([sys id src dst opts]
   (let [r (rwa/assign sys src dst)]
     (if (:apn/ok? r)
       (let [lp (m/lightpath id src dst
                              (merge opts {:apn/path (:apn/path r)
                                          :apn/wavelength (:apn/wavelength r)
                                          :apn/state :active}))]
         {:apn/system' (-> sys
                           (m/add-lightpath lp)
                           (m/occupy-path (:apn/path r) (:apn/wavelength r) id))
          :apn/event {:apn/t :provisioned :apn/lightpath id
                      :apn/path (:apn/path r) :apn/wavelength (:apn/wavelength r)}})
       {:apn/system' sys
        :apn/event {:apn/t :blocked :apn/lightpath id :apn/reason (:apn/reason r)}}))))

(defn teardown
  "Release id's wavelength on every hop and mark it :torn-down. A no-op
  (unchanged system, a :not-found event) if id isn't a known lightpath."
  [sys id]
  (if-let [lp (m/lightpath-by-id sys id)]
    {:apn/system' (-> sys
                      (m/free-path (:apn/path lp) (:apn/wavelength lp))
                      (assoc-in [:apn/lightpaths id :apn/state] :torn-down))
     :apn/event {:apn/t :torn-down :apn/lightpath id}}
    {:apn/system' sys
     :apn/event {:apn/t :not-found :apn/lightpath id}}))
