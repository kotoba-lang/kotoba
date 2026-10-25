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
            [asn1.oid :as oid]
            [cms.core :as cms]
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

(def attached (cms/parse-signed-data (asn1/unhex "308205e806092a864886f70d010702a08205d9308205d5020101310d300b0609608648016503040201302906092a864886f70d010701a01c041a6b6f746f626120657369676e207465737420636f6e74656e740aa08203e6308201e63082018da00302010202142ee1b06995d7b8c61ef21ceb91b93703b38a9a67300a06082a8648ce3d0403023041310b3009060355040613024a5031173015060355040a0c0e4b6f746f626120546573742043413119301706035504030c104b6f746f6261205465737420526f6f74301e170d3236303733303133313233335a170d3336303732373133313233335a3041310b3009060355040613024a5031173015060355040a0c0e4b6f746f626120546573742043413119301706035504030c104b6f746f6261205465737420526f6f743059301306072a8648ce3d020106082a8648ce3d03010703420004099900d98e0fda9b1f77526e5404608d169d3ec3881147b564e0ae5887290ecd267dc6976f912c2d4cb855e716dbbd8bb7c32f4c537524fd8dd87f97d7d98b11a3633061301d0603551d0e041604148033d385f87b532fc1a9fb42fee110ffe73040c3301f0603551d230418301680148033d385f87b532fc1a9fb42fee110ffe73040c3300f0603551d130101ff040530030101ff300e0603551d0f0101ff040403020106300a06082a8648ce3d04030203470030440220772238ee68742f994e673f8454a97f038e7e4ed01781770a0bc604d7d71a61b70220224f27531c8cb1574c3d777079bd08d5df702b10270752f6f9dd880f5eeacc89308201f83082019ea003020102021459b29c4d07173c1b16871d7129d6213e51e1f25f300a06082a8648ce3d0403023041310b3009060355040613024a5031173015060355040a0c0e4b6f746f626120546573742043413119301706035504030c104b6f746f6261205465737420526f6f74301e170d3236303733303133313233335a170d3336303732373133313233335a303d310b3009060355040613024a5031143012060355040a0c0b4b6f746f626120546573743118301606035504030c0f4b6f746f62612054657374205453413059301306072a8648ce3d020106082a8648ce3d030107034200047d5f6c637af986a8847f6f23755d24a192e348c86f9ff35468f4b5592de6fbd447a02e8139feee9baff1ef0c79179e0746293bc7dafba0a0e7f9d69e1d3a032da3783076300c0603551d130101ff04023000300e0603551d0f0101ff0404030206c030160603551d250101ff040c300a06082b06010505070308301d0603551d0e04160414817bdc5258db8e6f9e32edcd1d046f30cdaf8f31301f0603551d230418301680148033d385f87b532fc1a9fb42fee110ffe73040c3300a06082a8648ce3d04030203480030450221009300639acf8fd27cdb85761a9ccd298ee89cd549b964cb78b29b489b08671adb02203111acf98ca2aaa0b9d227a29ce1d9ddc8a63b802ecda444528885c1c23d4178318201aa308201a602010130593041310b3009060355040613024a5031173015060355040a0c0e4b6f746f626120546573742043413119301706035504030c104b6f746f6261205465737420526f6f74021459b29c4d07173c1b16871d7129d6213e51e1f25f300b0609608648016503040201a081e4301806092a864886f70d010903310b06092a864886f70d010701301c06092a864886f70d010905310f170d3236303733303133333730395a302f06092a864886f70d01090431220420404d8f2246f3a6948de6aee686a6e3d116ed2eb56a74b9b1d3df75f2130203e2307906092a864886f70d01090f316c306a300b060960864801650304012a300b0609608648016503040116300b0609608648016503040102300a06082a864886f70d0307300e06082a864886f70d030202020080300d06082a864886f70d0302020140300706052b0e030207300d06082a864886f70d0302020128300a06082a8648ce3d04030204463044022040c81d8b8d41ff7d8e32178679a9646daea9dbc0cdb55fedc8291be791c7cb17022000cc9ba65f9cd2c6b5977ad4fb414ddec4240bea6151a7d26853dab817628186")))
(def content (asn1/unhex "6b6f746f626120657369676e207465737420636f6e74656e740a"))

(println "cms on nbb:")
(check "parses as SignedData" 1 (:cms/version attached))
(check "content is attached" false (:cms/detached? attached))
(check "eContentType" :data (oid/named (:cms/econtent-type attached)))
(check "two certificates" 2 (count (:cms/certificates attached)))
(check "one signer" 1 (count (:cms/signer-infos attached)))

(let [signer (first (:cms/signer-infos attached))
      attrs (:signer/signed-attrs signer)]
  (check "signedAttrs are hashed as a SET, not as the [0] they arrived with"
         0x31 (first (:signer/signed-attrs-der signer)))
  (check "and those bytes re-encode to themselves"
         true (asn1/der-round-trips? (:signer/signed-attrs-der signer)))
  (check "messageDigest matches the content"
         (asn1/hex (digest-fn :sha256 content))
         (asn1/hex (:asn1/content (cms/single-value attrs :message-digest))))
  (check "and NOT some other content"
         false (= (asn1/hex (digest-fn :sha256 [0x00]))
                  (asn1/hex (:asn1/content (cms/single-value attrs :message-digest))))))

;; The refusal that this whole library is written around, on cljs too: a
;; verifier reaching the content only through messageDigest.
(let [swapped (assoc attached :cms/econtent (asn1/unhex "6e6f742074686520636f6e74656e74"))
      result (cms/verify swapped {:digest-fn digest-fn
                                  :verify-fn (fn [_] (throw (ex-info "must not be reached" {})))})]
  (check "swapped content fails at messageDigest, before any signature check"
         :message-digest-mismatch (:reason (first (:signers result)))))

(check-throws "a multi-valued single-valued attribute is refused"
              #(cms/single-value [{:name :message-digest
                                   :values [(asn1/octet-string [1]) (asn1/octet-string [2])]}]
                                 :message-digest))
(done!)
