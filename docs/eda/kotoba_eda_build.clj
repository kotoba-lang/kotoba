(ns kotoba-eda-build
  "Regenerates docs/eda/index.html from kotoba_eda_ui.cljc (kotoba-ui/appkit
  hiccup + the ONE theme map) + kotoba_eda_style.cljc (small unlayered
  --hig-* app CSS) via kotoba-ui.core/->page, embedding the compiled reagent
  app bundle (resources/main.js, built by `npx shadow-cljs release app` per
  shadow-cljs.edn, from kotoba_eda_app.cljs — see that file's docstring) as
  the page's <script>. The design-system theme CSS (HIG tokens light+dark,
  glass material, shell layout — all inside @layer kotoba.hig/kotoba.glass)
  is emitted inline by ->page from this same entrypoint, so theme + markup
  regeneration stays atomic (the itonami cockpit pattern, adapted: this page
  is a fully generated single file, so an inline <style> beats a separate
  theme.css link).

  kotoba_eda_ui.cljc / kotoba_eda_style.cljc / kotoba_eda_app.cljs are
  deliberately kept flat in this directory (not under src/kotoba/eda/...)
  because source.html's in-page source viewer fetches them by flat filename
  (?file=kotoba_eda_ui.cljc) relative to this directory — moving them into a
  namespace-matching directory tree would break those links. Their
  namespaces are therefore single dash-joined segments (`kotoba-eda-ui`, not
  `kotoba.eda.ui`) so plain `require` still resolves them off a `:paths
  [\".\"]` classpath root without any directory nesting.

  Run from this directory: clojure -M:build"
  (:require [kotoba-eda-ui :as ui]))

(defn -main [& _args]
  (let [script (slurp "resources/main.js")
        doc (str (ui/page-html script) "\n")]
    (spit "index.html" doc)
    (println "wrote index.html —" (count doc) "bytes")))
