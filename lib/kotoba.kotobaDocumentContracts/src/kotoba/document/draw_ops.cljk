(ns kotoba.document.draw-ops
  "The draw-ops vocabulary `kotoba-lang/cssom`'s `layout` namespace already
   emits, and both real paint hosts in `kotoba-lang/dom-gpu` (`webgl.cljs`/
   `webgpu.cljs`) already consume. This is the single most directly
   reusable piece of this whole contract for a future non-Clojure renderer
   (e.g. an `aiueos` system-UI painter): a draw-ops LIST is a flat,
   ALREADY-LAID-OUT paint plan in device pixels -- no further cascade or
   box-model computation needed to consume it, only a paint backend that
   can fill rects, draw text, and push/pop a clip rect, painted strictly in
   array order (no z-index, no re-ordering -- see `cssom.layout`'s own
   background-before-border ordering convention, itself the fix for a real
   engine-wide bug this session found and documented).

   Every op is a map with a `:draw/op` discriminant:

     {:draw/op :rect  :x n :y n :w n :h n :color string? :opacity n}
     {:draw/op :text  :x n :y n :text string? :color string? :opacity n
                      :font-size n (optional) :font-weight kw (optional)
                      :font-style kw (optional) :text-decoration kw (optional)}
     {:draw/op :clip  :clip/op (:push | :pop) :x n :y n :w n :h n}
     {:draw/op :node  :id pos-int? :tag keyword? ...}  ; semantic/hit-test
                                                         ; metadata, not a
                                                         ; paint instruction
                                                         ; -- a renderer MAY
                                                         ; ignore :node ops
                                                         ; entirely and still
                                                         ; paint correctly.

   `:opacity` is a single already-cascaded 0..1 float per op (cumulative
   down the element tree -- see `cssom.layout`'s own `(* opacity (:opacity
   st))` composition), never a per-channel color alpha; a color string's OWN
   alpha (e.g. `rgba(0,0,0,0.5)`) is separate and orthogonal, matching
   `kotoba-lang/dom-gpu`'s own `kotoba.wasm.host.color` ALPHA CONTRACT.

   Growing this vocabulary (new optional keys on `:text`, e.g. as
   text-decoration/text-align/measure-text-aware offsets were each added
   incrementally this session) is expected; a renderer that doesn't
   recognize an optional key simply doesn't act on it, matching every
   `:text` extension already landed against this pipeline."
  )

(def op-kinds #{:rect :text :clip :node})

(defn draw-op?
  [x]
  (and (map? x) (contains? op-kinds (:draw/op x))))

(defn rect-op?
  [x]
  (and (draw-op? x) (= :rect (:draw/op x))
       (number? (:x x)) (number? (:y x))
       (number? (:w x)) (number? (:h x))))

(defn text-op?
  [x]
  (and (draw-op? x) (= :text (:draw/op x))
       (number? (:x x)) (number? (:y x))
       (string? (:text x))))

(defn clip-op?
  [x]
  (and (draw-op? x) (= :clip (:draw/op x))
       (contains? #{:push :pop} (:clip/op x))))
