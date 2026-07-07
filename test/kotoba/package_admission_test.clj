(ns kotoba.package-admission-test
  (:require [clojure.edn :as edn]
            [clojure.test :refer [deftest is run-tests testing]]
            [kotoba.launcher :as launcher]
            [kotoba.package-admission :as admission]))

(defn fixture [name]
  (str "test/fixtures/package/" name))

(def positive-lock (fixture "positive-lock.edn"))
(def positive-manifest (fixture "positive-manifest.edn"))
(def empty-deps-lock (fixture "empty-deps-lock.edn"))
(def trust (fixture "trust.edn"))

(defn verify-argv [& argv]
  (launcher/dispatch (into ["package" "verify"] argv)))

(defn first-problem [result]
  (get-in result [:kotoba.cli/data :kotoba.package/receipt
                  :kotoba.package/problems 0 :kotoba.package/problem]))

(defn receipt [result]
  (get-in result [:kotoba.cli/data :kotoba.package/receipt]))

;; ---------------------------------------------------------------------------
;; Positive admission

(deftest positive-lock-is-admitted
  (let [result (verify-argv "--lock" positive-lock "--trust" trust "--json")]
    (is (true? (:kotoba.cli/ok? result)))
    (is (= :package-verified (:kotoba.cli/code result)))
    (is (= 0 (launcher/result->exit result)))
    (is (true? (:kotoba.package/verified? (receipt result))))
    (is (= [] (:kotoba.package/problems (receipt result))))))

(deftest positive-lock-with-manifest-declares-capabilities
  ;; With no trust file, declared capabilities come from the package manifest.
  (let [result (verify-argv "--lock" positive-lock "--manifest" positive-manifest)]
    (is (true? (:kotoba.cli/ok? result)))
    (is (= :package-verified (:kotoba.cli/code result)))
    (is (true? (:kotoba.package/verified? (receipt result))))))

;; ---------------------------------------------------------------------------
;; Manifest integrity: a real CID mismatch, not just shape

(deftest compute-manifest-cid-matches-the-fixtures-own-self-declared-cid
  (testing "positive-manifest.edn's :manifest-cid genuinely IS its own content's real CID
            (kotoba.package-admission/compute-manifest-cid, canonical DAG-CBOR + CIDv1) --
            not just a CID-shaped placeholder that happens to pass the structural check"
    (let [manifest (edn/read-string (slurp positive-manifest))]
      (is (= (get-in manifest [:kotoba.package/source :manifest-cid])
             (admission/compute-manifest-cid manifest))))))

(deftest manifest-with-a-mismatched-cid-is-rejected-not-silently-accepted
  (testing "a manifest edited without updating its pinned :manifest-cid (or a CID copied
            from an unrelated package) is caught here -- kotoba.lang.package-contract/cid?'s
            structural check alone (kotoba-lang/kotoba-lang#13) can't detect this: the
            tampered value is still a perfectly well-formed CIDv1, just not THIS content's"
    (let [manifest (edn/read-string (slurp positive-manifest))
          tampered (assoc-in manifest [:kotoba.package/source :manifest-cid]
                             (admission/compute-manifest-cid
                              (assoc manifest :kotoba.package/version "9.9.9")))
          error (admission/manifest-integrity-error tampered)]
      (is (some? error))
      (is (= "manifest cid does not match manifest content" (:message error)))
      (is (not= (get-in tampered [:kotoba.package/source :manifest-cid])
                (:computed (:data error)))
          "the declared (tampered) CID and the real computed CID must differ")))
  (testing "wired end to end through verify-lock: a rejected manifest fails the whole build,
            not just the standalone helper function"
    (let [manifest (edn/read-string (slurp positive-manifest))
          tampered (assoc-in manifest [:kotoba.package/source :manifest-cid]
                             (admission/compute-manifest-cid
                              (assoc manifest :kotoba.package/version "9.9.9")))
          lock (edn/read-string (slurp positive-lock))
          r (admission/verify-lock {:lock lock :lock-path positive-lock
                                    :manifest tampered :manifest-path positive-manifest
                                    :trust {:declared-capabilities [:graph-read]}})]
      (is (false? (:kotoba.package/verified? r)))
      (is (= :package/manifest-cid-mismatch
             (get-in r [:kotoba.package/problems 0 :kotoba.package/problem]))))))

(deftest receipt-has-release-evidence-shape
  (let [result (verify-argv "--lock" positive-lock "--trust" trust)
        r (receipt result)
        entry (first (:kotoba.package/entries r))]
    (is (true? (:kotoba.package/verified? r)))
    (is (= positive-lock (:kotoba.package/lock-path r)))
    (is (string? (:kotoba.package/checked-at r)))
    (is (re-find #"^\d{4}-\d{2}-\d{2}T" (:kotoba.package/checked-at r)))
    (is (vector? (:kotoba.package/problems r)))
    (is (= 1 (count (:kotoba.package/entries r))))
    (is (= "kotoba-lang/json@0.1.0" (:package/id entry)))
    (is (= "bafyreiarfykm5z7sphdaldk27xkdioykfxkyib7iyglqiteaszqlhoka5i"
           (:package/repo-rid entry)))
    (is (= "bafyreic7obercaz225ab3xc4nes5tijjhhl2cc4ws5xipozv4vexq5ucxm"
           (:package/manifest-cid entry)))
    (is (= "bafyreiawokfmkzvlt3yhwb5qd6widilkuvriucz6kxlrwb2o5whnpkjek4"
           (:package/tree-cid entry)))
    (is (= :accepted (:package/result entry)))))

(deftest receipt-file-is-written-on-accept-and-reject
  (let [accept-out (doto (java.io.File/createTempFile "kotoba-receipt-accept" ".edn")
                     (.deleteOnExit))
        reject-out (doto (java.io.File/createTempFile "kotoba-receipt-reject" ".edn")
                     (.deleteOnExit))
        accepted (verify-argv "--lock" positive-lock "--trust" trust
                              "--receipt" (.getPath accept-out))
        rejected (verify-argv "--lock" (fixture "version-only-lock.edn")
                              "--receipt" (.getPath reject-out))
        accept-receipt (edn/read-string (slurp accept-out))
        reject-receipt (edn/read-string (slurp reject-out))]
    (is (true? (:kotoba.cli/ok? accepted)))
    (is (= (.getPath accept-out)
           (get-in accepted [:kotoba.cli/data :kotoba.package/receipt-path])))
    (is (true? (:kotoba.package/verified? accept-receipt)))
    (is (false? (:kotoba.cli/ok? rejected)))
    (is (false? (:kotoba.package/verified? reject-receipt)))
    (is (seq (:kotoba.package/problems reject-receipt)))))

;; ---------------------------------------------------------------------------
;; Rejection classes (mirror kotoba-lang package-conformance negatives)

(deftest rejects-version-only-dependency
  (let [result (verify-argv "--lock" (fixture "version-only-lock.edn") "--json")]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :package-rejected (:kotoba.cli/code result)))
    (is (= 1 (launcher/result->exit result)))
    (is (= :package/missing-lock-field (first-problem result)))
    (is (= :rejected (get-in (receipt result)
                             [:kotoba.package/entries 0 :package/result])))))

(deftest rejects-missing-repo-rid
  (let [result (verify-argv "--lock" (fixture "missing-repo-rid-lock.edn"))]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :package/missing-lock-field (first-problem result)))
    (is (= {:missing :dep/repo-rid}
           (get-in result [:kotoba.cli/data :kotoba.package/receipt
                           :kotoba.package/problems 0 :kotoba.package/data])))))

(deftest rejects-missing-tree-cid
  (let [result (verify-argv "--lock" (fixture "missing-tree-cid-lock.edn"))]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :package/missing-lock-field (first-problem result)))
    (is (= {:missing :dep/tree-cid}
           (get-in result [:kotoba.cli/data :kotoba.package/receipt
                           :kotoba.package/problems 0 :kotoba.package/data])))))

(deftest rejects-missing-manifest-cid
  (let [result (verify-argv "--lock" (fixture "missing-manifest-cid-lock.edn"))]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :package/missing-lock-field (first-problem result)))
    (is (= {:missing :dep/manifest-cid}
           (get-in result [:kotoba.cli/data :kotoba.package/receipt
                           :kotoba.package/problems 0 :kotoba.package/data])))))

(deftest rejects-capability-grant-exceeding-declaration
  (let [result (verify-argv "--lock" (fixture "excessive-capability-lock.edn")
                            "--trust" trust)]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :package-rejected (:kotoba.cli/code result)))
    (is (= :package/capability-exceeds-declaration (first-problem result)))))

(deftest rejects-revoked-signer
  (let [result (verify-argv "--lock" (fixture "revoked-signer-lock.edn")
                            "--trust" (fixture "revoked-trust.edn"))]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :package/signer-not-trusted (first-problem result)))))

(deftest rejects-expired-signer
  (let [result (verify-argv "--lock" (fixture "expired-signer-lock.edn")
                            "--trust" (fixture "expired-trust.edn"))]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :package/signer-not-trusted (first-problem result)))))

(deftest rejects-unsigned-manifest
  (let [result (verify-argv "--lock" positive-lock
                            "--manifest" (fixture "unsigned-manifest.edn")
                            "--trust" trust)]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :package/signature-required (first-problem result)))
    (is (= :manifest (get-in result [:kotoba.cli/data :kotoba.package/receipt
                                     :kotoba.package/problems 0 :kotoba.package/input])))))

(deftest rejects-bad-signature-alg-manifest
  (let [result (verify-argv "--lock" positive-lock
                            "--manifest" (fixture "bad-signature-alg-manifest.edn")
                            "--trust" trust)]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :package/signature-alg-unsupported (first-problem result)))))

(deftest rejects-local-path-dependency-in-safe-mode
  (let [result (verify-argv "--lock" (fixture "local-path-lock.edn") "--trust" trust)]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :package/local-path-dependency (first-problem result)))
    (is (= :rejected (get-in (receipt result)
                             [:kotoba.package/entries 0 :package/result])))))

(deftest rejects-path-looking-refs-at-fn-level
  (let [dep {:dep/name "kotoba-lang/json"
             :dep/version "0.1.0"
             :dep/repo-rid "bafyreiarfykm5z7sphdaldk27xkdioykfxkyib7iyglqiteaszqlhoka5i"
             :dep/commit "0123456789abcdef0123456789abcdef01234567"
             :dep/tree-cid "bafyreiawokfmkzvlt3yhwb5qd6widilkuvriucz6kxlrwb2o5whnpkjek4"
             :dep/manifest-cid "bafyreic7obercaz225ab3xc4nes5tijjhhl2cc4ws5xipozv4vexq5ucxm"
             :dep/signers ["did:key:z6Mkpkgjson"]
             :dep/capabilities []}
        verify (fn [d]
                 (admission/verify-lock {:lock {:kotoba.lock/version 1 :deps [d]}
                                         :lock-path "in-memory.lock.edn"
                                         :trust {:declared-capabilities []}}))]
    (is (true? (:kotoba.package/verified? (verify dep))))
    (doseq [ref ["../sibling/json" "./json" "/abs/json" "~/json" "file:///json"]]
      (let [r (verify (assoc dep :dep/ref ref))]
        (is (false? (:kotoba.package/verified? r)) (str "ref " ref))
        (is (= :package/local-path-dependency
               (get-in r [:kotoba.package/problems 0 :kotoba.package/problem])))))
    (is (false? (:kotoba.package/verified?
                 (verify (assoc dep :dep/local-root "../sibling/json")))))))

;; ---------------------------------------------------------------------------
;; Input errors and CLI surface

(deftest reports-unreadable-lock
  (let [result (verify-argv "--lock" "missing-lock.edn" "--json")]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :package/lock-not-readable (:kotoba.cli/code result)))
    (is (= 1 (launcher/result->exit result)))
    (is (= "missing-lock.edn"
           (get-in result [:kotoba.cli/data :kotoba.package/error :kotoba.package/path])))))

(deftest reports-missing-lock-option-and-unknown-subcommand
  (let [no-lock (verify-argv "--json")
        unknown (launcher/dispatch ["package" "wat"])]
    (is (false? (:kotoba.cli/ok? no-lock)))
    (is (= :package/missing-lock-option (:kotoba.cli/code no-lock)))
    (is (false? (:kotoba.cli/ok? unknown)))
    (is (= :package/unknown-command (:kotoba.cli/code unknown)))))

;; ---------------------------------------------------------------------------
;; Safe-build integration (`wasm emit --package-lock`)

(deftest safe-build-aborts-on-rejected-package-lock
  (let [result (launcher/dispatch ["wasm" "emit" "src/demo.kotoba"
                                   "--package-lock" (fixture "version-only-lock.edn")
                                   "--json"])]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :wasm/package-rejected (:kotoba.cli/code result)))
    (is (= :package-rejected
           (get-in result [:kotoba.cli/data :kotoba.package/admission-code])))
    (is (false? (get-in result [:kotoba.cli/data :kotoba.package/receipt
                                :kotoba.package/verified?])))
    (is (= :package/missing-lock-field (first-problem result)))
    ;; the build never ran: no wasm payload alongside the receipt
    (is (nil? (get-in result [:kotoba.cli/data :kotoba.wasm/binary?])))))

(deftest safe-build-aborts-on-unreadable-package-lock
  (let [result (launcher/dispatch ["wasm" "emit" "src/demo.kotoba"
                                   "--package-lock" "missing-lock.edn"
                                   "--json"])]
    (is (false? (:kotoba.cli/ok? result)))
    (is (= :wasm/package-rejected (:kotoba.cli/code result)))
    (is (= :package/lock-not-readable
           (get-in result [:kotoba.cli/data :kotoba.package/admission-code])))))

(deftest safe-build-proceeds-with-admitted-package-lock
  (let [result (launcher/dispatch ["wasm" "emit" "src/demo.kotoba"
                                   "--package-lock" positive-lock
                                   "--trust" trust
                                   "--json"])]
    (is (true? (:kotoba.cli/ok? result)))
    (is (= :wasm/binary-emitted (:kotoba.cli/code result)))
    (is (true? (get-in result [:kotoba.cli/data :kotoba.package/receipt
                               :kotoba.package/verified?])))
    (is (= :accepted (get-in result [:kotoba.cli/data :kotoba.package/receipt
                                     :kotoba.package/entries 0 :package/result])))))

(deftest safe-build-proceeds-with-zero-dependency-package-lock
  (testing "a genuinely dependency-free program can still be built under the
            mandatory --package-lock gate (F-001) -- an empty :deps lock is
            admitted, not rejected with lock-deps-required"
    (let [result (launcher/dispatch ["wasm" "emit" "src/demo.kotoba"
                                     "--package-lock" empty-deps-lock
                                     "--json"])]
      (is (true? (:kotoba.cli/ok? result)))
      (is (= :wasm/binary-emitted (:kotoba.cli/code result)))
      (is (true? (get-in result [:kotoba.cli/data :kotoba.package/receipt
                                 :kotoba.package/verified?])))
      (is (= [] (get-in result [:kotoba.cli/data :kotoba.package/receipt
                                :kotoba.package/entries]))))))

(defn -main [& _]
  (let [{:keys [fail error]} (run-tests 'kotoba.package-admission-test)]
    (when (pos? (+ (or fail 0) (or error 0)))
      (System/exit 1))))
