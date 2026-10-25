(ns kotoba.lang.kami-nv-compat.kotoba-datomic-nucleus.index
  "kotoba-datomic-nucleus — clean-room Nucleus engine. Portable .cljc port
  of src/kotoba-datomic-nucleus/index.ts. Wave 35 (closes
  kotoba-datomic-nucleus; completes the wave-28 deferral).

  Content-addressed, append-only, subscribable versioned store + an
  omni.client-style API. The canonical KAMI backend behind
  nv-compat/omni-nucleus; mirrors the kotoba Datom log content-addressing
  model.

  Most of index.ts is TS re-export bookkeeping with no CLJC equivalent —
  callers require kotoba-datomic-nucleus.store / .client directly. This
  namespace ports the real logic: read-scene-from-nucleus /
  read-path-scene-from-nucleus, deferred in wave 28 because they need
  omni-usd's Stage/stage->scene/stage->path-scene (now ported, wave 35).

  ADR-2605261800 SD6 / D10.4 kotoba-datomic-nucleus."
  (:require [kotoba.lang.kami-nv-compat.kotoba-datomic-nucleus.client :as client]
            [kotoba.lang.kami-nv-compat.omni-usd :as omni-usd]))

(defn read-scene-from-nucleus
  "Read a USDA layer from Nucleus and parse it into a kami-rt ray scene."
  [c url]
  (let [{:keys [content]} (client/read-file c url)]
    (when content (omni-usd/stage->scene (omni-usd/stage-open content)))))

(defn read-path-scene-from-nucleus
  "Read a USDA layer from Nucleus and parse it into a kami-rtx path scene."
  [c url]
  (let [{:keys [content]} (client/read-file c url)]
    (when content (omni-usd/stage->path-scene (omni-usd/stage-open content)))))
