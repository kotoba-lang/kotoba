(ns mfa.datom)

(defn policy-datoms [policy]
  [{:db/id (:mfa.policy/id policy)
    :mfa.policy/required (:mfa.policy/required policy)
    :mfa.policy/phishing-resistant? (:mfa.policy/phishing-resistant? policy)
    :mfa.policy/purpose (:mfa.policy/purpose policy)
    :mfa.policy/preferences (:mfa.policy/preferences policy)
    :mfa.policy/fallbacks (:mfa.policy/fallbacks policy)
    :mfa.policy/fallback-for (:mfa.policy/fallback-for policy)}])

(defn result-datoms [result]
  [{:db/id (:mfa.result/policy-id result)
    :mfa.result/policy-id (:mfa.result/policy-id result)
    :mfa.result/factor-types (mapv :authn.factor/type (:mfa.result/factors result))
    :mfa.result/ok? (:mfa.result/ok? result)}])
