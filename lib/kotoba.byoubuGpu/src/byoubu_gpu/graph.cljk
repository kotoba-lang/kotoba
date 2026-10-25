(ns byoubu-gpu.graph
  "The backdrop as a `kami.webgpu` render graph — one fullscreen pass.

  This is the whole reason T2 is not a second renderer. `kami.webgpu/init!`
  takes `{:graph <EDN>}`, and the engine's own default graph already contains
  fullscreen pipelines (`:atmosphere`, `:bloom`, `:ssao`) drawing three
  vertices with no mesh. A backdrop is that shape: one pipeline, one uniform,
  one pass to the screen. So the graph below is *data handed to the canonical
  executor*, not an engine.

  What the executor did not have was a way to bind a caller-supplied uniform:
  `build-bind` recognised exactly `:uniform`, `:atmosphere-uniform`,
  `:ssao-uniform` and `:style-uniform`, all engine-owned buffers with fixed
  sizes. `{:uniform <name>}` binds plus a `:uniforms {<name> {:size n}}` graph
  key were added to `kotoba-lang/webgpu` for this — a general capability any
  domain package can use, which is the alternative to every such package
  reaching for the raw W3C binding and growing its own renderer."
  (:require [byoubu-gpu.shader :as shader]))

(def uniform-name :byoubu)

(defn render-graph
  "Render graph EDN for one backdrop.

  `:color :screen` draws straight to the swapchain: a backdrop has no HDR
  chain to feed, and routing it through the engine's half-resolution HDR
  target would cost a resolve and a composite to produce the same pixels."
  [backdrop]
  {:shaders   {:byoubu (shader/wgsl backdrop)}
   :uniforms  {uniform-name {:size shader/uniform-bytes}}
   :targets   {}
   :samplers  {}
   :pipelines {:byoubu {:shader :byoubu
                        :fullscreen true
                        :color :screen
                        :binds [{:uniform uniform-name}]}}
   ;; The engine's own pass vocabulary: :color names the attachment, :clear its
   ;; clear value. A `:fullscreen` pipeline draws three vertices with no mesh —
   ;; the same path :atmosphere / :bloom / :ssao already take in the default
   ;; graph — so a backdrop needs no geometry and no instances.
   :passes    [{:pipeline :byoubu :color :screen :clear [0 0 0]}]})

(defn valid?
  "Structural check that does not need a GPU: one shader, one uniform of the
  size the struct declares, one fullscreen pipeline bound to it, one pass."
  [g]
  (boolean
   (and (= 1 (count (:shaders g)))
        (= shader/uniform-bytes (get-in g [:uniforms uniform-name :size]))
        (true? (get-in g [:pipelines :byoubu :fullscreen]))
        (= :screen (get-in g [:pipelines :byoubu :color]))
        (= [{:uniform uniform-name}] (get-in g [:pipelines :byoubu :binds]))
        (= 1 (count (:passes g)))
        (= :byoubu (get-in g [:passes 0 :pipeline]))
        (= :screen (get-in g [:passes 0 :color])))))
