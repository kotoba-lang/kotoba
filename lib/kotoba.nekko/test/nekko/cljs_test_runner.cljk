(ns nekko.cljs-test-runner
  "Real-ClojureScript test host for the async namespaces that nbb cannot run.

  Why this exists rather than adding to `test:async`: `nekko.key-journal` goes
  through `chain.core`, whose non-genesis commits encode `prev` as an
  `ipld.core/Link` — a `deftype`. Under nbb/sci that type's field is not
  readable (`ipld/link?` returns true while `ipld/link-cid` returns nil), so
  every commit after genesis throws. Real ClojureScript compiles the deftype
  properly and the same code passes. That is an nbb limitation, not a browser
  one, and the actual consumer is a browser bundle, so this host is the more
  faithful one anyway.

  Runs from a bare clone — it needs only `npm install` for @noble/*, no west
  workspace. That took fixing the actual cause rather than working around it:
  all seven of this repo's git pins were behind their mains, and the pinned
  `io-multiformats` had two `:require` forms in one ns, which sci tolerates and
  cljs rejects outright. Bumping one pin then surfaced a second skew (the
  pinned `org-ietf-cbor` could not decode what the newer ipld produced), so the
  pins had to move together. `:local` is no longer required here; if you find
  yourself adding it back, the pins have gone stale again.

  Run: npm run test:cljs"
  (:require [cljs.test :as t :refer-macros [run-tests]]
            [nekko.delegate-test]
            [nekko.journal-test]
            [nekko.key-journal-test]
            [nekko.push-gate-test]))

(defmethod t/report [:cljs.test/default :end-run-tests] [m]
  (set! (.-exitCode js/process) (if (t/successful? m) 0 1)))

(defn -main [& _]
  (run-tests 'nekko.delegate-test
             'nekko.journal-test
             'nekko.key-journal-test
             'nekko.push-gate-test))
