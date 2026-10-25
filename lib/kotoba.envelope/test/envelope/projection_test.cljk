(ns envelope.projection-test
  "The negative cases are the point. A projection guard that only proves
  clean values pass has not been tested — the question is whether it catches
  the two ways the three prior implementations got this wrong: a prefix that
  looks sealed, and a leak nested below the top level."
  (:require [cljs.test :refer [deftest is testing]]
            [envelope.projection :as p]))

(def identifying?
  #{:person/name :person/address :person/birth-date :person/photo})

(def shape
  {:required #{:envelope/ciphertext :envelope/nonce}
   :optional #{:envelope/alg :envelope/aad :envelope/rid}})

;; ── sealed? is structural, not textual ───────────────────────────────────

(deftest sealed-requires-the-shape-not-a-prefix
  (testing "a real envelope passes"
    (is (p/sealed? shape {:envelope/ciphertext "…" :envelope/nonce "…"
                          :envelope/alg :aes-256-gcm})))

  (testing "a string that merely looks sealed does NOT pass"
    ;; This is exactly what com-etzhayyim-talent's prefix check admits:
    ;; "signal:v1:" + plaintext satisfies a prefix rule and nothing else.
    (is (not (p/sealed? shape "signal:v1:山田太郎")))
    (is (not (p/sealed? shape {:envelope/ciphertext "signal:v1:山田太郎"
                               :envelope/nonce "…"
                               :person/name "山田太郎"}))))

  (testing "an unknown key makes it false — the gate must not loosen as schemas grow"
    (is (not (p/sealed? shape {:envelope/ciphertext "…" :envelope/nonce "…"
                               :envelope/extra "added later"}))))

  (testing "a missing required key makes it false"
    (is (not (p/sealed? shape {:envelope/ciphertext "…"})))))

;; ── leaks walks to any depth ─────────────────────────────────────────────

(deftest leaks-finds-nested-identifying-attributes
  (testing "top level"
    (is (= #{:person/name} (p/leaks identifying? {:person/name "山田" :cohort/country "JP"}))))

  (testing "nested in a map value — rirekisho's leaks would miss this"
    (is (= #{:person/name}
           (p/leaks identifying? {:cohort/country "JP"
                                  :cohort/profile {:person/name "山田"}}))))

  (testing "nested inside a vector of maps"
    (is (= #{:person/address}
           (p/leaks identifying? {:cohort/history [{:role "dev"}
                                                   {:person/address "大阪"}]}))))

  (testing "nested inside a set"
    (is (= #{:person/photo}
           (p/leaks identifying? {:cohort/x #{{:person/photo "…"}}}))))

  (testing "several at several depths"
    (is (= #{:person/name :person/birth-date}
           (p/leaks identifying? {:person/name "山田"
                                  :a [{:b {:person/birth-date "1990-01-01"}}]}))))

  (testing "a clean cohort leaks nothing"
    (is (empty? (p/leaks identifying? {:cohort/country "JP"
                                       :cohort/isco "2512"
                                       :cohort/skills #{"clojure" "rust"}
                                       :cohort/count 3})))))

;; ── the gate ─────────────────────────────────────────────────────────────

(deftest persistable-requires-both-conditions
  (testing "a clean projection is persistable"
    (is (p/persistable? {:identifying? identifying?}
                        {:cohort/country "JP" :cohort/count 3})))

  (testing "a leak anywhere blocks it"
    (is (not (p/persistable? {:identifying? identifying?}
                             {:cohort/country "JP"
                              :cohort/profile {:person/name "山田"}}))))

  (testing "with :sealed-shape the value must also BE an envelope"
    (is (p/persistable? {:identifying? identifying? :sealed-shape shape}
                        {:envelope/ciphertext "…" :envelope/nonce "…"}))
    (is (not (p/persistable? {:identifying? identifying? :sealed-shape shape}
                             {:cohort/country "JP"}))))

  (testing "without :identifying? nothing is identifying — an empty declaration
            is not a safety claim, and the caller must supply one"
    (is (p/persistable? {} {:person/name "山田"}))))

(deftest ensure-persistable-names-what-it-caught
  (testing "returns the value when clean"
    (let [v {:cohort/country "JP"}]
      (is (= v (p/ensure-persistable! {:identifying? identifying?} v)))))

  (testing "throws with the offending attributes, not just 'invalid'"
    (try
      (p/ensure-persistable! {:identifying? identifying?}
                             {:cohort/x [{:person/name "山田"}]})
      (is false "should have thrown")
      (catch :default e
        (is (= #{:person/name} (:leaks (ex-data e))))))))

;; ── split ────────────────────────────────────────────────────────────────

(deftest split-partitions-by-attribute
  (let [{:keys [envelope projection]}
        (p/split identifying? {:person/name "山田"
                               :person/address "大阪"
                               :cohort/country "JP"
                               :cohort/isco "2512"})]
    (is (= {:person/name "山田" :person/address "大阪"} envelope))
    (is (= {:cohort/country "JP" :cohort/isco "2512"} projection))
    (testing "and the projection half then passes the gate"
      (is (p/persistable? {:identifying? identifying?} projection)))))

;; ── the documented limit, pinned as a test ───────────────────────────────

(deftest identifying-values-under-innocuous-keys-are-NOT-caught
  (testing "this passes, and that is a known limit rather than a bug —
            pinned so nobody later reads the guard as PII detection"
    (is (p/persistable? {:identifying? identifying?}
                        {:cohort/note "山田太郎 lives in Osaka"}))))
