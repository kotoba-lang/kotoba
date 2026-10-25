(ns ibis.parser
  "Simplified line-based parser for a `.ibs`-like text format. Recognizes
  [Component]/[Manufacturer]/[Package]/[Pin]/[Model]/[Model Type]/
  [Pulldown]/[Pullup]/[POWER Clamp]/[GND Clamp]/[Ramp] section headers
  (case-insensitive), then either `key = value` lines or whitespace-
  separated tabular rows underneath each, accumulating them into the
  `ibis.component`/`ibis.model` data model.

  Not a conformant IBIS grammar parser: submodels, series models,
  [Voltage Range]/temperature corners, and continuation lines are out of
  scope."
  (:require [kotoba.lang.text :as str]
            [ibis.component :as component]
            [ibis.model :as model]))

(defn- parse-num
  "Parse a decimal number from `s`, or nil if `s` isn't one (e.g. IBIS's
  `NA`/`--` placeholders for an absent optional value)."
  [s]
  (when (and s (re-matches #"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?" s))
    #?(:clj (Double/parseDouble s) :cljs (js/parseFloat s))))

(defn- comment-or-blank?
  [line]
  (or (str/blank? line) (re-matches #"\s*[|;].*" line)))

(defn- section-header
  "If `line` is a `[Section Name] trailing text` header, return
  `[section-keyword trailing]`, else nil."
  [line]
  (when-let [[_ name trailing] (re-matches #"\[([^\]]+)\]\s*(.*)" line)]
    [(-> name str/trim str/lower (str/replace #"\s+" "-") keyword)
     (str/trim trailing)]))

(defn- kv-line
  "If `line` is a `key = value` line, return `[lower-cased-key value]`,
  else nil."
  [line]
  (when-let [[_ k v] (re-matches #"([^=]+?)\s*=\s*(.+)" (str/trim line))]
    [(str/lower (str/trim k)) (str/trim v)]))

(defn- table-row
  "If `line` is two whitespace-separated numbers, return `[voltage
  current]`, else nil."
  [line]
  (let [nums (map parse-num (str/split (str/trim line) #"\s+"))]
    (when (and (= 2 (count nums)) (every? some? nums)) nums)))

(def ^:private model-type-aliases
  {"input" :input "output" :output "io" :io "i/o" :io
   "3-state" :3-state "tristate" :3-state "open-drain" :open-drain})

(defn- apply-package-kv
  [cmp kv]
  (if-let [[k v] kv]
    (let [n (parse-num v)]
      (case k
        "r_pkg" (assoc-in cmp [:package :r-pkg] n)
        "l_pkg" (assoc-in cmp [:package :l-pkg] n)
        "c_pkg" (assoc-in cmp [:package :c-pkg] n)
        cmp))
    cmp))

(defn- apply-ramp-kv
  [ramp kv]
  (if-let [[k v] kv]
    (cond
      (= k "r_load") (assoc ramp :r-load (parse-num v))
      (re-find #"dv/dt" k) (let [[dv dt] (map parse-num (str/split v #"/"))]
                             (assoc ramp :dv dv :dt dt))
      :else ramp)
    ramp))

(defn- apply-pin-row
  [cmp line]
  (let [[pin-name signal-name model-name r l c] (str/split (str/trim line) #"\s+")]
    (if (and pin-name signal-name model-name)
      (component/add-pin cmp pin-name
                          {:signal-name signal-name :model-name model-name
                           :r-pin (parse-num r) :l-pin (parse-num l) :c-pin (parse-num c)})
      cmp)))

(defn- apply-header
  [state sec trailing]
  (case sec
    :component (assoc state :section :top
                       :component (component/component trailing nil (component/package {})))
    :manufacturer (-> state (assoc :section :top)
                      (assoc-in [:component :manufacturer] trailing))
    :model (-> state (assoc :section :top :model-name trailing)
               (assoc-in [:models trailing] (model/model {:name trailing})))
    :model-type (assoc-in state [:models (:model-name state) :model-type]
                           (get model-type-aliases (str/lower trailing)))
    (:package :pin :pulldown :pullup :power-clamp :gnd-clamp :ramp)
    (assoc state :section sec)
    state))

(defn- apply-body-line
  [{:keys [section model-name] :as state} line]
  (case section
    :package (update state :component apply-package-kv (kv-line line))
    :pin (update state :component apply-pin-row line)
    :ramp (update-in state [:models model-name :ramp] apply-ramp-kv (kv-line line))
    (:pulldown :pullup :power-clamp :gnd-clamp)
    (if-let [point (table-row line)]
      (update-in state [:models model-name section] (fnil conj []) point)
      state)
    state))

(defn parse-ibs
  "Parse `.ibs`-like text `s`, returning `{:component <ibis.component>
  :models {model-name -> <ibis.model>}}`."
  [s]
  (-> (reduce
       (fn [state line]
         (if (comment-or-blank? line)
           state
           (if-let [[sec trailing] (section-header line)]
             (apply-header state sec trailing)
             (apply-body-line state line))))
       {:section :top :component nil :models {} :model-name nil}
       (str/split-lines s))
      (select-keys [:component :models])))
