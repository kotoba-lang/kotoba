(ns kotoba.cap-table-test
  "Direct unit coverage of kotoba.cap-table -- the per-run capability
  registry itself, isolated from the wider launcher/host-providers stack
  that test/kotoba/cap_passing_test.clj already exercises end-to-end.
  That file proves the S4b acquire/use/deny/expire behavior through the
  full dispatch path; this file isolates two things it doesn't cover in
  isolation: handle sequencing across multiple acquisitions on the SAME
  table, and resolve-use's three denial branches called directly."
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.cap-table :as cap-table]
            [kotoba.host-providers :as host-providers]))

(def demo-policy
  {:kotoba.policy/capabilities #{:ledger/append}
   :kotoba.policy/capability-resources {:ledger/append #{"ledger:main"}}})

(defn- acquire-ledger!
  "Acquire :host/ledger-append over RESOURCE against demo-policy's grants
  (which only cover \"ledger:main\") -- requesting any other resource
  denies via :empty-intersection."
  [table resource now]
  (cap-table/acquire! table
                      {:kind :host/ledger-append
                       :resource resource
                       :grants (host-providers/policy-grants demo-policy)
                       :policy (host-providers/local-policy demo-policy)
                       :now now}))

(deftest make-table-starts-empty
  (let [table (cap-table/make-table)]
    (is (= {:next-handle 1 :caps {}} @table))
    (is (nil? (cap-table/resolve-cap table 1)))))

(deftest sequential-acquisitions-on-the-same-table-get-distinct-increasing-handles
  (testing "handles start at 1 and increment per acquisition, never reused"
    (let [table (cap-table/make-table)
          h1 (:kotoba.host/result (acquire-ledger! table "ledger:main" "2026-07-08"))
          h2 (:kotoba.host/result (acquire-ledger! table "ledger:main" "2026-07-08"))
          h3 (:kotoba.host/result (acquire-ledger! table "ledger:main" "2026-07-08"))]
      (is (= [1 2 3] [h1 h2 h3]))
      (testing "each handle resolves to its OWN concrete capability, even though
                all three requests were for the same kind/resource"
        (is (= :host/ledger-append (:cap/kind (cap-table/resolve-cap table h1))))
        (is (= :host/ledger-append (:cap/kind (cap-table/resolve-cap table h2))))
        (is (= :host/ledger-append (:cap/kind (cap-table/resolve-cap table h3))))
        (is (every? some? (map #(cap-table/resolve-cap table %) [h1 h2 h3]))))))
  (testing "a denied acquisition does not consume a handle slot -- the next
            successful acquisition still gets the next sequential handle"
    (let [table (cap-table/make-table)
          h1 (:kotoba.host/result (acquire-ledger! table "ledger:main" "2026-07-08"))
          denied (acquire-ledger! table "ledger:forbidden" "2026-07-08")
          h2 (:kotoba.host/result (acquire-ledger! table "ledger:main" "2026-07-08"))]
      (is (= 1 h1))
      (is (false? (:kotoba.host/ok? denied)))
      (is (= :empty-intersection (:kotoba.host/denied denied)))
      (is (= 2 h2)))))

(deftest resolve-use-success-returns-the-stored-concrete-capability
  (let [table (cap-table/make-table)
        handle (:kotoba.host/result (acquire-ledger! table "ledger:main" "2026-07-08"))
        result (cap-table/resolve-use table handle :host/ledger-append "2026-07-08")]
    (is (true? (:ok? result)))
    (is (= :host/ledger-append (get-in result [:cap :cap/kind])))
    (is (= "ledger:main" (get-in result [:cap :cap/resource])))))

(deftest resolve-use-denies-an-unissued-handle
  (let [table (cap-table/make-table)]
    (is (= {:denied :unknown-cap-handle}
           (cap-table/resolve-use table 999 :host/ledger-append "2026-07-08")))))

(deftest resolve-use-denies-a-kind-mismatch
  (let [table (cap-table/make-table)
        handle (:kotoba.host/result (acquire-ledger! table "ledger:main" "2026-07-08"))]
    (is (= {:denied :cap-kind-mismatch}
           (cap-table/resolve-use table handle :host/notify "2026-07-08")))))

(deftest resolve-use-denies-an-expired-capability
  (let [policy (assoc demo-policy
                      :kotoba.policy/capability-expires {:ledger/append "2026-12-31"})
        table (cap-table/make-table)
        handle (:kotoba.host/result
                (cap-table/acquire! table
                                    {:kind :host/ledger-append
                                     :resource "ledger:main"
                                     :grants (host-providers/policy-grants policy)
                                     :policy (host-providers/local-policy policy)
                                     :now "2026-07-08"}))]
    (testing "valid on and before the expiry date"
      (is (true? (:ok? (cap-table/resolve-use table handle :host/ledger-append "2026-12-31")))))
    (testing "denied once NOW has advanced past the stored expiry"
      (is (= {:denied :expired}
             (cap-table/resolve-use table handle :host/ledger-append "2027-01-01"))))))
