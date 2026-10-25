(ns didwebvh.async-test
  "The async paths -- signing (`entry/sign-async`, `witness-proof-async`) and
   verification (`log/verify-async`, `didwebvh.subtle`) -- against the
   synchronous path with the same keys.

   Node's `crypto.subtle` implements Ed25519, so the WebCrypto signer a
   Cloudflare Worker would use is exercised for real here — the same seed,
   imported as PKCS#8, signs the same hashData — and the proof it yields must
   be byte-for-byte the one the pure in-process signer yields (Ed25519 is
   deterministic, so equality is the whole test, not merely verifiability).

   Not a `deftest`: cljs.test's `async` needs the `:end-run-tests` report
   plumbing, which the nbb harness does not have (a run with an async test
   returns nil — exactly the shape of \"nothing ran\" the harness refuses).
   `run` returns a Promise of the failure count and the harness chains it
   after the synchronous suite. ClojureScript only, by construction."
  (:require [didwebvh.entry :as entry]
            [didwebvh.hash :as h]
            [didwebvh.log :as log]
            [didwebvh.signer :as signer]
            [didwebvh.subtle :as subtle]))

(def seed (vec (map #(bit-and (* 11 %) 0xff) (range 32))))
(def pkcs8-prefix [0x30 0x2e 0x02 0x01 0x00 0x30 0x05 0x06 0x03 0x2b 0x65 0x70 0x04 0x22 0x04 0x20])

(defn- webcrypto-signer
  "`{:multikey :sign-fn}` whose sign-fn is crypto.subtle.sign over a
   non-extractable key imported from the seed's PKCS#8 form."
  [multikey]
  (-> (js/crypto.subtle.importKey "pkcs8" (js/Uint8Array.from (clj->js (into pkcs8-prefix seed)))
                                  #js {:name "Ed25519"} false #js ["sign"])
      (.then (fn [key]
               {:multikey multikey
                :sign-fn (fn [hash-data]
                           (-> (js/crypto.subtle.sign "Ed25519" key (js/Uint8Array.from (clj->js hash-data)))
                               (.then #(js/Uint8Array. %))))}))))


;; ── verification ─────────────────────────────────────────────────────────────
;;
;; Under nbb the pure verifier costs about sixteen seconds per signature on a
;; loaded machine, so a twelve-signature log cannot be its own oracle here.
;; The claim is split in two and each half is measured:
;;
;;   1. the two-pass mechanism reproduces single-pass `verify` exactly, for
;;      the SAME injected verdicts -- no cryptography involved, so every
;;      interesting verdict pattern is affordable;
;;   2. WebCrypto agrees with the pure verifier on real signatures -- measured
;;      end to end on the one-entry log this file already signs, where the
;;      whole result map must be equal, not merely both true.

(defn- ubytes [x] (mapv #(bit-and (int %) 0xff) (seq x)))

(defn- wc-signer
  "A signer in `didwebvh.signer`'s shape whose key the platform generates:
   `signer/from-seed` would do a pure keygen per witness, which is seconds
   each here and is not what this file is measuring."
  []
  (-> (js/crypto.subtle.generateKey #js {:name "Ed25519"} true #js ["sign" "verify"])
      (.then (fn [kp]
               (-> (js/crypto.subtle.exportKey "raw" (.-publicKey kp))
                   (.then (fn [raw]
                            (let [pub (vec (array-seq (js/Uint8Array. raw)))]
                              {:multikey (signer/multikey pub)
                               :did-key (signer/did-key pub)
                               :public-key pub
                               :sign-fn (fn [hash-data]
                                          (-> (js/crypto.subtle.sign
                                               #js {:name "Ed25519"} (.-privateKey kp)
                                               (js/Uint8Array.from (clj->js hash-data)))
                                              (.then #(js/Uint8Array. %))))})))))))) 

(defn- witnessed-log
  "Two versions, 3-of-5 witnesses, pre-rotation active: twelve signatures,
   all made by WebCrypto."
  []
  (-> (js/Promise.all (into-array (repeatedly 8 wc-signer)))
      (.then
       (fn [signers]
         (let [[u1 u2 u3 & ws] (vec (array-seq signers))
               witness-param {"threshold" 3
                              "witnesses" (mapv (fn [w] {"id" (:did-key w)}) ws)}
               unsigned (entry/genesis
                         {:version-time "2026-09-01T00:00:00Z"
                          :parameters {"method" h/method-1-0
                                       "scid" h/scid-placeholder
                                       "updateKeys" [(:multikey u1)]
                                       "nextKeyHashes" [(h/key-hash (:multikey u2))]
                                       "portable" false
                                       "witness" witness-param}
                          :state {"@context" ["https://www.w3.org/ns/did/v1"]
                                  "id" (str "did:webvh:" h/scid-placeholder ":async.example")}})]
           (-> (entry/sign-async unsigned u1)
               (.then
                (fn [v1]
                  (-> (entry/sign-async
                       (entry/next-entry v1 {:version-time "2026-09-02T00:00:00Z"
                                             :parameters {"updateKeys" [(:multikey u2)]
                                                          "nextKeyHashes" [(h/key-hash (:multikey u3))]}
                                             :state (get v1 "state")})
                       u2)
                      (.then
                       (fn [v2]
                         (-> (js/Promise.all
                              (into-array
                               (concat (map #(entry/witness-proof-async (get v1 "versionId") %) ws)
                                       (map #(entry/witness-proof-async (get v2 "versionId") %) ws))))
                             (.then (fn [proofs]
                                      (let [proofs (vec (array-seq proofs))]
                                        {:entries [v1 v2]
                                         :witnesses (vec ws)
                                         :witness-file
                                         [{"versionId" (get v1 "versionId") "proof" (subvec proofs 0 5)}
                                          {"versionId" (get v2 "versionId")
                                           "proof" (subvec proofs 5 10)}]}))))))))))))))) 

(defn- verify-checks
  "`genesis` is the one-entry log the signing half already built, and
   `genesis-sync` the result the pure verifier gave for it."
  [check! genesis genesis-sync]
  (-> (witnessed-log)
      (.then
       (fn [{:keys [entries witness-file witnesses]}]
         (let [now 1830000000
               base {:witness-file witness-file :now now}
               sync-with (fn [f] (log/verify entries (assoc base :verify-signature f)))
               async-with (fn [f] (log/verify-async
                                   entries (assoc base :verify-signature-async
                                                  (fn [& args] (js/Promise.resolve (apply f args))))))
               ;; refuse exactly the witnesses whose public keys are named
               refusing (fn [ws] (let [bad (set (map (comp ubytes :public-key) ws))]
                                   (fn [pub _ _] (not (contains? bad (ubytes pub))))))
               patterns [["every signature accepted" (constantly true)]
                         ["every signature refused" (constantly false)]
                         ["two witnesses refused (threshold still met)" (refusing (take 2 witnesses))]
                         ["three witnesses refused (threshold unmet)" (refusing (take 3 witnesses))]]]
           (-> (js/Promise.all
                (into-array (map (fn [[_ f]] (async-with f)) patterns)))
               (.then
                (fn [async-results]
                  (doseq [[[label f] actual] (map vector patterns (array-seq async-results))]
                    (check! (str "verify-async reproduces verify: " label)
                            (= (sync-with f) actual)
                            (pr-str [(:error (sync-with f)) (:error actual)])))
                  ;; the patterns must not all mean the same thing, or the
                  ;; equalities above are four copies of one measurement
                  (let [errors (mapv #(:error (sync-with (second %))) patterns)]
                    (check! "the four patterns reach four different verdicts"
                            (= [nil :didwebvh/unauthorized-entry nil :didwebvh/witness-threshold-unmet]
                               errors)
                            (pr-str errors)))
                  (log/verify-async entries (assoc base :verify-signature-async
                                                   subtle/verify-signature))))
               (.then
                (fn [real]
                  (check! "WebCrypto resolves the two-version witnessed log"
                          (and (:ok? real) (= 2 (count (:versions real))))
                          (pr-str (dissoc real :state :versions)))
                  (let [swapped (assoc-in entries [1 "proof" 0 "proofValue"]
                                          (get-in witness-file [1 "proof" 0 "proofValue"]))]
                    (log/verify-async (assoc entries 1 (nth swapped 1))
                                      (assoc base :verify-signature-async subtle/verify-signature)))))
               (.then
                (fn [tampered]
                  (check! "WebCrypto refuses an entry whose proof was replaced"
                          (= :didwebvh/unauthorized-entry (:error tampered))
                          (pr-str (:error tampered)))
                  ;; A verifier that cannot answer must not be read as a
                  ;; verifier that answered "invalid".
                  (-> (log/verify-async entries
                                        (assoc base :verify-signature-async
                                               (fn [& _] (js/Promise.reject (js/Error. "no Ed25519 here")))))
                      (.then (fn [r]
                               (check! "a verifier that cannot run must not report a verdict" false
                                       (pr-str r))))
                      (.catch (fn [e]
                                (check! "a verifier that cannot run rejects rather than returning :ok? false"
                                        (= "no Ed25519 here" (.-message e)) (str e)))))))
               (.then
                (fn []
                  ;; the second half: WebCrypto and the pure verifier agree on
                  ;; a real signature, whole result map against whole result map
                  (log/verify-async [genesis] {:now 1800000000
                                               :verify-signature-async subtle/verify-signature})))
               (.then
                (fn [async-genesis]
                  (check! "verify-async (WebCrypto) equals verify (pure Ed25519) on a signed log"
                          (= genesis-sync async-genesis)
                          (pr-str [(:error genesis-sync) (:error async-genesis)]))))))))))

(defn run
  "Promise of the number of failed checks (0 = pass). Prints each check."
  []
  (let [failures (atom 0)
        signed (atom nil)
        signed-verified (atom nil)
        check! (fn [label ok? & [detail]]
                 (if ok? (println "ok  -" label)
                     (do (println "FAIL-" label (or detail "")) (swap! failures inc))))
        sync-signer (signer/from-seed seed)
        unsigned (entry/genesis {:version-time "2026-09-02T00:00:00Z"
                                 :parameters {"method" h/method-1-0
                                              "scid" h/scid-placeholder
                                              "updateKeys" [(:multikey sync-signer)]
                                              "portable" false}
                                 :state {"@context" ["https://www.w3.org/ns/did/v1"]
                                         "id" (str "did:webvh:" h/scid-placeholder ":async.example")}})
        expected (entry/sign unsigned sync-signer)]
    (-> (webcrypto-signer (:multikey sync-signer))
        (.then (fn [wc]
                 (-> (entry/sign-async unsigned wc)
                     (.then (fn [actual]
                              (check! "sign-async (WebCrypto) reproduces sign (pure) byte for byte"
                                      (= expected actual)
                                      (pr-str [(get-in expected ["proof" 0 "proofValue"])
                                               (get-in actual ["proof" 0 "proofValue"])]))
                              (reset! signed actual)
                              (reset! signed-verified (log/verify [actual] {:now 1800000000}))
                              (check! "the resolver accepts the async-signed genesis"
                                      (:ok? @signed-verified))
                              (entry/witness-proof-async (get actual "versionId") wc)))
                     (.then (fn [wp]
                              (check! "witness-proof-async likewise"
                                      (= (entry/witness-proof (get expected "versionId") sync-signer) wp)))))))
        (.catch (fn [e] (check! "async signing threw" false (str e))))
        (.then (fn [] (verify-checks check! @signed @signed-verified)))
        (.catch (fn [e] (check! "async verification threw" false (str e))))
        (.then (fn [] @failures)))))
