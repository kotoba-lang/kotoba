(ns lef.core
  "LEF (Library Exchange Format) physical-abstract library model + simplified
  parser (Si2, Silicon Integration Initiative, si2.org — companion format to
  DEF). Extracted from kotoba-lang/pdk into its own standards-substrate repo
  as part of the kotoba-lang org-<body>-<spec> reverse-domain naming
  initiative (ADR-2607072500, com-junkawasaki/root)."
  (:require [kotoba.lang.text :as str]))

(def macro-classes #{:core :block :pad :endcap})

(defn find-macro [lib name] (some #(when (= (:name %) name) %) (:macros lib)))

(defn- strip-semi [s] (str/replace s #";$" ""))

(defn- parse-num [s default]
  (try #?(:clj (Double/parseDouble s) :cljs (js/parseFloat s))
       (catch #?(:clj Exception :cljs js/Error) _ default)))

(defn- flush-pin [macro pin]
  (if pin (update macro :pins conj pin) macro))

(defn parse-lef
  "Parse a simplified LEF format string: recognizes MACRO/CLASS/SIZE/
  SYMMETRY/SITE/PIN/DIRECTION/OBS/LAYER/RECT/END."
  [input]
  (loop [lines (str/split-lines input)
         macros []
         current-macro nil
         current-pin nil
         in-obs false
         current-layer ""]
    (if (empty? lines)
      [:ok {:macros (if current-macro
                       (conj macros (flush-pin current-macro current-pin))
                       macros)}]
      (let [trimmed (str/trim (first lines))
            more (rest lines)
            tokens (when-not (str/blank? trimmed) (str/split trimmed #"\s+"))]
        (if (empty? tokens)
          (recur more macros current-macro current-pin in-obs current-layer)
          (let [n (count tokens)
                t0 (nth tokens 0)]
            (case t0
              "MACRO"
              (if (>= n 2)
                (recur more
                       (if current-macro (conj macros (flush-pin current-macro current-pin)) macros)
                       {:name (nth tokens 1) :class :core :size [0.0 0.0]
                        :symmetry "" :site "" :pins [] :obs []}
                       nil false current-layer)
                (recur more macros current-macro current-pin in-obs current-layer))

              "CLASS"
              (if (and current-macro (>= n 2))
                (recur more macros
                       (assoc current-macro :class
                              (case (str/upper (nth tokens 1))
                                "BLOCK" :block "PAD" :pad "ENDCAP" :endcap :core))
                       current-pin in-obs current-layer)
                (recur more macros current-macro current-pin in-obs current-layer))

              "SIZE"
              (if (and current-macro (>= n 4))
                (recur more macros
                       (assoc current-macro :size [(parse-num (nth tokens 1) 0.0)
                                                    (parse-num (nth tokens 3) 0.0)])
                       current-pin in-obs current-layer)
                (recur more macros current-macro current-pin in-obs current-layer))

              "SYMMETRY"
              (if (and current-macro (>= n 2))
                (recur more macros
                       (assoc current-macro :symmetry
                              (-> (str/join " " (subvec tokens 1)) strip-semi str/trim))
                       current-pin in-obs current-layer)
                (recur more macros current-macro current-pin in-obs current-layer))

              "SITE"
              (if (and current-macro (>= n 2))
                (recur more macros (assoc current-macro :site (strip-semi (nth tokens 1)))
                       current-pin in-obs current-layer)
                (recur more macros current-macro current-pin in-obs current-layer))

              "PIN"
              (if (and current-macro (>= n 2))
                (recur more macros (flush-pin current-macro current-pin)
                       {:name (nth tokens 1) :direction "INPUT" :port []}
                       false current-layer)
                (recur more macros current-macro current-pin in-obs current-layer))

              "DIRECTION"
              (if (and current-pin (>= n 2))
                (recur more macros current-macro
                       (assoc current-pin :direction (strip-semi (nth tokens 1)))
                       in-obs current-layer)
                (recur more macros current-macro current-pin in-obs current-layer))

              "OBS"
              (if current-macro
                (recur more macros (flush-pin current-macro current-pin) nil true current-layer)
                (recur more macros current-macro current-pin in-obs current-layer))

              "LAYER"
              (if (>= n 2)
                (recur more macros current-macro current-pin in-obs (strip-semi (nth tokens 1)))
                (recur more macros current-macro current-pin in-obs current-layer))

              "RECT"
              (if (>= n 5)
                (let [x1 (parse-num (nth tokens 1) 0.0)
                      y1 (parse-num (nth tokens 2) 0.0)
                      x2 (parse-num (nth tokens 3) 0.0)
                      y2 (parse-num (strip-semi (nth tokens 4)) 0.0)
                      r {:layer current-layer :rect [x1 y1 x2 y2]}]
                  (if in-obs
                    (recur more macros (update current-macro :obs conj r) current-pin in-obs current-layer)
                    (recur more macros current-macro (update current-pin :port conj r) in-obs current-layer)))
                (recur more macros current-macro current-pin in-obs current-layer))

              "END"
              (cond
                (and in-obs (= n 1))
                (recur more macros current-macro current-pin false current-layer)

                ;; "END <pin_name>" — ends a PIN block (name doesn't match the macro)
                (and current-pin (>= n 2) (not= (nth tokens 1) (:name current-macro)))
                (recur more macros (flush-pin current-macro current-pin) nil in-obs current-layer)

                ;; "END <macro_name>" — ends the MACRO block
                (>= n 2)
                (recur more (conj macros (flush-pin current-macro current-pin)) nil nil in-obs current-layer)

                :else
                (recur more macros current-macro current-pin in-obs current-layer))

              (recur more macros current-macro current-pin in-obs current-layer))))))))
