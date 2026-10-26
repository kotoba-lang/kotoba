(ns kototama.heartbeat
  "kototama.heartbeat — the shared IDEMPOTENT-BY-CONTENT autorun decision for atproto actors
  + artificial organisms. Every actor's `autorun/beat` repeats the same skeleton: compute
  this beat's datoms, compare to the last committed datoms, append a new tx ONLY when the
  content changed (else a no-op). This is that decision, factored out — pure + deterministic,
  so a beat is crash/re-run safe (replaying an unchanged beat is a structural no-op).

  The actual storage (read last tx, append tx, hash) is the HOST's job — see
  kototama.host (the `actor:host` ABI). This namespace only decides + shapes the result."
  (:require [kotoba.lang.text :as str]))

(defn changed?
  "True when this beat's datoms differ from the last committed datoms (idempotent-by-content)."
  [this-datoms last-datoms]
  (not= this-datoms last-datoms))

(defn decide
  "The beat decision. Given the freshly-folded `datoms` and the `last-datoms` from the head
  of the commit-DAG, return:
    {:append? true  :reason nil}        when content changed → host should append a tx
    {:append? false :reason :no-change} when unchanged       → host does nothing
  Pure; the host performs the append + hashing."
  [datoms last-datoms]
  (if (changed? datoms last-datoms)
    {:append? true :reason nil :count (count datoms)}
    {:append? false :reason :no-change :count (count datoms)}))

(defn beat
  "Fold one heartbeat. `fold` is a pure (ctx -> datoms) layer-fold (the actor's domain logic);
  `last-datoms` is the previous head's datoms (host-provided). Returns the decide map plus the
  freshly-folded :datoms, ready for the host to append when :append? is true."
  [fold ctx last-datoms]
  (let [datoms (vec (fold ctx))]
    (assoc (decide datoms last-datoms) :datoms datoms)))
