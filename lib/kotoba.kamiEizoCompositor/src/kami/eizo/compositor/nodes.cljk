(ns kami.eizo.compositor.nodes
  "VFX compositing node *types*, shaped as data compatible with
  `kotoba-lang/comfyui`'s node-type contract (`:type`/`:category`/
  `:inputs`/`:outputs`/`:fn`, registerable via `comfyui.node/register!`
  and executable via `comfyui.exec/execute` on a ComfyUI-API-format
  workflow) — see that repo's `src/comfyui/node.cljc` docstring for
  the exact contract this mirrors.

  DELIBERATELY NOT A DEPENDENCY of comfyui: `kotoba-lang/comfyui` is
  GPL-3.0-licensed (matching upstream ComfyUI); taking it as a
  `deps.edn` dependency would pull this Apache-2.0 repo's licensing
  into GPL-3.0 territory (GPL is a strong copyleft — requiring a GPL
  library generally obligates the combined work to also be GPL). This
  repo instead defines its node types as plain data in the same shape
  comfyui's registry expects, with zero import of comfyui code. A
  consumer app that has already chosen to accept comfyui's GPL-3.0
  license can wire these node-type maps into a `comfyui.node/registry`
  itself; that choice is left to the consumer, not baked in here."
  (:require [kami.eizo.compositor.chroma-key :as chroma-key]
            [kami.eizo.compositor.roto :as roto]
            [kami.eizo.compositor.tracking :as tracking]
            [kami.eizo.compositor.blend :as blend]))

(def layer-source-node
  {:type "EizoLayerSource"
   :category "eizo/compositor"
   :inputs {:source-id {:type "STRING"}}
   :outputs [{:name "layer" :type "EIZO_LAYER"}]
   :fn (fn [{:keys [source-id]}] [{:source-id source-id}])})

(def chroma-key-node
  {:type "EizoChromaKey"
   :category "eizo/compositor"
   :inputs {:pixel {:type "RGB"}
            :key-color {:type "RGB"}
            :tolerance {:type "FLOAT" :default 0.1}
            :softness {:type "FLOAT" :default 0.1}}
   :outputs [{:name "alpha" :type "FLOAT"}]
   :fn (fn [{:keys [pixel key-color tolerance softness]}]
         [(chroma-key/key-alpha pixel {:key-color key-color
                                        :tolerance tolerance
                                        :softness softness})])})

(def roto-mask-node
  {:type "EizoRotoMask"
   :category "eizo/compositor"
   :inputs {:polygon {:type "POINT_LIST"}
            :point {:type "POINT"}}
   :outputs [{:name "inside?" :type "BOOL"}]
   :fn (fn [{:keys [polygon point]}]
         [(roto/point-in-polygon? polygon point)])})

(def tracking-position-node
  {:type "EizoTrackPosition"
   :category "eizo/compositor"
   :inputs {:track {:type "TRACK"}
            :frame {:type "INT"}}
   :outputs [{:name "position" :type "POINT"}]
   :fn (fn [{:keys [track frame]}]
         [(tracking/position-at track frame)])})

(def composite-node
  {:type "EizoComposite"
   :category "eizo/compositor"
   :inputs {:top {:type "RGB"}
            :bottom {:type "RGB"}
            :mode {:type "ENUM" :default :normal}
            :opacity {:type "FLOAT" :default 1.0}}
   :outputs [{:name "result" :type "RGB"}]
   :fn (fn [{:keys [top bottom mode opacity]}]
         [(blend/composite mode top bottom opacity)])})

(def node-pack
  "A 'node pack' in comfyui's terminology — a seq of node-type maps
  a consumer can pass to `comfyui.node/register!`."
  [layer-source-node chroma-key-node roto-mask-node tracking-position-node composite-node])

(def example-workflow
  "A ComfyUI-API-format workflow (same shape as comfyui's own
  quickstart example) wiring layer -> chroma-key -> composite-over-background.
  This is workflow DATA only — executing it requires a comfyui.exec
  context with this repo's node-pack registered, which is a consumer-side
  choice (see namespace docstring). Included so the wiring is concrete
  and inspectable, not just described in prose."
  {"fg"  {:class_type "EizoLayerSource" :inputs {:source-id "greenscreen-take-04"}}
   "bg"  {:class_type "EizoLayerSource" :inputs {:source-id "studio-plate-02"}}
   "key" {:class_type "EizoChromaKey"
          :inputs {:pixel ["fg" 0] :key-color [0.0 1.0 0.0] :tolerance 0.15 :softness 0.1}}
   "out" {:class_type "EizoComposite"
          :inputs {:top ["fg" 0] :bottom ["bg" 0] :mode :normal :opacity ["key" 0]}}})
