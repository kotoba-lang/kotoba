(ns cloudflare.workers.conformance-test
  "Positive and denial conformance fixtures -- item 4 of the
  application-profile completion gate.

  Every denial reason the admission gate can produce gets a fixture here. The
  point is not coverage for its own sake: an enumerated reason that no test
  ever produces is a reason nobody has checked is *reachable*, and a gate with
  unreachable branches is a gate with unknown shape."
  (:require [clojure.test :refer [deftest is testing]]
            [cloudflare.workers.admission :as admission]
            [cloudflare.workers.fixtures :as fix]
            [cloudflare.workers.receipt :as receipt]))

(defn- admit
  [cmd]
  (admission/admit fix/policy (admission/initial-state) fix/now cmd))

(defn- denial
  [cmd]
  (let [r (admit cmd)]
    (is (= :denied (:outcome r)) (str "expected denial for " (pr-str cmd)))
    (is (receipt/complete? (:receipt r)) "denials are receipted like grants")
    (is (receipt/denial? (:receipt r)))
    (:reason r)))

;; ---------------------------------------------------------------------------
;; Positive fixtures
;; ---------------------------------------------------------------------------

(deftest granted-commands-carry-the-capability-they-needed
  (testing "KV read"
    (let [r (admit fix/session-read)]
      (is (= :allowed (:outcome r)))
      (is (= :cf/kv-read (:cap r)))
      (is (= "kv:SESSIONS/user:42" (:receipt/resource (:receipt r))))
      (is (= :granted (:receipt/outcome (:receipt r))))))

  (testing "KV write charges its payload against the quota state"
    (let [r (admit fix/session-write)]
      (is (= :allowed (:outcome r)))
      (is (= :cf/kv-write (:cap r)))
      (is (= 2 (:write-bytes (:state r))))))

  (testing "D1 read resolves the registered statement, host-side SQL and all"
    (let [r (admit fix/order-query)]
      (is (= :allowed (:outcome r)))
      (is (= :cf/d1-read (:cap r)))
      (is (= "select id, qty from orders where id = ?1" (:sql (:statement r)))
          "the provider gets its SQL from policy, never from the guest")))

  (testing "R2 write"
    (let [r (admit fix/asset-write)]
      (is (= :allowed (:outcome r)))
      (is (= :cf/r2-write (:cap r))))))

;; ---------------------------------------------------------------------------
;; Denial fixtures -- authority
;; ---------------------------------------------------------------------------

(deftest unknown-binding-is-denied
  (is (= :unknown-binding
         (denial {:cmd :cf.kv/get :binding "NOPE" :key "user:1"}))))

(deftest binding-kind-mismatch-is-denied
  (testing "a KV command aimed at the D1 binding cannot borrow its grants"
    (is (= :binding-kind-mismatch
           (denial {:cmd :cf.kv/get :binding "APP_DB" :key "user:1"})))))

(deftest capability-not-granted-is-denied
  (testing "read-only KV binding refuses a write"
    (is (= :capability-not-granted
           (denial {:cmd :cf.kv/put :binding "READONLY" :key "pub:1" :value "v"}))))

  (testing "D1 write statement under a read-only D1 grant"
    (is (= :capability-not-granted
           (denial {:cmd :cf.d1/exec :binding "APP_DB" :statement "insert-order"
                    :params ["o-2" 3]}))
        "the required capability comes from the statement's registered mode, so
         naming a write statement cannot be disguised as a read")))

(deftest key-outside-prefix-scope-is-denied
  (is (= :key-outside-prefix-scope
         (denial {:cmd :cf.kv/get :binding "SESSIONS" :key "admin:1"})))
  (is (= :key-outside-prefix-scope
         (denial {:cmd :cf.r2/get :binding "ASSETS" :key "secrets/key.pem"})))
  (testing "prefix matching is not substring matching"
    (is (= :key-outside-prefix-scope
           (denial {:cmd :cf.kv/get :binding "SESSIONS" :key "x-user:1"})))))

(deftest wildcard-scope-is-denied-by-default
  (testing ":any key scope needs an explicit opt-out that this policy never made"
    (is (= :wildcard-forbidden
           (denial {:cmd :cf.kv/get :binding "WIDE" :key "anything"}))))
  (testing "and is reachable once the operator opts out on purpose"
    (let [permissive (assoc fix/policy :policy/forbid-wildcard false)
          r (admission/admit permissive (admission/initial-state) fix/now
                             {:cmd :cf.kv/get :binding "WIDE" :key "anything"})]
      (is (= :allowed (:outcome r))))))

(deftest unknown-statement-is-denied
  (is (= :unknown-statement
         (denial {:cmd :cf.d1/exec :binding "APP_DB" :statement "drop-orders"}))))

(deftest statement-arity-mismatch-is-denied
  (is (= :statement-arity-mismatch
         (denial {:cmd :cf.d1/exec :binding "APP_DB" :statement "order-by-id"
                  :params ["a" "b"]})))
  (is (= :statement-arity-mismatch
         (denial {:cmd :cf.d1/exec :binding "APP_DB" :statement "order-by-id"}))
      "omitting :params entirely is arity 0, not 'whatever the statement wants'"))

;; ---------------------------------------------------------------------------
;; Denial fixtures -- structural
;; ---------------------------------------------------------------------------

(deftest structural-denials-reach-the-gate
  (is (= :raw-sql-forbidden
         (denial {:cmd :cf.d1/exec :binding "APP_DB" :sql "select 1"})))
  (is (= :unknown-command
         (denial {:cmd :cf.kv/list :binding "SESSIONS"})))
  (is (= :unknown-command-key
         (denial {:cmd :cf.kv/get :binding "SESSIONS" :key "user:1" :cf {}})))
  (is (= :missing-required-field
         (denial {:cmd :cf.kv/put :binding "SESSIONS" :key "user:1"})))
  (is (= :malformed-command (denial [:cf.kv/get "SESSIONS" "user:1"])))
  (is (= :malformed-binding-name
         (denial {:cmd :cf.kv/get :binding "sessions" :key "user:1"}))))

;; ---------------------------------------------------------------------------
;; Denial fixtures -- bounds
;; ---------------------------------------------------------------------------

(deftest value-too-large-is-denied
  (is (= :value-too-large
         (denial {:cmd :cf.kv/put :binding "SESSIONS" :key "user:1"
                  :value (apply str (repeat 65 "x"))}))))

(deftest ttl-out-of-range-is-denied
  (testing "above the binding's band"
    (is (= :ttl-out-of-range
           (denial {:cmd :cf.kv/put :binding "SESSIONS" :key "user:1"
                    :value "v" :ttl 7200}))))
  (testing "below Cloudflare's own floor, caught structurally"
    (is (= :ttl-out-of-range
           (denial {:cmd :cf.kv/put :binding "SESSIONS" :key "user:1"
                    :value "v" :ttl 10})))))

(deftest quota-ceilings-are-enforced
  (testing "write bytes across a batch"
    (let [big (fn [i] {:cmd :cf.kv/put :binding "SESSIONS" :key (str "user:" i)
                       :value (apply str (repeat 60 "x"))})
          state (reduce (fn [s i]
                          (let [r (admission/admit fix/policy s fix/now (big i))]
                            (if (= :allowed (:outcome r)) (:state r) (reduced r))))
                        (admission/initial-state)
                        (range 4))]
      (is (= :denied (:outcome state)))
      (is (= :quota-write-bytes-exceeded (:reason state)))))

  (testing "D1 statements"
    (let [state (-> (admission/initial-state) (assoc :d1-statements 2))
          r (admission/admit fix/policy state fix/now fix/order-query)]
      (is (= :quota-d1-statements-exceeded (:reason r)))))

  (testing "reads"
    (let [state (-> (admission/initial-state) (assoc :reads 4))
          r (admission/admit fix/policy state fix/now fix/session-read)]
      (is (= :quota-reads-exceeded (:reason r))))))

;; ---------------------------------------------------------------------------
;; Batch semantics
;; ---------------------------------------------------------------------------

(deftest batch-envelope-is-checked-before-any-command
  (testing "a guest cannot spend the admission budget on commands it knows are denied"
    (let [r (admission/admit-batch fix/policy
                                   (vec (repeat 5 fix/session-read))
                                   {:now fix/now})]
      (is (= :denied (:outcome r)))
      (is (= :quota-commands-exceeded (:reason r)))
      (is (= 1 (count (:receipts r)))
          "one envelope receipt, not one per command"))))

(deftest batch-admission-is-fail-closed-by-default
  (let [batch [fix/session-write
               {:cmd :cf.kv/put :binding "SESSIONS" :key "admin:1" :value "v"}]
        r (admission/admit-batch fix/policy batch {:now fix/now})]
    (is (= :denied (:outcome r)))
    (is (= :key-outside-prefix-scope (:reason r)))
    (is (= 1 (:index r)))
    (is (nil? (:admitted r))
        "there is deliberately no partial plan for a caller to run by mistake")
    (is (= 2 (count (:receipts r)))
        "the granted first command is still receipted -- it was admitted, then the batch died")))

(deftest batch-skip-mode-keeps-the-survivors
  (let [batch [fix/session-write
               {:cmd :cf.kv/put :binding "SESSIONS" :key "admin:1" :value "v"}
               fix/session-read]
        r (admission/admit-batch fix/policy batch {:now fix/now :on-deny :skip})]
    (is (= :allowed (:outcome r)))
    (is (= 2 (count (:admitted r))))
    (is (= 3 (count (:receipts r))))
    (is (= 1 (count (filter receipt/denial? (:receipts r)))))))

(deftest every-attempt-is-receipted
  (let [batch [fix/session-read
               {:cmd :cf.kv/get :binding "NOPE" :key "user:1"}
               fix/order-query]
        r (admission/admit-batch fix/policy batch {:now fix/now :on-deny :skip})]
    (is (= 3 (count (:receipts r))))
    (is (every? receipt/complete? (:receipts r)))
    (is (every? (fn [x] (= fix/now (:receipt/at x))) (:receipts r))
        "receipts carry the caller's timestamp; the pure core never reads a clock")))

(deftest every-declared-denial-reason-is-reachable
  (testing "the enumerated reasons in the descriptors are not aspirational"
    (let [reached
          (set
           (keep (fn [cmd] (:reason (admission/admit fix/policy
                                                     (admission/initial-state)
                                                     fix/now cmd)))
                 [{:cmd :cf.d1/exec :binding "APP_DB" :sql "select 1"}
                  {:cmd :cf.kv/list :binding "SESSIONS"}
                  {:cmd :cf.kv/get :binding "SESSIONS" :key "user:1" :extra 1}
                  {:cmd :cf.kv/put :binding "SESSIONS" :key "user:1"}
                  {:cmd :cf.kv/get :binding "sessions" :key "user:1"}
                  {:cmd :cf.kv/get :binding "SESSIONS" :key "user:\u0007"}
                  {:cmd :cf.kv/get :binding "SESSIONS" :key (apply str (repeat 600 "x"))}
                  {:cmd :cf.kv/put :binding "SESSIONS" :key "user:1" :value 1}
                  {:cmd :cf.kv/put :binding "SESSIONS" :key "user:1" :value "v" :ttl "x"}
                  {:cmd :cf.d1/exec :binding "APP_DB" :statement "Bad Id"}
                  {:cmd :cf.d1/exec :binding "APP_DB" :statement "order-by-id" :params '("a")}
                  {:cmd :cf.d1/exec :binding "APP_DB" :statement "order-by-id"
                   :params (vec (repeat 40 "x"))}
                  {:cmd :cf.r2/put :binding "ASSETS" :key "img/a" :body "b"
                   :content-type "x\u0007y"}
                  {:cmd :cf.kv/get :binding "NOPE" :key "user:1"}
                  {:cmd :cf.kv/get :binding "APP_DB" :key "user:1"}
                  {:cmd :cf.kv/put :binding "READONLY" :key "pub:1" :value "v"}
                  {:cmd :cf.kv/get :binding "SESSIONS" :key "admin:1"}
                  {:cmd :cf.d1/exec :binding "APP_DB" :statement "nope"}
                  {:cmd :cf.d1/exec :binding "APP_DB" :statement "order-by-id" :params []}
                  {:cmd :cf.kv/get :binding "WIDE" :key "k"}
                  {:cmd :cf.kv/put :binding "SESSIONS" :key "user:1"
                   :value (apply str (repeat 65 "x"))}
                  {:cmd :cf.kv/put :binding "SESSIONS" :key "user:1" :value "v" :ttl 99999}
                  "not-a-map"]))
          expected #{:raw-sql-forbidden :unknown-command :unknown-command-key
                     :missing-required-field :malformed-binding-name :malformed-key
                     :key-too-long :malformed-value :malformed-ttl
                     :malformed-statement-id :malformed-params :too-many-params
                     :malformed-content-type :unknown-binding :binding-kind-mismatch
                     :capability-not-granted :key-outside-prefix-scope
                     :unknown-statement :statement-arity-mismatch :wildcard-forbidden
                     :value-too-large :ttl-out-of-range :malformed-command}]
      (is (= expected reached)))))
