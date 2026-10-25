(ns yield.corner
  "PVT (Process-Voltage-Temperature) corner analysis. Restored from
  kami-yield's `corner` module (deleted PR #82).")

(def process-corners #{:tt :ff :ss :fs :sf})

(defn pvt-corner [name process voltage temperature-c]
  {:name name :process process :voltage voltage :temperature-c temperature-c})

(defn corner-result [corner-name value pass] {:corner-name corner-name :value value :pass pass})

(defn standard-corners
  "The 5 standard PVT corners (TT/FF/SS/FS/SF at nominal, best, worst conditions)."
  []
  [(pvt-corner "TT_0.9V_25C" :tt 0.9 25.0)
   (pvt-corner "FF_0.99V_-40C" :ff 0.99 -40.0)
   (pvt-corner "SS_0.81V_125C" :ss 0.81 125.0)
   (pvt-corner "FS_0.9V_25C" :fs 0.9 25.0)
   (pvt-corner "SF_0.9V_25C" :sf 0.9 25.0)])

(defn run-corners
  "Run all `corners` through `eval-fn` (a function of `[voltage temperature-c]`
  -> metric value) and check against `[spec-min spec-max]`. Process corner
  effects should be embedded in `eval-fn` or handled externally."
  [corners eval-fn spec-min spec-max]
  (mapv (fn [c]
          (let [value (eval-fn (:voltage c) (:temperature-c c))
                pass (and (>= value spec-min) (<= value spec-max))]
            (corner-result (:name c) value pass)))
        corners))
