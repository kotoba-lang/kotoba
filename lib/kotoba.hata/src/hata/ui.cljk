(ns hata.ui
  "UI への局所 API（ADR-2610082200 §2「UI への局所 API」の最小形）。

  機 は UI を bundle から取り出して宿 に渡す。表示そのもの・DOM・ネットは
  すべて宿（browser / wasm-webcomponent）の仕事で、ここは「どの entry を
  どの型で開くか」という指示だけを持つ。"
  (:require [hata.bundle :as bundle]))

(def content-types
  {"html" "text/html; charset=utf-8"
   "htm" "text/html; charset=utf-8"
   "js" "text/javascript; charset=utf-8"
   "css" "text/css; charset=utf-8"
   "json" "application/json"
   "svg" "image/svg+xml"
   "wasm" "application/wasm"})

(defn- entry-ext [entry]
  (when entry (last (re-seq #"[^.]+" entry))))

(defn ui-entry
  "What to open: the manifest's UI entry and its bytes. nil when the bundle
  carries none — a UI-less app (service) is legal, an empty UI is not
  pretended to exist."
  [bundle]
  (when-let [ui (:ui bundle)]
    {:entry (:entry ui)
     :bytes (:bytes ui)
     :content-type (get content-types (entry-ext (:entry ui))
                        "application/octet-stream")}))

(defn serve-plan
  "The 局所 API answer for a host: open this entry over this local origin.
  The origin is the 機's own loopback — never the app origin (the shared
  architecture contract: app origins serve static artifacts only)."
  [bundle & {:keys [origin] :or {origin "http://127.0.0.1:0"}}]
  (when-let [plan (ui-entry bundle)]
    (assoc plan
           :origin origin
           :path (str "/" (:entry plan))
           :app-id (get-in bundle [:manifest :kotoba.app/id]))))
