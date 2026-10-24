;; nbb smoke test — proves the :cljs branches are real, and agree with the JVM.
;;
;; This file exists because `to-rdf` formats NUMBERS per host, and the string it
;; produces is what gets hashed and signed. The two platforms disagree natively —
;; the JVM writes `1.0E0` where JavaScript writes `1e+0` — so `double-lexical`
;; assembles the XSD canonical form by hand on both. If it were wrong on one of them,
;; a credential signed on the JVM would not verify in a browser and nothing else
;; would notice: `json-ld-api` had NO cljs verification at all until this file.
;;
;; Every expected value below was measured on the JVM first and is pinned
;; identically here. Whichever host is wrong, one of the two runs fails.
;;
;;   npm run smoke
(ns nbb-smoke
  (:require [json-ld-api.core :as jld]
            [json-ld-api.to-rdf :as tordf]))

(def ^:private failures (atom 0))
(defn- check [label expected actual]
  (if (= expected actual)
    (println "  ok  " label)
    (do (swap! failures inc)
        (println "  FAIL" label "\n        expected:" (pr-str expected)
                 "\n        actual:  " (pr-str actual)))))

(defn- literal-of
  "The [lexical-form datatype] a JSON value becomes in RDF."
  [v]
  (let [[st] (tordf/to-rdf [{"@id" "http://e/s" "http://e/p" [{"@value" v}]}])]
    [(get-in st [:object :value]) (get-in st [:object :datatype])]))

(def xsd-int "http://www.w3.org/2001/XMLSchema#integer")
(def xsd-dbl "http://www.w3.org/2001/XMLSchema#double")

(println "json-ld-api :cljs smoke")

;; ── §7.4 number lexical forms: the reason this file exists ───────────────────

(check "integer 5"            ["5" xsd-int]      (literal-of 5))
(check "integer 0"            ["0" xsd-int]      (literal-of 0))
(check "integer -1"           ["-1" xsd-int]     (literal-of -1))

;; An integral double is an xsd:integer with plain digits — NOT 1.0, and not 1.0E0.
(check "1.0 is an integer"    ["1" xsd-int]      (literal-of 1.0))
(check "100.0 is an integer"  ["100" xsd-int]    (literal-of 100.0))

;; A fractional value is xsd:double in XSD canonical form: one digit before the
;; point, at least one after, then E and a bare exponent. `1.5e+0` would be wrong.
(check "1.5 -> 1.5E0"         ["1.5E0" xsd-dbl]  (literal-of 1.5))
(check "-1.5 -> -1.5E0"       ["-1.5E0" xsd-dbl] (literal-of -1.5))
(check "0.1 -> 1.0E-1"        ["1.0E-1" xsd-dbl] (literal-of 0.1))
(check "1e-7 -> 1.0E-7"       ["1.0E-7" xsd-dbl] (literal-of 1.0E-7))
(check "pi keeps its digits"  ["3.14159265358979E0" xsd-dbl]
       (literal-of 3.14159265358979))

;; The 1e21 boundary: at or above it a value is a double even though it is integral,
;; because JSON's own toString switches to exponential there.
(check "1e21 is a double"     ["1.0E21" xsd-dbl] (literal-of 1e21))

(check "true"                 ["true" "http://www.w3.org/2001/XMLSchema#boolean"]
       (literal-of true))
(check "false"                ["false" "http://www.w3.org/2001/XMLSchema#boolean"]
       (literal-of false))
;; xsd:string is assigned and then dropped by nquads.core, because canonical
;; N-Triples forbids writing that datatype
(check "a plain string carries no written datatype" ["x" nil] (literal-of "x"))

;; ── §7.3 lists ───────────────────────────────────────────────────────────────

(let [sts (tordf/to-rdf [{"@id" "http://e/s"
                          "http://e/p" [{"@list" [{"@value" "a"} {"@value" "b"}]}]}])
      preds (frequencies (map #(get-in % [:predicate :value]) sts))]
  (check "a list is an rdf:first/rest chain" [2 2]
         [(get preds tordf/rdf-first) (get preds tordf/rdf-rest)])
  (check "terminating at rdf:nil" true
         (boolean (some #(= tordf/rdf-nil (get-in % [:object :value])) sts))))

(check "an empty list is rdf:nil itself" [1 tordf/rdf-nil]
       (let [sts (tordf/to-rdf [{"@id" "http://e/s" "http://e/p" [{"@list" []}]}])]
         [(count sts) (get-in (first sts) [:object :value])]))

;; ── blank node identity, the bug the toRdf suite caught ──────────────────────

(check "one anonymous node is named ONCE, not twice" 1
       (let [sts (tordf/to-rdf [{"@id" "http://e/s"
                                 "http://e/p" [{"http://e/q" [{"@value" "v"}]}]}])]
         (count (distinct (keep (fn [st]
                                  (when (= :blank (get-in st [:object :type]))
                                    (get-in st [:object :value])))
                                sts)))))

;; ── dropping, which §7 mandates ──────────────────────────────────────────────

(check "a relative IRI subject is dropped" []
       (tordf/to-rdf [{"@id" "relative/path" "http://e/p" [{"@value" "v"}]}]))
(check "a blank-node predicate is dropped" []
       (tordf/to-rdf [{"@id" "http://e/s" "_:p" [{"@value" "v"}]}]))
(check "unless generalized RDF is asked for" 1
       (count (tordf/to-rdf [{"@id" "http://e/s" "_:p" [{"@value" "v"}]}]
                            {:produce-generalized-rdf? true})))

;; ── expansion, whose reader conditionals also matter ─────────────────────────

(check "a free-floating node is dropped" []
       (jld/expand {"@id" "http://ex.com/only-an-id"}))
(check "a keyword-like term is dropped, not made a property" []
       (jld/expand {"@foo" "bar"}))
(check "an inline context expands a term" [{"http://schema.org/name" [{"@value" "x"}]}]
       (jld/expand {"@context" {"name" "http://schema.org/name"} "name" "x"}))
(check "@type is an array on a node object" [{"@type" ["http://e/T"]
                                              "@id" "http://e/s"}]
       (jld/expand {"@context" {"T" "http://e/T"} "@id" "http://e/s" "@type" "T"}))

;; ── contexts are never fetched, on this host either ──────────────────────────

(check "a remote context is refused, not fetched" "context-not-provided"
       (try (jld/expand {"@context" "https://example.com/c.jsonld" "name" "x"})
            :no-throw
            (catch :default e (:json-ld/error (ex-data e)))))

(check "an unsupported construct refuses rather than dropping triples" "@nest"
       (try (jld/expand {"@context" {"p" "http://e/p"} "@nest" {}}) :no-throw
            (catch :default e (:json-ld/unsupported (ex-data e)))))

;; ── the two together, which is what a cryptosuite hashes ─────────────────────

(check "expand -> to-rdf over a typed value, end to end"
       [["http://e/n" "42" xsd-int]]
       (->> (jld/expand {"@context" {"n" {"@id" "http://e/n" "@type" xsd-int}}
                         "@id" "http://e/s" "n" 42})
            (tordf/to-rdf)
            (mapv (fn [st] [(get-in st [:predicate :value])
                            (get-in st [:object :value])
                            (get-in st [:object :datatype])]))))

(println (if (zero? @failures)
           "all json-ld-api :cljs checks passed"
           (str @failures " json-ld-api :cljs check(s) FAILED")))
(when (pos? @failures) (throw (js/Error. (str @failures " failure(s)"))))
