(ns kotoba.scheduler
  "Assembled from one repo per definition.

  This namespace holds no implementation. It re-exports the definitions
  that each live in their own repo, so a call site can require one name
  and a library can require only the definitions it actually uses.
"
  (:require [kotoba.scheduler.at :as at-ns]
            [kotoba.scheduler.cancel :as cancel-ns]
            [kotoba.scheduler.due :as due-ns]
            [kotoba.scheduler.every :as every-ns]
            [kotoba.scheduler.scheduler :as scheduler-ns]
            [kotoba.scheduler.tick :as tick-ns]))

(def at "See kotoba.scheduler.at/at." at-ns/at)
(def cancel "See kotoba.scheduler.cancel/cancel." cancel-ns/cancel)
(def due? "See kotoba.scheduler.due/due?." due-ns/due?)
(def every "See kotoba.scheduler.every/every." every-ns/every)
(def scheduler "See kotoba.scheduler.scheduler/scheduler." scheduler-ns/scheduler)
(def tick "See kotoba.scheduler.tick/tick." tick-ns/tick)
