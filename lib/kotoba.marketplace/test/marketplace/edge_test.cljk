(ns marketplace.edge-test
  "The host half's actor pass. `.cljs` on purpose: this namespace is the
  host, so the JVM suite never sees it and only the ClojureScript run
  (`npm run test:cljs`) exercises it.

  Nothing here reaches the network. `run` and `outcome` are pure functions
  over an injected `ops` map; the Promise work lives in `with-store`,
  which is not under test."
  (:require [cljs.test :refer [deftest is testing]]
            [marketplace.edge :as edge]))

(defn- recording-ops
  "An actor whose five functions record what they were asked to do.
  `verdict` and `gate` are the two dials each test turns."
  [log {:keys [verdict gate]}]
  {:advise      (fn [_st req] {:op (:op req) :cites ["c-1"] :summary "s"
                               :value {:v 1} :effect :propose :confidence 0.9})
   :check       (fn [_req _ctx _proposal _st] verdict)
   :disposition (fn [v] (cond (:hard? v) :hold (:escalate? v) :escalate :else :commit))
   :gate        (fn [_phase _req base] (or gate {:disposition base :reason nil}))
   :commit!     (fn [_st proposal _req]
                  (swap! log conj [:commit! (:op proposal)])
                  {:record :written})
   :ledger!     (fn [_st fact] (swap! log conj [:ledger! fact]) fact)
   :hold-fact   (fn [req _ctx v] {:t :governor-hold :op (:op req)
                                  :violations (:violations v)
                                  :basis (mapv :rule (:violations v))})})

(def ^:private ctx {:actor-id "test-actor" :phase 3 :now "2026-06-01T00:00:00Z"})
(def ^:private request {:op :propose-release :ref "esc-1"})

(defn- facts [log] (mapv second (filter #(= :ledger! (first %)) @log)))

(deftest a-clean-pass-commits-and-writes-one-committed-fact
  (let [log (atom [])
        result (edge/run (recording-ops log {:verdict {:confidence 0.9}}) :store ctx request)
        [fact] (facts log)]
    (is (= :commit (:disposition result)))
    (is (= [] (:violations result)))
    (is (= "esc-1" (:ref result)))
    (is (some #{[:commit! :propose-release]} @log) "the store was actually written")
    (testing "and the fact carries what an auditor needs"
      (is (= :committed (:t fact)))
      (is (= :propose-release (:op fact)))
      (is (= "esc-1" (:ref fact)))
      (is (= "test-actor" (:actor fact)))
      (is (= ["c-1"] (:basis fact))))))

(deftest an-escalation-is-written-or-the-gate-is-a-black-hole
  (testing "the fact `escalations` pairs on must exist, with :t and :ref"
    (let [log (atom [])
          result (edge/run (recording-ops log {:verdict {:escalate? true :high-stakes? true
                                                         :confidence 0.95}})
                           :store ctx request)
          [fact] (facts log)]
      (is (= :escalate (:disposition result)))
      (is (= :approval-requested (:t fact)))
      (is (= "esc-1" (:ref fact)) "escalations pairs asked-vs-answered by this")
      (is (= :always-escalate (:reason fact)))
      (is (= 3 (:phase fact)))
      (is (not (some #{[:commit! :propose-release]} @log))
          "nothing was committed"))))

(deftest a-low-confidence-escalation-says-so-instead-of-always-escalate
  (let [log (atom [])
        _ (edge/run (recording-ops log {:verdict {:escalate? true :confidence 0.2}})
                    :store ctx request)
        [fact] (facts log)]
    (is (= :low-confidence (:reason fact)))))

(deftest a-hold-writes-the-governors-own-fact-with-its-violations
  (let [log (atom [])
        v {:hard? true :confidence 0.9
           :violations [{:rule :escrow-not-releasable :detail "配達未確認"}]}
        result (edge/run (recording-ops log {:verdict v}) :store ctx request)
        [fact] (facts log)]
    (is (= :hold (:disposition result)))
    (is (= [{:rule :escrow-not-releasable :detail "配達未確認"}] (:violations result)))
    (is (= :governor-hold (:t fact)))
    (is (= :hold (:disposition fact)))
    (is (= "esc-1" (:ref fact)) "a hold is findable by ref too")
    (is (not (some #{[:commit! :propose-release]} @log)))))

(deftest the-phase-gate-can-stop-a-governor-clean-pass
  (testing "phase-disabled becomes a hold, and the fact says which"
    (let [log (atom [])
          result (edge/run (recording-ops log {:verdict {:confidence 0.9}
                                               :gate {:disposition :hold
                                                      :reason :phase-disabled}})
                           :store ctx request)
          [fact] (facts log)]
      (is (= :hold (:disposition result)))
      (is (= :phase-disabled (:phase-reason fact)))
      (is (= 3 (:phase fact)))
      (is (not (some #{[:commit! :propose-release]} @log)))))
  (testing "phase-approval becomes an escalation carrying that reason"
    (let [log (atom [])
          result (edge/run (recording-ops log {:verdict {:confidence 0.9}
                                               :gate {:disposition :escalate
                                                      :reason :phase-approval}})
                           :store ctx request)
          [fact] (facts log)]
      (is (= :escalate (:disposition result)))
      (is (= :phase-approval (:reason fact)))
      (is (= :approval-requested (:t fact))))))

(deftest the-ref-is-found-the-way-fact-ref-finds-it
  (testing "an actor that names its subject `:applicant-id` still gets a ref —
            the onboarding worker does exactly this"
    (let [log (atom [])
          result (edge/run (recording-ops log {:verdict {:confidence 0.9}})
                           :store ctx {:op :propose-credential :applicant-id "app-1"})]
      (is (= "app-1" (:ref result)))
      (is (= "app-1" (:ref (first (facts log))))))))

(deftest outcome-is-json-shaped-not-clojure-shaped
  (let [o (edge/outcome "esc-1" {:disposition :hold :op :propose-release
                                 :confidence 0.9
                                 :violations [{:rule :escrow-disputed :detail "係争中"}]})]
    (is (= "esc-1" (:ref o)))
    (is (= "hold" (:disposition o)) "a JSON client should not parse keywords")
    (is (= "propose-release" (:op o)))
    (is (= [{:rule "escrow-disputed" :detail "係争中"}] (:violations o))
        "the detail survives — a rule name alone sends the reader to the source")
    (testing "and a clean pass carries an empty vector, not nil"
      (is (= [] (:violations (edge/outcome "x" {:disposition :commit :violations []})))))))

(deftest outcome-matches-what-the-hand-written-routes-return
  (testing "a client must not need to know which routes ran an actor"
    (let [by-hand {:ref "b-1" :disposition "commit" :violations []}
          by-run (edge/outcome "b-1" {:disposition :commit :violations []})]
      (is (= (select-keys by-hand [:ref :disposition :violations])
             (select-keys by-run [:ref :disposition :violations]))))))
