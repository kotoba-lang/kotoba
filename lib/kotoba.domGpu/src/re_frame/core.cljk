(ns re-frame.core
  "Compatibility namespace for kotoba WASM.
   Existing CLJS code can require [re-frame.core :as rf] and use the small
   synchronous app-db/event/subscription runtime."
  (:refer-clojure :exclude [subscribe])
  (:require [kotoba.wasm.re-frame :as rf]))

(def app-db rf/app-db)
(def clear! rf/clear!)
(def reg-event-db rf/reg-event-db)
(def reg-sub rf/reg-sub)
(def dispatch rf/dispatch)
(def dispatch-sync rf/dispatch-sync)
(def subscribe rf/subscribe)
