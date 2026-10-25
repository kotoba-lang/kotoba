;; nbb smoke test — proves the :cljs branch is real.
;;
;; This namespace has three reader conditionals that a hash depends on: `utf8-bytes`
;; (TextEncoder vs String.getBytes), `hex` (Number.toString(16) vs
;; Integer/toHexString) and `code-points` (a hand-written surrogate-pair walk vs
;; String.codePoints). A host that differed in ANY of them would compute a different
;; canonical hash for the same graph — which is the one thing this library exists to
;; make impossible.
;;
;; So the values below are not "some hash": they are the exact strings the JVM suite
;; produces, measured and pinned identically in both places. Whichever host is wrong,
;; one of the two runs fails.
;;
;;   npm run smoke
(ns nbb-smoke
  (:require ["node:fs" :as fs]
            [nquads.core :as nq]
            [rdf-canon.core :as c14n]))

(def ^:private failures (atom 0))
(defn- check [label expected actual]
  (if (= expected actual)
    (println "  ok  " label)
    (do (swap! failures inc)
        (println "  FAIL" label "\n        expected:" (pr-str expected)
                 "\n        actual:  " (pr-str actual)))))

(defn- fixture [n] (str (fs/readFileSync (str "test/fixtures/rdfc10/" n))))

(println "rdf-canon :cljs smoke")

;; ── the canonical form, byte for byte ────────────────────────────────────────

(check "test020 canonical form"
       (str "<http://example.org/vocab#test> <http://example.org/vocab#A> _:c14n2 .\n"
            "<http://example.org/vocab#test> <http://example.org/vocab#B> _:c14n0 .\n"
            "_:c14n0 <http://example.org/vocab#next> _:c14n1 .\n"
            "_:c14n2 <http://example.org/vocab#next> _:c14n1 .\n")
       (c14n/canonicalize (fixture "test020-in.nq")))

(check "test020 issued identifier map"
       {"e1" "c14n0" "e2" "c14n1" "e0" "c14n2"}
       (:issued (c14n/canonicalize-dataset (nq/parse (fixture "test020-in.nq")))))

;; ── the hash: where every reader conditional shows up at once ─────────────────

(check "test020 canonical hash (SHA-256)"
       "c8136cd87e6ef2a278f2f3e017f5aabff154ab5d6a4793b4564bafb1728e71fb"
       (c14n/canonical-hash (fixture "test020-in.nq")))

(check "test020 canonical hash (SHA-384) — the optional algorithm"
       (str "929800285c69ebab3183e53fb0d448099a3fc6e0ecdfe635351dc29e58e15b25"
            "d9f5357ef49fc03a1ec77b05125fffae")
       (c14n/canonical-hash (fixture "test020-in.nq") {:hash-algorithm :sha384}))

;; test044 is the heaviest legitimate vector in the suite (3,348 work units), so it
;; exercises N-degree recursion and permutation pruning rather than the simple path.
(check "test044 canonical hash — the heaviest N-degree vector"
       "fe8b404b4d8dbfc0f6108155df11e9d180936efde8ce747d47784f5740e5d0af"
       (c14n/canonical-hash (fixture "test044-in.nq")))

;; ── N-degree hashing itself ──────────────────────────────────────────────────

(let [p (nq/iri "http://example.com/p")
      mk (fn [a b] [{:subject (nq/blank a) :predicate p :object (nq/literal "v")}
                    {:subject (nq/blank b) :predicate p :object (nq/literal "v")}])]
  (check "two nodes sharing a first-degree hash are resolved"
         "_:c14n0 <http://example.com/p> \"v\" .\n_:c14n1 <http://example.com/p> \"v\" .\n"
         (c14n/canonicalize (mk "b0" "b1")))
  (check "and relabelling the input does not change the output"
         (c14n/canonicalize (mk "b0" "b1"))
         (c14n/canonicalize (mk "b1" "b0"))))

;; ── code point order, which is NOT this host's default string order either ───

(check "code point order puts U+1F600 AFTER U+E000"
       true
       (pos? (c14n/compare-code-points "😀" "")))
(check "whereas the default UTF-16 comparison puts it before"
       true
       (neg? (compare "😀" "")))
(check "sorting by code point"
       ["a" "" "😀"]
       (sort c14n/compare-code-points ["" "😀" "a"]))

;; ── the escaping fix, on this host ───────────────────────────────────────────
;; test060 is W3C's escaping vector, and getting it right needs the corrected
;; canonical N-Triples rules in nquads plus UCHAR decoding in IRIs.

(check "test060 canonical form matches W3C byte for byte"
       (fixture "test060-rdfc10.nq")
       (c14n/canonicalize (fixture "test060-in.nq")))

;; ── the work limit, which is a spec MUST ─────────────────────────────────────

(check "the poison clique is REFUSED, not answered"
       :rdf-canon/work-limit-exceeded
       (try (c14n/canonicalize (fixture "test074-in.nq")) :no-throw
            (catch :default e (:rdf-canon/error (ex-data e)))))

(check "and the heaviest legitimate vector still fits the measured bound"
       :ok
       (try (c14n/canonicalize (fixture "test044-in.nq")
                               {:max-work c14n/measured-worst-legitimate-work})
            :ok
            (catch :default e (:rdf-canon/error (ex-data e)))))

(check "an unknown hash algorithm is refused"
       :rdf-canon/unknown-hash-algorithm
       (try (c14n/canonicalize "" {:hash-algorithm :md5}) :no-throw
            (catch :default e (:rdf-canon/error (ex-data e)))))

(println (if (zero? @failures)
           "all rdf-canon :cljs checks passed"
           (str @failures " rdf-canon :cljs check(s) FAILED")))
(when (pos? @failures) (throw (js/Error. (str @failures " failure(s)"))))
