(ns build
  (:require [clojure.tools.build.api :as b]))

(def lib 'io.github.kotoba-lang/kotoba)
(def class-dir "target/classes")
(def uber-file "target/kotoba-standalone.jar")
(def basis (delay (b/create-basis {:project "deps.edn"})))

(defn clean [_]
  (b/delete {:path "target"}))

(defn uber [_]
  (clean nil)
  (b/copy-dir {:src-dirs ["src" "resources"] :target-dir class-dir})
  (b/compile-clj {:basis @basis :src-dirs ["src"] :class-dir class-dir
                  :ns-compile '[kotoba.launcher]})
  (b/uber {:class-dir class-dir :uber-file uber-file :basis @basis
           :main 'kotoba.launcher})
  {:uber-file uber-file})
