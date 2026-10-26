(ns aiueos.model-channel
  "Admission and update planning for a Kotobase/IPFS model channel.

  The network and disk drivers are ports. This namespace decides whether a
  verified IPNS head may replace the locally committed model and which
  immutable raw blocks are missing. It never fetches a URL or writes a disk."
  (:require [kotoba.lang.text :as str]))

(def schema "aiueos.model-channel/v1")
(def max-block-bytes (* 95 1024 1024))
(def max-blocks 900)
(def max-artifact-bytes (* 1024 1024 1024 1024))

(def ^:private raw-cid-pattern #"bafkrei[a-z2-7]{52}")
(def ^:private dag-cid-pattern #"bafyrei[a-z2-7]{52}")
(def ^:private ipns-name-pattern #"k51[a-z0-9]{20,60}")
(def ^:private sha256-pattern #"[0-9a-f]{64}")

(defn- field [m k]
  (let [underscore (str/replace (name k) "-" "_")]
    (or (get m k)
        (get m (name k))
        (get m underscore)
        (get m (keyword underscore)))))

(defn- natural? [x] (and (integer? x) (<= 0 x)))
(defn- positive? [x] (and (integer? x) (pos? x)))
(defn- matches? [pattern x]
  (boolean (and (string? x) (re-matches pattern x))))

(defn normalize-manifest
  "Normalize keyword or JSON-style string keys into the contract shape."
  [manifest]
  (let [target (field manifest :target)
        artifact (field manifest :artifact)
        blocks (vec (or (field manifest :blocks) []))]
    {:schema (field manifest :schema)
     :channel (field manifest :channel)
     :sequence (field manifest :sequence)
     :previous (field manifest :previous)
     :published-at (field manifest :published-at)
     :target {:architecture (field target :architecture)
              :machine (field target :machine)
              :min-aiueos-abi (field target :min-aiueos-abi)}
     :artifact {:name (field artifact :name)
                :bytes (field artifact :bytes)
                :sha256 (field artifact :sha256)
                :format (field artifact :format)
                :revision-cid (field artifact :revision-cid)}
     :blocks (mapv (fn [block]
                     {:cid (field block :cid)
                      :bytes (field block :bytes)})
                   blocks)}))

(defn manifest-errors
  "Return every structural error in a model-channel manifest."
  [manifest]
  (let [{:keys [channel sequence previous target artifact blocks] :as m}
        (normalize-manifest manifest)
        block-bytes (map :bytes blocks)
        block-cids (map :cid blocks)]
    (cond-> []
      (not= schema (:schema m)) (conj :schema)
      (not (and (string? channel)
                (re-matches #"[a-z0-9][a-z0-9._-]{1,79}" channel)))
      (conj :channel)
      (not (positive? sequence)) (conj :sequence)
      (not (or (nil? previous) (matches? raw-cid-pattern previous)))
      (conj :previous)
      (not= "x86_64" (:architecture target)) (conj :target-architecture)
      (not= "gmktec-k16" (:machine target)) (conj :target-machine)
      (not (positive? (:min-aiueos-abi target))) (conj :target-abi)
      (not (and (string? (:name artifact))
                (<= 1 (count (:name artifact)) 255)))
      (conj :artifact-name)
      (not (and (positive? (:bytes artifact))
                (<= (:bytes artifact) max-artifact-bytes)))
      (conj :artifact-bytes)
      (not (matches? sha256-pattern (:sha256 artifact)))
      (conj :artifact-sha256)
      (not= "gguf-v3" (:format artifact)) (conj :artifact-format)
      (not (or (nil? (:revision-cid artifact))
               (matches? dag-cid-pattern (:revision-cid artifact))))
      (conj :artifact-revision-cid)
      (or (empty? blocks) (> (count blocks) max-blocks))
      (conj :block-count)
      (some #(not (matches? raw-cid-pattern %)) block-cids)
      (conj :block-cid)
      (not= (count block-cids) (count (distinct block-cids)))
      (conj :duplicate-block-cid)
      (some #(not (and (positive? %) (<= % max-block-bytes))) block-bytes)
      (conj :block-bytes)
      (and (natural? (:bytes artifact))
           (every? positive? block-bytes)
           (not= (:bytes artifact) (reduce + 0 block-bytes)))
      (conj :artifact-block-size-mismatch))))

(defn- head-errors
  [{:keys [name cid sequence signature-verified? valid?]} context manifest]
  (cond-> []
    (not (matches? ipns-name-pattern name)) (conj :ipns-name)
    (not= name (:ipns-name context)) (conj :unexpected-ipns-name)
    (not (matches? raw-cid-pattern cid)) (conj :manifest-cid)
    (not (true? signature-verified?)) (conj :ipns-signature)
    (not (true? valid?)) (conj :ipns-validity)
    (not= sequence (:sequence manifest)) (conj :ipns-sequence-mismatch)))

(defn- compatibility-errors [context manifest]
  (let [target (:target manifest)]
    (cond-> []
      (not= (:channel context) (:channel manifest)) (conj :unexpected-channel)
      (not= (:architecture context) (:architecture target))
      (conj :incompatible-architecture)
      (not= (:machine context) (:machine target)) (conj :incompatible-machine)
      (< (or (:aiueos-abi context) 0) (or (:min-aiueos-abi target) 1))
      (conj :incompatible-aiueos-abi))))

(defn- continuity-errors [state head manifest]
  (let [last-sequence (or (:last-sequence state) 0)
        last-cid (:manifest-cid state)]
    (cond-> []
      (< (:sequence head) last-sequence) (conj :rollback)
      (and (= (:sequence head) last-sequence)
           last-cid
           (not= (:cid head) last-cid))
      (conj :sequence-equivocation)
      (and (> (:sequence head) last-sequence)
           last-cid
           (not= (:previous manifest) last-cid))
      (conj :broken-history)
      (and (zero? last-sequence) (:previous manifest))
      (conj :unexpected-genesis-parent))))

(defn plan-update
  "Admit a verified IPNS head and produce a crash-safe update plan.

  `head` is the output of the IPNS verifier, not untrusted record bytes. The
  caller must also recompute the manifest CID before supplying `:cid`."
  [{:keys [context state head manifest]}]
  (let [manifest (normalize-manifest manifest)
        errors (vec (concat (manifest-errors manifest)
                            (head-errors head context manifest)
                            (compatibility-errors context manifest)
                            (continuity-errors state head manifest)))]
    (if (seq errors)
      {:status :refused :errors errors :fallback :last-known-good}
      (let [cached (set (or (:cached-block-cids state) #{}))
            missing (filterv #(not (contains? cached (:cid %))) (:blocks manifest))
            same-artifact? (= (get-in state [:artifact :sha256])
                              (get-in manifest [:artifact :sha256]))
            base {:sequence (:sequence manifest)
                  :manifest-cid (:cid head)
                  :artifact (:artifact manifest)
                  :commit-state {:last-sequence (:sequence manifest)
                                 :manifest-cid (:cid head)
                                 :artifact (:artifact manifest)}
                  :fallback :last-known-good}]
        (cond
          same-artifact?
          (assoc base :status :current :download [])

          (seq missing)
          (assoc base :status :download :download missing
                 :activation {:staging :inactive-slot
                              :verify [:raw-cid-each-block :artifact-sha256]
                              :commit :atomic-after-full-verification})

          :else
          (assoc base :status :activate :download []
                 :activation {:staging :inactive-slot
                              :verify [:artifact-sha256]
                              :commit :atomic-after-full-verification}))))))

(defn boot-decision
  "Choose what may boot. A download/activation plan is not proof that its
  inactive slot was fully verified and atomically committed. Callers set
  :activation-committed? only after that separate device-side transaction."
  [{:keys [update-plan state]}]
  (if (and update-plan
           (or (= :current (:status update-plan))
               (:activation-committed? update-plan)))
    {:boot :admitted-channel
     :status (:status update-plan)
     :artifact (:artifact update-plan)}
    (if-let [artifact (:artifact state)]
      {:boot :last-known-good
       :status :offline-or-refused
       :artifact artifact}
      {:boot :without-model
       :status :no-admitted-model})))
