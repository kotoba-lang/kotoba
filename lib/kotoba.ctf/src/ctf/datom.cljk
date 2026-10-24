(ns ctf.datom)

(defn result-datoms [r]
  [{:db/id (str (:ctf/id r) ":" (name (:ctf/route r)))
    :ctf/id (:ctf/id r)
    :ctf/route (:ctf/route r)
    :ctf/level (:ctf/level r)
    :ctf/score (:ctf/score r)
    :ctf/categories (:ctf/categories r)
    :ctf/evidence-ref (:ctf/evidence-ref r)
    :ctf/asserter (:ctf/asserter r)
    :ctf/observed-at (:ctf/observed-at r)
    :ctf/non-adjudicating (:ctf/non-adjudicating r)}])

(defn screening-datoms [s]
  [{:db/id (:ctf/id s)
    :ctf/status (:ctf/status s)
    :ctf/case-ref (:ctf/case-ref s)
    :ctf/routes (:ctf/routes s)
    :ctf/non-adjudicating true}])
