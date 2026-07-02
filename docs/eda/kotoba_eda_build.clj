(ns kotoba-eda-build
  "Regenerates docs/eda/index.html from kotoba_eda_ui.cljc + kotoba_eda_style.cljc
  via kotoba.html/html5 + css.core, embedding the compiled reagent app bundle
  (resources/main.js, built by `npx shadow-cljs release app` per
  shadow-cljs.edn, from kotoba_eda_app.cljs — see that file's docstring) as
  the page's <script>.

  kotoba_eda_ui.cljc / kotoba_eda_style.cljc / kotoba_eda_app.cljs are
  deliberately kept flat in this directory (not under src/kotoba/eda/...)
  because source.html's in-page source viewer fetches them by flat filename
  (?file=kotoba_eda_ui.cljc) relative to this directory — moving them into a
  namespace-matching directory tree would break those links. Their
  namespaces are therefore single dash-joined segments (`kotoba-eda-ui`, not
  `kotoba.eda.ui`) so plain `require` still resolves them off a `:paths
  [\".\"]` classpath root without any directory nesting.

  Run from this directory: clojure -M:build"
  (:require [kotoba.html :as html]
            [kotoba-eda-style]
            [kotoba-eda-ui :as ui]))

(defn -main [& _args]
  (let [script (slurp "resources/main.js")
        doc (html/html5 (ui/page script))]
    (spit "index.html" doc)
    (println "wrote index.html —" (count doc) "bytes")))
