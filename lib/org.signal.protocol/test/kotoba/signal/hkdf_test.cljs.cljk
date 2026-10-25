(ns kotoba.signal.hkdf-test
  (:require [cljs.test :refer-macros [deftest is async]]
            [kotoba.signal.hkdf :as hkdf]))

;; RFC 5869 Appendix A — HKDF-SHA256 test vectors (A.1, A.2, A.3), verbatim,
;; same vectors kotoba.signal.hkdf (JVM) is pinned against.

(defn- unhex [^string s]
  (let [n (/ (count s) 2) out (js/Uint8Array. n)]
    (dotimes [i n] (aset out i (js/parseInt (subs s (* 2 i) (+ 2 (* 2 i))) 16)))
    out))

(defn- hex [^js b]
  (apply str (map (fn [x] (.padStart (.toString (bit-and x 0xff) 16) 2 "0")) (array-seq b))))

(deftest rfc5869-test-case-1-basic
  (async done
    (let [ikm (unhex (apply str (repeat 22 "0b")))
          salt (unhex "000102030405060708090a0b0c")
          info (unhex "f0f1f2f3f4f5f6f7f8f9")]
      (-> (hkdf/hkdf-extract salt ikm)
          (.then (fn [prk]
                   (is (= "077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5" (hex prk)))
                   (-> (hkdf/hkdf-expand prk info 42)
                       (.then (fn [okm]
                                (is (= "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"
                                       (hex okm)))
                                (-> (hkdf/hkdf salt ikm info 42)
                                    (.then (fn [okm2] (is (= (hex okm) (hex okm2))) (done)))))))))))))

(deftest rfc5869-test-case-2-longer-inputs
  (async done
    (let [ikm (unhex (apply str (map #(.padStart (.toString % 16) 2 "0") (range 0 80))))
          salt (unhex (apply str (map #(.padStart (.toString % 16) 2 "0") (range 0x60 (+ 0x60 80)))))
          info (unhex (apply str (map #(.padStart (.toString % 16) 2 "0") (range 0xb0 (+ 0xb0 80)))))]
      (-> (hkdf/hkdf-extract salt ikm)
          (.then (fn [prk]
                   (is (= "06a6b88c5853361a06104c9ceb35b45cef760014904671014a193f40c15fc244" (hex prk)))
                   (-> (hkdf/hkdf-expand prk info 82)
                       (.then (fn [okm]
                                (is (= (str "b11e398dc80327a1c8e7f78c596a4934"
                                            "4f012eda2d4efad8a050cc4c19afa97c"
                                            "59045a99cac7827271cb41c65e590e09"
                                            "da3275600c2f09b8367793a9aca3db71"
                                            "cc30c58179ec3e87c14c01d5c1f3434f1d87")
                                       (hex okm)))
                                (done))))))))))

(deftest rfc5869-test-case-3-zero-length-salt-and-info
  (async done
    (let [ikm (unhex (apply str (repeat 22 "0b")))
          salt (js/Uint8Array. 0)
          info (js/Uint8Array. 0)]
      (-> (hkdf/hkdf-extract salt ikm)
          (.then (fn [prk]
                   (is (= "19ef24a32c717b167f33a91d6f648bdf96596776afdb6377ac434c1c293ccb04" (hex prk)))
                   (-> (hkdf/hkdf-expand prk info 42)
                       (.then (fn [okm]
                                (is (= "8da4e775a563c18f715f802a063c5a31b8a11f5c5ee1879ec3454e5f3c738d2d9d201395faa4b61a96c8"
                                       (hex okm)))
                                (-> (hkdf/hkdf nil ikm nil 42)
                                    (.then (fn [okm2]
                                             (is (= (hex okm) (hex okm2)) "nil salt/info == zero-length salt/info")
                                             (done)))))))))))))

(deftest hkdf-expand-rejects-oversized-length
  (is (thrown? js/Error (hkdf/hkdf-expand (js/Uint8Array. 32) (js/Uint8Array. 0) (* 256 32)))))
