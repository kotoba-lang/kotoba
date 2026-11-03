(ns cae.dataset
  "License-aware, solver-neutral dataset manifests and sample normalization."
  (:require [kotoba.lang.text :as str]))

(defn manifest [{:keys [id revision license domain files source]}]
  {:dataset/id (str id) :revision revision :license license :domain (keyword domain) :files (vec files) :source source :status :unverified})

(defn verify-manifest [m]
  (when-not (and (:dataset/id m) (:revision m) (:license m) (:domain m))
    (throw (ex-info "dataset manifest requires id, revision, license and domain" {:manifest m})))
  (assoc m :status :metadata-verified))

(def ^:private sha-pattern #"^[0-9a-f]{64}$")
(def ^:private revision-pattern #"^[0-9a-f]{40}$")
(def ^:private validation-usages #{:verification-reference :experimental-validation})

(defn download-policy
  "Classify distribution/download policy independently from validation quality.
  Standard OSS workflows accept only explicitly commercial-compatible data."
  [m]
  (cond
    (true? (:commercial-use? m))
    {:profile (if (= :experiment (:data-origin m)) :commercial-experiment :commercial-reference)
     :standard-download? true :reason nil}

    (false? (:commercial-use? m))
    {:profile :research-only :standard-download? false :reason :noncommercial-license}

    :else
    {:profile :blocked-unverified :standard-download? false :reason :commercial-rights-unverified}))

(defn require-standard-download! [m]
  (let [policy (download-policy m)]
    (when-not (:standard-download? policy)
      (throw (ex-info "dataset is excluded from the standard OSS download profile"
                      {:dataset/id (:dataset/id m) :policy policy})))
    m))

(defn- finite-number? [x]
  (and (number? x) #?(:clj (Double/isFinite (double x))
                      :cljs (js/Number.isFinite x))))

(defn audit-manifest
  "Strict v2 audit for immutable, license-aware external CAE evidence.
  This verifies metadata declarations only; use `verify-content` with hashes
  calculated from downloaded bytes before consuming any file."
  [m]
  (let [required [:dataset/id :provider :repository :revision :license :license-uri
                  :domain :data-origin :intended-use :commercial-use? :citation :files]
        missing (vec (remove #(some? (get m %)) required))
        files (:files m)
        file-errors (vec
                     (mapcat (fn [{:keys [path sha256 bytes split]}]
                               (cond-> []
                                 (not (seq path)) (conj {:path path :reason :missing-path})
                                 (not (re-matches sha-pattern (or sha256 ""))) (conj {:path path :reason :invalid-sha256})
                                 (not (and (integer? bytes) (pos? bytes))) (conj {:path path :reason :invalid-size})
                                 (nil? split) (conj {:path path :reason :missing-split}))) files))]
    (when (or (seq missing) (not (re-matches revision-pattern (or (:revision m) "")))
              (not (vector? files)) (seq file-errors))
      (throw (ex-info "dataset v2 manifest audit failed"
                      {:missing missing :revision (:revision m) :file-errors file-errors})))
    (assoc m :manifest-version 2 :status :metadata-audited)))

(defn immutable-download-urls [m]
  (let [m (audit-manifest m)
        base (case (:provider m)
               :hugging-face (str "https://huggingface.co/datasets/" (:repository m) "/resolve/" (:revision m))
               :github-raw (str "https://raw.githubusercontent.com/" (:repository m) "/" (:revision m))
               :direct-https nil
               (throw (ex-info "unsupported immutable dataset provider" {:provider (:provider m)})))]
    (mapv (fn [{:keys [path url]}]
            (let [resolved (if (= :direct-https (:provider m)) url (str base "/" path))]
              (when-not (and (string? resolved) (str/starts-with? resolved "https://"))
                (throw (ex-info "direct dataset file requires an HTTPS URL" {:path path :url url})))
              {:path path :url resolved})) (:files m))))

(defn parse-nist-midas-1045
  "Parse the public NIST MIDAS 1045-steel experiment/model CSV.

  The source concatenates experiment blocks. Each returned block retains the
  initial condition and paired measured/model stresses; no uncertainty is
  invented when the source does not provide it."
  [text]
  (let [number #(double #?(:clj (Double/parseDouble (str/trim %))
                           :cljs (js/parseFloat (str/trim %))))
        lines (vec (str/split-lines text))
        starts (keep-indexed #(when (str/starts-with? %2 "Experiment Number:") %1) lines)
        blocks (mapv
                (fn [[start end]]
                  (let [rows (subvec lines start end)
                        field (fn [prefix]
                                (some #(when (str/starts-with? % prefix)
                                         (second (str/split % #"," 2))) rows))
                        header-index (first (keep-indexed #(when (str/starts-with? %2 "Strain, Measured Stress") %1) rows))
                        samples (if header-index
                                  (->> (subvec rows (inc header-index))
                                       (take-while #(re-matches #"\s*[-+0-9.eE]+\s*,.*" %))
                                       (mapv (fn [line]
                                               (let [[strain measured temp model model-temp]
                                                     (mapv number (str/split line #","))]
                                                 {:strain strain :measured-stress-MPa measured
                                                  :temperature-C temp :model-stress-MPa model
                                                  :model-temperature-C model-temp}))))
                                  [])]
                    {:experiment/id (str/trim (field "Experiment Number:"))
                     :initial-temperature-C (number (field "Initial Temp [C]:"))
                     :normal-strain-rate-1-s (number (field "Normal Strain Rate [1/s]:"))
                     :samples samples :sample-count (count samples)}))
                (map vector starts (concat (rest starts) [(count lines)])))]
    {:format :nist-midas-1045-v1 :material "annealed AISI 1045 steel"
     :experiments blocks :experiment-count (count blocks)
     :sample-count (reduce + (map :sample-count blocks))
     :measurement-uncertainty :not-provided-in-source}))

(defn calibration-report
  "Calculate paired model-vs-experiment residual statistics without converting
  them into an experimental-validation claim. A declared RMSE limit is required."
  [parsed rmse-limit-MPa]
  (when-not (and (finite-number? rmse-limit-MPa) (pos? (double rmse-limit-MPa)))
    (throw (ex-info "a positive finite RMSE limit is required" {:rmse-limit-MPa rmse-limit-MPa})))
  (let [samples (mapcat :samples (:experiments parsed))
        errors (mapv #(- (:model-stress-MPa %) (:measured-stress-MPa %)) samples)
        n (count errors)]
    (when (zero? n) (throw (ex-info "calibration dataset contains no samples" {})))
    (let [rmse (#?(:clj Math/sqrt :cljs js/Math.sqrt) (/ (reduce + (map #(* % %) errors)) n))
          bias (/ (reduce + errors) n)
          maximum (apply max (map #(#?(:clj Math/abs :cljs js/Math.abs) %) errors))]
      {:check :constitutive-calibration-correlation :samples n :rmse-MPa rmse
       :mean-bias-MPa bias :maximum-absolute-error-MPa maximum
       :rmse-limit-MPa (double rmse-limit-MPa) :passed? (<= rmse rmse-limit-MPa)
       :experimental-validation? false
       :limitations [:source-does-not-provide-measurement-uncertainty
                     :published-model-correlation-is-not-independent-validation]})))

(defn parse-nasa-ofi
  "Parse NASA TMR smooth-body-separation Oil Film Interferometry text.
  Returns the measured Cf and its per-sample absolute uncertainty e_Cf."
  [text]
  (let [number-pattern #"[-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?"
        rows (->> (str/split-lines text)
                  (map str/trim)
                  (filter #(re-matches (re-pattern (str "(?:" number-pattern "\\s+){6}" number-pattern)) %))
                  (mapv (fn [line]
                          (let [[x y z dx dz cf uncertainty] (mapv #(double #?(:clj (Double/parseDouble %) :cljs (js/parseFloat %)))
                                                                   (re-seq number-pattern line))]
                            {:x-mm x :y-mm y :z-mm z :dx-mm dx :dz-mm dz
                             :skin-friction-coefficient cf :absolute-uncertainty uncertainty}))))]
    {:format :nasa-tmr-ofi-v1 :quantity :skin-friction-coefficient
     :uncertainty :per-sample-absolute :samples rows :sample-count (count rows)}))

(defn verify-content
  "Compare independently calculated `{path {:sha256 ... :bytes ...}}` facts."
  [manifest observed]
  (let [m (audit-manifest manifest)
        checks (mapv (fn [{:keys [path sha256 bytes]}]
                       (let [actual (get observed path)]
                         {:path path :expected-sha256 sha256 :actual-sha256 (:sha256 actual)
                          :expected-bytes bytes :actual-bytes (:bytes actual)
                          :passed? (and (= sha256 (:sha256 actual)) (= bytes (:bytes actual)))})) (:files m))
        passed? (and (seq checks) (every? :passed? checks))]
    (assoc m :content-checks checks :content-verified? (boolean passed?)
           :status (if passed? :content-verified :content-rejected))))

(defn qualification-eligibility
  "Determine whether a dataset may support an industrial validation claim.
  Synthetic/simulation data can verify regression but cannot independently
  validate physical accuracy. Non-commercial licenses are rejected here."
  [m]
  (let [reasons (cond-> []
                  (not= :content-verified (:status m)) (conj :content-not-verified)
                  (not (validation-usages (:intended-use m))) (conj :not-validation-use)
                  (not= :experiment (:data-origin m)) (conj :not-independent-experiment)
                  (not (true? (:commercial-use? m))) (conj :commercial-use-not-permitted)
                  (not= :independent (:validation-role m)) (conj :not-independent-from-solver)
                  (or (not (map? (:uncertainty m)))
                      (= :not-provided-in-source (get-in m [:uncertainty :status])))
                  (conj :measurement-uncertainty-missing)
                  (not (some #{:validation :test} (map :split (:files m)))) (conj :held-out-split-missing))]
    {:dataset/id (:dataset/id m) :eligible? (empty? reasons) :reasons reasons
     :scope (:validation-scope m)}))

(defn z24-fem-validation-readiness
  "Gate processed Z24 signals before they can be compared with FEM modes.
  Byte-valid vibration arrays alone cannot establish frequencies or mode shapes."
  [m semantic]
  (let [scope (:validation-scope m)
        reasons (cond-> []
                  (not= :content-verified (:status m)) (conj :content-not-verified)
                  (not= [1530 27 6000] (get-in semantic [:inputs :shape])) (conj :unexpected-input-shape)
                  (not= "<f4" (get-in semantic [:inputs :descriptor])) (conj :unexpected-input-dtype)
                  (not (finite-number? (:sampling-frequency-hz scope))) (conj :sampling-frequency-missing)
                  (not (and (vector? (:sensor-layout scope)) (= 27 (count (:sensor-layout scope)))))
                  (conj :sensor-layout-missing)
                  (not (and (map? (:label-semantics scope)) (= 17 (count (:label-semantics scope)))))
                  (conj :damage-label-semantics-missing)
                  (or (not (map? (:uncertainty m)))
                      (= :not-provided-in-source (get-in m [:uncertainty :status])))
                  (conj :measurement-uncertainty-missing)
                  (not= :float32 (get-in m [:source-declarations :input-dtype]))
                  (conj :source-dtype-declaration-mismatch))]
    {:dataset/id (:dataset/id m) :ready? (empty? reasons) :reasons reasons
     :required-comparison [:natural-frequency-hz :mode-shape]
     :scope scope}))

(defn sample [{:keys [dataset-id split index coordinates fields target]}]
  {:dataset/id (str dataset-id) :split (keyword (or split :unknown)) :index (long (or index 0)) :coordinates (vec coordinates) :fields (into {} fields) :target target :format :kotoba-physics-sample-v1})

(defn scalar-field [sample field]
  (let [values (get-in sample [:fields field])]
    {:dataset/id (:dataset/id sample) :field field :count (count values) :values (vec (map double values)) :units nil :status :unverified}))

(defn file-kind [path]
  (let [p (str/lower (str path))]
    (cond (str/ends-with? p ".h5") :hdf5 (str/ends-with? p ".vtu") :vtu (str/ends-with? p ".vtk") :vtk (str/ends-with? p ".msh") :gmsh (str/ends-with? p ".inp") :calculix :else :unknown)))
