(ns engineer-io.gerber
  "Gerber RS-274X generator. Restored from kami-eng-io's `gerber` module
  (deleted PR #82). Apertures are `[id {:kind :circle|:rectangle|:obround ...}]`
  pairs; commands are `{:cmd :select-aperture|:move-to|:line-to|:flash|
  :arc-cw|:arc-ccw ...}` maps.")

(defn- coord [val] (long (* val 1000000.0)))

(defn- fmt6
  "Portable fixed 6-decimal-place formatting (clojure.core/format wraps
  java.util.Formatter -- JVM-only, no cljs equivalent)."
  [n]
  #?(:clj (format "%.6f" (double n))
     :cljs (.toFixed n 6)))

(defn- aperture-line [id {:keys [kind diameter width height]}]
  (case kind
    :circle (str "%ADD" id "C," (fmt6 diameter) "*%\n")
    :rectangle (str "%ADD" id "R," (fmt6 width) "X"
                     (fmt6 height) "*%\n")
    :obround (str "%ADD" id "O," (fmt6 width) "X"
                    (fmt6 height) "*%\n")))

(defn- command-lines [{:keys [cmd id x y i j]}]
  (case cmd
    :select-aperture (str "D" id "*\n")
    :move-to (str "X" (coord x) "Y" (coord y) "D02*\n")
    :line-to (str "G01*\n" "X" (coord x) "Y" (coord y) "D01*\n")
    :flash (str "X" (coord x) "Y" (coord y) "D03*\n")
    :arc-cw (str "G02*\n" "X" (coord x) "Y" (coord y) "I" (coord i) "J" (coord j) "D01*\n")
    :arc-ccw (str "G03*\n" "X" (coord x) "Y" (coord y) "I" (coord i) "J" (coord j) "D01*\n")))

(defn generate
  "Generate RS-274X Gerber file content. `apertures` is a seq of `[id spec]`
  pairs; `commands` is a seq of command maps. Header declares leading-zero
  absolute 3.6 format, millimeter units, positive image polarity."
  [apertures commands]
  (str "%FSLAX36Y36*%\n"
       "%MOIN*%\n"
       "%IPPOS*%\n"
       (apply str (for [[id ap] apertures] (aperture-line id ap)))
       (apply str (map command-lines commands))
       "M02*\n"))
