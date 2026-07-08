(ns kotoba.cap-affine-test
  "Narrow S2 -- capability value affinity (deterministic drop, no implicit
  clone), scoped ONLY to capability-typed values (ADR-safe-capability-
  language.md, §0/§13(c)): every `^{:cap <kind>}` param, `(cap-acquire ...)`
  result, or let-bound alias may be consumed at most once along any single
  execution path through a function body. This is a static discipline check
  layered on top of the already-independent runtime confinement (T3) --
  every `<op>-with` use, reused or not, still re-resolves through
  `kotoba.cap-table/resolve-use` at the actual host call."
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.launcher :as launcher])
  (:import [java.io File]))

(defn temp-file
  [prefix suffix content]
  (let [file (doto (File/createTempFile prefix suffix)
               (.deleteOnExit))]
    (spit file content)
    (.getPath file)))

(defn temp-edn-file
  [content]
  (temp-file "kotoba-cap-affine-policy" ".edn" (pr-str content)))

(def demo-policy
  {:kotoba.policy/capabilities #{:ledger/append}
   :kotoba.policy/capability-resources {:ledger/append #{"ledger:main"}}})

(defn check-problems
  [source]
  (let [result (launcher/dispatch ["check"
                                   (temp-file "kotoba-cap-affine" ".kotoba" source)
                                   "--policy" (temp-edn-file demo-policy)
                                   "--json"])]
    {:ok? (:kotoba.cli/ok? result)
     :problems (get-in result [:kotoba.cli/data :kotoba.runtime/result
                               :kotoba.runtime/problems])}))

(defn reused-problems
  [source]
  (filterv #(= :cap-value-reused (:kotoba.runtime/problem %))
           (:problems (check-problems source))))

;; ---------------------------------------------------------------------------
;; Positive: deterministic drop (unused is fine) + single use is fine.

(deftest single-use-via-with-op-is-fine
  (is (empty? (reused-problems
               (str "(ns demo-single)\n"
                    "(defn ^{:i64 true} f [^{:cap :host/ledger-append} c ^:i64 code]\n"
                    "  (host-i64-roundtrip-with c code))\n"
                    "(defn main [] 0)\n")))))

(deftest unused-cap-typed-param-is-fine
  (testing "deterministic drop: no linear must-use requirement"
    (is (empty? (reused-problems
                 (str "(ns demo-unused)\n"
                      "(defn f [^{:cap :host/ledger-append} c] 0)\n"
                      "(defn main [] 0)\n"))))))

(deftest single-use-in-only-one-if-branch-is-fine
  (testing "if branches are mutually exclusive at runtime"
    (is (empty? (reused-problems
                 (str "(ns demo-branch)\n"
                      "(defn ^{:i64 true} f [^{:cap :host/ledger-append} c ^:i64 flag]\n"
                      "  (if flag (host-i64-roundtrip-with c (i64 1)) (i64 0)))\n"
                      "(defn main [] 0)\n"))))))

(deftest passing-through-one-level-of-calls-is-fine
  (testing "passing to a callee's cap-typed param is itself the caller's one use"
    (is (empty? (reused-problems
                 (str "(ns demo-pass-through)\n"
                      "(defn ^{:i64 true} inner [^{:cap :host/ledger-append} h ^:i64 code]\n"
                      "  (host-i64-roundtrip-with h code))\n"
                      "(defn ^{:i64 true} f [^{:cap :host/ledger-append} c ^:i64 code]\n"
                      "  (inner c code))\n"
                      "(defn main [] 0)\n"))))))

(deftest sibling-lets-reusing-the-same-local-name-are-independent
  (testing "two DIFFERENT capability instances bound to the same name `c` in
            sibling (not nested) lets are not confused with each other"
    (is (empty? (reused-problems
                 (str "(ns demo-sibling-lets)\n"
                      "(defn ^{:i64 true} f []\n"
                      "  (do\n"
                      "    (let [c (cap-acquire :host/ledger-append \"ledger:main\")]\n"
                      "      (host-i64-roundtrip-with c (i64 1)))\n"
                      "    (let [c (cap-acquire :host/ledger-append \"ledger:main\")]\n"
                      "      (host-i64-roundtrip-with c (i64 2)))))\n"
                      "(defn main [] 0)\n"))))))

;; ---------------------------------------------------------------------------
;; Negative: no implicit clone.

(deftest reusing-a-cap-typed-param-via-two-with-op-calls-is-rejected
  (let [problems (reused-problems
                  (str "(ns demo-reuse-sequential)\n"
                       "(defn ^{:i64 true} f [^{:cap :host/ledger-append} c]\n"
                       "  (do (host-i64-roundtrip-with c (i64 1))\n"
                       "      (host-i64-roundtrip-with c (i64 2))))\n"
                       "(defn main [] 0)\n"))]
    (is (= [{:kotoba.runtime/problem :cap-value-reused
             :kotoba.runtime/fn "f"
             :kotoba.runtime/op "host-i64-roundtrip-with"
             :kotoba.runtime/binding "c"
             :kotoba.runtime/kind :host/ledger-append
             :kotoba.runtime/first-use "host-i64-roundtrip-with"}]
           problems))))

(deftest reusing-after-a-conditional-use-is-rejected
  (testing "a binding used in EITHER if-branch is treated as possibly-already-
            used by whatever follows, since only one branch actually runs"
    (let [problems (reused-problems
                    (str "(ns demo-reuse-after-if)\n"
                         "(defn ^{:i64 true} f [^{:cap :host/ledger-append} c ^:i64 flag]\n"
                         "  (do (if flag (host-i64-roundtrip-with c (i64 1)) (i64 0))\n"
                         "      (host-i64-roundtrip-with c (i64 2))))\n"
                         "(defn main [] 0)\n"))]
      (is (= 1 (count problems)))
      (is (= "c" (:kotoba.runtime/binding (first problems)))))))

(deftest passing-to-a-callee-and-also-using-it-directly-is-rejected
  (testing "passing a capability to a callee's cap-typed param IS a consuming
            use -- using the same binding again afterward is a reuse"
    (let [problems (reused-problems
                    (str "(ns demo-reuse-pass-and-use)\n"
                         "(defn ^{:i64 true} inner [^{:cap :host/ledger-append} h ^:i64 code]\n"
                         "  (host-i64-roundtrip-with h code))\n"
                         "(defn ^{:i64 true} f [^{:cap :host/ledger-append} c ^:i64 code]\n"
                         "  (do (inner c code)\n"
                         "      (host-i64-roundtrip-with c code)))\n"
                         "(defn main [] 0)\n"))]
      (is (= 1 (count problems)))
      (is (= "c" (:kotoba.runtime/binding (first problems))))
      (is (= "inner" (:kotoba.runtime/first-use (first problems)))))))

;; ---------------------------------------------------------------------------
;; Documented known limitation: per-name tracking, not per-value provenance.

(deftest renaming-through-a-let-alias-is-a-known-uncaught-evasion
  (testing "tracked per LOCAL BINDING NAME -- `alias` and `c` are two
            different names for the same underlying value here, so using
            each once is not (yet) flagged as reusing the same capability.
            This is a documented conservative false-negative
            (kotoba.runtime/cap-affine-problems docstring); it does not
            weaken runtime confinement (T3), since kotoba.cap-table/
            resolve-use re-checks kind/expiry at every actual host call
            regardless of how the language-level checker classified it."
    (is (empty? (reused-problems
                 (str "(ns demo-alias-evasion)\n"
                      "(defn ^{:i64 true} f [^{:cap :host/ledger-append} c]\n"
                      "  (let [alias c]\n"
                      "    (do (host-i64-roundtrip-with alias (i64 1))\n"
                      "        (host-i64-roundtrip-with c (i64 2)))))\n"
                      "(defn main [] 0)\n"))))))

;; ---------------------------------------------------------------------------
;; Regression: the narrow affine check must not disturb the existing S4b
;; kind/effect checks or the interpreter/wasm-emit happy path.

(deftest existing-demo-cap-threading-source-still-checks-clean
  (testing "the real two-level capability-threading demo has exactly one use
            of its handle per function -- the new affine gate must not
            introduce false positives on it"
    (let [{:keys [ok? code]}
          (let [result (launcher/dispatch ["check" "src/demo_cap_threading.kotoba"
                                           "--policy" "src/demo_cap_threading_policy.edn"
                                           "--json"])]
            {:ok? (:kotoba.cli/ok? result) :code (:kotoba.cli/code result)})]
      (is (true? ok?))
      (is (= :check/valid code)))))
