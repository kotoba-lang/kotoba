(ns aiueos.runtime-update
  "Signed blue/green updates for the Kototama inference runtime.

  AIUEOS remains the base and authority boundary.  Runtime bundles are pulled
  as immutable signed objects into an inactive runtime slot, probed beside the
  active runtime, then switched without a kernel reboot."
  (:require [grant.ota :as ota]
            [grant.update :as update]))

(def schema "aiueos.kototama-runtime-update/v1")
(def required-artifact-kinds #{:component :guest})
(def required-health-signals
  #{:runtime-admission :model-bind :murakumo-result})
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

(defn manifest-errors [context manifest]
  (let [artifacts (vec (:artifacts manifest))
        kinds (mapv :kind artifacts)
        target (:target manifest)]
    (cond-> (vec (mapcat artifact-errors artifacts))
      (not= schema (:schema manifest)) (conj :schema)
      (not (and (string? (:manifest-id manifest))
                (re-matches sha256-pattern (:manifest-id manifest))))
      (conj :manifest-id)
      (not (positive? (:sequence manifest))) (conj :sequence)
      (not= (:architecture context) (:architecture target))
      (conj :incompatible-architecture)
      (< (or (:aiueos-abi context) 0) (or (:min-aiueos-abi target) 1))
      (conj :incompatible-aiueos-abi)
      (< (or (:kototama-runtime-abi context) 0)
         (or (:min-kototama-runtime-abi target) 1))
      (conj :incompatible-runtime-abi)
      (not= required-artifact-kinds (set kinds)) (conj :artifact-set)
      (not= (count kinds) (count (distinct kinds)))
      (conj :duplicate-artifact-kind))))

(defn plan-pull [{:keys [context manifest publisher-state]}]
  (let [errors (manifest-errors context manifest)]
    (if (seq errors)
      {:status :refused :errors errors :fallback :active-runtime}
      (let [verdict (ota/admit manifest publisher-state)]
        (if-not (ota/granted? verdict)
          {:status :refused :verdict verdict :fallback :active-runtime}
          {:status :pull
           :manifest-id (:manifest-id manifest)
           :sequence (:sequence manifest)
           :admission (:aiueos.ota/admission verdict)
           :downloads (mapv #(select-keys % [:kind :bytes :sha256 :url])
                            (:artifacts manifest))
           :transport :https
           :source :kotobase-ipfs-immutable
           :staging {:slot :inactive-runtime
                     :active-runtime-writes? false
                     :verify [:artifact-bytes :artifact-sha256]
                     :activation :blue-green}
           :kernel-reboot? false
           :fallback :active-runtime})))))

(defn health-status [signals]
  (let [values (map signals required-health-signals)]
    (cond
      (some false? values) :fail
      (every? true? values) :pass
      :else :unknown)))

(defn advance
  [{:keys [context manifest admission step observed-digests now-ms
           previous-preserved? rollback-window health-signals probe-elapsed-ms]}]
  (let [errors (manifest-errors context manifest)
        health (health-status health-signals)
        base {:manifest-id (:manifest-id manifest)
              :admission admission
              :step step
              :class :blue-green
              :kinds [:component :guest]
              :observed-digests observed-digests
              :artifacts (:artifacts manifest)
              :now-ms now-ms
              :previous-preserved? previous-preserved?
              :rollback-window rollback-window
              :owner-peers-updating 0
              :machine-busy? false
              :in-maintenance-window? true
              :consent? false
              :health health
              :probe-elapsed-ms probe-elapsed-ms}]
    (cond
      (seq errors)
      {:status :refused :errors errors :fallback :active-runtime}

      (and (= :probing step) (update/rollback-required? base))
      {:status :rolled-back :reason (if (= :fail health)
                                      :runtime-health-failed
                                      :runtime-health-timeout)
       :activate :previous-runtime :kernel-reboot? false}

      (and (= :probing step) (= :unknown health))
      {:status :probing :action :wait-for-runtime-health
       :kernel-reboot? false}

      :else
      (let [verdict (ota/advance base)]
        (if-not (ota/granted? verdict)
          {:status :refused :verdict verdict :fallback :active-runtime}
          (let [next-step (:aiueos.update/step verdict)]
            {:status next-step
             :action (case next-step
                       :fetched :persist-verified-runtime-bundle
                       :staged :write-inactive-runtime
                       :probing :start-candidate-side-by-side
                       :committed :switch-routing-and-drain-previous
                       :none)
             :manifest-id (:manifest-id manifest)
             :sequence (:sequence manifest)
             :activation :blue-green
             :active-runtime-writes? false
             :kernel-reboot? false}))))))
