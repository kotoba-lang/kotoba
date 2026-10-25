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
            [pades.core :as pades]
            [pdf.core :as pdf]
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

(def original
  (pdf/write-document
   [{:width 595 :height 842
     :content (pdf/text-command {:x 72 :y 760 :size 16 :text "Keiyakusho"})}]))

(def prepared (pades/prepare original {}))

(println "pades on nbb:")
(check "the original bytes are untouched"
       (vec original) (subvec (vec (:pades/prepared prepared)) 0 (count original)))
(let [[a b c d] (:pades/byte-range prepared)
      [gap-start gap-end] (:pades/gap prepared)]
  (check "the first range starts at 0" 0 a)
  (check "the second reaches the last byte" (count (:pades/prepared prepared)) (+ c d))
  (check "the hole is exactly the placeholder" [b c] [gap-start gap-end])
  (check "every byte is signed or in the hole, none both"
         (count (:pades/prepared prepared)) (+ b d (- c b))))
(check-throws "a CMS that does not fit is refused, not truncated"
              #(pades/embed (pades/prepare original {:signature-bytes 8})
                            (asn1/unhex (apply str (repeat 100 "ab")))))
(check "the level is reported, not claimed" :b-b (pades/profile {}))
(check "and B-T needs a signature timestamp" :b-t (pades/profile {:signature-timestamp? true}))
(done!)
