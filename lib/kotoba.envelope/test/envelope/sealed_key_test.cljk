(ns envelope.sealed-key-test
  "The framing both ends of a key delivery have to agree on before either has
  done any crypto — so the tests that matter are the ones where they don't."
  (:require [cljs.test :refer [deftest is testing async]]
            [envelope.kem :as kem]
            [envelope.sealed-key :as sk]
            [kotoba.signal.x25519 :as x25519]))

(defn- hybrid-recipient []
  (let [x (x25519/generate-keypair)
        pq (kem/generate-keypair)]
    {:pub (:pub x) :priv (:priv x) :pq-pub (:pub pq) :pq-priv (:priv pq)}))

(defn- bytes= [^js a ^js b]
  (and (= (.-length a) (.-length b))
       (every? #(= (aget a %) (aget b %)) (range (.-length a)))))

(defn- fails [p]
  (-> (js/Promise.resolve p) (.then (fn [_] false)) (.catch (fn [_] true))))

(def ^:private data-key (js/Uint8Array. 32))

(deftest a-sealed-key-round-trips-and-has-the-length-the-layout-says
  (async done
    (let [r (hybrid-recipient)]
      (-> (sk/seal-key data-key r "binding:one")
          (.then (fn [^js frame]
                   (is (= (+ 1 32 1088 12 (+ 32 16)) (.-length frame)))
                   (is (= sk/version (aget frame 0)))
                   (sk/open-key frame r "binding:one")))
          (.then (fn [opened]
                   (is (bytes= data-key opened))
                   (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest the-octet-vector-survives-the-value-codec-shape
  (async done
    (let [r (hybrid-recipient)]
      (-> (sk/seal-key data-key r "aad")
          (.then (fn [frame]
                   (let [octets (sk/octets frame)]
                     (testing "small integers, which both value codecs carry"
                       (is (vector? octets))
                       (is (every? #(and (integer? %) (<= 0 % 255)) octets)))
                     (sk/open-key (sk/from-octets octets) r "aad"))))
          (.then (fn [opened] (is (bytes= data-key opened)) (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest a-frame-does-not-open-under-another-binding
  (async done
    (let [r (hybrid-recipient)]
      (-> (sk/seal-key data-key r "binding:one")
          (.then (fn [frame] (fails (sk/open-key frame r "binding:two"))))
          (.then (fn [rejected] (is (true? rejected)) (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest a-frame-does-not-open-for-another-recipient
  (async done
    (let [alice (hybrid-recipient)
          bob (hybrid-recipient)]
      (-> (sk/seal-key data-key alice "aad")
          (.then (fn [frame]
                   (js/Promise.all
                    #js [(fails (sk/open-key frame bob "aad"))
                         (testing "substituting only the public key the opener claims
                                   is not enough, because it is in the transcript"
                           (fails (sk/open-key frame (assoc bob :pub (:pub alice)) "aad")))])))
          (.then (fn [[stranger claimed-pub]]
                   (is (true? stranger))
                   (is (true? claimed-pub))
                   (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest a-malformed-frame-is-refused-before-any-crypto
  (async done
    (let [r (hybrid-recipient)]
      (-> (js/Promise.all
           #js [(fails (sk/open-key (js/Uint8Array. 10) r "aad"))
                (fails (sk/open-key (js/Uint8Array. sk/version) r "aad"))
                (fails (sk/open-key (clj->js [1 2 3]) r "aad"))])
          (.then (fn [[short-frame empty-frame not-bytes]]
                   (testing "and it rejects rather than throwing, so a host with
                             only a .catch still fails closed"
                     (is (true? short-frame))
                     (is (true? empty-frame))
                     (is (true? not-bytes)))
                   (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest an-unknown-version-is-refused-rather-than-guessed
  (async done
    (let [r (hybrid-recipient)]
      (-> (sk/seal-key data-key r "aad")
          (.then (fn [^js frame]
                   (let [other (js/Uint8Array.from frame)]
                     (aset other 0 99)
                     (fails (sk/open-key other r "aad")))))
          (.then (fn [rejected] (is (true? rejected)) (done)))
          (.catch (fn [e] (is false (str e)) (done)))))))

(deftest a-flipped-byte-in-every-region-of-the-frame-is-caught
  ;; One offset per region, named. The first version of this test used a
  ;; literal 1200, which is PAST the end of a 1181-byte frame -- `aset` on a
  ;; typed array silently ignores an out-of-range index, so that case flipped
  ;; nothing and the frame opened, correctly. A corrupted-input test that
  ;; corrupts no input reports the same green as one that does, so the
  ;; offsets are computed from the layout now and asserted to be inside it.
  (async done
    (let [r (hybrid-recipient)]
      (-> (sk/seal-key data-key r "aad")
          (.then (fn [^js frame]
                   (let [len (.-length frame)
                         regions {:ephemeral-pub 1
                                  :ml-kem-ciphertext 40
                                  :iv (+ 1 32 1088 2)
                                  :wrapped (+ 1 32 1088 12 1)
                                  :tag (dec len)}]
                     (is (every? #(< % len) (vals regions))
                         (str "every offset must land inside the frame; length " len))
                     (-> (js/Promise.all
                          (clj->js
                           (for [[_ offset] (sort-by val regions)]
                             (let [other (js/Uint8Array.from frame)]
                               (aset other offset (bit-xor (aget other offset) 1))
                               (fails (sk/open-key other r "aad"))))))
                         (.then (fn [results]
                                  (is (= (count regions) (.-length results)))
                                  (is (every? true? (array-seq results))
                                      "every region of the frame is authenticated")
                                  (done)))))))
          (.catch (fn [e] (is false (str e)) (done)))))))
