(ns fleet.kcm
  "Kotoba Capability Machine (KCM) contract.

  A KCM is not a small general-purpose VM.  It is a content-addressed Kotoba
  definition closure plus an explicit HostCaps policy.  The guest never gets a
  shell or a process-spawn tool.  Host execution is limited to declared
  `kotoba` argv vectors, invoked without a shell by the sandbox host.

  This namespace owns only the deterministic contract and identities.  The
  outer OS backing (Seatbelt today, a container/microVM for higher-risk work)
  remains fleet.sandbox-agent's responsibility."
  (:require ["node:crypto" :as crypto]
            [kotoba.lang.text :as str]))

(def contract-version :kotoba-capability-machine/v1)

(def allowed-capabilities
  #{:code/list :code/read :code/write :code/edit :build/check :build/compile})

(def required-identity-keys
  [:definition-closure-cid :compiler-cid :module-lock-cid :target-abi
   :hostcaps-policy-cid :provider-closure-sha256 :runtime-sha256])

(defn kcm? [spec]
  (= :kotoba-capability-machine (:machine spec)))

(defn sha256-hex? [x]
  (boolean (and (string? x) (re-matches #"[0-9a-f]{64}" x))))

(defn- canonical
  "Stable data representation used as the hash input.  Maps and sets must not
  inherit host iteration order."
  [x]
  (cond
    (map? x) (into (sorted-map-by #(compare (pr-str %1) (pr-str %2)))
                   (map (fn [[k v]] [k (canonical v)])) x)
    (set? x) (vec (sort-by pr-str (map canonical x)))
    (sequential? x) (mapv canonical x)
    :else x))

(defn sha256 [x]
  (-> (crypto/createHash "sha256")
      (.update (pr-str (canonical x)))
      (.digest "hex")))

(defn sha256-bytes [x]
  (-> (crypto/createHash "sha256")
      (.update x)
      (.digest "hex")))

(defn confined-arg?
  "True when a declared compiler argument cannot name a path outside the KCM
  workspace. Flags and ordinary values remain valid; absolute paths, home
  shortcuts, NUL bytes, and parent traversal are rejected even after `=` (for
  example `--output=/tmp/x`)."
  [x]
  (let [parts (when (string? x) (str/split x #"="))]
    (boolean
     (and (string? x)
          (not (str/includes? x "\u0000"))
          (every?
           (fn [part]
             (and (not (re-find #"^(?:/|\\|~(?:/|\\)|[A-Za-z]:[\\/])" part))
                  (not-any? #{".."} (str/split part #"[\\/]"))))
           parts)))))

(defn validation-reasons
  "Fail-closed validation for a KCM work-unit. A check stores only arguments
  for the content-addressed provider. The executable, NBB entrypoint and
  classpath come from the verified provider manifest; neither PATH nor the
  model can select them."
  [spec]
  (let [caps (set (:kcm/capabilities spec))
        identity (:kcm/identity spec)
        provider (:kcm/provider spec)
        checks (:kcm/checks spec)
        builds (:kcm/builds spec)]
    (cond-> []
      (not (kcm? spec))
      (conj "machine is not :kotoba-capability-machine")

      (empty? caps)
      (conj "KCM capabilities are empty")

      (seq (remove allowed-capabilities caps))
      (conj (str "unknown KCM capabilities: "
                 (pr-str (set (remove allowed-capabilities caps)))))

      (seq (remove #(not (str/blank? (str (get identity %)))) required-identity-keys))
      (conj (str "KCM identity is incomplete; required " required-identity-keys))

      (or (str/blank? (str (:archive provider)))
          (str/blank? (str (:manifest provider)))
          (str/blank? (str (:archive-sha256 provider))))
      (conj "KCM provider transport requires archive, manifest and archive-sha256")

      (not-every? sha256-hex?
                  [(:provider-closure-sha256 identity)
                   (:runtime-sha256 identity)
                   (:archive-sha256 provider)])
      (conj "KCM provider closure, runtime and archive digests must be lowercase SHA-256")

      (not (vector? checks))
      (conj ":kcm/checks must be a vector")

      (empty? checks)
      (conj "KCM declares no checks")

      (and (contains? caps :build/compile) (empty? builds))
      (conj "KCM grants build/compile but declares no builds")

      (and (seq builds) (not (contains? caps :build/compile)))
      (conj "KCM declares builds without build/compile capability")

      (not= (count checks) (count (distinct (map :id checks))))
      (conj "KCM check ids must be unique")

      (some #(or (nil? (:id %))
                 (not (vector? (:args %)))
                 (empty? (:args %))
                 (not= "check" (first (:args %)))
                 (some (complement confined-arg?) (:args %))) checks)
      (conj "every KCM check must have an id and args beginning with check")

      (some #(or (nil? (:id %))
                 (not (vector? (:args %)))
                 (empty? (:args %))
                 (not= "compile" (first (:args %)))
                 (some (complement confined-arg?) (:args %))) builds)
      (conj "every KCM build must have an id and args beginning with compile")

      (not= (count builds) (count (distinct (map :id builds))))
      (conj "KCM build ids must be unique")

      (and (some :pure? checks) (seq (:effects identity)))
      (conj "effectful KCM identities cannot declare cacheable pure checks"))))

(defn validate! [spec]
  (when-let [rs (seq (validation-reasons spec))]
    (throw (ex-info (str "invalid Kotoba Capability Machine: "
                         (str/join "; " rs))
                    {:reasons rs})))
  spec)

(defn identity-body [spec]
  {:contract contract-version
   :identity (select-keys (:kcm/identity spec)
                          (conj required-identity-keys :effects))
   :capabilities (set (:kcm/capabilities spec))
   :checks (mapv #(select-keys % [:id :args :pure?]) (:kcm/checks spec))
   :builds (mapv #(select-keys % [:id :args]) (:kcm/builds spec))})

(defn machine-id [spec]
  (str "sha256:" (sha256 (identity-body (validate! spec)))))

(defn check-by-id [spec id]
  (let [wanted (if (keyword? id) id (keyword (str id)))]
    (or (first (filter #(= wanted (:id %)) (:kcm/checks spec)))
        (throw (ex-info (str "undeclared KCM check " (pr-str wanted))
                        {:check wanted})))))

(defn build-by-id [spec id]
  (let [wanted (if (keyword? id) id (keyword (str id)))]
    (or (first (filter #(= wanted (:id %)) (:kcm/builds spec)))
        (throw (ex-info (str "undeclared KCM build " (pr-str wanted))
                        {:build wanted})))))

(defn cache-key
  "Cache identity for a pure check. The patch digest makes edits part of the
  input; machine-id binds compiler, closure, lock, ABI, policy and exact args."
  [spec check patch]
  (str "sha256:"
       (sha256 {:machine (machine-id spec)
                :check (select-keys check [:id :args :pure?])
                :patch-sha256 (sha256 (or patch ""))})))

(defn tool-names [spec]
  (let [caps (set (:kcm/capabilities spec))]
    (cond-> #{}
      (caps :code/list) (conj "list_files")
      (caps :code/read) (conj "read_file")
      (caps :code/write) (conj "write_file" "append_file")
      (caps :code/edit) (conj "edit_file")
      (caps :build/check) (conj "kotoba_check")
      (caps :build/compile) (conj "kotoba_build"))))
