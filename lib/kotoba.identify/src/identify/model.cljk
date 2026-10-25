(ns identify.model)

(def identifier-types #{:did :email :phone :wallet :account :device :document :ip-address :username})

(defn identifier [type value opts]
  {:identify.identifier/type type
   :identify.identifier/value value
   :identify.identifier/source (:source opts)
   :identify.identifier/observed-at (:observed-at opts)})

(defn candidate [subject confidence opts]
  {:identify.candidate/subject subject
   :identify.candidate/confidence confidence
   :identify.candidate/evidence-ref (:evidence-ref opts)
   :identify.candidate/asserter (:asserter opts)
   :identify.candidate/source (:source opts)
   :identify.candidate/evidence-refs (vec (:evidence-refs opts))
   :identify.candidate/assertions (vec (:assertions opts))
   :identify.candidate/conflict? (boolean (:conflict? opts))
   :identify/non-adjudicating true})
