;; The portable half of this library, on nbb (SCI).
;;
;; The JVM suite is `.clj` because it verifies real ECDSA through JCA, and that
;; is where the crypto belongs — `verify-fn` is injected precisely so this
;; library holds none. What is portable is everything up to the signature:
;; parsing, extensions, the refusals, validity. This runs THAT on ClojureScript,
;; against the same certificate the JVM suite uses.
;;
;; It is a smaller claim than the JVM job makes and it is stated as one: a green
;; run here means the structural half loads and answers correctly on cljs, not
;; that a signature was verified there.
(ns run-tests
  (:require [asn1.core :as asn1]
            [asn1.oid :as oid]
            [x509.core :as x509]))

(def tsa-der (asn1/unhex "308201f83082019ea003020102021459b29c4d07173c1b16871d7129d6213e51e1f25f300a06082a8648ce3d0403023041310b3009060355040613024a5031173015060355040a0c0e4b6f746f626120546573742043413119301706035504030c104b6f746f6261205465737420526f6f74301e170d3236303733303133313233335a170d3336303732373133313233335a303d310b3009060355040613024a5031143012060355040a0c0b4b6f746f626120546573743118301606035504030c0f4b6f746f62612054657374205453413059301306072a8648ce3d020106082a8648ce3d030107034200047d5f6c637af986a8847f6f23755d24a192e348c86f9ff35468f4b5592de6fbd447a02e8139feee9baff1ef0c79179e0746293bc7dafba0a0e7f9d69e1d3a032da3783076300c0603551d130101ff04023000300e0603551d0f0101ff0404030206c030160603551d250101ff040c300a06082b06010505070308301d0603551d0e04160414817bdc5258db8e6f9e32edcd1d046f30cdaf8f31301f0603551d230418301680148033d385f87b532fc1a9fb42fee110ffe73040c3300a06082a8648ce3d04030203480030450221009300639acf8fd27cdb85761a9ccd298ee89cd549b964cb78b29b489b08671adb02203111acf98ca2aaa0b9d227a29ce1d9ddc8a63b802ecda444528885c1c23d4178"))

(def failures (atom 0))
(defn check [label expected actual]
  (if (= expected actual)
    (println "  ok  " label)
    (do (swap! failures inc)
        (println "  FAIL" label "expected" (pr-str expected) "got" (pr-str actual)))))

(let [c (x509/parse tsa-der)]
  (println "x509 on nbb:")
  (check "subject" "CN=Kotoba Test TSA,O=Kotoba Test,C=JP" (:text (:x509/subject c)))
  (check "serial is hex" "59b29c4d07173c1b16871d7129d6213e51e1f25f" (:x509/serial-number c))
  (check "not-before" "2026-07-30T13:12:33Z" (:x509/not-before c))
  (check "algorithm" :ecdsa-with-sha256 (oid/named (:x509/signature-algorithm c)))
  (check "key usage" #{:digital-signature :non-repudiation} (x509/key-usage c))
  (check "eku" true (x509/has-extended-key-usage? c :kp-time-stamping))
  (check "not a CA" false (x509/ca? c))
  (check "usable" true (:usable? (x509/usable? c)))
  (check "valid at a time inside" true (x509/valid-at? c "2026-08-01T00:00:00Z"))
  (check "not valid before" false (x509/valid-at? c "2020-01-01T00:00:00Z"))
  (check "tbs re-encodes to itself" true (asn1/der-round-trips? (:x509/tbs-der c)))
  (check "a critical extension nobody handles makes it unusable" false
         (:usable? (x509/usable?
                    (update c :x509/extensions conj
                            {:oid "1.3.6.1.4.1.99999.1" :name nil
                             :critical? true :der [0x05 0x00]})))))

(println "\nnbb:" @failures "failures")
(when (pos? @failures) (js/process.exit 1))
