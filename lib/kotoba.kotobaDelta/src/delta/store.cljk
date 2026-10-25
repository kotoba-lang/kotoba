(ns delta.store
  "⑱ IStore-stream persistence for the kotoba-delta op-log (ADR-2607161325).

  The op-log is an append-only stream with a monotonic :seq cursor — exactly
  kotobase's IStore stream shape (kotobase.store/IStore -append/-read). This
  adapter persists ops through any IStore (LocalStore standalone, or the
  KotobaseStore edge runtime — `KotobaseStore ≡ LocalStore` by contract), so
  the op-log gets the same durable, cursor-resumable substrate as manimani's
  Decision Ledger and the kotoba Datom log.

  Pure over the injected IStore protocol fns (append/read), so it runs under
  nbb with kotobase's LocalStore and against kotobase.net unchanged."
  (:require [kotobase.store :as store]
            [delta.op :as op]))

(def ^:const stream "kotoba-delta/ops")

(defn append-op!
  "Append a signed op envelope {:op :sig} to the op-log stream. Returns the
  event stamped with :seq (the log's monotonic cursor)."
  [istore envelope]
  (store/-append istore stream envelope))

(defn read-ops
  "Ops appended after `since` (0/nil = from the start), :seq-ordered."
  [istore since]
  (store/-read istore stream (or since 0)))

(defn log-head
  "The op-log head over what's persisted: id of the last op in the stream,
  plus its :seq cursor — the pair that folds into the signed fleet head."
  [hash-fn istore]
  (let [evs (read-ops istore 0)]
    (when (seq evs)
      {:head (op/op-id hash-fn (:op (last evs)))
       :seq (:seq (last evs))
       :count (count evs)})))
