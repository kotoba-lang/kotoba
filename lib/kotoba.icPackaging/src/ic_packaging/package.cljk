(ns ic-packaging.package
  "IC package type definitions and estimation. Restored from kami-pkg's
  `package` module (kami-engine/kami-pkg/src/package.rs, deleted PR #82).")

;; PackageType variants
(defn qfp [pin-count pitch-mm] {:kind :qfp :pin-count pin-count :pitch-mm pitch-mm})
(defn bga [rows cols pitch-mm] {:kind :bga :rows rows :cols cols :pitch-mm pitch-mm})
(defn csp [rows cols pitch-mm] {:kind :csp :rows rows :cols cols :pitch-mm pitch-mm})
(defn wlcsp [bump-rows bump-cols bump-pitch-um] {:kind :wlcsp :bump-rows bump-rows :bump-cols bump-cols :bump-pitch-um bump-pitch-um})
(defn sip [] {:kind :sip})
(defn chiplet-2-5d [] {:kind :chiplet-2-5d})
(defn chiplet-3d [] {:kind :chiplet-3d})

(defn package
  [{:keys [name pkg-type body-size-mm die-size-mm pin-count
           thermal-resistance-jc thermal-resistance-ja]}]
  {:name name :pkg-type pkg-type :body-size-mm body-size-mm :die-size-mm die-size-mm
   :pin-count pin-count :thermal-resistance-jc thermal-resistance-jc
   :thermal-resistance-ja thermal-resistance-ja})

(defn- geometry-for [pkg-type [die-x die-y]]
  (case (:kind pkg-type)
    :qfp (let [{:keys [pin-count pitch-mm]} pkg-type
               side-pins (quot pin-count 4)
               body-side (+ (* side-pins pitch-mm) 2.0)]
           [pin-count body-side body-side 1.4])
    :bga (let [{:keys [rows cols pitch-mm]} pkg-type
               count (* rows cols)]
           [count (+ (* cols pitch-mm) 1.0) (+ (* rows pitch-mm) 1.0) 1.2])
    :csp (let [{:keys [rows cols pitch-mm]} pkg-type
               count (* rows cols)]
           [count (+ (* cols pitch-mm) 0.5) (+ (* rows pitch-mm) 0.5) 0.8])
    :wlcsp (let [{:keys [bump-rows bump-cols bump-pitch-um]} pkg-type
                 count (* bump-rows bump-cols)
                 pitch-mm (/ bump-pitch-um 1000.0)]
             [count (+ die-x pitch-mm) (+ die-y pitch-mm) 0.5])
    :sip [256 (* die-x 2.5) (* die-y 2.5) 2.0]
    :chiplet-2-5d [512 (* die-x 3.0) (* die-y 2.0) 1.5]
    :chiplet-3d [1024 (* die-x 1.5) (* die-y 1.5) 2.5]))

(defn- name-for [pkg-type]
  (case (:kind pkg-type)
    :qfp (str "QFP-" (:pin-count pkg-type))
    :bga (str "BGA-" (* (:rows pkg-type) (:cols pkg-type)))
    :csp (str "CSP-" (* (:rows pkg-type) (:cols pkg-type)))
    :wlcsp (str "WLCSP-" (* (:bump-rows pkg-type) (:bump-cols pkg-type)))
    :sip "SiP"
    :chiplet-2-5d "Chiplet-2.5D"
    :chiplet-3d "Chiplet-3D"))

(defn estimate-package
  "Estimate package body size and thermal properties from `pkg-type` and
  `die-size-mm` (`[x y]`). Body dimensions include clearance around the
  die; thermal resistances are estimated from package area using
  simplified empirical models
  (`theta_jc ~ 0.5 + 20/area`, `theta_ja ~ theta_jc + 30/area`)."
  [pkg-type die-size-mm]
  (let [[pin-count body-x body-y body-z] (geometry-for pkg-type die-size-mm)
        area (* body-x body-y)
        theta-jc (+ 0.5 (/ 20.0 area))
        theta-ja (+ theta-jc (/ 30.0 area))]
    (package {:name (name-for pkg-type) :pkg-type pkg-type
              :body-size-mm [body-x body-y body-z] :die-size-mm die-size-mm
              :pin-count pin-count :thermal-resistance-jc theta-jc :thermal-resistance-ja theta-ja})))
