(ns manimani.build
  (:require [clojure.java.io :as io]
            [shadow.css.build :as css]))

(defn release! [_]
  (io/make-parents "public/css/ui.css")
  (-> (css/start)
      (css/index-path (io/file "src/main") {})
      (css/generate '{:ui {:entries [manimani.ui]}})
      (css/minify)
      (css/write-outputs-to (io/file "public/css")))
  {:built ["public/css/ui.css"]})
