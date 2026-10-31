(ns kami.eizo.timeline.e2e.render-proof
  "Timeline model + frame/color query layer for the real-browser render
  proof (test/e2e/). Builds a real kami.eizo.timeline value (three
  solid-color clips, hard cuts, film-24 timebase) using this repo's own
  constructors and validator, and exposes a single frame-index -> expected
  RGB query (`color-at-frame`) driven entirely by `kami.eizo.timeline`'s own
  `clip-at-frame`/`clip-end` frame math.

  `test/e2e/page/index.html` (plain browser JS, not compiled — the only
  place in this proof that touches Canvas/VideoFrame/VideoEncoder/
  VideoDecoder, same split as org-w3-webcodecs's own E2E page) calls into
  this namespace for \"what color should frame N be\" both to *paint* each
  frame before encoding and to *verify* what came back out of decode.
  Render and verification oracle therefore share exactly one source of
  frame-accuracy truth — `kami.eizo.timeline` itself — so a passing result
  is proof the timeline's own frame math drove the render, not a
  independently-hardcoded stand-in for it.

  This is a **test/proof harness**, not a render pipeline: no effects,
  grading, or compositing — see the repo README's E2E section."
  (:require [kami.eizo.timeline :as tl]
            [kami.eizo.timeline.timecode :as tc]))

;; ---------------------------------------------------------------------------
;; The timeline under test: three 5-frame solid-color clips, back to back
;; (hard cuts — no overlap, so no transition object is needed for validity),
;; at a 24fps (film-24, non-drop) timebase.
;;
;;   clip-a [0,5)   src-red
;;   clip-b [5,10)  src-green
;;   clip-c [10,15) src-blue
;;
;; The two cut boundaries this proof must land exactly on are frame 5
;; (clip-a -> clip-b) and frame 10 (clip-b -> clip-c).

(def timebase tc/film-24)

(def clip-a (tl/clip {:id :a :source-id :src-red   :source-in 0 :source-out 5 :timeline-start 0}))
(def clip-b (tl/clip {:id :b :source-id :src-green :source-in 0 :source-out 5 :timeline-start 5}))
(def clip-c (tl/clip {:id :c :source-id :src-blue  :source-in 0 :source-out 5 :timeline-start 10}))

(def video-track
  (tl/track {:id :video-1 :type :video :clips [clip-a clip-b clip-c]}))

(def the-timeline
  (tl/timeline {:timebase timebase :tracks [video-track]}))

(def validation-result (tl/validate-timeline the-timeline))

(def color-by-source-id
  "The synthetic 'media' behind each clip's :clip/source-id: a single solid
  RGB triple. Stands in for real footage the same way org-w3-webcodecs's
  own E2E uses solid quadrant colors instead of a real video file — large
  uniform regions survive lossy H.264 compression well enough for a tight
  pixel-tolerance check."
  {:src-red   [230  20  20]
   :src-green [ 20 200  20]
   :src-blue  [ 20  20 230]})

(defn color-at-frame
  "Expected RGB for global timeline frame `frame`, or nil if no clip on
  `video-track` covers it. Derived *only* from
  `kami.eizo.timeline/clip-at-frame` — the actual frame/timecode math under
  test — never a re-hardcoded frame range."
  [frame]
  (when-let [c (tl/clip-at-frame video-track frame)]
    (get color-by-source-id (:clip/source-id c))))

;; --- browser-facing surface --------------------------------------------
;; Plain vars/fns. With `:optimizations simple` (no renaming/inlining, same
;; as org-w3-webcodecs's src/w3/webcodecs.cljs), these stay reachable from
;; plain JS as e.g. `kami.eizo.timeline.e2e.render_proof.color_at_frame_js`.

(defn timeline-duration []
  (tl/timeline-duration the-timeline))

(defn timeline-valid? []
  (:valid? validation-result))

(defn validation-errors []
  (clj->js (:errors validation-result)))

(defn color-at-frame-js
  "`color-at-frame` as a plain JS array (or nil/null), for index.html."
  [frame]
  (when-let [rgb (color-at-frame frame)]
    (clj->js rgb)))

(defn frame-duration-us
  "Frame duration in microseconds for `timebase`, computed from its own
  :num/:den (never a separately-hardcoded frame rate)."
  []
  (Math/round (/ (* 1000000 (:den timebase)) (:num timebase))))
