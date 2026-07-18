(ns kotoba.guest-maturity-p0-p1-test
  "ADR-2607180900 P0/P1: strict-grammar, F-001 safe-release-ready?,
  S4b forbid-wildcard, host-parity matrix."
  (:require [clojure.string :as str]
            [clojure.test :refer [deftest is testing]]
            [kotoba.guest-grammar :as guest-grammar]
            [kotoba.host-parity :as host-parity]
            [kotoba.lang.capability-host :as capability-host]
            [kotoba.lang.capability-values :as capability-values]
            [kotoba.package-admission :as package-admission]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(deftest strict-grammar-opt-in-rejects-unknown-form
  (let [forms (runtime/read-forms "(ns t)\n(defn main [] (totally-unknown-op 1))" :kotoba)
        problems (guest-grammar/strict-problems forms {:kotoba.policy/strict-grammar true})
        unknown (first (filter #(= :unknown-form (:kotoba.runtime/problem %)) problems))]
    (is (true? (guest-grammar/strict-grammar? nil))
        "safe emit/run defaults to the fail-closed authority grammar")
    (is (true? (guest-grammar/strict-grammar? {:kotoba.policy/strict-grammar true})))
    (is unknown)
    (is (= "totally-unknown-op" (:kotoba.runtime/form unknown)))))

(deftest strict-grammar-can-be-opted-out
  (let [forms (runtime/read-forms "(ns t)\n(defn main [] (totally-unknown-op 1))" :kotoba)
        problems (guest-grammar/strict-problems forms {:kotoba.policy/strict-grammar false})]
    (is (false? (guest-grammar/strict-grammar? {:kotoba.policy/strict-grammar false})))
    (is (empty? (filter #(= :unknown-form (:kotoba.runtime/problem %)) problems)))))

(deftest strict-grammar-still-allows-admitted-and-host-ops
  (let [forms (runtime/read-forms
               "(ns t)\n(defn main [] (when 1 (and 1 2) (+ 1 2)))" :kotoba)
        problems (guest-grammar/strict-problems forms nil)]
    (is (empty? (filter #(#{:unknown-form :denied-form} (:kotoba.runtime/problem %))
                        problems)))))

(deftest catalog-forbidden-always-denied
  (let [forms (runtime/read-forms "(ns t)\n(defn main [] (eval 1))" :kotoba)
        problems (guest-grammar/strict-problems forms {:kotoba.policy/strict-grammar false})
        denied (first (filter #(= :denied-form (:kotoba.runtime/problem %)) problems))]
    (is denied)
    (is (= "eval" (:kotoba.runtime/form denied)))
    (is (string? (:kotoba.lang/hint denied)))))

(deftest multi-body-when-still-emits-under-strict
  (let [forms (runtime/read-file "src/demo_guest_maturity_l2.kotoba" :kotoba)
        problems (runtime/source-problems
                  {:non-executable-forms #{}
                   :effect-ops #{}}
                  (runtime/lower-language-forms forms)
                  nil)
        wasm (runtime/wasm-binary forms)]
    (is (empty? (filter #(= :unknown-form (:kotoba.runtime/problem %)) problems)))
    (is (:kotoba.wasm/ok? wasm) (str (:kotoba.wasm/problems wasm)))
    (is (= 42 (wasm-exec/run-main (:kotoba.wasm/binary wasm) [])))))

(defn- run-kotoba-main [source]
  (let [forms (runtime/read-forms source :kotoba)
        wasm (runtime/wasm-binary forms)]
    (is (:kotoba.wasm/ok? wasm) (str (:kotoba.wasm/problems wasm)))
    (wasm-exec/run-main (:kotoba.wasm/binary wasm) [])))

(deftest bounded-set-literals-and-operations-run-on-primary-wasm-backend
  (is (= 1 (run-kotoba-main
            "(defn main [] (contains? #{:a :b} :a))")))
  (is (= 1 (run-kotoba-main
            "(defn main [] (contains? (conj #{:a} :b) :b))")))
  (is (= 0 (run-kotoba-main
            "(defn main [] (contains? (disj #{:a :b} :a) :a))"))))

(deftest primary-wasm-set-removes-runtime-equal-duplicates
  (is (= 1 (run-kotoba-main
            "(defn count-set [s] (if (= s 0) 0 (+ 1 (count-set (pair-second s)))))
             (defn main [] (count-set #{(+ 1 1) 2}))"))))

(deftest primary-wasm-persistent-collection-operations
  (is (= 7 (run-kotoba-main
            "(defn main []
               (+ (count (vals {:a 4 :b 5}))
                  (nth (vals {:a 4 :b 5}) 1 0)))")))
  (is (= 4 (run-kotoba-main
            "(defn main [] (get (dissoc {:a 4 :b 5} :b) :a))")))
  (is (= 5 (run-kotoba-main
            "(defn main [] (peek (pop (vals {:a 4 :b 5}))))")))
  (is (= 0 (run-kotoba-main
            "(defn main [] (peek (vals {})))"))))

(deftest primary-wasm-vector-literals-share-the-bounded-persistent-slice
  (is (= 9 (run-kotoba-main
            "(defn main [] (nth [7 8 9] 2 0))")))
  (is (= 3 (run-kotoba-main
            "(defn main [] (count [7 8 9]))")))
  (is (= 8 (run-kotoba-main
            "(defn main [] (peek (pop [7 8 9])))")))
  (let [items (str/join " " (range 129))
        forms (runtime/read-forms (str "(defn main [] (count [" items "]))") :kotoba)
        wasm (runtime/wasm-binary forms)]
    (is (false? (:kotoba.wasm/ok? wasm)))
    (is (= :admission-limit
           (:kotoba.wasm/problem (first (:kotoba.wasm/problems wasm)))))))

(deftest primary-wasm-named-higher-order-collection-operations
  (is (= 10 (run-kotoba-main
            "(defn add [a b] (+ a b))
             (defn main [] (nth (map add [1 2] [7 8]) 1 0))")))
  (is (= 4 (run-kotoba-main
            "(defn above-two [x] (> x 2))
             (defn main [] (pair-first (filter above-two [1 4 2])))")))
  (is (= 10 (run-kotoba-main
             "(defn add [a b] (+ a b))
              (defn main [] (reduce add 4 [1 2 3]))")))
  (is (= 15 (run-kotoba-main
             "(defn sum5 [a b c d e] (+ (+ a b) (+ c (+ d e))))
              (defn main []
                (pair-first (map sum5 [1] [2] [3] [4] [5])))"))))

(deftest primary-wasm-inline-higher-order-callbacks-capture-lexically
  (is (= 7 (run-kotoba-main
            "(defn main []
               (let [n 3] (pair-first (map (fn [x] (+ x n)) [4]))))")))
  (is (= 5 (run-kotoba-main
            "(defn main []
               (let [limit 3]
                 (pair-first (filter (fn [x] (> x limit)) [1 5 2]))))")))
  (is (= 16 (run-kotoba-main
             "(defn main []
                (let [scale 2]
                  (reduce (fn [acc x] (+ acc (* scale x))) 4 [1 2 3])))"))))

(deftest primary-wasm-no-init-reduce-supports-inline-zero-binary-clauses
  (is (= 6 (run-kotoba-main
            "(defn main []
               (reduce (fn ([] 40) ([acc x] (+ acc x))) [1 2 3]))")))
  (is (= 40 (run-kotoba-main
             "(defn main []
                (reduce (fn ([] 40) ([acc x] (+ acc x))) []))")))
  (is (= 6 (run-kotoba-main
            "(defn main []
               (let [bias 4]
                 (reduce (fn ([] bias) ([acc x] (+ acc x bias))) [1 1])))"))))

(deftest primary-wasm-nested-let-destructuring
  (is (= 11 (run-kotoba-main
             "(defn main []
                (let [[a [b c] & rest] [1 [2 3] 4 5]]
                  (+ (+ a b) (+ c (nth rest 1 0)))))")))
  (is (= 12 (run-kotoba-main
             "(defn main []
                (let [{:keys [a] :or {a 7} :as whole :b [x y]}
                      {:b [2 3]}]
                  (+ a (+ x y))))"))))

(deftest primary-wasm-function-parameter-destructuring
  (is (= 6 (run-kotoba-main
            "(defn sum [[a b] {:keys [c]}] (+ a (+ b c)))
             (defn main [] (sum [1 2] {:c 3}))")))
  (is (= 10 (run-kotoba-main
             "(defn pick [{:keys [x] :or {x 9}} [a & rest]]
                (+ x (+ a (nth rest 0 0))))
              (defn main [] (pick {} [0 1]))"))))

(deftest primary-wasm-record-constructors-use-tagged-persistent-maps
  (is (= 7 (run-kotoba-main
            "(defrecord Point [x y])
             (defn main [] (get (->Point 3 7) :y))")))
  (is (= 5 (run-kotoba-main
            "(defrecord Point [x y])
             (defn main [] (get (map->Point {:x 5 :y 6}) :x))")))
  (is (= 9 (run-kotoba-main
            "(defrecord Point [x y])
             (defn main [] (get (assoc (->Point 3 7) :x 9) :x))")))
  (is (= 1 (run-kotoba-main
            "(defrecord Point [x y])
             (defn main []
               (if (= (get (->Point 1 2) :kotoba.record/type) :Point) 1 0))"))))

(deftest primary-wasm-record-protocol-static-dispatch
  (is (= 7 (run-kotoba-main
            "(defprotocol Value (value [this]))
             (defrecord Box [x] Value (value [this] (get this :x)))
             (defn main [] (value (->Box 7)))")))
  (is (= 9 (run-kotoba-main
            "(defprotocol Value (value [this]))
             (defrecord Box [x])
             (extend-type Box Value (value [this] (get this :x)))
             (defn main [] (value (->Box 9)))")))
  (is (= 99 (run-kotoba-main
             "(defprotocol Value (value [this]))
              (defrecord Box [x])
              (extend-protocol Value default (value [this] 99))
              (defn main [] (value {:x 1}))"))))

(deftest primary-wasm-named-multi-arity-and-variadic-functions
  (is (= 12 (run-kotoba-main
             "(defn choose ([x] x) ([x y] (+ x y)))
              (defn main [] (+ (choose 3) (choose 4 5)))")))
  (is (= 7 (run-kotoba-main
            "(defn tally ([x] x) ([x & more] (+ x (count more))))
             (defn main [] (tally 5 8 9))")))
  (is (= 40 (run-kotoba-main
             "(defn add ([] 40) ([a b] (+ a b)))
              (defn main [] (reduce add []))")))
  (is (= 6 (run-kotoba-main
            "(defn add ([] 40) ([a b] (+ a b)))
             (defn main [] (reduce add [1 2 3]))"))))

(deftest primary-wasm-first-class-closures-invoke-and-apply
  (is (= 7 (run-kotoba-main
            "(defn main []
               (let [n 3 f (fn [x] (+ x n))]
                 (invoke f 4)))")))
  (is (= 12 (run-kotoba-main
             "(defn make [n] (fn [x] (+ x n)))
              (defn main [] (invoke (make 5) 7))")))
  (is (= 11 (run-kotoba-main
             "(defn add [a b] (+ a b))
              (defn main [] (invoke (fn-ref add) 3 8))")))
  (is (= 6 (run-kotoba-main
            "(defn main []
               (apply (fn [a b c] (+ a (+ b c))) 1 [2 3]))")))
  (is (= 11 (run-kotoba-main
             "(defn main []
                (let [n 2 f (fn [acc x] (+ acc (* n x)))]
                  (reduce f 1 [2 3])))")))
  (is (= 7 (run-kotoba-main
            "(defn make [n] (fn [x] (+ x n)))
             (defn main [] (pair-first (map (make 3) [4])))")))
  (is (= 6 (run-kotoba-main
            "(defn main []
               (let [f (fn ([] 40) ([a b] (+ a b)))]
                 (reduce f [1 2 3])))"))))

(deftest primary-wasm-pure-call-by-name-lazy-sequences
  (is (= 6 (run-kotoba-main
            "(defn nums [n] (lazy-cons n (nums (+ n 1))))
             (defn main [] (nth (take 4 (nums 3)) 3 0))")))
  (is (= 6 (run-kotoba-main
            "(defn nums [n] (lazy-cons n (nums (+ n 1))))
             (defn main [] (lazy-first (drop 5 (nums 1))))")))
  (is (= 6 (run-kotoba-main
            "(defn nums [n] (lazy-cons n (nums (+ n 1))))
             (defn main []
               (nth (take 3 (lazy-map (fn [x] (* x 2)) (nums 1))) 2 0))")))
  (is (= 5 (run-kotoba-main
            "(defn nums [n] (lazy-cons n (nums (+ n 1))))
             (defn main []
               (nth (take 2 (lazy-filter (fn [x] (> x 3)) (nums 1))) 1 0))")))
  (is (= 15 (run-kotoba-main
             "(defn nums [n] (lazy-cons n (nums (+ n 1))))
              (defn add [a b] (+ a b))
              (defn main []
                (nth (take 3 (lazy-map add (nums 1) (nums 10))) 2 0))"))))

(deftest primary-wasm-rejects-transitively-effectful-lazy-thunks
  (doseq [source ["(defn main [] (lazy-cons (http-fetch 0 0) 0))"
                  "(defn fetch [] (http-fetch 0 0))
                   (defn main [] (lazy-cons (fetch) 0))"]]
    (let [error (try
                  (runtime/wasm-binary (runtime/read-forms source :kotoba))
                  nil
                  (catch clojure.lang.ExceptionInfo e e))]
      (is (= :effectful-lazy-thunk
             (:kotoba.runtime/problem (ex-data error)))))))

(deftest safe-release-ready-requires-verified-receipt
  (is (false? (:ok? (package-admission/safe-release-ready? nil))))
  (is (false? (:ok? (package-admission/safe-release-ready?
                     {:kotoba.package/verified? false}))))
  (is (true? (:ok? (package-admission/safe-release-ready?
                    {:kotoba.package/verified? true
                     :kotoba.package/problems []})))))

(deftest s4b-forbid-wildcard-denies-any-intersection
  (let [cap (capability-values/make-cap :host/http :any)
        grants [{:grant/kind :host/http
                 :grant/resources #{:any}
                 :grant/id "g1"}]
        open (capability-values/intersect-grants
              {:requested cap
               :cacao-grants grants
               :local-policy {:policy/allow {:host/http :any}}
               :now "2026-07-18"})
        closed (capability-values/intersect-grants
                {:requested cap
                 :cacao-grants grants
                 :local-policy {:policy/allow {:host/http :any}
                                :policy/forbid-wildcard true}
                 :now "2026-07-18"})]
    (is (capability-values/capability? open))
    (is (= :any (:cap/resource open)))
    (is (capability-values/denied? closed))
    (is (= :wildcard-forbidden (:denied closed)))))

(deftest s4b-forbid-wildcard-allows-concrete-resource
  (let [cap (capability-values/make-cap :host/http "https://api.example/")
        grants [{:grant/kind :host/http
                 :grant/resources #{"https://api.example/"}
                 :grant/id "g1"}]
        outcome (capability-values/intersect-grants
                 {:requested cap
                  :cacao-grants grants
                  :local-policy {:policy/allow {:host/http #{"https://api.example/"}}
                                 :policy/forbid-wildcard true}
                  :now "2026-07-18"})]
    (is (capability-values/capability? outcome))
    (is (= "https://api.example/" (:cap/resource outcome)))
    (let [guarded (capability-host/guard-call
                   {:call :http-fetch
                    :requested cap
                    :cacao-grants grants
                    :local-policy {:policy/allow {:host/http #{"https://api.example/"}}
                                   :policy/forbid-wildcard true}
                    :now "2026-07-18"
                    :handler (fn [concrete] concrete)})]
      (is (true? (:kotoba.host/ok? guarded)))
      (is (map? (:kotoba.host/receipt guarded)))
      (is (= "https://api.example/"
             (get-in guarded [:kotoba.host/receipt :receipt/cap :cap/resource]))))))

(deftest host-parity-matrix-meets-threshold
  (let [s (host-parity/score)
        r (host-parity/report)]
    (is (pos? (:total s)))
    (is (true? (:ok? s)) (str "ratio=" (:ratio s) " missing=" (:missing s)))
    (is (= :meets-threshold (:status r)))
    (is (some #(= :llm-infer (:import %)) (host-parity/matrix)))
    (is (some #(= :no (:browser %)) (host-parity/matrix))
        "honest gap: llm-infer browser absent")))

(deftest primary-collection-walks-use-fuel-beyond-eight-items
  (let [source "(defn inc1 [x] (+ x 1))
                (defn add [a b] (+ a b))
                (defn main []
                  (let [xs [1 2 3 4 5 6 7 8 9 10 11 12]
                        ys (map inc1 xs)]
                    (+ (count ys) (nth ys 11 0) (reduce add 0 xs))))"
        forms (runtime/read-forms source :kotoba)
        wasm (runtime/wasm-binary forms)]
    (is (:kotoba.wasm/ok? wasm) (str (:kotoba.wasm/problems wasm)))
    (when (:kotoba.wasm/ok? wasm)
      (is (= 103 (wasm-exec/run-main (:kotoba.wasm/binary wasm) []))))))

(deftest portable-string-values-have-a-fail-closed-byte-bound
  (is (= 3 (run-kotoba-main "(defn main [] (string-length \"猫\"))")))
  (is (thrown-with-msg?
       clojure.lang.ExceptionInfo #"exceeds 127 UTF-8 bytes"
       (runtime/wasm-binary
        (runtime/read-forms
         (str "(defn main [] \"" (apply str (repeat 128 "a")) "\")") :kotoba)))))
