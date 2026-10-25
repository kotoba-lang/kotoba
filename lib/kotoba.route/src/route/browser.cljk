(ns route.browser
  "The one part of routing that touches the browser: reading the fragment and
  hearing about changes to it. Kept out of `route.core` so the resolution and the
  nav stay testable without a browser — which is where the invariants live."
  (:require [route.core :as route]))

(defn current-fragment [] (.-hash js/location))

(defn current-view
  "The view the address bar is currently naming."
  [views]
  (route/fragment->view views (current-fragment)))

(defn on-change!
  "Call `f` with the resolved view now and on every fragment change. Returns a
  zero-arg function that removes the listener — an app that mounts more than once
  (hot reload, a test harness) otherwise stacks handlers and dispatches N times."
  [views f]
  (let [handler (fn [_] (f (current-view views)))]
    (.addEventListener js/window "hashchange" handler)
    (f (current-view views))
    (fn [] (.removeEventListener js/window "hashchange" handler))))
