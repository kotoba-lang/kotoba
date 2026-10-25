(ns package-table-smoke
  (:require [package-support :as support]))

(def fixtures
  {"table-border-effects" "examples/table-border-effects.dml"
   "table-fill-effects" "examples/table-fill-effects.dml"
   "table-rich" "examples/table-rich.dml"
   "table-merge-bool" "examples/table-merge-bool.dml"
   "table-scaled" "examples/table-scaled.dml"
   "table-scaled-insets" "examples/table-scaled-insets.dml"})

(defn generated [] (into {} (map (fn [[name path]] [name (support/dml->svg path)]) fixtures)))

(defn run! []
  (let [out (generated)
        rich (get out "table-rich")
        merge (get out "table-merge-bool")]
    (support/includes-all "table border effects" (get out "table-border-effects") ["id=\"border-effect-table\"" "stroke=\"#800080\"" "stroke-opacity=\"0.75\"" "stroke=\"#008000\"" "stroke-width=\"2\"" "Border effects</text>"])
    (support/includes-all "table fill effects" (get out "table-fill-effects") ["id=\"fill-effect-table\"" "fill=\"#800080\"" "fill-opacity=\"0.75\"" "fill=\"#008000\"" "Gradient</text>" "Pattern</text>"])
    (support/includes-all "table rich" rich ["data-kind=\"table\"" "fill=\"#e0f2fe\"" "fill-opacity=\"0.6\"" "stroke=\"#dc2626\"" "stroke-opacity=\"0.5\"" "stroke-width=\"2\"" "stroke-linecap=\"square\"" "stroke-dasharray=\"4 2\"" "stroke-miterlimit=\"6\"" "x=\"16\" y=\"21\"" "text-anchor=\"middle\"" "font-weight=\"bold\"" "dominant-baseline=\"text-after-edge\"" "direction=\"rtl\"" "white-space=\"nowrap\"" "<tspan" "fill=\"#dc2626\"" "font-size=\"14\""])
    (support/ok (empty? (re-seq #"<text [^>]*fill=\"#000000\"[^>]*fill=\"" rich)) "table rich text should not duplicate fill attrs")
    (support/includes-all "table merge bool" merge ["id=\"boolean-merge-table\"" "data-kind=\"table\"" "x=\"0\" y=\"0\" width=\"80\" height=\"40\"" "x=\"0\" y=\"40\" width=\"40\" height=\"80\"" "x=\"40\" y=\"80\" width=\"40\" height=\"40\"" "data-colspan=\"2\"" "Wide</text>" "Tall</text>" "B</text>" "D</text>"])
    (support/ok (= 4 (count (re-seq #"data-kind=\"cell\"" merge))) "table merge bool expected four cells")
    (support/includes-all "table scaled" (get out "table-scaled") ["id=\"scaled-table\"" "data-kind=\"table\"" "x=\"10\" y=\"20\" width=\"20\" height=\"30\"" "x=\"30\" y=\"20\" width=\"20\" height=\"30\"" "x=\"10\" y=\"50\" width=\"40\" height=\"30\"" "data-colspan=\"2\"" "A</text>" "B</text>" "Wide</text>"])
    (support/includes-all "table scaled insets" (get out "table-scaled-insets") ["id=\"scaled-inset-table\"" "data-kind=\"table\"" "x=\"0\" y=\"0\" width=\"40\" height=\"80\"" "x=\"10\" y=\"50\"" "Inset</text>"])
    (js/console.log "package table smoke pass")))

(support/run-script! run!)
