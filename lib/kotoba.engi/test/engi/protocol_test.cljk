(ns engi.protocol-test
  "Protocol-level tests: full propose -> validate -> counter-commit ->
  finalize handshake against an in-memory fake kotobase.net (no network —
  `engi.fake-kotobase`), exercising the REAL `engi.store`/`engi.crypto`/
  `engi.protocol` code, only the HTTP transport is fake."
  (:require [cljs.test :refer-macros [deftest is testing async]]
            [kotobase.client :as client]
            [engi.core :as core]
            [engi.crypto :as crypto]
            [engi.store :as store]
            [engi.protocol :as protocol]
            [engi.metrics :as metrics]
            [engi.fake-kotobase :as fake]))

;; ── fixtures / helpers ───────────────────────────────────────────────────

(defn- owner-client [fetch-fn identity]
  (client/make-client {:endpoint store/default-endpoint
                       :operator-did store/default-operator-did
                       :secret-key (:secret-key identity)
                       :fetch-fn fetch-fn}))

(defn- reader-client [fetch-fn did]
  (client/make-client {:endpoint store/default-endpoint
                       :operator-did store/default-operator-did
                       :did did
                       :public-reads? true
                       :fetch-fn fetch-fn}))

(defn- write-genesis! [client credit-limit]
  (store/write-genesis! client (core/genesis {:credit-limit credit-limit :created-at 0})))

;; A full, successful propose->validate->counter-commit->finalize round trip.
;; → Promise<{:validation :counter-commit :finalize}>.
(defn- run-full-transfer!
  [{:keys [spender-identity spender-owner spender-reader
           receiver-identity receiver-owner amount opts]}]
  (-> (protocol/propose-transfer! spender-owner (:secret-key spender-identity)
                                   (:did receiver-identity) amount (or opts {}))
      (.then (fn [proposal]
               (-> (protocol/validate-proposal! spender-reader proposal)
                   (.then (fn [validation] {:proposal proposal :validation validation})))))
      (.then (fn [{:keys [proposal validation]}]
               (if-not (:valid? validation)
                 {:proposal proposal :validation validation}
                 (-> (protocol/counter-commit! receiver-owner (:secret-key receiver-identity) proposal)
                     (.then (fn [cc] {:proposal proposal :validation validation :counter-commit cc}))))))
      (.then (fn [{:keys [proposal counter-commit] :as acc}]
               (if-not counter-commit
                 acc
                 (-> (protocol/finalize! spender-owner (:secret-key spender-identity)
                                         proposal (:counter-sig counter-commit))
                     (.then (fn [fin] (assoc acc :finalize fin)))))))))

(defn- fresh-agent [fetch-fn credit-limit]
  (let [identity (crypto/generate-identity)
        owner (owner-client fetch-fn identity)
        reader (reader-client fetch-fn (:did identity))]
    (-> (write-genesis! owner credit-limit)
        (.then (fn [_] {:identity identity :owner owner :reader reader})))))

;; ── (a) clean single transfer, both sides end up correct & net-zero ───────

(deftest clean-transfer-both-sides-correct-and-net-zero
  (async done
    (let [fetch-fn (:fetch-fn (fake/make-fake-kotobase))]
      (-> (js/Promise.all #js [(fresh-agent fetch-fn -1000) (fresh-agent fetch-fn -1000)])
          (.then (fn [^js agents]
                   (let [[alice bob] (array-seq agents)]
                     (-> (run-full-transfer!
                          {:fetch-fn fetch-fn
                           :spender-identity (:identity alice) :spender-owner (:owner alice) :spender-reader (:reader alice)
                           :receiver-identity (:identity bob) :receiver-owner (:owner bob)
                           :amount 42 :opts {:memo "test transfer" :now-ms 1000}})
                         (.then (fn [result]
                                  (is (true? (get-in result [:validation :valid?]))
                                      (str "validation: " (pr-str (:validation result))))
                                  (is (true? (get-in result [:finalize :finalized?])))
                                  (js/Promise.all #js [(protocol/audit-agent! (:reader alice))
                                                       (protocol/audit-agent! (:reader bob))])))
                         (.then (fn [^js audits]
                                  (let [[alice-audit bob-audit] (array-seq audits)]
                                    (testing "alice spent 42 -> balance -42"
                                      (is (= -42 (:balance alice-audit)))
                                      (is (empty? (:violations alice-audit)))
                                      (is (empty? (:forks alice-audit))))
                                    (testing "bob received 42 -> balance +42"
                                      (is (= 42 (:balance bob-audit)))
                                      (is (empty? (:violations bob-audit)))
                                      (is (empty? (:forks bob-audit))))
                                    (testing "net-zero across the pair"
                                      (is (= 0 (+ (:balance alice-audit) (:balance bob-audit)))))
                                    (done))))))))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

;; ── (b) exceeding the spender's credit limit -> validate-proposal rejects ──

(deftest transfer-exceeding-credit-limit-rejected
  (async done
    (let [fetch-fn (:fetch-fn (fake/make-fake-kotobase))]
      (-> (js/Promise.all #js [(fresh-agent fetch-fn -100) (fresh-agent fetch-fn -1000)])
          (.then (fn [^js agents]
                   (let [[alice bob] (array-seq agents)]
                     (run-full-transfer!
                      {:fetch-fn fetch-fn
                       :spender-identity (:identity alice) :spender-owner (:owner alice) :spender-reader (:reader alice)
                       :receiver-identity (:identity bob) :receiver-owner (:owner bob)
                       :amount 500 :opts {:now-ms 1}}))))
          (.then (fn [result]
                   (is (false? (get-in result [:validation :valid?])))
                   (is (= :credit-limit-exceeded (get-in result [:validation :reason])))
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

;; ── (c) stale/incorrect `prev` (simulated race) -> validation rejects ─────

;; alice proposes transfer #1 to bob (kept stale — never finalized), THEN
;; (simulating a race) finalizes an UNRELATED transfer to carol, advancing
;; her real chain head — the stale proposal's `spender-prev` no longer
;; matches. → Promise<validation-of-the-stale-proposal>.
(defn- stale-prev-scenario! [fetch-fn]
  (-> (js/Promise.all #js [(fresh-agent fetch-fn -1000) (fresh-agent fetch-fn -1000) (fresh-agent fetch-fn -1000)])
      (.then (fn [^js agents]
               (let [[alice bob carol] (array-seq agents)]
                 {:alice alice :bob bob :carol carol})))
      (.then (fn [{:keys [alice bob carol]}]
               (-> (protocol/propose-transfer! (:owner alice) (:secret-key (:identity alice))
                                                (:did (:identity bob)) 10 {:now-ms 1})
                   (.then (fn [stale-proposal] {:alice alice :carol carol :stale-proposal stale-proposal})))))
      (.then (fn [{:keys [alice carol stale-proposal]}]
               (-> (run-full-transfer!
                    {:spender-identity (:identity alice) :spender-owner (:owner alice)
                     :spender-reader (:reader alice)
                     :receiver-identity (:identity carol) :receiver-owner (:owner carol)
                     :amount 5 :opts {:now-ms 2}})
                   (.then (fn [_] {:alice alice :stale-proposal stale-proposal})))))
      (.then (fn [{:keys [alice stale-proposal]}]
               (protocol/validate-proposal! (:reader alice) stale-proposal)))))

(deftest stale-prev-race-rejected
  (async done
    (let [fetch-fn (:fetch-fn (fake/make-fake-kotobase))]
      (-> (stale-prev-scenario! fetch-fn)
          (.then (fn [validation]
                   (is (false? (:valid? validation)))
                   (is (= :stale-prev (:reason validation)))
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

;; ── (d) audit against a deliberately-forked graph -> detect-fork finds it ──

(deftest audit-finds-deliberately-forked-graph
  (async done
    (let [fetch-fn (:fetch-fn (fake/make-fake-kotobase))]
      (-> (fresh-agent fetch-fn -1000)
          (.then (fn [alice]
                   (let [bob-did "did:key:zPlaceholderBob"
                         e-a (core/next-entry {:seq -1} "genesis"
                                               {:id "engi/tx/fork-a" :kind "debit" :counterparty bob-did
                                                :amount 10 :transfer-id "t-a" :ts 1 :self-sig "sigA"})
                         e-b (core/next-entry {:seq -1} "genesis"
                                               {:id "engi/tx/fork-b" :kind "debit" :counterparty bob-did
                                                :amount 999 :transfer-id "t-b" :ts 2 :self-sig "sigB"})]
                     (-> (js/Promise.all #js [(store/write-entry! (:owner alice) e-a)
                                              (store/write-entry! (:owner alice) e-b)])
                         (.then (fn [_] (protocol/audit-agent! (:reader alice))))))))
          (.then (fn [audit]
                   (is (seq (:forks audit)) "the fork must be detected")
                   (is (some #(= :seq-fork (:kind %)) (:forks audit)))
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

;; ── bilateral confirmation: an unfinalized credit must not be spendable ───

(deftest unconfirmed-credit-not-spendable-until-debit-lands
  (async done
    (let [fetch-fn (:fetch-fn (fake/make-fake-kotobase))]
      (-> (js/Promise.all #js [(fresh-agent fetch-fn -1000) (fresh-agent fetch-fn -1000)])
          (.then (fn [^js agents]
                   (let [[alice bob] (array-seq agents)]
                     (-> (protocol/propose-transfer! (:owner alice) (:secret-key (:identity alice))
                                                      (:did (:identity bob)) 20 {:now-ms 1})
                         (.then (fn [proposal] (protocol/counter-commit! (:owner bob) (:secret-key (:identity bob)) proposal)))
                         ;; deliberately DO NOT finalize — bob's credit stays unconfirmed.
                         (.then (fn [_]
                                  (protocol/spendable-balance!
                                   (:owner bob)
                                   (fn [did] (if (= did (:did (:identity alice))) (:reader alice) (:reader bob))))))))))
          (.then (fn [result]
                   (is (= 20 (:balance result)) "raw ledger sees the credit")
                   (is (= 0 (:spendable-balance result)) "but it's not spendable — alice never finalized")
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

;; ── funnel emission (engi.metrics, adr-ledger seq 66) ────────────────────
;;
;; These assert the seam, not the counters: engi.metrics' own arithmetic is
;; covered by the pure engi.metrics-test. What can only be tested here is that
;; the protocol emits the RIGHT event at the RIGHT moment against the real
;; store/crypto path, and that a broken or absent emitter changes nothing about
;; the transfer itself.

(defn- recording-emitter []
  (let [seen (atom [])]
    {:seen seen :on-event (fn [ev] (swap! seen conj ev))}))

(deftest full-transfer-emits-the-whole-funnel-in-order
  (async done
    (let [fetch-fn (:fetch-fn (fake/make-fake-kotobase))
          {:keys [seen on-event]} (recording-emitter)]
      (-> (js/Promise.all #js [(fresh-agent fetch-fn -1000) (fresh-agent fetch-fn -1000)])
          (.then (fn [^js agents]
                   (let [[alice bob] (array-seq agents)]
                     (-> (protocol/propose-transfer! (:owner alice) (:secret-key (:identity alice))
                                                      (:did (:identity bob)) 15
                                                      {:now-ms 1 :on-event on-event})
                         (.then (fn [proposal]
                                  (-> (protocol/validate-proposal! (:reader alice) proposal {:on-event on-event})
                                      (.then (fn [_] proposal)))))
                         (.then (fn [proposal]
                                  (-> (protocol/counter-commit! (:owner bob) (:secret-key (:identity bob))
                                                                 proposal {:on-event on-event})
                                      (.then (fn [cc] [proposal cc])))))
                         (.then (fn [[proposal cc]]
                                  (protocol/finalize! (:owner alice) (:secret-key (:identity alice))
                                                      proposal (:counter-sig cc) {:on-event on-event})))))))
          (.then (fn [_]
                   (is (= [:proposal :validation :counter-commit :finalization]
                          (mapv :event @seen))
                       "all four stages, in protocol order")
                   (is (= [:proposals :validations :counter-commits :finalizations]
                          (mapv :stage @seen))
                       "each event carries the metrics stage it bumps")
                   (is (every? :transfer-id @seen) "every event correlates by transfer-id")
                   (is (= 1 (count (distinct (map :transfer-id @seen))))
                       "one transfer produces one transfer-id across all four stages")
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(deftest rejected-validation-emits-rejection-with-its-reason
  (async done
    (let [fetch-fn (:fetch-fn (fake/make-fake-kotobase))
          {:keys [seen on-event]} (recording-emitter)]
      ;; alice's credit limit is -100, so a 500 transfer must breach it
      (-> (js/Promise.all #js [(fresh-agent fetch-fn -100) (fresh-agent fetch-fn -1000)])
          (.then (fn [^js agents]
                   (let [[alice bob] (array-seq agents)]
                     (-> (protocol/propose-transfer! (:owner alice) (:secret-key (:identity alice))
                                                      (:did (:identity bob)) 500
                                                      {:now-ms 1 :on-event on-event})
                         (.then (fn [proposal]
                                  (protocol/validate-proposal! (:reader alice) proposal
                                                               {:on-event on-event})))))))
          (.then (fn [validation]
                   (is (false? (:valid? validation)))
                   (is (= [:proposal :rejection] (mapv :event @seen)))
                   (is (= :credit-limit-exceeded (:reason (last @seen)))
                       "the reason rides on the event -- an aggregate rejection count
                        cannot tell you WHICH invariant is costing transfers")
                   (is (nil? (:reason (first @seen))) "a proposal carries no reason")
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(deftest a-throwing-emitter-cannot-break-a-transfer
  (async done
    (let [fetch-fn (:fetch-fn (fake/make-fake-kotobase))
          exploding (fn [_] (throw (js/Error. "telemetry backend is down")))]
      (-> (js/Promise.all #js [(fresh-agent fetch-fn -1000) (fresh-agent fetch-fn -1000)])
          (.then (fn [^js agents]
                   (let [[alice bob] (array-seq agents)]
                     (run-full-transfer!
                      {:spender-identity (:identity alice) :spender-owner (:owner alice)
                       :spender-reader (:reader alice)
                       :receiver-identity (:identity bob) :receiver-owner (:owner bob)
                       :amount 15 :opts {:now-ms 1 :on-event exploding}}))))
          (.then (fn [{:keys [validation]}]
                   ;; run-full-transfer! only threads opts into propose-transfer!, which
                   ;; is enough: that is the first emission point, so if a throwing
                   ;; emitter could break anything it would break here.
                   (is (:valid? validation)
                       "an emitter that throws must not fail the transfer -- a broken
                        counter is a measurement problem, a transfer that fails because
                        of one is a correctness problem")
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(deftest no-emitter-means-no-behaviour-change
  (async done
    (let [fetch-fn (:fetch-fn (fake/make-fake-kotobase))]
      (-> (js/Promise.all #js [(fresh-agent fetch-fn -1000) (fresh-agent fetch-fn -1000)])
          (.then (fn [^js agents]
                   (let [[alice bob] (array-seq agents)]
                     ;; the 3-arity counter-commit! / 4-arity finalize! the pre-funnel
                     ;; callers used must still exist and still work
                     (-> (protocol/propose-transfer! (:owner alice) (:secret-key (:identity alice))
                                                      (:did (:identity bob)) 15 {:now-ms 1})
                         (.then (fn [proposal]
                                  (-> (protocol/counter-commit! (:owner bob) (:secret-key (:identity bob)) proposal)
                                      (.then (fn [cc] [proposal cc])))))
                         (.then (fn [[proposal cc]]
                                  (protocol/finalize! (:owner alice) (:secret-key (:identity alice))
                                                      proposal (:counter-sig cc))))))))
          (.then (fn [fin]
                   (is (:finalized? fin) "old arities still finalize")
                   (done)))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))

(deftest persisted-funnel-matches-what-the-protocol-emitted
  (async done
    (let [fetch-fn (:fetch-fn (fake/make-fake-kotobase))
          {:keys [seen on-event]} (recording-emitter)]
      (-> (js/Promise.all #js [(fresh-agent fetch-fn -1000) (fresh-agent fetch-fn -1000)])
          (.then (fn [^js agents]
                   (let [[alice bob] (array-seq agents)]
                     (-> (protocol/propose-transfer! (:owner alice) (:secret-key (:identity alice))
                                                      (:did (:identity bob)) 15
                                                      {:now-ms 1 :on-event on-event})
                         (.then (fn [proposal]
                                  (-> (protocol/counter-commit! (:owner bob) (:secret-key (:identity bob))
                                                                 proposal {:on-event on-event})
                                      (.then (fn [cc] [proposal cc])))))
                         (.then (fn [[proposal cc]]
                                  (-> (protocol/finalize! (:owner alice) (:secret-key (:identity alice))
                                                          proposal (:counter-sig cc) {:on-event on-event})
                                      (.then (fn [_]
                                               (js/Promise.all
                                                #js [(store/fetch-entities! (:owner alice))
                                                     (store/fetch-entities! (:owner bob))]))))))))))
          (.then (fn [^js graphs]
                   (let [[alice-entities bob-entities] (array-seq graphs)
                         alice-f (metrics/funnel-from-entities alice-entities)
                         bob-f (metrics/funnel-from-entities bob-entities)
                         emitted (frequencies (map :stage @seen))]
                     (is (= 1 (:finalizations alice-f)) "spender's ledger holds the debit")
                     (is (= 0 (:counter-commits alice-f)))
                     (is (= 1 (:counter-commits bob-f)) "receiver's ledger holds the credit")
                     (is (= 0 (:finalizations bob-f)))
                     (is (= (:finalizations alice-f) (get emitted :finalizations))
                         "the durable half must agree with what was emitted -- if these
                          ever disagree, the emitter is lying or a write silently failed")
                     (is (= (:counter-commits bob-f) (get emitted :counter-commits)))
                     (done))))
          (.catch (fn [e] (is false (str "unexpected rejection: " e)) (done)))))))
