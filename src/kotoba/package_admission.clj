(ns kotoba.package-admission
  "Safe-execution admission gate for Kotoba package inputs (issue #262 / F-001).

  Validates a `kotoba.lock.edn` (and optionally the package manifest it locks)
  through the `kotoba.lang.package-contract` validation kernel from
  kotoba-lang/kotoba-lang, and layers launcher-owned safe-mode checks on top
  (local-path dependencies are never admitted). Every verification — accept or
  reject — emits a package-verification receipt; the receipt is the
  release-evidence artifact required before a safe build may proceed.

  `manifest-integrity-error` closes a real gap `kotoba.lang.package-contract/
  cid?` alone doesn't (kotoba-lang/kotoba-lang#13 made `cid?` a genuine
  CIDv1 structural check, but structural validity says nothing about
  whether a CID actually matches the content it claims to pin): a
  manifest's own self-declared `:manifest-cid` is recomputed from the
  manifest's actual content (canonical DAG-CBOR + CIDv1, `cbor.core`/
  `multiformats.core`) and compared against the declared value. A manifest
  edited without updating its pinned CID -- or a manifest whose CID was
  copied from a different package entirely -- is rejected here, where the
  previous shape-only check would have silently accepted it as long as the
  string merely looked CID-shaped."
  (:require [cbor.core :as cbor]
            [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.pprint :as pprint]
            [clojure.string :as str]
            [kotoba.lang.package-contract :as package-contract]
            [multiformats.core :as mf])
  (:import [java.time Instant]))

(def local-path-message
  "local-path dependency not allowed in safe mode")

(def problem-codes
  "Map kotoba.lang.package-contract (and admission-layer) messages to stable
  problem keywords surfaced in receipts."
  {"lock version 1 required" :package/lock-version-unsupported
   "lock deps vector required" :package/lock-deps-required
   "missing required lock field" :package/missing-lock-field
   "cid required" :package/cid-required
   "signer required" :package/signer-required
   "signer not currently trusted" :package/signer-not-trusted
   "capability grant exceeds package declaration" :package/capability-exceeds-declaration
   "unknown package kind" :package/unknown-kind
   "contract surface vector required" :package/contract-surface-invalid
   "contract surface keyword required" :package/contract-surface-invalid
   "missing required package field" :package/missing-manifest-field
   "missing required source field" :package/missing-source-field
   "repo-rid cid required" :package/cid-required
   "tree cid required" :package/cid-required
   "manifest cid required" :package/cid-required
   "capabilities vector required" :package/capabilities-invalid
   "signature required" :package/signature-required
   "signature missing required field" :package/signature-invalid
   "signature did required" :package/signature-invalid
   "signature alg unsupported" :package/signature-alg-unsupported
   "signature bytes required" :package/signature-invalid
   "manifest cid does not match manifest content" :package/manifest-cid-mismatch
   local-path-message :package/local-path-dependency})

(defn problem-code
  [message]
  (get problem-codes message :package/invalid))

;; ---------------------------------------------------------------------------
;; Admission-layer safe-mode checks (not owned by package-contract)

(defn path-looking?
  "True when a string looks like a filesystem path rather than a git ref,
  package name, or CID."
  [x]
  (and (string? x)
       (or (str/starts-with? x "/")
           (str/starts-with? x "./")
           (str/starts-with? x "../")
           (str/starts-with? x "~")
           (str/starts-with? x "file:")
           (str/includes? x "\\"))))

(def local-root-keys
  [:package/local-root :dep/local-root :dep/local-path :dep/path :dep/root])

(def path-checked-ref-keys
  [:dep/ref :dep/url :dep/source])

(defn local-path-error
  "Safe mode never admits a dependency resolved from a local path: a local
  path has no repo RID / CID provenance, so its content cannot be pinned or
  attested. Returns a package-contract-shaped error map or nil."
  [dep]
  (or (some (fn [k]
              (when (contains? dep k)
                (package-contract/invalid local-path-message
                                          {:field k
                                           :value (get dep k)
                                           :dependency (:dep/name dep)})))
            local-root-keys)
      (some (fn [k]
              (let [value (get dep k)]
                (when (path-looking? value)
                  (package-contract/invalid local-path-message
                                            {:field k
                                             :value value
                                             :dependency (:dep/name dep)}))))
            path-checked-ref-keys)))

;; ---------------------------------------------------------------------------
;; Verification

(defn trust-context
  "Build the trust context handed to the package-contract lockfile validator.

  `trust` is the optional trust EDN (`:declared-capabilities`,
  `:revoked-signers`, `:expired-signers`, `:compromised-signers`). When the
  trust EDN does not pin `:declared-capabilities`, the manifest's declared
  `:kotoba.package/capabilities` are used; with neither, no capability grant
  is admitted (strict default)."
  [trust manifest]
  (assoc (or trust {})
         :declared-capabilities
         (vec (or (:declared-capabilities trust)
                  (:kotoba.package/capabilities manifest)
                  []))))

(defn manifest-without-self-cid
  "MANIFEST with its own self-declared :manifest-cid removed -- the content a
  manifest's CID must be computed OVER, since including the CID field inside
  the thing the CID hashes would make the value depend on itself (the same
  reason a git commit's hash never covers its own hash, or an IPFS DAG
  node's CID never covers its own CID field)."
  [manifest]
  (update manifest :kotoba.package/source dissoc :manifest-cid))

(defn compute-manifest-cid
  "The real CIDv1 (canonical DAG-CBOR + sha2-256, `cbor.core`/
  `multiformats.core` -- the same CID shape `kotoba.lang.package-contract/
  cid?` now structurally validates, kotoba-lang/kotoba-lang#13) of
  MANIFEST's actual content, excluding its own self-declared :manifest-cid."
  [manifest]
  (mf/cidv1-dag-cbor (cbor/encode (manifest-without-self-cid manifest))))

(defn manifest-integrity-error
  "nil if MANIFEST's self-declared :manifest-cid matches what its content
  actually hashes to; a package-contract-shaped error otherwise. Only
  meaningful once the shape check (`package-contract/package-manifest-error`)
  has already confirmed :manifest-cid is CID-shaped at all -- a missing or
  malformed field is that check's problem to report, not this one's."
  [manifest]
  (let [declared (get-in manifest [:kotoba.package/source :manifest-cid])]
    (when (package-contract/cid? declared)
      (let [computed (compute-manifest-cid manifest)]
        (when (not= declared computed)
          (package-contract/invalid "manifest cid does not match manifest content"
                                    {:declared declared :computed computed}))))))

(defn lock-level-error
  [lock]
  (or (when-not (= 1 (:kotoba.lock/version lock))
        (package-contract/invalid "lock version 1 required"
                                  {:value (:kotoba.lock/version lock)}))
      (when-not (vector? (:deps lock))
        (package-contract/invalid "lock deps vector required"
                                  {:value (:deps lock)}))))

(defn dep-error
  "First problem for a single lock entry: admission-layer safe-mode checks,
  then the package-contract lockfile kernel."
  [dep trust]
  (or (local-path-error dep)
      (package-contract/lockfile-error {:kotoba.lock/version 1 :deps [dep]} trust)))

(defn ->problem
  [source error]
  (merge {:kotoba.package/problem (problem-code (:message error))
          :kotoba.package/message (:message error)
          :kotoba.package/data (:data error)}
         source))

(defn dep-entry
  [dep error]
  {:package/id (str (:dep/name dep) "@" (:dep/version dep))
   :package/repo-rid (:dep/repo-rid dep)
   :package/manifest-cid (:dep/manifest-cid dep)
   :package/tree-cid (:dep/tree-cid dep)
   :package/result (if error :rejected :accepted)})

(defn checked-at []
  (str (Instant/now)))

(defn verify-lock
  "Verify a parsed lock (plus optional parsed manifest and trust EDN) and
  return the package-verification receipt. The receipt is emitted on both
  accept and reject."
  [{:keys [lock lock-path manifest manifest-path trust]}]
  (let [tc (trust-context trust manifest)
        manifest-error (when manifest (package-contract/package-manifest-error manifest))
        ;; Only check integrity once the shape check passed -- a missing or
        ;; malformed :manifest-cid is manifest-error's problem to report, not
        ;; a mismatch (there is nothing valid to mismatch against yet).
        integrity-error (when (and manifest (not manifest-error))
                          (manifest-integrity-error manifest))
        lock-error (lock-level-error lock)
        dep-results (mapv (fn [dep] [dep (dep-error dep tc)]) (:deps lock))
        problems (vec (concat
                       (when manifest-error
                         [(->problem {:kotoba.package/input :manifest
                                      :kotoba.package/path manifest-path}
                                     manifest-error)])
                       (when integrity-error
                         [(->problem {:kotoba.package/input :manifest
                                      :kotoba.package/path manifest-path}
                                     integrity-error)])
                       (when lock-error
                         [(->problem {:kotoba.package/input :lock
                                      :kotoba.package/path lock-path}
                                     lock-error)])
                       (keep (fn [[dep error]]
                               (when error
                                 (->problem {:kotoba.package/input :lock-entry
                                             :kotoba.package/dependency (:dep/name dep)}
                                            error)))
                             dep-results)))]
    {:kotoba.package/verified? (empty? problems)
     :kotoba.package/lock-path lock-path
     :kotoba.package/manifest-path manifest-path
     :kotoba.package/checked-at (checked-at)
     :kotoba.package/problems problems
     :kotoba.package/entries (mapv (fn [[dep error]] (dep-entry dep error)) dep-results)}))

;; ---------------------------------------------------------------------------
;; File-level admission

(defn read-edn-file
  [path]
  (let [file (io/file path)]
    (if (and (.isFile file) (.canRead file))
      (try
        {:ok? true :value (edn/read-string (slurp file))}
        (catch Exception e
          {:ok? false :error (.getMessage e)}))
      {:ok? false :error "file not readable"})))

(defn write-receipt!
  [path receipt]
  (let [file (io/file path)]
    (io/make-parents file)
    (spit file (with-out-str (pprint/pprint receipt)))))

(def usage
  "kotoba package verify --lock <kotoba.lock.edn> [--manifest <package-manifest.edn>] [--trust <trust.edn>] [--receipt <out.edn>] [--json]")

(defn not-readable
  [code path error]
  {:kotoba.admission/ok? false
   :kotoba.admission/code code
   :kotoba.admission/error {:kotoba.package/path path
                            :kotoba.package/error (:error error)}})

(defn admit
  "Run the package admission gate over file paths. Returns
  {:kotoba.admission/ok? bool
   :kotoba.admission/code keyword
   :kotoba.admission/receipt receipt (when the inputs were readable)
   :kotoba.admission/receipt-path path (when a receipt file was written)
   :kotoba.admission/error data (when the inputs were not readable)}"
  [{:keys [lock-path manifest-path trust-path receipt-path]}]
  (if-not lock-path
    {:kotoba.admission/ok? false
     :kotoba.admission/code :package/missing-lock-option
     :kotoba.admission/error {:kotoba.package/usage usage}}
    (let [lock (read-edn-file lock-path)
          manifest (some-> manifest-path read-edn-file)
          trust (some-> trust-path read-edn-file)]
      (cond
        (not (:ok? lock))
        (not-readable :package/lock-not-readable lock-path lock)

        (and manifest (not (:ok? manifest)))
        (not-readable :package/manifest-not-readable manifest-path manifest)

        (and trust (not (:ok? trust)))
        (not-readable :package/trust-not-readable trust-path trust)

        :else
        (let [receipt (verify-lock {:lock (:value lock)
                                    :lock-path lock-path
                                    :manifest (:value manifest)
                                    :manifest-path manifest-path
                                    :trust (:value trust)})
              verified? (:kotoba.package/verified? receipt)]
          (when receipt-path
            (write-receipt! receipt-path receipt))
          (cond-> {:kotoba.admission/ok? verified?
                   :kotoba.admission/code (if verified? :package-verified :package-rejected)
                   :kotoba.admission/receipt receipt}
            receipt-path (assoc :kotoba.admission/receipt-path receipt-path)))))))

(defn cli-result
  "Wrap an admission run as a launcher CLI result map."
  [opts]
  (let [admission (admit opts)]
    {:kotoba.cli/ok? (:kotoba.admission/ok? admission)
     :kotoba.cli/code (:kotoba.admission/code admission)
     :kotoba.cli/data (cond-> {}
                        (:kotoba.admission/receipt admission)
                        (assoc :kotoba.package/receipt (:kotoba.admission/receipt admission))

                        (:kotoba.admission/receipt-path admission)
                        (assoc :kotoba.package/receipt-path (:kotoba.admission/receipt-path admission))

                        (:kotoba.admission/error admission)
                        (assoc :kotoba.package/error (:kotoba.admission/error admission)))}))

(defn safe-release-ready?
  "F-001 / F-007 partial: a safe release may proceed only when a package-
  verification receipt exists and is verified. Returns
  {:ok? bool :problems [...]}. Does not perform crypto re-verification —
  callers pass the receipt produced by `admit`/`verify-lock`."
  [receipt]
  (cond
    (nil? receipt)
    {:ok? false
     :problems [{:kotoba.package/problem :package/missing-receipt
                 :kotoba.package/message "package verification receipt required for safe release"}]}

    (not (map? receipt))
    {:ok? false
     :problems [{:kotoba.package/problem :package/invalid-receipt
                 :kotoba.package/message "receipt must be a map"}]}

    (not (true? (:kotoba.package/verified? receipt)))
    {:ok? false
     :problems (into [{:kotoba.package/problem :package/not-verified
                       :kotoba.package/message "receipt is not verified"}]
                     (:kotoba.package/problems receipt))}

    :else
    {:ok? true :problems []}))
