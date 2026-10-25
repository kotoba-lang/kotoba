(ns kami.isekai.render-adapter
  "Bridges a kami-isekai-assets composed entity (chargen/monsters/structures/tensei `:sprite`
   output) into the `kami.scene2d` + `kami.sprite-gpu` GPU-instanced-quad pipeline
   (kotoba-lang/webgpu) that network-isekai's games already render every frame through.

   The gap this closes turned out to be small: `compose-character`/`compose-slime`/etc.'s
   `:sprite` vector already IS the exact primitive vocabulary `kami.sprite-gpu/prims->quads`
   consumes (`[:circle/:rect/:ellipse/:arc {...}]` — see kami.isekai.chargen's own docstring,
   which already promised this). What `kami.scene2d/frame-quads` actually wants around that
   vector isn't a single composed entity map, though — it's a whole *scene* ({:sprites {tag
   prims}, :render/sky {...}, ...}) plus a *snap* (the per-frame entity list,
   `[{:tag :pos} ...]`, see `kami.sprite2d.layout/draw-list`). This namespace is that small
   glue — turning one (or several) composed entities into the {:scene :snap} shape
   `kami.scene2d/frame-quads` expects — not a new renderer, and not a dependency of this
   library's own `deps.edn` (kami.scene2d/kami.sprite-gpu stay an opt-in, test/demo-only
   sibling dependency — see this repo's bb.edn `render-test` task + README).

   Pure data in, pure data out — no dependency on kami.scene2d/kami.sprite-gpu at compile
   time, so requiring this namespace never pulls in the render pipeline for callers who only
   want the EDN."
  )

(defn preset->scene
  "One composed entity (a map with a `:sprite` primitive vector — chargen/compose-character,
   monsters/compose-*, structures/compose-*, tensei/compose-summoning-circle, ...) at world
   position `[x y]` (default the origin) → `{:scene :snap}`, ready to hand straight to
   `(kami.scene2d/frame-quads scene snap fx tick W H)`.

   `id` becomes both the scene's `:sprites` key and the snap's `:tag` string —
   `kami.sprite2d.layout/draw-list` looks up `(keyword tag)` in `:sprites`, so the two must
   agree (this fn keeps that invariant so callers can't get it wrong)."
  ([id composed] (preset->scene id composed [0 0]))
  ([id composed [x y]]
   {:scene {:sprites {(keyword id) (:sprite composed)}}
    :snap  [{:tag (name id) :pos [x y]}]}))

(defn presets->scene
  "Several composed entities in one frame (e.g. `kami.isekai.party/compose-party`'s members, or
   any hand-picked group) → one `{:scene :snap}`. `placements` is `[[id composed pos] ...]`
   (`pos` optional, defaults to the origin per entry)."
  [placements]
  {:scene {:sprites (into {} (map (fn [[id composed _]] [(keyword id) (:sprite composed)]))
                     placements)}
   :snap  (mapv (fn [[id _ pos]] {:tag (name id) :pos (or pos [0 0])}) placements)})
