(ns kotoba.async
  "Assembled from one repo per definition.

  This namespace holds no implementation. It re-exports the definitions
  that each live in their own repo, so a call site can require one name
  and a library can require only the definitions it actually uses."
  (:refer-clojure :exclude [chan close put take])
  (:require [kotoba.async.can-put :as can-put-ns]
            [kotoba.async.can-take :as can-take-ns]
            [kotoba.async.chan :as chan-ns]
            [kotoba.async.close :as close-ns]
            [kotoba.async.closed :as closed-ns]
            [kotoba.async.drain :as drain-ns]
            [kotoba.async.fixed-chan :as fixed-chan-ns]
            [kotoba.async.put :as put-ns]
            [kotoba.async.scope :as scope-ns]
            [kotoba.async.scope-cancel :as scope-cancel-ns]
            [kotoba.async.scope-close :as scope-close-ns]
            [kotoba.async.scope-complete :as scope-complete-ns]
            [kotoba.async.scope-fail :as scope-fail-ns]
            [kotoba.async.scope-join-ready :as scope-join-ready-ns]
            [kotoba.async.scope-spawn :as scope-spawn-ns]
            [kotoba.async.scope-summary :as scope-summary-ns]
            [kotoba.async.take :as take-ns]))

(def can-put? "See kotoba.async.can-put/can-put?." can-put-ns/can-put?)
(def can-take? "See kotoba.async.can-take/can-take?." can-take-ns/can-take?)
(def chan "See kotoba.async.chan/chan." chan-ns/chan)
(def close "See kotoba.async.close/close." close-ns/close)
(def closed? "See kotoba.async.closed/closed?." closed-ns/closed?)
(def drain "See kotoba.async.drain/drain." drain-ns/drain)
(def fixed-chan "See kotoba.async.fixed-chan/fixed-chan." fixed-chan-ns/fixed-chan)
(def put "See kotoba.async.put/put." put-ns/put)
(def scope "See kotoba.async.scope/scope." scope-ns/scope)
(def scope-cancel "See kotoba.async.scope-cancel/scope-cancel." scope-cancel-ns/scope-cancel)
(def scope-close "See kotoba.async.scope-close/scope-close." scope-close-ns/scope-close)
(def scope-complete "See kotoba.async.scope-complete/scope-complete." scope-complete-ns/scope-complete)
(def scope-fail "See kotoba.async.scope-fail/scope-fail." scope-fail-ns/scope-fail)
(def scope-join-ready? "See kotoba.async.scope-join-ready/scope-join-ready?." scope-join-ready-ns/scope-join-ready?)
(def scope-spawn "See kotoba.async.scope-spawn/scope-spawn." scope-spawn-ns/scope-spawn)
(def scope-summary "See kotoba.async.scope-summary/scope-summary." scope-summary-ns/scope-summary)
(def take "See kotoba.async.take/take." take-ns/take)
