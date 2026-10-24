(ns identify.datom)

(defn identifier-datoms [identifier]
  [{:db/id (str "identify:" (:identify.identifier/type identifier) ":" (:identify.identifier/value identifier))
    :identify.identifier/type (:identify.identifier/type identifier)
    :identify.identifier/value (:identify.identifier/value identifier)
    :identify.identifier/source (:identify.identifier/source identifier)
    :identify.identifier/observed-at (:identify.identifier/observed-at identifier)}])

(defn candidate-datoms [identifier candidate]
  [{:db/id (str "identify:candidate:" (:identify.identifier/type identifier) ":"
                (:identify.identifier/value identifier) ":"
                (:identify.candidate/subject candidate))
    :identify.candidate/identifier-value (:identify.identifier/value identifier)
    :identify.candidate/identifier-type (:identify.identifier/type identifier)
    :identify.candidate/subject (:identify.candidate/subject candidate)
    :identify.candidate/confidence (:identify.candidate/confidence candidate)
    :identify.candidate/evidence-ref (:identify.candidate/evidence-ref candidate)
    :identify.candidate/evidence-refs (:identify.candidate/evidence-refs candidate)
    :identify.candidate/asserter (:identify.candidate/asserter candidate)
    :identify.candidate/source (:identify.candidate/source candidate)
    :identify.candidate/conflict? (:identify.candidate/conflict? candidate)
    :identify/non-adjudicating (:identify/non-adjudicating candidate)}])
