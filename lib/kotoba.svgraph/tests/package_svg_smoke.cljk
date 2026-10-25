(ns package-svg-smoke
  (:require [package-support :as support]))

(def fixtures
  {"group" "examples/group.dml"
   "freeform-closed-duplicate" "examples/freeform-closed-duplicate.dml"
   "freeform" "examples/freeform.dml"
   "picture" "examples/picture.dml"
   "picture-invalid-alpha" "examples/picture-invalid-alpha.dml"
   "picture-invalid-src-rect" "examples/picture-invalid-src-rect.dml"
   "preset" "examples/preset.dml"
   "alpha" "examples/alpha.dml"
   "color" "examples/color.dml"
   "color-invalid-modifier" "examples/color-invalid-modifier.dml"
   "connector-style-ref" "examples/connector-style-ref.dml"
   "fill-effects" "examples/fill-effects.dml"
   "line-arrow" "examples/line-arrow.dml"
   "line-flip-bool" "examples/line-flip-bool.dml"
   "line-invalid-dash" "examples/line-invalid-dash.dml"
   "line-style" "examples/line-style.dml"
   "style-ref" "examples/style-ref.dml"})


(defn generated [] (support/generated fixtures))

(defn run! []
  (let [out (generated)]
    (support/includes-all "group" (get out "group") ["transform=\"matrix(2 0 0 2 10 20)\""])
    (support/includes-all "freeform closed" (get out "freeform-closed-duplicate") ["<polygon" "points=\"0,0 20,0 20,20 0,0\"" "fill=\"#22c55e\"" "stroke=\"#14532d\""])
    (support/includes-all "freeform" (get out "freeform") ["<polygon" "fill=\"#f97316\""])
    (support/includes-all "picture" (get out "picture") ["<image" "opacity=\"0.35\"" "preserveAspectRatio=\"xMidYMid slice\"" "transform=\"rotate(30 20 25) translate(20 25) scale(-1 1) translate(-20 -25)\""])
    (support/includes-all "invalid picture alpha" (get out "picture-invalid-alpha") ["id=\"invalid-picture-alpha\"" "<image" "width=\"20\"" "height=\"10\""])
    (support/excludes-all "invalid picture alpha" (get out "picture-invalid-alpha") ["opacity="])
    (support/includes-all "invalid picture crop" (get out "picture-invalid-src-rect") ["id=\"invalid-picture-crop\"" "<image" "width=\"20\"" "height=\"10\""])
    (support/excludes-all "invalid picture crop" (get out "picture-invalid-src-rect") ["preserveAspectRatio="])
    (support/includes-all "preset" (get out "preset") ["<polygon" "points=\"30,20 50,40 10,40\"" "points=\"70,20 80,30 70,40 60,30\"" "points=\"227,20 233,20 233,27 240,27 240,33 233,33 233,40 227,40 227,33 220,33 220,27 227,27\"" "points=\"280,25 306,25 306,20 320,30 306,40 306,35 280,35\"" "<rect x=\"570\" y=\"20\" width=\"40\" height=\"20\" rx=\"3.3333\" ry=\"3.3333\" fill=\"#fde2e2\"" "<ellipse cx=\"630\" cy=\"30\" rx=\"10\" ry=\"10\" fill=\"#cffafe\""])
    (support/includes-all "alpha" (get out "alpha") ["fill-opacity=\"0.5\"" "stroke-opacity=\"0.25\"" "stroke-width=\"2\""])
    (support/includes-all "color" (get out "color") ["fill=\"#99b2cc\"" "stroke=\"#223962\"" "fill=\"#336699\"" "fill=\"#339999\"" "fill=\"#112233\"" "stroke=\"#555e66\"" "fill=\"#3cb371\"" "stroke=\"#804600\"" "fill=\"#f5f5f5\""])
    (support/includes-all "invalid color modifier" (get out "color-invalid-modifier") ["id=\"invalid-color-modifier\"" "fill=\"#336699\"" "stroke=\"#111111\""])
    (support/excludes-all "invalid color modifier" (get out "color-invalid-modifier") ["fill-opacity=" "stroke-opacity="])
    (support/includes-all "connector style ref" (get out "connector-style-ref") ["data-kind=\"relation\"" "stroke=\"#dc2626\"" "stroke-opacity=\"0.6\"" "stroke-width=\"2\""])
    (support/includes-all "fill effects" (get out "fill-effects") ["fill=\"#800080\"" "fill-opacity=\"0.75\"" "stroke=\"#004000\"" "stroke-opacity=\"0.75\""])
    (support/includes-all "line arrow" (get out "line-arrow") ["<marker id=\"svgraph-arrow\"" "marker-start=\"url(#svgraph-arrow)\"" "marker-end=\"url(#svgraph-arrow)\"" "stroke=\"#111827\"" "stroke-width=\"2\""])
    (support/includes-all "line flip bool" (get out "line-flip-bool") ["id=\"boolean-flip-line\"" "x1=\"50\"" "y1=\"40\"" "x2=\"10\"" "y2=\"20\"" "stroke=\"#111827\"" "stroke-width=\"2\""])
    (support/excludes-all "line flip bool" (get out "line-flip-bool") ["transform=\"translate"])
    (support/includes-all "invalid dash" (get out "line-invalid-dash") ["id=\"invalid-dash\"" "stroke=\"#111111\"" "stroke-width=\"2\"" "stroke-dasharray=\"0 0\""])
    (support/excludes-all "invalid dash" (get out "line-invalid-dash") ["stroke-dasharray=\"4 2\""])
    (support/includes-all "line style" (get out "line-style") ["stroke-linecap=\"round\"" "stroke-linejoin=\"round\"" "stroke-dasharray=\"4 3 1 3\"" "stroke-linecap=\"square\"" "stroke-linejoin=\"miter\"" "stroke-dasharray=\"4 2\"" "stroke-miterlimit=\"6\""])
    (support/includes-all "style ref" (get out "style-ref") ["fill=\"#223962\"" "stroke=\"#ed7d31\"" "stroke-opacity=\"0.5\"" "stroke-width=\"2\"" "fill=\"#16a34a\"" "fill-opacity=\"0.75\""])
    (js/console.log "package svg smoke pass")))

(support/run-script! run!)
