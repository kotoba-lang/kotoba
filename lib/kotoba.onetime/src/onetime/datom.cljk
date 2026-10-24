(ns onetime.datom)

(defn challenge-datoms [challenge]
  [{:db/id (:onetime/id challenge)
    :onetime/kind (:onetime/kind challenge)
    :onetime/subject (:onetime/subject challenge)
    :onetime/purpose (:onetime/purpose challenge)
    :onetime/digest-ref (:onetime/digest-ref challenge)
    :onetime/created-at (:onetime/created-at challenge)
    :onetime/expires-at (:onetime/expires-at challenge)}])

(defn result-datoms [result]
  [{:db/id (str (:onetime/id result) ":result")
    :onetime/id (:onetime/id result)
    :onetime/kind (:onetime/kind result)
    :onetime/ok? (:onetime/ok? result)
    :onetime/attempts (:onetime/attempts result)
    :onetime/verified-at (:onetime/verified-at result)}])
