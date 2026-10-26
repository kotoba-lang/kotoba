(ns aiueos.os-update
  "Signed, fail-closed A/B update decisions for a GMKtec K16.

  Network and block I/O remain provider mechanisms. This namespace binds the
  publisher admission to the exact release, constrains downloads to immutable
  Kotobase/IPFS HTTPS objects, and decides when an inactive OS slot may be
  tried, committed, or rolled back."
  (:require [grant.ota :as ota]
            [grant.update :as update]))

(def schema "aiueos.os-update/v1")
(def required-artifact-kinds #{:loader :kernel :initramfs})
(def required-health-signals
  #{:boot :storage :direct-https :murakumo-node})
(def ^:private sha256-pattern #"[0-9a-f]{64}")
(def ^:private immutable-url-pattern
  #"https://ipfs\.kotobase\.net/ipfs/[a-z0-9]+")

(defn- positive? [value]
  (and (integer? value) (pos? value)))

(defn- artifact-errors [{:keys [kind bytes sha256 url]}]
  (cond-> []
    (not (contains? required-artifact-kinds kind))
    (conj :unknown-artifact-kind)
    (not (positive? bytes))
    (conj :artifact-bytes)
    (not (and (string? sha256) (re-matches sha256-pattern sha256)))
    (conj :artifact-sha256)
    (not (and (string? url) (re-matches immutable-url-pattern url)))
    (conj :artifact-url)))

(defn manifest-errors
  "Return every local compatibility or byte-shape fault in `manifest`.

  Publisher signatures, revocation, sequence and freshness are intentionally
  left to `grant.publisher`; this check runs before that admission."
  [context manifest]
  (let [artifacts (vec (:artifacts manifest))
        kinds (mapv :kind artifacts)
        target (:target manifest)]
    (cond-> (vec (mapcat artifact-errors artifacts))
      (not= schema (:schema manifest))
      (conj :schema)
      (not (and (string? (:manifest-id manifest))
                (re-matches sha256-pattern (:manifest-id manifest))))
      (conj :manifest-id)
      (not (positive? (:sequence manifest)))
      (conj :sequence)
      (not= "x86_64" (:architecture target))
      (conj :target-architecture)
      (not= "gmktec-k16" (:machine target))
      (conj :target-machine)
      (not= (:architecture context) (:architecture target))
      (conj :incompatible-architecture)
      (not= (:machine context) (:machine target))
      (conj :incompatible-machine)
      (< (or (:aiueos-abi context) 0) (or (:min-aiueos-abi target) 1))
      (conj :incompatible-aiueos-abi)
      (not= required-artifact-kinds (set kinds))
      (conj :artifact-set)
      (not= (count kinds) (count (distinct kinds)))
      (conj :duplicate-artifact-kind))))

(defn plan-pull
  "Admit a release and return its bounded, immutable fetch plan.

  `publisher-state` contains the installed sequence, root, revocation bitmap
  and clock evidence consumed by `grant.publisher`. A refusal never produces
  download work."
  [{:keys [context manifest publisher-state]}]
  (let [errors (manifest-errors context manifest)]
    (if (seq errors)
      {:status :refused :errors errors :fallback :last-known-good}
      (let [verdict (ota/admit manifest publisher-state)]
        (if-not (ota/granted? verdict)
          {:status :refused :verdict verdict :fallback :last-known-good}
          {:status :pull
           :manifest-id (:manifest-id manifest)
           :sequence (:sequence manifest)
           :admission (:aiueos.ota/admission verdict)
           :downloads (mapv #(select-keys % [:kind :bytes :sha256 :url])
                            (:artifacts manifest))
           :transport :https
           :source :kotobase-ipfs-immutable
           :staging {:slot :inactive-os
                     :active-slot-writes? false
                     :verify [:artifact-bytes :artifact-sha256]
                     :write-order [:inactive-data :flush :full-readback
                                   :inactive-header :flush-and-readback]
                     :selector-write :after-full-verification}
           :fallback :last-known-good})))))

(defn health-status
  "Collapse the required physical signals without treating absence as success."
  [signals]
  (let [values (map signals required-health-signals)]
    (cond
      (some false? values) :fail
      (every? true? values) :pass
      :else :unknown)))

(defn- update-kinds [artifacts]
  ;; An initramfs changes the booted kernel environment and therefore uses the
  ;; same disruptive class. Artifact identity remains separate in OTA hashes.
  (->> artifacts
       (map (fn [{:keys [kind]}] (if (= :initramfs kind) :kernel kind)))
       distinct
       vec))

(defn advance
  "Advance one signed update step or choose rollback/wait during trial boot.

  `step` follows `grant.update/steps`. Downloaded bytes are supplied as
  `observed-digests`; the provider may not turn a partial fetch into a stage.
  During `:probing`, false health or timeout rolls back, missing evidence waits,
  and only all required physical signals commit the candidate slot."
  [{:keys [context manifest admission step observed-digests now-ms
           previous-preserved? rollback-window owner-peers-updating
           machine-busy? in-maintenance-window? consent? health-signals
           probe-elapsed-ms] :as request}]
  (let [errors (manifest-errors context manifest)
        health (health-status health-signals)
        base {:manifest-id (:manifest-id manifest)
              :admission admission
              :step step
              :class :ab-reboot
              :kinds (update-kinds (:artifacts manifest))
              :observed-digests observed-digests
              :artifacts (:artifacts manifest)
              :now-ms now-ms
              :previous-preserved? previous-preserved?
              :rollback-window rollback-window
              :owner-peers-updating owner-peers-updating
              :machine-busy? machine-busy?
              :in-maintenance-window? in-maintenance-window?
              :consent? consent?
              :health health
              :probe-elapsed-ms probe-elapsed-ms}]
    (cond
      (seq errors)
      {:status :refused :errors errors :fallback :last-known-good}

      (and (= :probing step)
           (update/rollback-required? base))
      {:status :rolled-back
       :reason (if (= :fail health) :health-failed :health-timeout)
       :boot :previous-slot
       :manifest-id (:manifest-id manifest)}

      (and (= :probing step) (= :unknown health))
      {:status :probing
       :action :wait-for-health
       :manifest-id (:manifest-id manifest)}

      :else
      (let [verdict (ota/advance base)]
        (if-not (ota/granted? verdict)
          {:status :refused :verdict verdict :fallback :last-known-good}
          (let [next-step (:aiueos.update/step verdict)]
            {:status next-step
             :action (case next-step
                       :fetched :persist-verified-download
                       :staged :write-inactive-slot
                       :probing :trial-boot-inactive-once
                       :committed :activate-candidate
                       :none)
             :manifest-id (:manifest-id manifest)
             :sequence (:sequence manifest)
             :admission admission
             :active-slot-writes? false
             :previous-preserved? previous-preserved?}))))))

(defn boot-selection
  "Choose a slot without letting an unconfirmed candidate become permanent."
  [{:keys [step previous-slot candidate-slot trial-attempts]}]
  (cond
    (= :committed step)
    {:boot candidate-slot :mode :committed}

    (and (= :staged step) (zero? (or trial-attempts 0)))
    {:boot candidate-slot :mode :trial :next-trial-attempts 1}

    (#{:staged :rolled-back :refused} step)
    {:boot previous-slot :mode :last-known-good}

    :else
    {:boot previous-slot :mode :current}))
