(ns spice.model
  "Device compact-model parameters (MOSFET/BJT/diode) + a named model
  library. Restored from kami-spice's `model` module (deleted PR #82).")

(defn default-nmos
  "Default Level-1-style NMOS compact model."
  [name]
  {:name name :mosfet-type :nmos :vth0 0.7 :kp 110e-6 :lambda 0.04
   :tox 9e-9 :nsub 1e17 :uo 600.0 :phi 0.65 :gamma 0.37})

(defn default-npn
  "Default Ebers-Moll-style NPN BJT compact model."
  [name]
  {:name name :bjt-type :npn :is-sat 1e-15 :bf 100.0 :br 1.0 :vaf 100.0 :var 0.0})

(defn default-diode
  "Default diode model."
  [name]
  {:name name :is-sat 1e-14 :n 1.0 :bv 100.0 :rs 0.0})

(defn library
  "A fresh, empty device-model library."
  []
  {:models {}})

(defn add-mosfet [lib model] (assoc-in lib [:models (:name model)] [:mosfet model]))
(defn add-bjt [lib model] (assoc-in lib [:models (:name model)] [:bjt model]))
(defn add-diode [lib model] (assoc-in lib [:models (:name model)] [:diode model]))

(defn get-model [lib name] (get-in lib [:models name]))
(defn model-count [lib] (count (:models lib)))
