(ns face-match.model
  "Result records for face-match comparison. HONESTY NOTE (do not remove):
   this repo has NO comparison algorithm and NO embedding model -- see
   README.md/MATURITY.md. `statuses` intentionally does NOT include
   :verified/:flagged as reachable outcomes of `face-match.core/compare`
   today (a caller passing a real face-match.ports/IFaceMatcher could reach
   them once one exists, but none does) -- reachable in practice is only
   :review.")

(def statuses #{:review :verified :flagged})
(def reasons #{:not-implemented :matcher-returned-nil})

(defn compare-result
  [opts]
  {:face-match/status (:status opts :review)
   :face-match/confidence (:confidence opts)
   :face-match/reason (:reason opts :not-implemented)
   :face-match/non-adjudicating true})
