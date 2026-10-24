;; The portable half of this library, on nbb (SCI).
;;
;; The JVM suite is `.clj` because it verifies real signatures through JCA, and
;; that is where the crypto belongs — the verify function is injected precisely
;; so this library holds none. What is portable is everything up to the
;; signature: parsing, structure, the refusals. This runs THAT on ClojureScript
;; against the same fixtures.
;;
;; A smaller claim than the JVM job makes, stated as one.
(ns run-tests
  (:require [asn1.core :as asn1]
            [ers.core :as ers]
            ["crypto" :as node-crypto]))

(def failures (atom 0))
(defn check [label expected actual]
  (if (= expected actual)
    (println "  ok  " label)
    (do (swap! failures inc)
        (println "  FAIL" label "expected" (pr-str expected) "got" (pr-str actual)))))
(defn check-throws [label f]
  (if (try (f) false (catch :default _ true))
    (println "  ok  " label)
    (do (swap! failures inc) (println "  FAIL" label "did not throw"))))
(defn done! []
  (println "\nnbb:" @failures "failures")
  (when (pos? @failures) (js/process.exit 1)))

;; Node's crypto as the injected `digest-fn`. In the JVM suite this is
;; `cms.jvm/digest`; the point of injection is that neither is inside the
;; library.
(defn digest-fn [algorithm data]
  (let [h (.createHash node-crypto (case algorithm
                                     :sha256 "sha256" :sha384 "sha384"
                                     :sha512 "sha512" :sha1 "sha1"
                                     (throw (ex-info "unsupported" {:algorithm algorithm}))))]
    (.update h (js/Buffer.from (clj->js (vec (asn1/->ints data)))))
    (vec (js/Array.from (.digest h)))))

(def leaves (mapv #(asn1/->ints (digest-fn :sha256 [%])) (range 4)))
(def tree (ers/build-tree digest-fn :sha256 leaves))

(println "ers on nbb:")
;; The same root a nine-line Python script computed independently. Checking it
;; on BOTH platforms is what makes the sorted-concatenation rule a fact rather
;; than a convention this codebase agreed with itself about.
(check "root matches the independent implementation"
       "a932f0ce28c9f994df39eed8956600a00e64cff2aa2a0675032a7b6cf28ce6a3"
       (asn1/hex (:root tree)))
(check "a node hash does not depend on the order its children arrive in"
       (ers/node-hash digest-fn :sha256 [(nth leaves 0) (nth leaves 1)])
       (ers/node-hash digest-fn :sha256 [(nth leaves 1) (nth leaves 0)]))
(doseq [i (range 4)]
  (check (str "leaf " i " reaches the root through its reduced path")
         (:root tree)
         (ers/root-from-path digest-fn :sha256 (nth leaves i) (ers/reduced-path tree i))))
(check "an odd node is promoted rather than duplicated"
       false (= (:root tree) (:root (ers/build-tree digest-fn :sha256 (subvec leaves 0 3)))))
(check-throws "a path that does not mention the document proves nothing"
              #(ers/root-from-path digest-fn :sha256
                                   (asn1/->ints (digest-fn :sha256 [0xff]))
                                   (ers/reduced-path tree 0)))
(check-throws "an empty archive is refused" #(ers/build-tree digest-fn :sha256 []))
(check-throws "a hash renewal without the data is refused"
              #(ers/hash-renewal-digest digest-fn :sha512 nil []))
(done!)
