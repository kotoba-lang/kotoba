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
            [jpki.core :as jpki]
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

(def cert-der (asn1/unhex "3082030b308202b1a0030201020214488254e694cb7cc9b861d98aa79a6d428d90d3e7300a06082a8648ce3d0403023041310b3009060355040613024a5031173015060355040a0c0e4b6f746f626120546573742043413119301706035504030c104b6f746f6261205465737420526f6f74301e170d3236303733303134343432395a170d3331303732393134343432395a3081aa310b3009060355040613024a50313d303b060355040a0c344a6170616e204167656e637920666f72204c6f63616c20417574686f7269747920496e666f726d6174696f6e2053797374656d733141303f060355040b0c384a6170616e657365205075626c6963204b657920496e66726173747275637475726520666f72206469676974616c207369676e61747572653119301706035504030c10313233343536373839303132333435363059301306072a8648ce3d020106082a8648ce3d030107034200047838d968127eca9cdd5c7793be2a6c690dc13ac46d511d086edf21f3412db79a330a6f7c413e3f58bdc8668cf07a82eb59aed9165f03f890710846f9a1559594a382011b30820117300c0603551d130101ff04023000300e0603551d0f0101ff0404030206403081b60603551d110481ae3081aba029060a2a83088c9b5508050501a01b0c19c3a5c2b1c2b1c3a7c294c2b020c3a5c2a4c2aac3a9c283c28ea018060a2a83088c9b5508050502a00a0c083139383530333132a011060a2a83088c9b5508050503a0030c0131a051060a2a83088c9b5508050504a0430c41c3a6c29dc2b1c3a4c2bac2acc3a9c283c2bdc3a5c28dc283c3a4c2bbc2a3c3a7c294c2b0c3a5c28cc2bac3a9c29cc29ec3a3c281c28cc3a9c296c2a2312d312d31301d0603551d0e041604145a1fa7019ca96225b1d4a9524adb6fb74ba1df04301f0603551d230418301680148033d385f87b532fc1a9fb42fee110ffe73040c3300a06082a8648ce3d04030203480030450220743d95648852ad570e3d91b766aed27a96cd0add5166deb2d6aba1b68e566cf5022100fb8fb91911edf36da45a84e31201253c2ccaad8272e92f7511cbf7cfd1cee877"))

(println "jpki on nbb:")
(let [parsed (jpki/parse-certificate cert-der)]
  (check "shaped like a signature certificate" true (:jpki/shaped? parsed))
  (check "issuer hint matches" true (:jpki/issuer-hint-matches? parsed))
  (check "nonRepudiation only" #{:non-repudiation} (:jpki/key-usage parsed))
  ;; The 基本4情報 must not be in what `parse-certificate` returns.
  (check "the person is not in the parse result" false
         (boolean (re-find #"19850312" (pr-str parsed)))))

(let [four (jpki/basic-four (:jpki/certificate (jpki/parse-certificate cert-der)))]
  (check "and IS there when asked for by name" "19850312" (:birth-date four))
  (check "the sex code is returned as a code, not translated" "1" (:sex four)))

(check-throws "verifying with no trusted roots is refused"
              #(jpki/verify-signature {:cms/signer-infos [] :cms/certificates []}
                                      {:roots [] :digest-fn digest-fn
                                       :verify-fn (constantly true)}))
(done!)
