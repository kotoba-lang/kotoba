(ns kotoba.eda.oss-report
  "Normalizes OSS EDA report text into kotoba signoff evidence EDN."
  (:require [kotoba.lang.text :as str]
            [kotoba.eda.core :as eda]))

(def tool->type
  {:sw/opensta :signoff/timing-pvt
   :sw/openroad :signoff/route
   :sw/klayout :signoff/drc
   :sw/magic :signoff/drc
   :sw/netgen :signoff/lvs
   :sw/ngspice :signoff/spice-corner
   :sw/openlane :signoff/route})

(def operation->type
  {:op/analyze-timing :signoff/timing-pvt
   :op/route :signoff/route
   :op/drc :signoff/drc
   :op/lvs :signoff/lvs
   :op/simulate :signoff/spice-corner})

(defn- parse-num [s]
  (when s #?(:clj (Double/parseDouble s) :cljs (js/parseFloat s))))

(defn- parse-int [s]
  (when s #?(:clj (Long/parseLong s) :cljs (js/parseInt s 10))))

(defn- first-match [re text]
  (second (re-find re text)))

(defn- all-doubles [re text]
  (mapv #(parse-num (second %)) (re-seq re text)))

(defn- status [pass?]
  (if pass? :passed :failed))

(defn- evidence [spec metrics pass?]
  (let [tool (:eda.job/tool spec)
        op (:eda.job/operation spec)
        row {:eda.signoff/type (or (:eda.signoff/type spec)
                                   (operation->type op)
                                   (tool->type tool)
                                   :signoff/oss-report)
             :eda.signoff/tool tool
             :eda.signoff/operation op
             :eda.signoff/status (status pass?)
             :eda.signoff/corner (:eda.signoff/corner spec)
             :eda.signoff/pvt (:eda.signoff/pvt spec)
             :eda.signoff/coverage (:eda.signoff/coverage spec)
             :eda.signoff/metrics metrics
             :eda.signoff/source-report (:eda.job/report spec)}]
    (assoc row :eda.signoff/evidence-cid (eda/stable-cid row))))

(defn parse-opensta [spec text]
  (let [slacks (all-doubles #"(?i)(?:slack|worst slack).*?(-?\d+(?:\.\d+)?)" text)
        worst (if (seq slacks) (reduce min slacks) (parse-num (first-match #"(?i)wns\s+(-?\d+(?:\.\d+)?)" text)))
        corners (or (parse-int (first-match #"(?i)corners?\s*[:=]\s*(\d+)" text)) 1)
        pass? (and (number? worst) (not (neg? worst)))]
    (evidence spec {:worst-slack-ns worst
                    :corners corners
                    :slacks slacks}
              pass?)))

(defn parse-openroad [spec text]
  (let [overflow (or (parse-int (first-match #"(?i)(?:remaining\s+)?overflow\s*[:=]?\s*(\d+)" text))
                     (parse-int (first-match #"(?i)total overflows:\s*(\d+)" text))
                     0)
        drvs (or (parse-int (first-match #"(?i)(?:route\s+)?violations\s*[:=]\s*(\d+)" text)) 0)]
    (evidence spec {:overflow overflow :route-violations drvs}
              (and (zero? overflow) (zero? drvs)))))

(defn parse-openlane [spec text]
  (let [wns (parse-num (first-match #"(?i)wns\s*[:=]\s*(-?\d+(?:\.\d+)?)" text))
        tns (parse-num (first-match #"(?i)tns\s*[:=]\s*(-?\d+(?:\.\d+)?)" text))
        drc (or (parse-int (first-match #"(?i)drc(?:\s+violations)?\s*[:=]\s*(\d+)" text)) 0)
        lvs (or (parse-int (first-match #"(?i)lvs(?:\s+errors| mismatches)?\s*[:=]\s*(\d+)" text)) 0)]
    (evidence spec {:wns wns :tns tns :drc-violations drc :lvs-mismatches lvs}
              (and (or (nil? wns) (not (neg? wns)))
                   (or (nil? tns) (not (neg? tns)))
                   (zero? drc)
                   (zero? lvs)))))

(defn parse-drc [spec text]
  (let [violations (or (parse-int (first-match #"(?i)(?:total\s+)?(?:drc\s+)?violations?\s*[:=]\s*(\d+)" text))
                       (parse-int (first-match #"(?i)errors?\s*[:=]\s*(\d+)" text))
                       0)]
    (evidence spec {:violations violations}
              (zero? violations))))

(defn parse-netgen [spec text]
  (let [mismatches (cond
                     (re-find #"(?i)netlists match uniquely|circuits match" text) 0
                     :else (or (parse-int (first-match #"(?i)(?:mismatches|errors)\s*[:=]\s*(\d+)" text))
                               (count (re-seq #"(?i)\b(mismatch|discrepancy|failed)\b" text))))]
    (evidence spec {:mismatches mismatches}
              (zero? mismatches))))

(defn parse-ngspice [spec text]
  (let [failed? (boolean (re-find #"(?i)\b(failed|fatal|singular|timestep too small)\b" text))
        measures (into {}
                       (map (fn [[_ k v]] [(keyword k) (parse-num v)]))
                       (re-seq #"(?im)^([A-Za-z_][\w.-]*)\s*=\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)" text))]
    (evidence spec {:measures measures :failure-detected failed?}
              (not failed?))))

(def parsers
  {:sw/opensta parse-opensta
   :sw/openroad parse-openroad
   :sw/openlane parse-openlane
   :sw/klayout parse-drc
   :sw/magic parse-drc
   :sw/netgen parse-netgen
   :sw/ngspice parse-ngspice})

(defn normalize-report [spec text]
  (if-let [parser (parsers (:eda.job/tool spec))]
    (parser spec text)
    (evidence spec {:error :unsupported-report-tool} false)))

(defn normalize-reports [reports]
  (let [rows (mapv (fn [{:keys [text] :as spec}]
                     (normalize-report spec text))
                   reports)
        passed (count (filter #(= :passed (:eda.signoff/status %)) rows))]
    {:eda.oss/source :oss-report-normalizer
     :eda.oss/pass-count passed
     :eda.oss/total (count rows)
     :eda.oss/status (if (= passed (count rows)) :passed :failed)
     :eda.signoff/evidence rows}))
