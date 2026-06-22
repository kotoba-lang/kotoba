;; ingest.clj — KOTOBA Mesh default-language component (Clojure / kotoba-clj).
;;
;; KSE-topic-triggered: records an inbound mail event as a Datom. Like reply.clj,
;; all triggers currently dispatch to `run(ctx)` (multi-export codegen — on-kse —
;; is a kotoba-clj increment; ADR §14.3).
(ns ingest)

(defn run [ctx]
  (kqe-assert! "g" "ingest" "status" "received")
  (kqe-query "status(?s) :- ingest(?s)."))
