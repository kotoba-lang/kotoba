(ns nostr.event-test
  (:require [clojure.test :refer [deftest is testing]]
            [nostr.event :as event]
            [nostr.fixtures :as fx]))

(deftest canonical-serialize-matches-nip01-shape
  (let [ev {"pubkey" "abc" "created_at" 100 "kind" 1 "tags" [["e" "x"]] "content" "hi"}]
    (is (= "[0,\"abc\",100,1,[[\"e\",\"x\"]],\"hi\"]" (event/canonical-serialize ev)))))

(deftest canonical-serialize-escapes-only-nip01-named-chars
  (let [ev {"pubkey" "p" "created_at" 1 "kind" 1 "tags" []
            "content" "line1\nline2\ttab\"quote\\slash"}]
    (is (= "[0,\"p\",1,1,[],\"line1\\nline2\\ttab\\\"quote\\\\slash\"]"
           (event/canonical-serialize ev)))))

(deftest genuinely-signed-event-round-trips
  (let [ev (fx/text-note fx/alice-sk "hello nostr")]
    (testing "structurally valid"
      (is (event/structurally-valid? ev)))
    (testing "id matches its own canonical serialization"
      (is (event/id-matches? ev)))
    (testing "signature verifies (real BIP-340 verification, not a stand-in)"
      (is (event/signature-valid? ev)))
    (testing "validate accepts it wholesale"
      (is (= {:valid? true :reason nil} (event/validate ev))))))

(deftest tampering-is-detected
  (let [ev (fx/text-note fx/alice-sk "original content")]
    (testing "content tampered after signing -> id no longer matches"
      (let [tampered (assoc ev "content" "tampered content")]
        (is (not (event/id-matches? tampered)))
        (is (= :id-mismatch (:reason (event/validate tampered))))))
    (testing "id forged to match tampered content, but signature now invalid"
      (let [tampered (assoc ev "content" "tampered content")
            forged (assoc tampered "id" (event/compute-id tampered))]
        (is (event/id-matches? forged))
        (is (not (event/signature-valid? forged)))
        (is (= :invalid-signature (:reason (event/validate forged))))))
    (testing "signed by a different key than claimed pubkey -> rejected"
      (let [other (fx/text-note fx/bob-sk "original content")
            frankenstein (assoc ev "sig" (get other "sig") "id" (get other "id"))]
        ;; using bob's id+sig under alice's claimed pubkey field
        (is (not (event/signature-valid?
                  (assoc frankenstein "pubkey" (get ev "pubkey")))))))))

(deftest malformed-events-rejected
  (is (= :malformed (:reason (event/validate {}))))
  (is (= :malformed (:reason (event/validate {"id" "not-hex" "pubkey" "x"
                                              "created_at" 1 "kind" 1
                                              "tags" [] "content" "" "sig" "y"})))))

(deftest filter-matching
  (let [e1 (fx/text-note fx/alice-sk "note 1" {:created_at 100})
        e2 (fx/text-note fx/alice-sk "note 2" {:created_at 200})
        e3 (fx/text-note fx/bob-sk "note 3" {:created_at 300})
        events [e1 e2 e3]]
    (testing "empty filter matches everything"
      (is (= 3 (count (event/run-filter events {})))))
    (testing "authors filter"
      (is (= [(get e2 "id") (get e1 "id")]
             (map #(get % "id") (event/run-filter events {"authors" [(fx/pubkey fx/alice-sk)]})))))
    (testing "ids filter"
      (is (= [(get e3 "id")]
             (map #(get % "id") (event/run-filter events {"ids" [(get e3 "id")]})))))
    (testing "kinds filter"
      (is (= 3 (count (event/run-filter events {"kinds" [1]})))))
    (testing "since/until"
      (is (= [(get e2 "id")]
             (map #(get % "id") (event/run-filter events {"since" 150 "until" 250})))))
    (testing "limit caps result count, newest-first"
      (is (= [(get e3 "id") (get e2 "id")]
             (map #(get % "id") (event/run-filter events {"limit" 2})))))
    (testing "#e tag filter"
      (let [tagged (fx/sign-event fx/alice-sk
                                  {"kind" 1 "created_at" 400
                                   "tags" [["e" (get e1 "id")]] "content" "reply"})
            events2 (conj events tagged)]
        (is (= [(get tagged "id")]
               (map #(get % "id") (event/run-filter events2 {"#e" [(get e1 "id")]}))))))
    (testing "run-filters unions multiple filters, de-duped, newest-first"
      (is (= [(get e3 "id") (get e1 "id")]
             (map #(get % "id")
                  (event/run-filters events [{"ids" [(get e1 "id")]}
                                              {"authors" [(fx/pubkey fx/bob-sk)]}])))))))
