(ns apn.runner
  "A conservative, host-side runner for offline what-if planning: validate
  a topology, then apply a batch of demands against it entirely in memory.
  JVM only (.clj, not .cljc) — the same host-side-tool boundary as
  dcs.runner."
  (:require [apn.validate :as validate]
            [apn.provision :as provision]))

(defn dry-run
  "Apply demands (a seq of maps with :apn/id :apn/src :apn/dst, and
  optionally further apn.model/lightpath opts) against sys in order.
  Returns immediately with :apn/valid? false and no provisioning if sys
  fails structural validation up front."
  [sys demands]
  (let [problems (validate/validate sys)]
    (if (seq problems)
      {:apn/valid? false :apn/problems problems :apn/system' sys :apn/trace []}
      (let [{:apn/keys [system' trace]}
            (reduce
             (fn [{:apn/keys [system' trace]} {:apn/keys [id src dst] :as demand}]
               (let [opts   (dissoc demand :apn/id :apn/src :apn/dst)
                     result (provision/request system' id src dst opts)]
                 {:apn/system' (:apn/system' result)
                  :apn/trace   (conj trace (:apn/event result))}))
             {:apn/system' sys :apn/trace []}
             demands)]
        {:apn/valid? true :apn/problems [] :apn/system' system' :apn/trace trace}))))
