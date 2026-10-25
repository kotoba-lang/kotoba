(ns package-text-smoke
  (:require [package-support :as support]))

(def fixtures
  {"text-caps" "examples/text-caps.dml"
   "text-baseline-threshold" "examples/text-baseline-threshold.dml"
   "text-style" "examples/text-style.dml"
   "text-defaults" "examples/text-defaults.dml"
   "text-bullets" "examples/text-bullets.dml"
   "text-layout" "examples/text-layout.dml"
   "text-invalid-level" "examples/text-invalid-level.dml"
   "text-invalid-numeric" "examples/text-invalid-numeric.dml"
   "text-shape-paint" "examples/text-shape-paint.dml"})

(defn generated [] (into {} (map (fn [[name path]] [name (support/dml->svg path)]) fixtures)))

(defn run! []
  (let [out (generated)
        baseline (get out "text-baseline-threshold")]
    (support/includes-all "text caps" (get out "text-caps") ["id=\"all-caps-text\"" "font-variant=\"all-small-caps\"" "All Caps</text>"])
    (support/ok (not (or (re-find #"baseline-shift=\"super\"[^>]*>Low<" baseline) (re-find #"baseline-shift=\"sub\"[^>]*>Low<" baseline))) "Low baseline should not shift")
    (support/includes-all "text baseline" baseline [">Low</tspan>" "baseline-shift=\"super\"> Super</tspan>" "baseline-shift=\"sub\"> Sub</tspan>"])
    (support/includes-all "text style" (get out "text-style") ["<tspan" "font-size=\"18\"" "font-weight=\"bold\"" "font-style=\"italic\"" "font-family=\"Aptos Display\"" "font-variant=\"small-caps\"" "fill=\"#dc2626\"" "fill-opacity=\"0.85\"" "stroke=\"#2563eb\"" "stroke-width=\"1\"" "stroke-linecap=\"square\"" "stroke-linejoin=\"round\"" "text-decoration=\"underline\"" "text-decoration-style=\"dashed\"" "text-decoration-color=\"#16a34a80\"" "text-decoration-thickness=\"2\"" "baseline-shift=\"super\"" "letter-spacing=\"2\""])
    (support/includes-all "text defaults" (get out "text-defaults") ["font-size=\"18\"" "font-weight=\"bold\"" "font-style=\"italic\"" "font-family=\"Aptos Display\"" "font-variant=\"small-caps\"" "text-decoration=\"underline line-through\"" "fill=\"#334455\"" "font-size=\"12\"" "fill=\"#aa5500\"" "font-size=\"16\"" "font-family=\"Aptos\"" "letter-spacing=\"1.6\"" "stroke=\"#cc5500\"" "stroke-width=\"2\"" "font-family=\"Yu Gothic\""])
    (support/includes-all "text bullets" (get out "text-bullets") ["* " "Direct bullet" "\t" "Tabbed" "- " "List bullet" "dy=\"1.2em\"" "After break" "d) " "Auto alpha" "VII. " "Roman" "4000. " "Roman overflow"])
    (support/includes-all "text layout" (get out "text-layout") ["id=\"inset-text\"" "x=\"12\" y=\"35\"" "white-space=\"nowrap\"" "id=\"centered-text\"" "x=\"40\"" "text-anchor=\"middle\"" "id=\"middle-text\"" "y=\"120\"" "dominant-baseline=\"middle\"" "id=\"right-rtl-text\"" "x=\"100\" y=\"170\"" "text-anchor=\"end\"" "dominant-baseline=\"text-after-edge\"" "direction=\"rtl\"" "id=\"list-align-text\""])
    (support/includes-all "text invalid level" (get out "text-invalid-level") ["id=\"invalid-paragraph-level\"" "- </tspan>" "Invalid level</tspan>"])
    (support/excludes-all "text invalid level" (get out "text-invalid-level") ["+ </tspan>"])
    (support/includes-all "text invalid numeric" (get out "text-invalid-numeric") ["id=\"invalid-text-numeric\"" "fill=\"#111827\"" "Invalid numeric text</text>"])
    (support/excludes-all "text invalid numeric" (get out "text-invalid-numeric") ["font-size=" "baseline-shift=" "letter-spacing="])
    (support/includes-all "text shape paint" (get out "text-shape-paint") ["fill=\"#aa5500\"" "fill-opacity=\"0.7\"" "stroke=\"#224466\"" "stroke-opacity=\"0.4\"" "stroke-width=\"1\"" "stroke-linecap=\"round\"" "stroke-linejoin=\"round\"" "stroke-dasharray=\"4 3\""])
    (js/console.log "package text smoke pass")))

(support/run-script! run!)
