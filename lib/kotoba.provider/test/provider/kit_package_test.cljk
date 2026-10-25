(ns provider.kit-package-test
  (:require [clojure.edn :as edn]
            [kotoba.lang.text :as str]
            [clojure.java.io :as io]
            [clojure.test :refer [deftest is testing]]
            [ed25519.core :as ed]
            [provider.kit-package :as kit]))

(deftest sha256-hex-stable
  (is (= "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
         (kit/sha256-hex "")))
  (is (= (kit/sha256-hex "abc") (kit/sha256-hex "abc")))
  (is (not= (kit/sha256-hex "abc") (kit/sha256-hex "abd"))))

(deftest package-digest-unsigned
  (let [d (kit/package-digest "{:a 1}\n")]
    (is (= :sha256 (:alg d)))
    (is (false? (:signed? d)))
    (is (string? (:digest d)))
    (is (= 64 (count (:digest d))))))

(deftest secret-kit-receipt-not-production-signed
  (let [path "kotoba/lang/capability-kits/secret-v1.edn"
        text (slurp (io/resource path))
        rec (kit/kit-package-receipt :secret path text)]
    (is (= :secret (:kit-name rec)))
    (is (false? (:signed? (:package rec))))
    (is (false? (:production-signed-claim? rec)))
    ;; ADR 0166: inventory marks signed package path ready; unsigned receipt still not a claim.
    (is (= :ready (get-in rec [:qualification :signed-content-addressed-package])))))

(deftest readiness-table-http-secret-process
  (let [table (kit/readiness-table
               (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        http (kit/readiness-for table :http)
        secret (kit/readiness-for table :secret)
        process (kit/readiness-for table :process)]
    (is (= 1 (:kotoba.kit-readiness/version table)))
    (is (= :ready (get-in http [:scores :package])))
    ;; ADR 0165/0166: http + secret Components flip signed-wasm ready.
    (is (= :ready (get-in http [:scores :signed-wasm])))
    (is (= :ready (get-in secret [:scores :signed-wasm])))
    (is (true? (kit/production-signed-allowed? http)))
    (is (true? (kit/production-signed-allowed? secret)))
    (is (true? (kit/production-signed-allowed? process))
        "ADR 0168 process signed-wasm ready")
    (let [path "kotoba/lang/capability-kits/http-v1.edn"
          text (slurp (io/resource path))
          pkg (kit/kit-package-receipt :http path text)
          rr (kit/readiness-receipt http pkg)]
      (is (= (:digest (:package pkg)) (:package-digest rr)))
      ;; ADR 0165: readiness signed-wasm ready for http → claim allowed once
      ;; readiness gate alone is considered (unsigned receipts still noted elsewhere).
      (is (true? (:production-signed-claim-allowed? rr))))))


(deftest readiness-object-deny-fixtures-0272
  "ADR 0272: object deny-fixtures :ready after pure validate-*."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        object (kit/readiness-for table :object)]
    (is (= :ready (get-in object [:scores :deny-fixtures])))
    (is (= :ready (get-in object [:scores :audit])))
    (is (re-find #"0272" (:kotoba.kit-readiness/summary table)))))

(deftest readiness-ops-audit-ready-after-edn-wire
  "ADR 0269: ops kits with EDN audit wire score audit :ready; entropy stays :n/a."
  (let [table (kit/readiness-table
               (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))]
    (doseq [n [:http :secret :process :scoped-fs :git]]
      (is (= :ready (get-in (kit/readiness-for table n) [:scores :audit]))
          (str n)))
    (is (= :n/a (get-in (kit/readiness-for table :entropy) [:scores :audit])))
    (is (re-find #"0269|audit ready" (:kotoba.kit-readiness/summary table)))))

(deftest readiness-object-storage-audit-ready
  "ADR 0271: object/storage audit :ready via mem + production on-call."
  (let [table (kit/readiness-table
               (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))]
    (is (= :ready (get-in (kit/readiness-for table :object) [:scores :audit])))
    (is (= :ready (get-in (kit/readiness-for table :storage) [:scores :audit])))
    (is (re-find #"0271" (:kotoba.kit-readiness/summary table)))))

(deftest readiness-object-storage-signed-wasm-0275
  "ADR 0275: object/storage signed-wasm :ready + Component packaging gate."
  (let [table (kit/readiness-table
               (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        pkg (kit/load-wasm-packages-table)
        object (kit/readiness-for table :object)
        storage (kit/readiness-for table :storage)
        o-comp (kit/wasm-package-for pkg :object-digest-len-component)
        s-comp (kit/wasm-package-for pkg :storage-value-len-component)
        o-bytes (-> (io/resource (:resource o-comp)) io/input-stream .readAllBytes)
        s-bytes (-> (io/resource (:resource s-comp)) io/input-stream .readAllBytes)]
    (is (= :ready (get-in object [:scores :signed-wasm])))
    (is (= :ready (get-in storage [:scores :signed-wasm])))
    (is (true? (kit/production-signed-allowed? object)))
    (is (true? (kit/production-signed-allowed? storage)))
    (is (true? (kit/ops-network-kit? object)))
    (is (true? (kit/ops-network-kit? storage)))
    (is (true? (kit/ops-signed-wasm-ready-allowed? object o-comp o-bytes)))
    (is (true? (kit/ops-signed-wasm-ready-allowed? storage s-comp s-bytes)))
    (is (re-find #"0275" (:kotoba.kit-readiness/summary table)))))



(deftest readiness-covers-t8-critical-kits
  (let [table (kit/readiness-table
               (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        names (set (map :name (:kits table)))]
    (doseq [n [:http :secret :process :scoped-fs :object :storage]]
      (is (contains? names n) (str n)))))

(deftest readiness-lists-secret-and-fs-path-ok-components
  "ADR 0206/0207/0208: inventory must list pure Component twins (not only typed modules)."
  (let [table (kit/readiness-table
               (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        secret (kit/readiness-for table :secret)
        fs (kit/readiness-for table :scoped-fs)
        secret-ev (set (:evidence secret))
        fs-ev (set (:evidence fs))]
    (is (some #(re-find #"secret-name-ok-v1\.component\.wasm" %) secret-ev)
        "secret readiness must list ADR 0206 Component")
    (is (some #(re-find #"ADR 0206" %) secret-ev))
    (is (some #(re-find #"fs-path-ok-v1\.component\.wasm" %) fs-ev)
        "scoped-fs readiness must list ADR 0207 Component")
    (is (some #(re-find #"ADR 0207" %) fs-ev))
    (is (re-find #"0206|0207" (:kotoba.kit-readiness/summary table)))))

(deftest signing-input-canonical
  (is (= "kotoba.kit-package.signed/v1\nsha256\nabc\npath/x.edn\n"
         (kit/signing-input {:digest "abc" :resource "path/x.edn"}))))

(deftest signed-kit-receipt-round-trip
  (let [path "kotoba/lang/capability-kits/secret-v1.edn"
        text (slurp (io/resource path))
        unsigned (kit/kit-package-receipt :secret path text)
        {:keys [sign verify]} (kit/test-hmac-signer "test-secret-key")
        signed (kit/sign-kit-package-receipt unsigned sign)
        v (kit/verify-kit-package-receipt signed verify)]
    (is (true? (:signed-kit-receipt? signed)))
    (is (true? (get-in signed [:package :signed?])))
    (is (false? (:signed-wasm-provider? signed)))
    (is (false? (:production-signed-claim? signed)))
    (is (true? (:ok? v)))
    (is (= :signed-kit-edn-receipt (:layer v)))
    (is (false? (:signed-wasm-provider? v)))
    (is (= (get-in unsigned [:package :digest]) (:digest v)))))

(deftest signed-kit-receipt-rejects-forgery
  (let [path "kotoba/lang/capability-kits/http-v1.edn"
        text (slurp (io/resource path))
        unsigned (kit/kit-package-receipt :http path text)
        a (kit/test-hmac-signer "key-a")
        b (kit/test-hmac-signer "key-b")
        signed (kit/sign-kit-package-receipt unsigned (:sign a))
        bad (kit/verify-kit-package-receipt signed (:verify b))
        tampered (assoc-in signed [:package :digest] (kit/sha256-hex "nope"))
        bad2 (kit/verify-kit-package-receipt tampered (:verify a))]
    (is (false? (:ok? bad)))
    (is (= :bad-signature (:reason bad)))
    (is (false? (:ok? bad2)))
    (is (= :signing-input-mismatch (:reason bad2)))))

(deftest readiness-still-blocks-production-claim-after-signed-kit
  "Readiness gate may be ready (ADR 0166); kit EDN receipt alone still does not
  produce a production signed Wasm claim (needs signed non-fixture wasm receipt)."
  (let [table (kit/readiness-table
               (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        secret (kit/readiness-for table :secret)
        path "kotoba/lang/capability-kits/secret-v1.edn"
        text (slurp (io/resource path))
        {:keys [sign]} (kit/test-hmac-signer "k")
        signed (kit/sign-kit-package-receipt
                (kit/kit-package-receipt :secret path text) sign)
        rr (kit/readiness-receipt secret signed)]
    (is (true? (:signed-kit-receipt? rr)))
    (is (true? (:production-signed-claim-allowed? rr))
        "readiness signed-wasm ready (inventory)")
    (is (false? (:production-signed-claim? rr))
        "kit EDN alone is not a production signed Wasm claim")
    (is (seq (:package-blockers rr)))))

(deftest empty-wasm-module-digest-stable
  (let [d (kit/wasm-artifact-digest kit/empty-wasm-module-bytes :fixture-synthetic)]
    (is (= :sha256 (:alg d)))
    (is (= 64 (count (:digest d))))
    (is (= :fixture-synthetic (:artifact-kind d)))
    (is (false? (:signed? d)))
    ;; magic\0asm + version is fixed → stable digest
    (is (= (kit/sha256-hex-bytes kit/empty-wasm-module-bytes) (:digest d)))))

(deftest wasm-signing-input-canonical
  (is (= (str "kotoba.kit-package.wasm-signed/v1\n"
              "sha256\n"
              "deadbeef\n"
              "kotoba/lang/capability-kits/secret-v1.edn\n"
              "application/wasm\n"
              "fixture-synthetic\n"
              "kitdig\n")
         (kit/wasm-signing-input
          {:digest "deadbeef"
           :resource "kotoba/lang/capability-kits/secret-v1.edn"
           :media-type "application/wasm"
           :artifact-kind :fixture-synthetic
           :kit-edn-digest "kitdig"}))))

(deftest signed-wasm-provider-receipt-round-trip
  (let [path "kotoba/lang/capability-kits/secret-v1.edn"
        text (slurp (io/resource path))
        kit-rec (kit/kit-package-receipt :secret path text)
        unsigned (-> (kit/wasm-provider-receipt
                      :secret path kit/empty-wasm-module-bytes
                      {:artifact-kind :fixture-synthetic})
                     (kit/chain-kit-and-wasm-receipts kit-rec))
        {:keys [sign verify]} (kit/test-hmac-signer "wasm-test-key")
        signed (kit/sign-wasm-provider-receipt unsigned sign)
        v (kit/verify-wasm-provider-receipt signed verify)]
    (is (true? (:signed-wasm-provider? signed)))
    (is (true? (:fixture? signed)))
    (is (false? (:production-signed-claim? signed)))
    (is (= (get-in kit-rec [:package :digest]) (:kit-edn-digest signed)))
    (is (true? (:ok? v)))
    (is (= :signed-wasm-provider-receipt (:layer v)))
    (is (true? (:fixture? v)))
    (is (false? (:production-signed-claim? v)))))

(deftest signed-wasm-receipt-rejects-forgery
  (let [path "kotoba/lang/capability-kits/http-v1.edn"
        unsigned (kit/wasm-provider-receipt
                  :http path kit/empty-wasm-module-bytes
                  {:artifact-kind :fixture-synthetic})
        a (kit/test-hmac-signer "key-a")
        b (kit/test-hmac-signer "key-b")
        signed (kit/sign-wasm-provider-receipt unsigned (:sign a))
        bad (kit/verify-wasm-provider-receipt signed (:verify b))
        tampered (assoc-in signed [:artifact :digest] (kit/sha256-hex "nope"))
        bad2 (kit/verify-wasm-provider-receipt tampered (:verify a))]
    (is (false? (:ok? bad)))
    (is (= :bad-signature (:reason bad)))
    (is (false? (:ok? bad2)))
    (is (= :signing-input-mismatch (:reason bad2)))))

(deftest readiness-still-blocks-after-signed-wasm-fixture
  (let [table (kit/readiness-table
               (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        secret (kit/readiness-for table :secret)
        path "kotoba/lang/capability-kits/secret-v1.edn"
        text (slurp (io/resource path))
        {:keys [sign]} (kit/test-hmac-signer "k")
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :secret path text) sign)
        wasm-signed (kit/sign-wasm-provider-receipt
                     (kit/chain-kit-and-wasm-receipts
                      (kit/wasm-provider-receipt
                       :secret path kit/empty-wasm-module-bytes
                       {:artifact-kind :fixture-synthetic})
                      kit-signed)
                     sign)
        rr (kit/readiness-receipt secret kit-signed wasm-signed)]
    (is (true? (:signed-kit-receipt? rr)))
    (is (true? (:signed-wasm-provider? rr)))
    (is (true? (:wasm-fixture? rr)))
    (is (string? (:wasm-artifact-digest rr)))
    (is (= :ready (get-in secret [:scores :signed-wasm]))
        "inventory ready under ADR 0166")
    (is (true? (:production-signed-claim-allowed? rr))
        "readiness gate alone")
    (is (false? (:production-signed-claim? rr))
        "fixture signed Wasm must not open production-signed claim")
    (is (some #{:wasm-artifact-is-fixture} (:package-blockers rr)))))

(deftest hex-encode-decode-round-trip
  (let [raw (byte-array (map unchecked-byte [0 1 255 16]))
        h (kit/hex-encode raw)]
    (is (= "0001ff10" h))
    (is (= (seq raw) (seq (kit/hex-decode h))))))

(deftest fixture-wasm-matches-empty-module
  (let [fix (kit/load-fixture-wasm-bytes)]
    (is (= (seq kit/empty-wasm-module-bytes) (seq fix)))
    (is (= (kit/sha256-hex-bytes kit/empty-wasm-module-bytes)
           (kit/sha256-hex-bytes fix)))))

(deftest identity-signer-kit-receipt-round-trip
  "Production-shaped inject: host supplies byte sign/verify; kit-package
   normalises to string receipt API."
  (let [pub (byte-array (map unchecked-byte (range 32)))
        secret "host-identity-seed"
        sign-bytes (fn [msg-bytes]
                     (let [msg (String. ^bytes msg-bytes java.nio.charset.StandardCharsets/UTF_8)]
                       (kit/hex-decode (kit/hmac-sha256-hex secret msg))))
        verify-bytes (fn [msg-bytes _pub sig-bytes]
                       (let [msg (String. ^bytes msg-bytes java.nio.charset.StandardCharsets/UTF_8)
                             expected (kit/hex-decode (kit/hmac-sha256-hex secret msg))]
                         (= (seq expected) (seq sig-bytes))))
        id (kit/identity-signer {:sign-bytes sign-bytes
                                 :verify-bytes verify-bytes
                                 :public-key-bytes pub
                                 :alg :ed25519
                                 :key-id "test-identity"})
        path "kotoba/lang/capability-kits/secret-v1.edn"
        text (slurp (io/resource path))
        signed (kit/sign-kit-package-receipt
                (kit/kit-package-receipt :secret path text)
                (:sign id))
        v (kit/verify-kit-package-receipt signed (:verify id))
        wasm (kit/sign-wasm-provider-receipt
              (kit/wasm-provider-receipt
               :secret path (kit/load-fixture-wasm-bytes)
               {:artifact-kind :fixture-synthetic
                :kit-edn-digest (get-in signed [:package :digest])})
              (:sign id))
        vw (kit/verify-wasm-provider-receipt wasm (:verify id))]
    (is (= :ed25519 (get-in signed [:signature :alg])))
    (is (= "test-identity" (get-in signed [:signature :key-id])))
    (is (true? (:ok? v)))
    (is (true? (:ok? vw)))
    (is (true? (:fixture? vw)))
    (is (false? (:production-signed-claim? signed)))))

(deftest ed25519-identity-signer-kit-and-wasm
  "Real Ed25519 (org-ietf-ed25519, test dep) injected via identity-signer."
  (let [seed (byte-array 32)
        _ (dotimes [i 32] (aset-byte seed i (unchecked-byte i)))
        pub (ed/pubkey-from-seed seed)
        id (kit/identity-signer
            {:sign-bytes (fn [msg] (ed/sign seed msg))
             :verify-bytes (fn [msg pub-b sig] (ed/verify pub-b msg sig))
             :public-key-bytes pub
             :alg :ed25519
             :key-id "ed25519-test"})
        path "kotoba/lang/capability-kits/http-v1.edn"
        text (slurp (io/resource path))
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :http path text)
                    (:sign id))
        v (kit/verify-kit-package-receipt kit-signed (:verify id))
        wasm (kit/sign-wasm-provider-receipt
              (kit/chain-kit-and-wasm-receipts
               (kit/wasm-provider-receipt
                :http path (kit/load-fixture-wasm-bytes)
                {:artifact-kind :fixture-synthetic})
               kit-signed)
              (:sign id))
        vw (kit/verify-wasm-provider-receipt wasm (:verify id))]
    (is (true? (:ok? v)))
    (is (= :ed25519 (get-in kit-signed [:signature :alg])))
    (is (true? (:ok? vw)))
    (is (false? (:production-signed-claim? kit-signed)))
    ;; ADR 0165: inventory flips http signed-wasm ready; fixture receipts still non-production.
    (is (= :ready
           (get-in (kit/readiness-for
                    (kit/readiness-table
                     (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
                    :http)
                   [:scores :signed-wasm])))))

(deftest package-manifest-blocks-fixture-production-claim
  (let [table (kit/readiness-table
               (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        secret (kit/readiness-for table :secret)
        path "kotoba/lang/capability-kits/secret-v1.edn"
        text (slurp (io/resource path))
        {:keys [sign]} (kit/test-hmac-signer "manifest-key")
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :secret path text) sign)
        wasm-signed (kit/sign-wasm-provider-receipt
                     (kit/chain-kit-and-wasm-receipts
                      (kit/wasm-provider-receipt
                       :secret path (kit/load-fixture-wasm-bytes)
                       {:artifact-kind :fixture-synthetic})
                      kit-signed)
                     sign)
        m (kit/package-manifest
           {:kit-name :secret
            :kit-resource path
            :kit-receipt kit-signed
            :wasm-receipt wasm-signed
            :readiness-row secret})
        rr (kit/readiness-receipt secret kit-signed wasm-signed)]
    (is (= :kotoba.kit-package.manifest/v1 (:format m)))
    (is (true? (get-in m [:layers :kit-edn :signed?])))
    (is (true? (get-in m [:layers :wasm :signed?])))
    (is (true? (get-in m [:layers :wasm :fixture?])))
    (is (false? (:production-signed-claim? m)))
    ;; ADR 0166: secret readiness is ready → no signed-wasm-not-ready blocker;
    ;; fixture still blocks production claim.
    (is (not-any? #{:signed-wasm-not-ready} (:blockers m)))
    (is (some #{:wasm-artifact-is-fixture} (:blockers m)))
    (is (false? (:production-signed-claim? rr)))
    (is (seq (:package-blockers rr)))))

(deftest wasm-packages-registry-hash-sha256
  (let [table (kit/load-wasm-packages-table)
        entry (kit/wasm-package-for table :hash-sha256)
        bytes (kit/load-wasm-package-bytes (:resource entry))]
    (is (= 1 (:kotoba.wasm-packages/version table)))
    (is (some? entry))
    (is (false? (:fixture? entry)))
    (is (= :wasm-module (:artifact-kind entry)))
    (is (= 64 (count (:sha256 entry))))
    (is (true? (kit/verify-wasm-package-digest entry bytes)))
    (is (= (:sha256 entry) (kit/sha256-hex-bytes bytes)))
    ;; magic \0asm
    (is (= [0x00 0x61 0x73 0x6d] (map #(bit-and % 0xff) (take 4 bytes))))
    (is (not= (seq kit/empty-wasm-module-bytes) (seq bytes))
        "real package must not be empty-module fixture")))

(deftest real-wasm-provider-receipt-not-fixture
  (let [table (kit/load-wasm-packages-table)
        entry (kit/wasm-package-for table :hash-sha256)
        bytes (kit/load-wasm-package-bytes (:resource entry))
        rec (kit/real-wasm-provider-receipt entry bytes)]
    (is (= :hash-sha256 (:name rec)))
    (is (= :wasm-module (:artifact-kind rec)))
    (is (false? (:fixture? rec)))
    (is (false? (:signed-wasm-provider? rec)))
    (is (false? (:production-signed-claim? rec)))
    (is (= (:sha256 entry) (get-in rec [:artifact :digest])))))

(deftest real-wasm-rejects-digest-mismatch
  (let [table (kit/load-wasm-packages-table)
        entry (kit/wasm-package-for table :hash-sha256)]
    (is (thrown-with-msg? clojure.lang.ExceptionInfo #"digest mismatch"
          (kit/real-wasm-provider-receipt entry kit/empty-wasm-module-bytes)))))

(deftest package-manifest-real-wasm-production-claim-under-publisher-policy
  "ADR 0161: pure-allowlist real wasm + signed receipts + readiness
   :signed-wasm :ready → production-signed-claim; fixture blocker stays clear."
  (let [table (kit/readiness-table
               (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        row (kit/readiness-for table :hash-sha256)
        path "kotoba/lang/capability-kits/hash-sha256-v1.edn"
        text (slurp (io/resource path))
        pkg-table (kit/load-wasm-packages-table)
        entry (kit/wasm-package-for pkg-table :hash-sha256)
        bytes (kit/load-wasm-package-bytes (:resource entry))
        {:keys [sign]} (kit/test-hmac-signer "real-wasm-key")
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :hash-sha256 path text) sign)
        wasm-signed (kit/sign-wasm-provider-receipt
                     (kit/chain-kit-and-wasm-receipts
                      (kit/real-wasm-provider-receipt entry bytes)
                      kit-signed)
                     sign)
        m (kit/package-manifest
           {:kit-name :hash-sha256
            :kit-resource path
            :kit-receipt kit-signed
            :wasm-receipt wasm-signed
            :readiness-row row})
        rr (kit/readiness-receipt row kit-signed wasm-signed)]
    (is (some? row))
    (is (= :ready (get-in row [:scores :signed-wasm])))
    (is (true? (kit/pure-allowlist-publisher-policy-satisfied? row entry bytes)))
    (is (true? (get-in m [:layers :kit-edn :signed?])))
    (is (true? (get-in m [:layers :wasm :signed?])))
    (is (false? (get-in m [:layers :wasm :fixture?])))
    (is (= :wasm-module (get-in m [:layers :wasm :artifact-kind])))
    (is (true? (:production-signed-claim? m)))
    (is (empty? (:blockers m)))
    (is (not-any? #{:wasm-artifact-is-fixture} (:blockers m))
        "real wasm must clear fixture blocker")
    (is (not-any? #{:kit-edn-receipt-unsigned :wasm-receipt-unsigned} (:blockers m)))
    (is (false? (:wasm-fixture? rr)))
    (is (true? (:production-signed-claim? rr)))
    (is (empty? (:package-blockers rr)))))

(deftest readiness-covers-hash-sha256-pilot
  (let [table (kit/readiness-table
               (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        names (set (map :name (:kits table)))]
    (is (contains? names :hash-sha256))))

(deftest pure-allowlist-wasm-packages-all-digest-match
  (let [table (kit/load-wasm-packages-table)
        ;; Exclude ops kit packaging classes (:ops, :ops-network, :ops-process,
        ;; :ops-git, …). Pure-allowlist packages have nil :class.
        pure (filterv (fn [e]
                        (let [c (:class e)]
                          (not (and c (or (= c :ops)
                                          (.startsWith (name c) "ops-"))))))
                      (:packages table))]
    (is (= 8 (count pure)))
    (is (<= 16 (count (:packages table))))
    (doseq [entry pure]
      (let [bytes (kit/load-wasm-package-bytes (:resource entry))]
        (is (false? (:fixture? entry)) (str (:name entry)))
        (is (true? (kit/verify-wasm-package-digest entry bytes))
            (str (:name entry) " digest"))
        (is (= [0x00 0x61 0x73 0x6d]
               (map #(bit-and % 0xff) (take 4 bytes)))
            (str (:name entry) " wasm magic"))))))

(deftest pure-allowlist-publisher-policy
  (let [readiness (kit/readiness-table
                   (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        row (kit/readiness-for readiness :math-sin)
        secret (kit/readiness-for readiness :secret)
        pkg-table (kit/load-wasm-packages-table)
        entry (kit/wasm-package-for pkg-table :math-sin)
        bytes (kit/load-wasm-package-bytes (:resource entry))]
    (is (true? (kit/pure-allowlist-kit? row)))
    (is (false? (kit/pure-allowlist-kit? secret)))
    (is (true? (kit/pure-allowlist-publisher-policy-satisfied? row entry bytes)))
    (is (false? (kit/pure-allowlist-publisher-policy-satisfied? secret)))
    (is (= :ready (get-in row [:scores :signed-wasm])))
    ;; ADR 0166: secret inventory may be ready via Component; pure-allowlist path still false.
    (is (false? (kit/pure-allowlist-kit? secret)))
    (is (true? (kit/production-signed-allowed? row)))
    (is (true? (kit/production-signed-allowed? secret))
        "secret signed-wasm ready under ADR 0166 inventory")))

(deftest grant-binding-host-admissible-pure-allowlist
  "Signed real wasm + kit receipts → host-admissible grant binding;
   ADR 0161: pure-allowlist production-admissible when readiness signed-wasm ready."
  (let [readiness (kit/readiness-table
                   (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        row (kit/readiness-for readiness :math-sin)
        path "kotoba/lang/capability-kits/math-sin-v1.edn"
        text (slurp (io/resource path))
        pkg-table (kit/load-wasm-packages-table)
        entry (kit/wasm-package-for pkg-table :math-sin)
        bytes (kit/load-wasm-package-bytes (:resource entry))
        {:keys [sign]} (kit/test-hmac-signer "grant-bind-key")
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :math-sin path text) sign)
        wasm-signed (kit/sign-wasm-provider-receipt
                     (kit/chain-kit-and-wasm-receipts
                      (kit/real-wasm-provider-receipt entry bytes)
                      kit-signed)
                     sign)
        m (kit/package-manifest
           {:kit-name :math-sin
            :kit-resource path
            :kit-receipt kit-signed
            :wasm-receipt wasm-signed
            :readiness-row row})
        gb (kit/grant-binding
            {:kit-name :math-sin
             :kit-receipt kit-signed
             :wasm-receipt wasm-signed
             :manifest m
             :readiness-row row
             :package-entry entry
             :wasm-bytes bytes})
        v (kit/verify-grant-binding gb kit-signed wasm-signed)]
    (is (true? (:host-admissible? gb)))
    (is (true? (:production-admissible? gb)))
    (is (empty? (:host-blockers gb)))
    (is (empty? (:production-blockers gb)))
    (is (true? (:production-signed-claim? m)))
    (is (string? (:grant-key gb)))
    (is (str/starts-with? (:grant-key gb) "kotoba.kit-package.grant-binding/v1\n"))
    (is (true? (:ok? v)))
    (is (true? (:host-admissible? v)))
    (is (true? (:production-admissible? v)))))

(deftest grant-binding-rejects-fixture
  (let [readiness (kit/readiness-table
                   (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        row (kit/readiness-for readiness :secret)
        path "kotoba/lang/capability-kits/secret-v1.edn"
        text (slurp (io/resource path))
        {:keys [sign]} (kit/test-hmac-signer "fx")
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :secret path text) sign)
        wasm-signed (kit/sign-wasm-provider-receipt
                     (kit/chain-kit-and-wasm-receipts
                      (kit/wasm-provider-receipt
                       :secret path (kit/load-fixture-wasm-bytes)
                       {:artifact-kind :fixture-synthetic})
                      kit-signed)
                     sign)
        gb (kit/grant-binding
            {:kit-name :secret
             :kit-receipt kit-signed
             :wasm-receipt wasm-signed
             :readiness-row row})]
    (is (false? (:host-admissible? gb)))
    (is (some #{:wasm-artifact-is-fixture} (:host-blockers gb)))
    (is (false? (:production-admissible? gb)))))

(deftest grant-binding-detects-digest-swap
  (let [readiness (kit/readiness-table
                   (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        row (kit/readiness-for readiness :math-cos)
        path "kotoba/lang/capability-kits/math-cos-v1.edn"
        text (slurp (io/resource path))
        pkg-table (kit/load-wasm-packages-table)
        entry (kit/wasm-package-for pkg-table :math-cos)
        bytes (kit/load-wasm-package-bytes (:resource entry))
        {:keys [sign]} (kit/test-hmac-signer "swap")
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :math-cos path text) sign)
        wasm-signed (kit/sign-wasm-provider-receipt
                     (kit/chain-kit-and-wasm-receipts
                      (kit/real-wasm-provider-receipt entry bytes)
                      kit-signed)
                     sign)
        gb (kit/grant-binding
            {:kit-name :math-cos
             :kit-receipt kit-signed
             :wasm-receipt wasm-signed
             :readiness-row row
             :package-entry entry
             :wasm-bytes bytes})
        tampered (assoc-in kit-signed [:package :digest] (kit/sha256-hex "nope"))
        v (kit/verify-grant-binding gb tampered wasm-signed)]
    (is (true? (:host-admissible? gb)))
    (is (false? (:ok? v)))
    (is (= :kit-edn-digest-mismatch (:reason v)))))

(deftest readiness-covers-pure-allowlist-set
  (let [table (kit/readiness-table
               (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        names (set (map :name (:kits table)))]
    (doseq [n [:math-sin :math-cos :hash-sha256 :data-cbor :data-json
               :clock-monotonic :random-bytes :time-now-days]]
      (is (contains? names n) (str n)))))

(deftest ops-http-post-wasm-package-digest-match
  "ADR 0162: ops/network real non-fixture http-post pilot."
  (let [table (kit/load-wasm-packages-table)
        entry (kit/wasm-package-for table :http-post)
        bytes (kit/load-wasm-package-bytes (:resource entry))]
    (is (= :http-post (:name entry)))
    (is (= :ops-network (:class entry)))
    (is (false? (:fixture? entry)))
    (is (true? (kit/verify-wasm-package-digest entry bytes)))
    (is (= [0x00 0x61 0x73 0x6d]
           (map #(bit-and % 0xff) (take 4 bytes))))
    (let [rec (kit/real-wasm-provider-receipt entry bytes)]
      (is (false? (:fixture? rec)))
      (is (= :http-post (:name rec))))))

(deftest ops-http-module-pilot-does-not-clear-component-gate
  "ADR 0162/0164: core module packaging ok; Component gate stays closed for module."
  (let [readiness (kit/readiness-table
                   (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        http (kit/readiness-for readiness :http)
        pkg-table (kit/load-wasm-packages-table)
        entry (kit/wasm-package-for pkg-table :http-post)
        bytes (kit/load-wasm-package-bytes (:resource entry))]
    (is (= :wasm-module (:artifact-kind entry)))
    (is (false? (kit/pure-allowlist-kit? http)))
    (is (true? (kit/ops-network-publisher-policy-satisfied? http entry bytes)))
    (is (false? (kit/ops-signed-wasm-ready-allowed? http entry bytes))
        "module pilot must not clear Component gate")
    ;; Inventory may still be :ready via Component entry (ADR 0165).
    (is (= :ready (get-in http [:scores :signed-wasm])))))
(deftest ops-secret-get-wasm-package-digest-match
  "ADR 0163: ops secret real non-fixture pure name-policy pilot."
  (let [table (kit/load-wasm-packages-table)
        entry (kit/wasm-package-for table :secret-get)
        bytes (kit/load-wasm-package-bytes (:resource entry))]
    (is (= :secret-get (:name entry)))
    (is (= :ops-network (:class entry)))
    (is (false? (:fixture? entry)))
    (is (true? (kit/verify-wasm-package-digest entry bytes)))
    (is (= [0x00 0x61 0x73 0x6d]
           (map #(bit-and % 0xff) (take 4 bytes))))
    (let [rec (kit/real-wasm-provider-receipt entry bytes)]
      (is (false? (:fixture? rec)))
      (is (= :secret-get (:name rec))))))

(deftest ops-secret-module-pilot-does-not-clear-component-gate
  "ADR 0163 module pilot: packaging bar true; Component gate false for module entry.
  Inventory may still be :ready via Component entry (ADR 0166)."
  (let [readiness (kit/readiness-table
                   (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        secret (kit/readiness-for readiness :secret)
        pkg-table (kit/load-wasm-packages-table)
        entry (kit/wasm-package-for pkg-table :secret-get)
        bytes (kit/load-wasm-package-bytes (:resource entry))
        path "kotoba/lang/capability-kits/secret-v1.edn"
        text (slurp (io/resource path))
        {:keys [sign]} (kit/test-hmac-signer "ops-secret-key")
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :secret path text) sign)
        wasm-signed (kit/sign-wasm-provider-receipt
                     (kit/chain-kit-and-wasm-receipts
                      (kit/real-wasm-provider-receipt entry bytes)
                      kit-signed)
                     sign)
        gb (kit/grant-binding
            {:kit-name :secret
             :kit-receipt kit-signed
             :wasm-receipt wasm-signed
             :readiness-row secret
             :package-entry entry
             :wasm-bytes bytes})]
    (is (false? (kit/pure-allowlist-kit? secret)))
    (is (false? (kit/pure-allowlist-publisher-policy-satisfied? secret entry bytes)))
    (is (true? (kit/ops-network-publisher-policy-satisfied? secret entry bytes)))
    (is (false? (kit/ops-signed-wasm-ready-allowed? secret entry bytes))
        "wasm-module pilot must not clear Component gate")
    (is (= :ready (get-in secret [:scores :signed-wasm]))
        "inventory flipped by Component entry, not module")
    (is (true? (:host-admissible? gb)))
    ;; production-admissible uses readiness scores (ready) + signed receipts;
    ;; module artifact is still non-fixture so may be production-admissible when
    ;; readiness is ready — gate honesty lives in ops-signed-wasm-ready-allowed?
    (is (true? (kit/production-signed-allowed? secret)))))

(deftest ops-network-publisher-policy
  "ADR 0164 packaging bar + ADR 0165 Component gate for http."
  (let [readiness (kit/readiness-table
                   (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        http (kit/readiness-for readiness :http)
        secret (kit/readiness-for readiness :secret)
        math (kit/readiness-for readiness :math-sin)
        process (kit/readiness-for readiness :process)
        pkg-table (kit/load-wasm-packages-table)
        http-entry (kit/wasm-package-for pkg-table :http-post)
        http-comp (kit/wasm-package-for pkg-table :http-post-component)
        secret-entry (kit/wasm-package-for pkg-table :secret-get)
        math-entry (kit/wasm-package-for pkg-table :math-sin)
        http-bytes (kit/load-wasm-package-bytes (:resource http-entry))
        http-comp-bytes (kit/load-wasm-package-bytes (:resource http-comp))
        secret-bytes (kit/load-wasm-package-bytes (:resource secret-entry))]
    (is (true? (kit/ops-network-kit? http)))
    (is (true? (kit/ops-network-kit? secret)))
    (is (false? (kit/ops-network-kit? math)))
    (is (true? (kit/ops-network-kit? process))
        "ADR 0168 process is ops kit")
    (is (true? (kit/ops-network-publisher-policy-satisfied? http http-entry http-bytes)))
    (is (true? (kit/ops-network-publisher-policy-satisfied? secret secret-entry secret-bytes)))
    (is (false? (kit/ops-network-publisher-policy-satisfied? math math-entry)))
    (is (false? (kit/ops-network-publisher-policy-satisfied? http))) ; needs package-entry
    (is (false? (kit/ops-signed-wasm-ready-allowed? http http-entry http-bytes))
        "wasm-module pilot must not flip signed-wasm")
    (is (false? (kit/ops-signed-wasm-ready-allowed? secret secret-entry secret-bytes))
        "wasm-module pilot must not flip signed-wasm")
    ;; ADR 0165/0166: Component entries clear flip gate; inventory flips both.
    (let [secret-comp (kit/wasm-package-for pkg-table :secret-get-component)
          secret-comp-bytes (kit/load-wasm-package-bytes (:resource secret-comp))]
      (is (= :wasm-component (:artifact-kind http-comp)))
      (is (true? (kit/verify-wasm-package-digest http-comp http-comp-bytes)))
      (is (true? (kit/ops-signed-wasm-ready-allowed? http http-comp http-comp-bytes)))
      (is (= :wasm-component (:artifact-kind secret-comp)))
      (is (true? (kit/verify-wasm-package-digest secret-comp secret-comp-bytes)))
      (is (true? (kit/ops-signed-wasm-ready-allowed? secret secret-comp secret-comp-bytes)))
      (is (= :ready (get-in http [:scores :signed-wasm])))
      (is (= :ready (get-in secret [:scores :signed-wasm])))
      (is (true? (kit/production-signed-allowed? http)))
      (is (true? (kit/production-signed-allowed? secret))))))

(deftest ops-http-component-grant-binding-production-admissible
  "ADR 0165: http readiness ready + signed Component receipts → production-admissible."
  (let [readiness (kit/readiness-table
                   (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        http (kit/readiness-for readiness :http)
        pkg-table (kit/load-wasm-packages-table)
        entry (kit/wasm-package-for pkg-table :http-post-component)
        bytes (kit/load-wasm-package-bytes (:resource entry))
        path "kotoba/lang/capability-kits/http-v1.edn"
        text (slurp (io/resource path))
        {:keys [sign]} (kit/test-hmac-signer "ops-http-component-key")
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :http path text) sign)
        wasm-signed (kit/sign-wasm-provider-receipt
                     (kit/chain-kit-and-wasm-receipts
                      (kit/real-wasm-provider-receipt entry bytes)
                      kit-signed)
                     sign)
        gb (kit/grant-binding
            {:kit-name :http
             :kit-receipt kit-signed
             :wasm-receipt wasm-signed
             :readiness-row http
             :package-entry entry
             :wasm-bytes bytes})
        m (kit/package-manifest
           {:readiness-row http
            :kit-receipt kit-signed
            :wasm-receipt wasm-signed})]
    (is (true? (kit/ops-signed-wasm-ready-allowed? http entry bytes)))
    (is (true? (:host-admissible? gb)))
    (is (true? (:production-admissible? gb)))
    (is (true? (:production-signed-claim? m)))
    (is (empty? (:blockers m)))))

(deftest ops-secret-component-grant-binding-production-admissible
  "ADR 0166: secret readiness ready + signed Component receipts → production-admissible."
  (let [readiness (kit/readiness-table
                   (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        secret (kit/readiness-for readiness :secret)
        pkg-table (kit/load-wasm-packages-table)
        entry (kit/wasm-package-for pkg-table :secret-get-component)
        bytes (kit/load-wasm-package-bytes (:resource entry))
        path "kotoba/lang/capability-kits/secret-v1.edn"
        text (slurp (io/resource path))
        {:keys [sign]} (kit/test-hmac-signer "ops-secret-component-key")
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :secret path text) sign)
        wasm-signed (kit/sign-wasm-provider-receipt
                     (kit/chain-kit-and-wasm-receipts
                      (kit/real-wasm-provider-receipt entry bytes)
                      kit-signed)
                     sign)
        gb (kit/grant-binding
            {:kit-name :secret
             :kit-receipt kit-signed
             :wasm-receipt wasm-signed
             :readiness-row secret
             :package-entry entry
             :wasm-bytes bytes})
        m (kit/package-manifest
           {:readiness-row secret
            :kit-receipt kit-signed
            :wasm-receipt wasm-signed})]
    (is (true? (kit/ops-signed-wasm-ready-allowed? secret entry bytes)))
    (is (true? (:host-admissible? gb)))
    (is (true? (:production-admissible? gb)))
    (is (true? (:production-signed-claim? m)))
    (is (empty? (:blockers m)))))

(deftest ops-entropy-component-signed-wasm-ready
  "ADR 0167: entropy pure draw-size Component flips signed-wasm."
  (let [readiness (kit/readiness-table
                   (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        entropy (kit/readiness-for readiness :entropy)
        pkg-table (kit/load-wasm-packages-table)
        mod (kit/wasm-package-for pkg-table :entropy-draw)
        comp (kit/wasm-package-for pkg-table :entropy-draw-component)
        mod-bytes (kit/load-wasm-package-bytes (:resource mod))
        comp-bytes (kit/load-wasm-package-bytes (:resource comp))
        path "kotoba/lang/capability-kits/entropy-v1.edn"
        text (slurp (io/resource path))
        {:keys [sign]} (kit/test-hmac-signer "ops-entropy-key")
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :entropy path text) sign)
        wasm-signed (kit/sign-wasm-provider-receipt
                     (kit/chain-kit-and-wasm-receipts
                      (kit/real-wasm-provider-receipt comp comp-bytes)
                      kit-signed)
                     sign)
        gb (kit/grant-binding
            {:kit-name :entropy
             :kit-receipt kit-signed
             :wasm-receipt wasm-signed
             :readiness-row entropy
             :package-entry comp
             :wasm-bytes comp-bytes})]
    (is (true? (kit/ops-network-kit? entropy)))
    (is (= :ops (:class mod)))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (true? (kit/verify-wasm-package-digest mod mod-bytes)))
    (is (true? (kit/verify-wasm-package-digest comp comp-bytes)))
    (is (true? (kit/ops-network-publisher-policy-satisfied? entropy mod mod-bytes)))
    (is (false? (kit/ops-signed-wasm-ready-allowed? entropy mod mod-bytes)))
    (is (true? (kit/ops-signed-wasm-ready-allowed? entropy comp comp-bytes)))
    (is (= :ready (get-in entropy [:scores :signed-wasm])))
    (is (true? (kit/production-signed-allowed? entropy)))
    (is (true? (:host-admissible? gb)))
    (is (true? (:production-admissible? gb)))))

(deftest ops-process-component-signed-wasm-ready
  "ADR 0168: process pure spawn-bounds Component flips signed-wasm."
  (let [readiness (kit/readiness-table
                   (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        process (kit/readiness-for readiness :process)
        pkg-table (kit/load-wasm-packages-table)
        mod (kit/wasm-package-for pkg-table :process-spawn)
        comp (kit/wasm-package-for pkg-table :process-spawn-component)
        mod-bytes (kit/load-wasm-package-bytes (:resource mod))
        comp-bytes (kit/load-wasm-package-bytes (:resource comp))
        path "kotoba/lang/capability-kits/process-v1.edn"
        text (slurp (io/resource path))
        {:keys [sign]} (kit/test-hmac-signer "ops-process-key")
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :process path text) sign)
        wasm-signed (kit/sign-wasm-provider-receipt
                     (kit/chain-kit-and-wasm-receipts
                      (kit/real-wasm-provider-receipt comp comp-bytes)
                      kit-signed)
                     sign)
        gb (kit/grant-binding
            {:kit-name :process
             :kit-receipt kit-signed
             :wasm-receipt wasm-signed
             :readiness-row process
             :package-entry comp
             :wasm-bytes comp-bytes})]
    (is (true? (kit/ops-network-kit? process)))
    (is (= :ops (:class mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (true? (kit/verify-wasm-package-digest mod mod-bytes)))
    (is (true? (kit/verify-wasm-package-digest comp comp-bytes)))
    (is (true? (kit/ops-network-publisher-policy-satisfied? process mod mod-bytes)))
    (is (false? (kit/ops-signed-wasm-ready-allowed? process mod mod-bytes)))
    (is (true? (kit/ops-signed-wasm-ready-allowed? process comp comp-bytes)))
    (is (= :ready (get-in process [:scores :signed-wasm])))
    (is (true? (kit/production-signed-allowed? process)))
    (is (true? (:host-admissible? gb)))
    (is (true? (:production-admissible? gb)))))

(deftest ops-scoped-fs-component-signed-wasm-ready
  "ADR 0169: scoped-fs pure path Component flips signed-wasm."
  (let [readiness (kit/readiness-table
                   (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        fs (kit/readiness-for readiness :scoped-fs)
        pkg-table (kit/load-wasm-packages-table)
        mod (kit/wasm-package-for pkg-table :scoped-fs-path)
        comp (kit/wasm-package-for pkg-table :scoped-fs-path-component)
        mod-bytes (kit/load-wasm-package-bytes (:resource mod))
        comp-bytes (kit/load-wasm-package-bytes (:resource comp))
        path "kotoba/lang/capability-kits/scoped-fs-v1.edn"
        text (slurp (io/resource path))
        {:keys [sign]} (kit/test-hmac-signer "ops-scoped-fs-key")
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :scoped-fs path text) sign)
        wasm-signed (kit/sign-wasm-provider-receipt
                     (kit/chain-kit-and-wasm-receipts
                      (kit/real-wasm-provider-receipt comp comp-bytes)
                      kit-signed)
                     sign)
        gb (kit/grant-binding
            {:kit-name :scoped-fs
             :kit-receipt kit-signed
             :wasm-receipt wasm-signed
             :readiness-row fs
             :package-entry comp
             :wasm-bytes comp-bytes})]
    (is (true? (kit/ops-network-kit? fs)))
    (is (= :ops (:class mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (true? (kit/verify-wasm-package-digest mod mod-bytes)))
    (is (true? (kit/verify-wasm-package-digest comp comp-bytes)))
    (is (true? (kit/ops-network-publisher-policy-satisfied? fs mod mod-bytes)))
    (is (false? (kit/ops-signed-wasm-ready-allowed? fs mod mod-bytes)))
    (is (true? (kit/ops-signed-wasm-ready-allowed? fs comp comp-bytes)))
    (is (= :ready (get-in fs [:scores :signed-wasm])))
    (is (true? (kit/production-signed-allowed? fs)))
    (is (true? (:host-admissible? gb)))
    (is (true? (:production-admissible? gb)))))

(deftest ops-git-component-signed-wasm-ready
  "ADR 0170: git pure run-bounds Component flips signed-wasm."
  (let [readiness (kit/readiness-table
                   (slurp (io/resource "kotoba/lang/kit-readiness-v1.edn")))
        git (kit/readiness-for readiness :git)
        pkg-table (kit/load-wasm-packages-table)
        mod (kit/wasm-package-for pkg-table :git-run)
        comp (kit/wasm-package-for pkg-table :git-run-component)
        mod-bytes (kit/load-wasm-package-bytes (:resource mod))
        comp-bytes (kit/load-wasm-package-bytes (:resource comp))
        path "kotoba/lang/capability-kits/git-v1.edn"
        text (slurp (io/resource path))
        {:keys [sign]} (kit/test-hmac-signer "ops-git-key")
        kit-signed (kit/sign-kit-package-receipt
                    (kit/kit-package-receipt :git path text) sign)
        wasm-signed (kit/sign-wasm-provider-receipt
                     (kit/chain-kit-and-wasm-receipts
                      (kit/real-wasm-provider-receipt comp comp-bytes)
                      kit-signed)
                     sign)
        gb (kit/grant-binding
            {:kit-name :git
             :kit-receipt kit-signed
             :wasm-receipt wasm-signed
             :readiness-row git
             :package-entry comp
             :wasm-bytes comp-bytes})]
    (is (true? (kit/ops-network-kit? git)))
    (is (= :ops (:class mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (true? (kit/verify-wasm-package-digest mod mod-bytes)))
    (is (true? (kit/verify-wasm-package-digest comp comp-bytes)))
    (is (true? (kit/ops-network-publisher-policy-satisfied? git mod mod-bytes)))
    (is (false? (kit/ops-signed-wasm-ready-allowed? git mod mod-bytes)))
    (is (true? (kit/ops-signed-wasm-ready-allowed? git comp comp-bytes)))
    (is (= :ready (get-in git [:scores :signed-wasm])))
    (is (true? (kit/production-signed-allowed? git)))
    (is (true? (:host-admissible? gb)))
    (is (true? (:production-admissible? gb)))))
