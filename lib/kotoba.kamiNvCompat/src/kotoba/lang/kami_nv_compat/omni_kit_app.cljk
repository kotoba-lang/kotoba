(ns kotoba.lang.kami-nv-compat.omni-kit-app
  "Drop-in `omni.kit.app` / `omni.kit.commands` API-compat facade — portable
  .cljc port of src/omni-kit-app.ts. The Kit application framework: mirrors
  the documented surface (the Application singleton via get-app, the IExt
  extension lifecycle + extension.toml, and the undoable command stack), so
  Kit extensions port to KAMI via require-path-only changes.

  `app`/`commands` are TS namespace-grouping objects with no CLJC equivalent
  need — every member is already ported 1:1 in amenominaka.application /
  amenominaka.commands / amenominaka.extension; callers require those
  namespaces directly (matching the kami-rt.index barrel precedent) instead
  of going through a re-export layer here.

  The one piece of real new logic is KamiViewerExtension: a Kit extension
  that wires the rest of the nv-compat stack (kami-usd → kami-rt) into a
  hosted Kit extension, demonstrating an end-to-end app — load a USD stage on
  startup, render a frame each update.

  Backed by the clean-room amenominaka engine. No Kit source/binaries; from-
  spec reproduction (Google v. Oracle, 593 U.S. ___ (2021)). Canonical engine:
  amenominaka.

  Trademark: NVIDIA® / Omniverse® / Kit are trademarks of NVIDIA Corporation;
  API-compat identifiers only.

  ADR-2605261800 §D1/D6, R1.4 omni-kit-app surface. Wave 37 of
  ADR-2607020130."
  (:require [kotoba.lang.kami-nv-compat.amenominaka.extension :as ext]
            [kotoba.lang.kami-nv-compat.kami-rt.bvh :as bvh]
            [kotoba.lang.kami-nv-compat.kami-rt.index :as rt]
            [kotoba.lang.kami-nv-compat.omni-usd :as usd]))

;; ── KAMI viewer extension (end-to-end integration) ──────────────────────────

(defprotocol IKamiViewerExtension
  "Read-only introspection of a KamiViewerExtension's state — mirrors the
  public fields TS exposes on the class instance."
  (viewer-scene       [this] "The Scene built on startup, or nil before that.")
  (viewer-camera      [this] "The pinhole Camera (fixed at construction).")
  (viewer-last-frame  [this] "The framebuffer from the most recent on-update, or nil.")
  (viewer-frame-count [this] "Number of on-update calls since startup."))

(defn kami-viewer-extension
  "Build a Kit extension that loads a USD stage on startup and renders it on
  each update — the nv-compat stack (kami-usd → kami-rt) hosted as a Kit
  extension. Demonstrates the Application lifecycle driving the renderer.
  `opts` = {:width 64 :height 64 :eye [0 0 4] :target [0 0 0]}."
  ([usda] (kami-viewer-extension usda {}))
  ([usda {:keys [width height eye target]
          :or   {width 64 height 64 eye [0 0 4] target [0 0 0]}}]
   (let [camera (bvh/look-at eye target [0 1 0] 45 (/ width height))
         state  (atom {:scene nil :last-frame nil :frame-count 0})]
     (reify
       ext/IExt
       (on-startup [_ _ext-id]
         (swap! state assoc :scene (usd/stage->scene (usd/stage-open usda))))
       (on-update [_ _dt]
         (when-let [scene (:scene @state)]
           (let [frame (:framebuffer (rt/trace-image-cpu scene camera width height))]
             (swap! state #(-> % (assoc :last-frame frame) (update :frame-count inc))))))
       (on-shutdown [_]
         (swap! state assoc :scene nil :last-frame nil))

       IKamiViewerExtension
       (viewer-scene       [_] (:scene @state))
       (viewer-camera      [_] camera)
       (viewer-last-frame  [_] (:last-frame @state))
       (viewer-frame-count [_] (:frame-count @state))))))

(def kami-engine "amenominaka")
(def adr "ADR-2605261800")
