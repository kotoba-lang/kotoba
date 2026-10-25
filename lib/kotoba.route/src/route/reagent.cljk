(ns route.reagent
  "The reagent binding: a ratom holding the current view, kept in step with the
  address bar. Separate from `route.core` (which is `.cljc` and has no browser and
  no reagent in it) and from `route.browser` (browser, no reagent), so an app can
  take exactly the layer it uses.

  `kami-app-daw` and `kami-app-nle` each carried this in their own route
  namespace, character for character identical, including the reload guard."
  (:require [reagent.core :as r]
            [route.browser :as browser]))

(defn make-tracker
  "A tracker for one view table: `{:current <ratom> :install! <fn> :uninstall! <fn>}`.

  `install!` is idempotent, because an app's `init!` runs again on every hot
  reload and one listener per reload leaks — that guard is the reason this is a
  function rather than three lines inside a `defonce`."
  [views]
  (let [current (r/atom (browser/current-view views))
        remove-listener (atom nil)]
    {:current current
     :install! (fn []
                 (when-not @remove-listener
                   (reset! remove-listener
                           (browser/on-change! views #(reset! current %)))))
     :uninstall! (fn []
                   (when-let [f @remove-listener]
                     (f)
                     (reset! remove-listener nil)))}))
