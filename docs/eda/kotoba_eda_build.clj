(ns kotoba.eda.build
  "Regenerates docs/eda/index.html from kotoba_eda_ui.cljc + kotoba_eda_style.cljc
  via kotoba.html/html5 + css.core. The page's JS stays in
  resources/eda_app.js, untouched, and is embedded verbatim.

  kotoba_eda_ui.cljc / kotoba_eda_style.cljc are deliberately kept flat in
  this directory (not under src/kotoba/eda/...) because source.html's
  in-page source viewer fetches them by flat filename
  (?file=kotoba_eda_ui.cljc) relative to this directory — moving them into a
  namespace-matching directory tree would break those links. That means
  they can't be `require`d off a normal classpath, so this script
  `load-file`s them directly instead.

  Run from this directory: clojure -M:build"
  (:require [kotoba.html :as html]))

(load-file "kotoba_eda_style.cljc")
(load-file "kotoba_eda_ui.cljc")

(defn -main [& _args]
  (let [script (slurp "resources/eda_app.js")
        doc (html/html5 (kotoba.eda.ui/page script))]
    (spit "index.html" doc)
    (println "wrote index.html —" (count doc) "bytes")))
