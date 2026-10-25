(ns cloudflare.workers.policy-test
  (:require [clojure.test :refer [deftest is testing]]
            [cloudflare.workers.fixtures :as fix]
            [cloudflare.workers.policy :as policy]))

(deftest absence-never-grants
  (testing "every omitted key resolves to the empty, not the permissive, value"
    (let [p (policy/normalize {:policy/bindings {"B" {:kind :kv}}})
          spec (policy/binding-spec p "B")]
      (is (= #{} (:caps spec)))
      (is (= #{} (:key-prefixes spec)))
      (is (= {} (:statements spec)))
      (is (false? (policy/granted? spec :cf/kv-read)))
      (is (false? (policy/key-in-scope? spec "anything")))))

  (testing "an entirely empty policy is well-formed and authorizes nothing"
    (let [p (policy/normalize {})]
      (is (empty? (policy/problems p)))
      (is (nil? (policy/binding-spec p "SESSIONS"))))))

(deftest wildcard-is-forbidden-unless-explicitly-opted-out
  (is (true? (:policy/forbid-wildcard (policy/normalize {}))))
  (is (true? (:policy/forbid-wildcard (policy/normalize {:policy/forbid-wildcard true}))))
  (is (false? (:policy/forbid-wildcard (policy/normalize {:policy/forbid-wildcard false})))
      "only an explicit false opts out -- nil must not")
  (testing "the opt-out plus :any scope is reported as a warning, not silently accepted"
    (let [problems (policy/problems (assoc fix/policy :policy/forbid-wildcard false))
          warnings (filter (comp #{:warning} :severity) problems)]
      (is (= 1 (count warnings)))
      (is (= :wildcard-scope-enabled (:problem (first warnings))))
      (is (policy/valid? (assoc fix/policy :policy/forbid-wildcard false))
          "a warning does not make the policy invalid"))))

(deftest quotas-are-clamped-visibly
  (let [p (policy/normalize {:policy/quota {:max-commands 1000000}})]
    (is (= (:max-commands policy/quota-ceiling) (:max-commands (:policy/quota p))))
    (is (contains? (:policy/quota-clamped p) :max-commands)
        "the clamp is recorded, so an operator can see their number was reduced"))
  (testing "tightening below the default is honoured as written"
    (let [p (policy/normalize {:policy/quota {:max-commands 2}})]
      (is (= 2 (:max-commands (:policy/quota p))))
      (is (nil? (:policy/quota-clamped p))))))

(deftest normalize-is-idempotent
  (let [once (policy/normalize fix/policy)
        twice (policy/normalize once)]
    (is (= once twice))))

(deftest key-scope-is-prefix-matching-not-substring
  (let [spec (policy/binding-spec (policy/normalize fix/policy) "SESSIONS")]
    (is (policy/key-in-scope? spec "user:1"))
    (is (policy/key-in-scope? spec "user:"))
    (is (not (policy/key-in-scope? spec "x-user:1")))
    (is (not (policy/key-in-scope? spec "use")))
    (is (not (policy/key-in-scope? spec "admin:1")))))

(deftest placeholder-counting-understands-sql-string-literals
  (is (= 1 (policy/placeholder-count "select 1 where id = ?1")))
  (is (= 2 (policy/placeholder-count "insert into t values (?1, ?2)")))
  (is (= 2 (policy/placeholder-count "insert into t values (?, ?)"))
      "anonymous placeholders are counted by occurrence")
  (is (= 1 (policy/placeholder-count "select 1 where a = ?1 or b = ?1"))
      "a reused numbered placeholder is still arity 1")
  (is (= 1 (policy/placeholder-count "select 1 where name = 'why?' and id = ?1"))
      "a ? inside a string literal is not a placeholder")
  (is (zero? (policy/placeholder-count "select count(*) from orders"))))

(deftest statement-registration-is-cross-checked
  (testing "declared arity must match the SQL's placeholders"
    (let [bad {:policy/bindings
               {"DB" {:kind :d1 :caps #{:cf/d1-read}
                      :statements {"s" {:sql "select 1 where a = ?1 and b = ?2"
                                        :arity 1 :mode :read}}}}}]
      (is (= [:statement-arity-mismatch] (map :problem (policy/problems bad))))))

  (testing "mode must be :read or :write"
    (let [bad {:policy/bindings
               {"DB" {:kind :d1 :caps #{:cf/d1-read}
                      :statements {"s" {:sql "select 1" :arity 0 :mode :readonly}}}}}]
      (is (= [:invalid-statement-mode] (map :problem (policy/problems bad))))))

  (testing "statements only make sense on a D1 binding"
    (let [bad {:policy/bindings
               {"K" {:kind :kv :caps #{:cf/kv-read}
                     :statements {"s" {:sql "select 1" :arity 0 :mode :read}}}}}]
      (is (contains? (set (map :problem (policy/problems bad)))
                     :statements-on-non-d1-binding)))))

(deftest capabilities-must-match-the-binding-kind
  (let [bad {:policy/bindings {"K" {:kind :kv :caps #{:cf/r2-write}}}}]
    (is (= [:capability-kind-mismatch] (map :problem (policy/problems bad)))))
  (let [bad {:policy/bindings {"K" {:kind :kv :caps #{:cf/kv-read :storage/all}}}}]
    (is (= [:unknown-capability] (map :problem (policy/problems bad)))))
  (let [bad {:policy/bindings {"K" {:kind :bucket :caps #{}}}}]
    (is (= [:invalid-binding-kind] (map :problem (policy/problems bad))))))

(deftest the-shared-fixture-policy-is-well-formed
  (is (= [] (policy/problems fix/policy)))
  (is (policy/valid? fix/policy)))
