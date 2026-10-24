(ns spice.netlist
  "SPICE netlist parser + exporter. Restored from kami-spice's `netlist`
  module (deleted PR #82). Recognizes element lines (R/C/L/V/I/M/Q/D),
  `.model` directives, and skips title/comment lines. `.dc`/`.ac`/`.tran`
  are not stored (matches the original — analysis-type selection is left
  to the caller)."
  (:require [kotoba.lang.text :as str]
            [spice.circuit :as circuit]))

(defn- letter-char?
  "Portable char-is-letter test (JVM `Character/isLetter` has no cljs
  equivalent; cljs chars are single-char strings, so a regex works there)."
  [c]
  #?(:clj (Character/isLetter ^char c)
     :cljs (some? (re-matches #"[a-zA-Z]" c))))

(defn- eng-parse-double
  "Portable strict double parse: throws on malformed input on both
  platforms (JVM `Double/parseDouble` throws; `js/parseFloat` returns
  NaN instead, so wrap it to preserve the caller's try/catch fallback)."
  [s]
  #?(:clj (Double/parseDouble s)
     :cljs (let [n (js/parseFloat s)]
             (if (js/isNaN n) (throw (js/Error. "not a number")) n))))

(defn- split-suffix [s]
  (let [idx (or (first (keep-indexed (fn [i c] (when (or (letter-char? c) (= c \µ)) i)) s))
                (count s))]
    [(subs s 0 idx) (subs s idx)]))

(defn parse-eng
  "Parse SPICE engineering notation (\"1k\" -> 1000.0, \"10u\" -> 1e-5)."
  [s]
  (let [s (str/trim s)]
    (if (str/blank? s)
      0.0
      (try
        (eng-parse-double s)
        (catch #?(:clj NumberFormatException :cljs js/Error) _
          (let [[num-part suffix] (split-suffix s)
                base (try (eng-parse-double num-part) (catch #?(:clj NumberFormatException :cljs js/Error) _ 0.0))
                mult (case (str/lower suffix)
                       "t" 1e12 "g" 1e9 ("meg" "x") 1e6 "k" 1e3 "m" 1e-3
                       ("u" "µ") 1e-6 "n" 1e-9 "p" 1e-12 "f" 1e-15
                       1.0)]
            (* base mult)))))))

(defn- find-param [tokens key]
  (some (fn [t]
          (when-let [rest (or (when (str/starts-with? t key) (subs t (count key)))
                               (let [lk (str/lower key)]
                                 (when (str/starts-with? t lk) (subs t (count lk)))))]
            (when (str/starts-with? rest "=")
              (parse-eng (subs rest 1)))))
        tokens))

(defn parse-spice-netlist
  "Parse a SPICE netlist string into a circuit map. Returns `[:ok circuit]`
  or `[:error msg]` on malformed element lines (mirrors the original's
  `Result<SpiceCircuit, NetlistError>`)."
  [input]
  (let [lines (str/split-lines input)]
    (if (empty? lines)
      [:ok (circuit/circuit)]
      (loop [remaining lines
             line-num 0
             title-skipped false
             ckt (circuit/circuit)]
        (if (empty? remaining)
          [:ok ckt]
          (let [line (first remaining)
                trimmed (str/trim line)]
            (cond
              (or (str/blank? trimmed) (str/starts-with? trimmed "*"))
              (recur (rest remaining) (inc line-num) title-skipped ckt)

              (not title-skipped)
              (recur (rest remaining) (inc line-num) true ckt)

              :else
              (let [tokens (str/split trimmed #"\s+")]
                (if (empty? tokens)
                  (recur (rest remaining) (inc line-num) title-skipped ckt)
                  (let [first-tok (first tokens)
                        prefix (str/upper (str (first first-tok)))
                        n (count tokens)]
                    (case prefix
                      "R"
                      (if (< n 4)
                        [:error (str "insufficient tokens at line " (inc line-num))]
                        (recur (rest remaining) (inc line-num) title-skipped
                               (circuit/add-element ckt {:kind :resistor :name (nth tokens 0)
                                                          :n1 (nth tokens 1) :n2 (nth tokens 2)
                                                          :value (parse-eng (nth tokens 3))})))
                      "C"
                      (if (str/starts-with? first-tok ".")
                        (recur (rest remaining) (inc line-num) title-skipped ckt)
                        (if (< n 4)
                          [:error (str "insufficient tokens at line " (inc line-num))]
                          (recur (rest remaining) (inc line-num) title-skipped
                                 (circuit/add-element ckt {:kind :capacitor :name (nth tokens 0)
                                                            :n1 (nth tokens 1) :n2 (nth tokens 2)
                                                            :value (parse-eng (nth tokens 3))}))))
                      "L"
                      (if (< n 4)
                        [:error (str "insufficient tokens at line " (inc line-num))]
                        (recur (rest remaining) (inc line-num) title-skipped
                               (circuit/add-element ckt {:kind :inductor :name (nth tokens 0)
                                                          :n1 (nth tokens 1) :n2 (nth tokens 2)
                                                          :value (parse-eng (nth tokens 3))})))
                      "V"
                      (if (< n 4)
                        [:error (str "insufficient tokens at line " (inc line-num))]
                        (recur (rest remaining) (inc line-num) title-skipped
                               (circuit/add-element ckt {:kind :voltage-source :name (nth tokens 0)
                                                          :n-pos (nth tokens 1) :n-neg (nth tokens 2)
                                                          :dc-value (parse-eng (nth tokens 3))
                                                          :ac-mag 0.0 :ac-phase 0.0})))
                      "I"
                      (if (< n 4)
                        [:error (str "insufficient tokens at line " (inc line-num))]
                        (recur (rest remaining) (inc line-num) title-skipped
                               (circuit/add-element ckt {:kind :current-source :name (nth tokens 0)
                                                          :n-pos (nth tokens 1) :n-neg (nth tokens 2)
                                                          :dc-value (parse-eng (nth tokens 3))})))
                      "M"
                      (if (< n 6)
                        [:error (str "insufficient tokens at line " (inc line-num))]
                        (recur (rest remaining) (inc line-num) title-skipped
                               (circuit/add-element ckt {:kind :mosfet :name (nth tokens 0)
                                                          :drain (nth tokens 1) :gate (nth tokens 2)
                                                          :source (nth tokens 3) :bulk (nth tokens 4)
                                                          :model-name (nth tokens 5)
                                                          :w (or (find-param tokens "W") 1e-6)
                                                          :l (or (find-param tokens "L") 1e-6)
                                                          :mosfet-type :nmos})))
                      "Q"
                      (if (< n 5)
                        [:error (str "insufficient tokens at line " (inc line-num))]
                        (recur (rest remaining) (inc line-num) title-skipped
                               (circuit/add-element ckt {:kind :bjt :name (nth tokens 0)
                                                          :collector (nth tokens 1) :base (nth tokens 2)
                                                          :emitter (nth tokens 3) :model-name (nth tokens 4)
                                                          :bjt-type :npn})))
                      "D"
                      (if (< n 4)
                        [:error (str "insufficient tokens at line " (inc line-num))]
                        (recur (rest remaining) (inc line-num) title-skipped
                               (circuit/add-element ckt {:kind :diode :name (nth tokens 0)
                                                          :anode (nth tokens 1) :cathode (nth tokens 2)
                                                          :model-name (nth tokens 3)})))
                      "."
                      (let [directive (str/lower first-tok)]
                        (recur (rest remaining) (inc line-num) title-skipped
                               (if (and (= directive ".model") (>= n 3))
                                 (assoc-in ckt [:models (nth tokens 1)] (str/join " " (subvec tokens 2)))
                                 ckt)))
                      ;; unrecognized prefix — skip
                      (recur (rest remaining) (inc line-num) title-skipped ckt))))))))))))

(defn- num->str [v]
  #?(:clj (if (= v (long v)) (str (long v)) (str v))
     :cljs (str v)))

(defn export-spice
  "Export a circuit map to SPICE netlist format."
  [circuit]
  (str "KAMI SPICE netlist\n"
       (apply str
              (for [el (:elements circuit)]
                (case (:kind el)
                  :resistor (str (:name el) " " (:n1 el) " " (:n2 el) " " (num->str (:value el)) "\n")
                  :capacitor (str (:name el) " " (:n1 el) " " (:n2 el) " " (num->str (:value el)) "\n")
                  :inductor (str (:name el) " " (:n1 el) " " (:n2 el) " " (num->str (:value el)) "\n")
                  :voltage-source (str (:name el) " " (:n-pos el) " " (:n-neg el) " " (num->str (:dc-value el)) "\n")
                  :current-source (str (:name el) " " (:n-pos el) " " (:n-neg el) " " (num->str (:dc-value el)) "\n")
                  :mosfet (str (:name el) " " (:drain el) " " (:gate el) " " (:source el) " "
                               (:bulk el) " " (:model-name el) " W=" (num->str (:w el))
                               " L=" (num->str (:l el)) "\n")
                  :bjt (str (:name el) " " (:collector el) " " (:base el) " " (:emitter el) " "
                            (:model-name el) "\n")
                  :diode (str (:name el) " " (:anode el) " " (:cathode el) " " (:model-name el) "\n"))))
       (apply str (for [[name def] (:models circuit)] (str ".model " name " " def "\n")))
       ".end\n"))
