(ns cae.material-card
  "Fail-closed provenance and applicability checks for analysis material data.

  Passing these checks establishes traceability, not physical validation."
  (:require [kotoba.lang.text :as str]))

(def ^:private sha256-pattern #"^[0-9a-f]{64}$")
(def ^:private allowed-units
  {:youngs-modulus :Pa :yield-stress :Pa :plastic-stress :Pa
   :plastic-strain :one :poisson-ratio :one :density :kg/m3
   :thermal-conductivity :W/mK :specific-heat :J/kgK
   :thermal-expansion :one/K :temperature :K :strain-rate :one/s})

(defn- finite-number? [x]
  (and (number? x) #?(:clj (Double/isFinite (double x))
                      :cljs (js/Number.isFinite x))))

(defn- nonblank? [x] (and (string? x) (not (str/blank? x))))
(defn- valid-range? [x]
  (and (vector? x) (= 2 (count x)) (every? finite-number? x)
       (< (double (first x)) (double (second x)))))

(defn audit
  "Audit a material card's identity, source, units, uncertainty and approval.
  Returns an audited card or throws ExceptionInfo with all detected reasons."
  [card]
  (let [required [:material/id :revision :designation :standard :batch/lot
                  :supplier :laboratory :test-report :source-uri :source-sha256
                  :license :commercial-use? :test-method :orientation :condition
                  :calibration :properties :uncertainty :validity :approval]
        missing (vec (remove #(some? (get card %)) required))
        properties (:properties card)
        unit-errors (->> properties
                         (keep (fn [[quantity {:keys [unit value curve]}]]
                                 (cond
                                   (nil? (allowed-units quantity)) {:quantity quantity :reason :unsupported-quantity}
                                   (not= (allowed-units quantity) unit) {:quantity quantity :reason :invalid-or-ambiguous-unit
                                                                        :expected (allowed-units quantity) :actual unit}
                                   (and (some? value) (not (finite-number? value))) {:quantity quantity :reason :non-finite-value}
                                   (and (nil? value) (not (seq curve))) {:quantity quantity :reason :value-or-curve-required})))
                         vec)
        plastic-curve (get-in properties [:plastic-stress :curve])
        plastic-errors (when (seq plastic-curve)
                         (let [strains (mapv :plastic-strain plastic-curve)
                               stresses (mapv :stress plastic-curve)]
                           (cond-> []
                             (not (every? finite-number? (concat strains stresses))) (conj :plastic-curve-non-finite)
                             (not (apply < strains)) (conj :plastic-strain-not-strictly-increasing)
                             (not (apply <= stresses)) (conj :plastic-stress-decreases))))
        validity (:validity card)
        reasons (cond-> []
                  (seq missing) (conj {:reason :missing-fields :fields missing})
                  (not (nonblank? (:material/id card))) (conj {:reason :invalid-material-id})
                  (not (nonblank? (:revision card))) (conj {:reason :invalid-revision})
                  (not (re-matches sha256-pattern (or (:source-sha256 card) ""))) (conj {:reason :invalid-source-sha256})
                  (not (map? properties)) (conj {:reason :properties-required})
                  (seq unit-errors) (conj {:reason :property-errors :errors unit-errors})
                  (seq plastic-errors) (conj {:reason :invalid-plastic-curve :errors plastic-errors})
                  (not (map? (:uncertainty card))) (conj {:reason :uncertainty-required})
                  (not (every? #(contains? (:uncertainty card) %) (keys properties)))
                  (conj {:reason :property-uncertainty-incomplete})
                  (not (valid-range? (:temperature-K validity))) (conj {:reason :invalid-temperature-range})
                  (not (valid-range? (:strain-rate-1-s validity))) (conj {:reason :invalid-strain-rate-range})
                  (not (nonblank? (get-in card [:calibration :procedure]))) (conj {:reason :calibration-procedure-required})
                  (not (nonblank? (get-in card [:calibration :version]))) (conj {:reason :calibration-version-required})
                  (not= :approved (get-in card [:approval :status])) (conj {:reason :revision-not-approved})
                  (not (nonblank? (get-in card [:approval :approved-by]))) (conj {:reason :approver-required}))]
    (when (seq reasons)
      (throw (ex-info "material card audit failed" {:material/id (:material/id card) :reasons reasons})))
    (assoc card :material-card/version 1 :status :metadata-audited)))

(defn usage-eligibility
  "Check an audited card against an analysis temperature/rate and intended use."
  [card {:keys [temperature-K strain-rate-1-s commercial? analysis-date]}]
  (let [audited (audit card)
        [tmin tmax] (get-in audited [:validity :temperature-K])
        [rmin rmax] (get-in audited [:validity :strain-rate-1-s])
        reasons (cond-> []
                  (not (finite-number? temperature-K)) (conj :temperature-required)
                  (and (finite-number? temperature-K) (not (<= tmin temperature-K tmax))) (conj :temperature-extrapolation)
                  (not (finite-number? strain-rate-1-s)) (conj :strain-rate-required)
                  (and (finite-number? strain-rate-1-s) (not (<= rmin strain-rate-1-s rmax))) (conj :strain-rate-extrapolation)
                  (and commercial? (not (true? (:commercial-use? audited)))) (conj :commercial-use-not-permitted)
                  (nil? analysis-date) (conj :analysis-date-required)
                  (and analysis-date (get-in audited [:approval :valid-from])
                       (neg? (compare analysis-date (get-in audited [:approval :valid-from])))) (conj :approval-not-yet-valid)
                  (and analysis-date (get-in audited [:approval :valid-until])
                       (pos? (compare analysis-date (get-in audited [:approval :valid-until])))) (conj :approval-expired))]
    {:material/id (:material/id audited) :revision (:revision audited)
     :eligible? (empty? reasons) :reasons reasons
     :scope {:temperature-K temperature-K :strain-rate-1-s strain-rate-1-s
             :commercial? (boolean commercial?) :analysis-date analysis-date}}))

(defn attach
  "Attach a traceable card and its passing applicability decision to a case."
  [case card conditions]
  (let [decision (usage-eligibility card conditions)]
    (when-not (:eligible? decision)
      (throw (ex-info "material card is outside qualified use" decision)))
    (assoc case :material/card (audit card) :material/eligibility decision)))
