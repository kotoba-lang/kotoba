(ns kotoba.live
  "kotoba.live — KAMI live-show / VRM-and-Live2D dance-scene domain.

  Domain layer for a live-music venue: turn a `:dance/*` EDN scene into a
  deterministic, beat-synced show driving a VRM (3D) and/or Live2D (2D)
  performer, a crowd, lighting, VJ visuals, reactions, and the render-IR the
  renderer consumes. No GPU deps, no network, no I/O in the domain
  namespaces — see the README for the ported/unported split and the
  adapter-only host responsibilities (mesh skinning, audio device I/O, CLI
  process/file I/O).

  ```text
  author.clj ──(edn/read-string)──▶ scene ──(scene/from-edn)──▶ DanceScene
  scene/frame(dt) ──▶ {:render-ir :actions :live2d :audio :sounds}
     render-ir → a host renderer (native or web)   actions → host applies
  ```

  This namespace re-exports the most-reached-for entry points; each
  subsystem also stands alone (`kotoba.live.beat`, `kotoba.live.show`,
  `kotoba.live.scene`, `kotoba.live.lint`, ...) and can be required
  directly."
  (:require [kotoba.live.beat :as beat]
            [kotoba.live.lint :as lint]
            [kotoba.live.render :as render]
            [kotoba.live.scene :as scene]))

(def new-grid
  "See `kotoba.live.beat/new-grid`." beat/new-grid)
(def tick
  "See `kotoba.live.beat/tick`." beat/tick)
(def new-scene
  "See `kotoba.live.scene/from-edn`." scene/from-edn)
(def frame
  "See `kotoba.live.scene/frame`." scene/frame)
(def run-headless
  "See `kotoba.live.scene/run-headless`." scene/run-headless)
(def lint-scene
  "See `kotoba.live.lint/lint-scene`." lint/lint-scene)
(def show->render-ir
  "See `kotoba.live.render/show->render-ir`." render/show->render-ir)
