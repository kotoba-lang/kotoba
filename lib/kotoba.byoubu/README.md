# byoubu

**A catalog of backdrops as data — not a folder of videos.**

屏風 (byōbu): the folding screen you stand behind people, historically painted
with landscapes. This library is the same object for a page: the scenery that
sits behind content, and the facts about what that scenery does to the content
on top of it.

```clojure
(require '[byoubu.core :as byoubu])

(byoubu/ids)
;; => [:cobalt-dune :ember-mesa :purple-desert :salt-flat]

(byoubu/facts :purple-desert)
;; => #:byoubu.facts{:content-color   "#725b94"     ; measured, not guessed
;;                   :luminance       0.1320
;;                   :appearance      :dark
;;                   :ink             "#f4f2fa"
;;                   :contrast        5.20          ; the WORST tier, not the average
;;                   :tier-contrasts  {:declared 16.64 :plate 8.61 :poster 5.20}
;;                   :accent          "#a887cf"
;;                   :accent-hue      267.5
;;                   :glass-surface   :thin}

(byoubu/poster-url :purple-desert "/assets")
;; => "/assets/byoubu/posters/purple-desert.svg"
```

Mounting one in a page is [`kotoba-lang/byoubu-ui`](https://github.com/kotoba-lang/byoubu-ui).

## Why this is not a video library

Commercial backdrop sets ship a looped 4K mp4 and a poster. Two things follow
from that format, and both are why this one is shaped differently.

**A video cannot be re-derived.** You can crop it. You cannot re-render it at
another aspect ratio, shift the time of day, recolor it to a brand, or fork a
sibling variant. Here a backdrop is a `:byoubu/scene` — a spec written in the
vocabulary the existing kami stack already speaks (`sky`, `atmosphere`,
`terrain` biome, `camera`, `postfx` grade) plus a `:byoubu/seed`. Everything a
renderer needs is in the entry, so the picture is reproducible rather than
merely distributable.

**A video says nothing about what may be put on top of it.** Every consumer
re-guesses the text color, the accent, and how opaque the panels need to be,
and at least one of them gets it wrong. `byoubu.facts` computes those answers
from the palette — ink, appearance, accent, WCAG contrast, and which glass
surface tier content wants — deterministically, with no renderer and no
browser. `byoubu.spec` then treats the answer as *structural*: a backdrop
whose own recommended ink fails AA body contrast on its own content band is
rejected by the same validator that rejects a missing palette key. The catalog
cannot contain a backdrop that is unreadable by its own recommendation.

## Three tiers

A backdrop is defined once and delivered at whichever tier the client can take.

| tier | what it is | cost | status |
|---|---|---|---|
| **T0** | `byoubu.plate` — layered CSS gradients derived from the palette | ~1 KB, first frame, no network | shipped |
| **T1** | a rendered SVG poster, procedural from the seed | 9–25 KB of text, in git | shipped |
| **T2** | the live WebGPU scene through the kami stack | GPU | shipped — [`byoubu-gpu`](https://github.com/kotoba-lang/byoubu-gpu) |

T0 is deliberately not a picture of dunes — CSS gradients cannot draw a ridge
line, and pretending otherwise is how gradient backgrounds come to look cheap.
What it reproduces is the vertical light structure: zenith, horizon glow,
ground fall-off, vignette, with the skyline placed from the same
`:camera :pitch-deg` the renderer uses.

T1 is SVG rather than a bitmap because the workspace 3D rule permits SVG for a
thumbnail or an explicit fallback (WebGPU stays authoritative for the live
scene), and SVG buys three things a PNG would not: the output is text, so it
is diffable, reviewable in a PR, and needs no B2/DataLad dataset; it is
resolution-independent; and it is byte-reproducible from `:byoubu/seed`. The
ridge and dune silhouettes come from `terrain.noise/fbm-noise` — the real
library the scene spec names, not a second noise implementation.

**The tiers do not share a luminance.** Measured, T0's content band runs about
half as bright as T1's on every dark backdrop, and T2 lands between them. What
is guaranteed, and tested, is that every tier resolves to the same ink and
appearance and that each independently clears AA — `byoubu.facts` picks ink by
the *worst* tier, because a client does not choose which tier it gets.

```
                 declared   plate    poster   gpu
purple-desert      16.64     8.61      5.20   7.42
cobalt-dune        16.21    10.12      7.54   9.69
ember-mesa         16.19     7.60      5.03   6.50
salt-flat          14.22    13.63     11.94  14.45     (dark ink)
```

## Zero runtime dependencies, on purpose

`:deps {}`. A page that wants a backdrop and legible text must not inherit
`sky` / `atmosphere` / `terrain` / `postfx` / `webgpu` (and, through terrain and
postfx, `kotoba-lang/compiler`). Those live in the `:render` alias, used only
by the offline exporter — the same split `liquid-glass-ui` keeps for
reagent/re-frame/shadow-css.

## Adding a backdrop

Add one map to `byoubu.catalog/catalog`. The tests do the rest: structure,
palette vocabulary, content-band weights, seed presence, biome membership in
the set `kami-terrain-scene` actually defines, and AA contrast.

IDs are **stable and immutable once published** — consumers pin them. A
changed look is a new id, not an edited entry.

## Tests

```bash
kbb --backend sci bin/test.cljk      # ClojureScript
kbb -M:test        # JVM
```

Both, always. The plate emitter formats numbers, and number formatting is
exactly where CLJ and CLJS quietly disagree — `(/ (Math/round x) 10.0)` prints
`62.0` on one and `62` on the other. There is a test for that.

## Measurement, and why it is not optional

The first four entries declared their content band as an authored weighting.
Sampling the rendered posters in Chrome showed the declared mixes were wrong —
content sits mostly on *sky*, three to nineteen times brighter than declared —
and that `:cobalt-dune` was actually at **3.97:1, under AA**, while its
declared facts claimed 15.42:1. Its palette was darkened in response.

So `:byoubu/measured` now carries the sampled content band for both the plate
and the poster tier, `byoubu.facts` prefers it over the declared mix, and a
backdrop with a rendered poster is required by test to have been measured.
Facts derived from an authored guess are a guess with a number printed on it.

## Status

The catalog, facts, T0 and T1 are implemented and tested on both runtimes;
28 tests / 308 assertions. The library's computed per-tier contrasts match
what Chrome measured off the rendered output to two decimals.

T2 lives in [`byoubu-gpu`](https://github.com/kotoba-lang/byoubu-gpu) — the
same scene spec compiled to WGSL and handed to `kami.webgpu` as a one-pass
render graph. Verified in Chrome on a real WebGPU device; its content band is
the `:gpu` tier above.

See `docs/adr/0001-byoubu.md`.
