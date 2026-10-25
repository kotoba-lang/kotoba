# ADR 0001 — byoubu: backdrops as reproducible specs, with derived legibility facts

- Status: accepted
- Date: 2026-08-02
- Workspace ADR: `com-junkawasaki/root` `90-docs/adr/2608530000-byoubu-backdrop-catalog.edn`

## Context

The design-system stack owns the material that sits *on* a page —
`shitsuke.hig` tokens, `liquid-glass-ui`'s blur/specular/edge, `kotoba-ui`'s
shell. It owns nothing that sits *behind* one. `kotoba-ui.shell/hero` has a
`color-mix()` accent wash whose own source comment says it is deliberately
"NOT a literal gradient color"; a grep for `background-image` or `<video>`
across shitsuke / liquid-glass-ui / kotoba-ui / uikit / appkit hits exactly one
`object-fit`, on an avatar.

That is a real gap, because `liquid-glass` is a material designed on the
assumption that something is behind it. With nothing behind it, the most
expensive part of the stack renders against a flat fill.

The prompting example was a commercial backdrop set (getlayers.ai) which ships,
per backdrop, a looped 4K mp4 and a 2K poster.

## Decision

Ship the backdrop as **data**, in a zero-dependency catalog, at three delivery
tiers, with legibility facts **derived** from the palette rather than authored.

1. **A backdrop is a spec, not an asset.** Each entry carries a
   `:byoubu/scene` written in the vocabulary the existing kami stack already
   speaks (`sky`, `atmosphere`, `terrain` biome, `camera`, `postfx` grade) plus
   a `:byoubu/seed`. This library does not depend on those repos — it describes
   scenes in their language and lets the renderer, behind the `:render` alias,
   bind the description.

2. **Facts are computed, and validation enforces them.** `byoubu.facts`
   derives ink, appearance, accent, WCAG contrast and glass surface tier from
   the palette. `byoubu.spec` rejects a backdrop whose own recommended ink
   fails AA body contrast on its own content band, with the same severity as a
   missing palette key.

3. **Three tiers, one definition.** T0 CSS gradients (this repo, ~1 KB, no
   network); T1 rendered still; T2 live WebGPU scene. T0 reproduces the
   vertical light structure — including the skyline position, taken from the
   same `:camera :pitch-deg` the renderer uses — so content does not shift when
   a higher tier loads.

4. **Zero runtime dependencies.** The render stack lives in an alias.

5. **IDs are immutable once published.** A changed look is a new id.

## Alternatives considered

**Ship rendered video like the commercial sets.** Rejected as the *primary*
form, not as a delivery tier: video is fine as T2 delivery and useless as a
definition. It cannot be re-derived, and it carries no information about what
may be placed on top of it.

**Put the catalog in `liquid-glass-ui` or `kotoba-ui`.** Rejected: it would put
scene data behind a `css.core` dependency and inside a library whose subject is
foreground material. The split also lets a non-design-system app use the
catalog.

**One repo per backdrop.** Rejected — 78 backdrops is a catalog, not 78 repos.
`kami-isekai-assets` is the precedent for one repo holding a composed-primitive
catalog.

**Store the catalog as `resources/*.edn` and load it.** Rejected: resource
loading differs between CLJ and CLJS and would either force a reader
conditional into the hot path or duplicate the data (which is exactly what
`kami-terrain-scene` does today — its biome presets exist both in
`resources/biomes.edn` and in `src/terrain_scene.cljc`). The catalog is a
literal in `.cljc`; an EDN/JSON export for non-Clojure consumers is a
generated artifact, not a second source.

**Declare `resources/repository-rules.edn`.** Not done. The workspace authority
(`manifest/repository-rules.edn`) does classify prefix-less repos as
`{:role :library :execution :none}`, but `scripts/verify-repository-roles.cljs`
only audits repos whose basename carries a known prefix, and its
`assert-prefix-declarations!` would call `str/starts-with?` on a nil prefix. A
declaration here would be unread at best and a verifier crash at worst.

## Consequences

- A consumer can ask "what backdrop, and what does it do to my text" without a
  renderer, a GPU, or a browser.
- The catalog cannot contain a backdrop that is unreadable by its own
  recommendation; that is a test, not a review convention.
- Adding a backdrop is one map. Adding a *kind* of backdrop (a scene the
  current nine-role palette vocabulary cannot express) is a schema change, and
  should be.
- T1/T2 do not exist yet. `catalog/generator` carries `:pin nil` rather than an
  unverified sha, and the scene specs — though structurally validated and
  authored in the renderer's vocabulary — have not been round-tripped through
  a GPU. The first render is the thing that will find whatever is wrong with
  them.

## Addendum — 2026-08-02: T1 shipped, and measurement overturned the facts layer

T1 is implemented (`render/byoubu/render/poster.cljk`, `bin/render.cljk`) and
all four backdrops have rendered posters in `resources/byoubu/posters/`. Three
things changed as a result, two of them corrections to this ADR.

**Posters are SVG, not bitmaps.** The 3D rule permits SVG for a thumbnail or an
explicit fallback while WebGPU stays authoritative for the live scene. SVG made
the output text — diffable, reviewable in a PR, and small enough to live in git
— which removed the need for the `byoubu-assets` DataLad/B2 dataset at this
tier entirely. The silhouettes come from `terrain.noise/fbm-noise`, so the
scene spec's `:dune-wavelength` and `:dune-amplitude` drive the real library
rather than a second noise implementation.

**The declared content bands were wrong, and the AA gate was passing on a
fiction.** Sampling the rendered posters in Chrome (mean sRGB over the full
width, 30%–75% of frame height) showed the content band is mostly *sky*, three
to nineteen times brighter than the authored ground-dominated mixes. Under
measurement `:cobalt-dune` sat at 3.97:1 — below AA — while its declared facts
reported 15.42:1. Its palette was darkened. `:byoubu/measured` now carries the
sampled band per tier, `byoubu.facts` prefers it over the declared mix, and a
backdrop with a rendered poster must have been measured. The original decision
("facts are computed, and validation enforces them") was right; computing them
from an authored weighting was not enough to make them true.

**"Content on T0 and T2 sit on the same luminance" was false.** Measured, T0's
band is about half as bright as T1's on every dark backdrop. Corrected: the
tiers share an *ink and appearance*, not a luminance, and `byoubu.facts` now
picks ink by the worst tier across all of them rather than a representative
one, so the AA guarantee holds whichever tier a client happens to get. Both
tiers were measured; the library's computed per-tier contrasts agree with
Chrome's to two decimals.

**Still not built: T2.** `generator :tier-2 :pin` remains nil. The scene specs
carry sky, atmosphere, camera and grade terms that only the live renderer
consumes; T1 uses the terrain and atmosphere terms and approximates the rest.
