(ns dcs.runner
  "A conservative, host-side dry-run runner: validates a dcs.model system,
  then simulates N scan cycles entirely in memory against a caller-supplied
  PV trajectory. No fieldbus, no network, no live process I/O — this is for
  offline commissioning checks and tuning trials before a system config is
  deployed to real hardware."
  (:require [dcs.validate :as v]
            [dcs.execute :as e]
            [dcs.ports :as ports]))

(defrecord MemIO [values]
  ports/IFieldIO
  (read-tag [_ tag-id] (get @values tag-id))
  (write-tag! [_ tag-id value] (swap! values assoc tag-id value)))

(defn mem-io
  "An in-memory IFieldIO backed by an atom map, seeded with `initial-values`."
  [initial-values]
  (->MemIO (atom (or initial-values {}))))

(defn dry-run
  "Validate `system`; if invalid, return immediately with no simulation.
  Otherwise run `n-cycles` scans (default 1) against a fresh `mem-io` seeded
  with `initial-values` ({tag-id value}); before each cycle, apply that
  cycle's entry of `pv-overrides` (a seq of {tag-id value} maps standing in
  for the live process — a shorter seq or nil entries just leave prior
  values in place). `dt` (default 1.0) is the fixed cycle period in
  seconds. Returns {:dcs/valid? bool :dcs/problems [...] :dcs/trace [...]},
  trace being a vector of {:dcs/cycle i :dcs/tags {...} :dcs/events [...]}."
  [system {:keys [n-cycles dt initial-values pv-overrides]
           :or {n-cycles 1 dt 1.0 initial-values {} pv-overrides []}}]
  (let [problems (v/validate system)]
    (if (seq problems)
      {:dcs/valid? false :dcs/problems problems :dcs/trace []}
      (let [io (mem-io initial-values)]
        (loop [i 0 state (e/init-state) trace []]
          (if (>= i n-cycles)
            {:dcs/valid? true :dcs/problems [] :dcs/trace trace}
            (do
              (doseq [[tag-id value] (nth pv-overrides i nil)]
                (ports/write-tag! io tag-id value))
              (let [{:dcs/keys [state' events]} (e/scan system state io dt)
                    snapshot {:dcs/cycle i :dcs/tags @(:values io) :dcs/events events}]
                (recur (inc i) state' (conj trace snapshot))))))))))
