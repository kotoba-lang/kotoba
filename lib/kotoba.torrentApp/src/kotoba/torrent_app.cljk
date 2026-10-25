(ns kotoba.torrent-app)

(defn start []
  {:kotoba.app/surface-ops
   [[:dom/create-element 1 :main]
    [:dom/set-attr 1 :class "liquid-glass__panel"]
    [:dom/create-element 2 :h1]
    [:dom/create-text 3 "Kotoba Torrent"]
    [:dom/append-child 2 3]
    [:dom/append-child 1 2]
    [:dom/create-element 4 :p]
    [:dom/create-text 5 "Capability-safe BitTorrent v1 downloader"]
    [:dom/append-child 4 5]
    [:dom/append-child 1 4]
    [:dom/create-element 6 :button]
    [:dom/set-attr 6 :data-action "torrent/pick-file"]
    [:dom/create-text 7 "Open .torrent…"]
    [:dom/append-child 6 7]
    [:dom/append-child 1 6]
    [:dom/create-element 8 :p]
    [:dom/create-text 9 "Open a .torrent file to begin. Verified pieces are committed atomically."]
    [:dom/append-child 8 9]
    [:dom/append-child 1 8]
    [:dom/set-root 1]]})
