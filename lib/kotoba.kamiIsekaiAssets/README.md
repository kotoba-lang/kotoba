# kami-isekai-assets

**An EDN template library for isekai/tensei-genre RPG characters and effects —
composed primitives, not asset files.**

`kami.isekai.chargen/compose-character` turns `{:race :class :seed}` into the
exact `kami.sprite2d` primitive vector every [network-isekai](https://isekai.network)
game already uses (`[:circle/:rect/:ellipse/:arc {...}]`), plus a
`:render/profiles` fallback for the 3D renderer. No PNG/GLB/WAV files — every
character, monster, and skill effect is data you can read, tweak, and fork,
same as the rest of the catalog.

## Why no real images/3D meshes/voice audio

This library stays inside the engine's existing "composed primitives +
synthesised audio, no asset files" philosophy (see network-isekai's own
`:render/sprite2d` games) rather than generating illustrated art, meshes, or
TTS voice lines — those need the AI-generation backend (`generate.html`,
Modal GPU) and are a separate, costed step per asset, not something this
library does by default.

## Aesthetic

The default palette (`kami.isekai.palette/watercolor`) desaturates every hue
toward a warm paper tone — the late-90s Squaresoft "artisan RPG" register
(*Legend of Mana*, *SaGa Frontier 2*, *Valkyrie Profile*, *Final Fantasy
Tactics*): watercolour over cel-shaded, restraint over saturation, a handful
of primitives reading as a whole silhouette rather than an illustration.
`kami.isekai.palette/brainrot` is an explicit **opt-in** loud/saturated remix
for the rare case you want the current internet-meme register instead — it
is never applied unless you ask for `:variant :brainrot`.
`kami.isekai.palette/pixel8` is a third opt-in variant: nearest-swatch
quantization down to a small fixed 24-colour retro palette, for an 8-bit
recolour of the same silhouette (`:variant :pixel8`) — still composed
primitives, not raster pixel art (see above). Pair it with
`kami.isekai.chargen/walk-cycle` (a torso `:bob` + desynced accessory `:sway`,
piped through `(update (compose-character ...) :sprite walk-cycle)`) for a
walking-in-place motion; idle characters already breathe via the head's
`:pulse` by default.

## Usage

```clojure
(require '[kami.isekai.chargen :as chargen])

(chargen/compose-character {:race :elf :class :mage :seed 42})
;; => {:sprite [[:circle {...}] [:circle {...}] [:arc {...}] [:rect {...}] ...]  ; incl. a staff — see below
;;     :render/profile {:color [...] :w 0.8 :h 1.7 :emissive 0.15}
;;     :tags ["elf" "mage"]}
```

Drop `:sprite` straight into a game's `scene.edn` under `:sprites {:my-npc
[...]}}`, and `:render/profile` under `:render/profiles {:my-npc {...}}`.

An unknown `:race`/`:class` (a typo — `:elve` for `:elf`) throws with the
full list of valid ids, rather than silently falling back to `:human`/
`:adventurer` and shipping a wrong-but-valid character with no signal.
Check an id up front with `kami.isekai.catalog/known-race?` if you're
taking `:race`/`:class` from untrusted input.

Every class draws its default weapon loadout automatically (a knight gets a
sword+shield, a mage a staff, an adventurer a dagger, a king a scepter —
`kami.isekai.equipment/class->weapons`) — a bare-handed "knight" reads as
unfinished, not restrained. Pass `:equip? false` to opt out, or call
`kami.isekai.equipment/equip` yourself for a custom loadout.

```clojure
(require '[kami.isekai.monsters :as monsters])
(monsters/compose-slime)                       ; the archetypal starter monster
(monsters/compose-slime-fire)                  ; and compose-slime-ice / compose-slime-poison
(monsters/compose-dragon {:seed 3})            ; boss-tier, menacing recolour
(monsters/compose-skeleton {:seed 1})          ; undead dungeon-tier, bone/glow recolour
(monsters/compose-troll {:seed 1})             ; large, bare-handed brute
(monsters/compose-ghost)                       ; standalone ethereal plan, floats
(monsters/compose-wolf)                        ; standalone quadruped plan (pack monster)

(require '[kami.isekai.skills :as skills])
(skills/skill :fireball)                       ; {:audio {...kami.audio recipe...} :fx {...burst...}}

(require '[kami.isekai.party :as party])
(party/compose-party party/starter-party)      ; 4 members, each with a formation :offset [dx dy]

(require '[kami.isekai.status :as status])
(status/compute-stats {:race :human :class :adventurer :level 5 :cheat? true})
;; => {:level 5 :hp 1184 :mp 237 :atk 118 :def 118 :spd 118 :luk 118 :cheat? true}
;;    the OP-protagonist trope as numbers, not just a visual aura

(require '[kami.isekai.tensei :as tensei])
(tensei/compose-summoning-circle)              ; the genre's namesake moment — a ground prop
tensei/transition                              ; {:audio {...} :fx {...}} — the arrival flash
```

## Catalog

- **Races** (`kami.isekai.races`) — human, hume (FFT-lineage flavour alias of
  human), elf, dwarf, orc, goblin, kobold, troll, beastman, dragon-kin.
- **Classes** (`kami.isekai.classes`) — adventurer, knight, mage, merchant,
  guild-master, king, princess, priest (the dedicated healer — bare-handed,
  a holy-symbol accessory, pairs with `kami.isekai.skills/:holy-heal`).
- **Monsters** (`kami.isekai.monsters`) — slime (+ fire/ice/poison elemental
  variants), goblin-raider, orc-brute, kobold-scout, troll (bare-handed
  brute), wyvern, dragon (boss), skeleton (undead recolour), ghost
  (standalone ethereal plan, floats), wolf (standalone quadruped plan, pack
  monster).
- **Skills/magic** (`kami.isekai.skills`) — fireball, ice-lance, holy-heal,
  curse, wind-blade, earth-spike, teleport, summon, cheat-aura (the isekai
  overpowered-protagonist trope, as a composable golden halo —
  `kami.isekai.chargen/cheat-aura`, or pass `:cheat? true` to
  `compose-character`).
- **Party formation** (`kami.isekai.party`) — `compose-party` arranges a list
  of character specs into a classic front-line/back-line RPG formation
  (1–5 dedicated slots, wraps beyond that); `starter-party` is the
  archetypal cheat-protagonist + knight + mage + rogue starter lineup.
- **Structures** (`kami.isekai.structures`) — world-decoration props, not
  characters: `compose-castle` (keep + flanking turrets + banner) and
  `compose-guild-hall` (the adventurer's-guild storefront), both taking an
  optional palette-hue override. `kami.isekai.catalog/structure-ids` (and
  `summary`'s `:structures` count) also counts `tensei/compose-summoning-
  circle` as a structure — it's a ground prop by shape, just documented
  under 転生/tensei below since that's its thematic home. `(catalog/summary)`
  reporting 3 structures while this section only lists 2 isn't a bug —
  check `structure-ids` if the count doesn't match what you expected.
- **Equipment** (`kami.isekai.equipment`) — weapon/held-item silhouettes
  (sword, dagger, staff, bow, shield, scepter); `equip`/`equip-for-class`
  compose one or more onto any character's `:sprite`. `compose-character`
  applies the class default loadout automatically.
- **Status/stats** (`kami.isekai.status`) — `compute-stats` derives
  HP/MP/ATK/DEF/SPD/LUK from race + class + level, deterministically.
  Deliberately separate from `compose-character` (mechanical data, not a
  visual) — call it explicitly when a game wants a status window.
  `:cheat? true` multiplies every stat 8× — the isekai overpowered-
  protagonist trope as numbers, not just `chargen/cheat-aura`'s halo.
- **転生 / tensei** (`kami.isekai.tensei`) — the genre's namesake moment.
  `compose-summoning-circle` is a static ground prop (concentric rings +
  radial rune ticks); `transition` is the arrival flash itself
  (`kami.audio` + `kami :fx`, same shape as a `kami.isekai.skills` entry).
- **Catalog** (`kami.isekai.catalog`) — one-stop introspection: `race-ids`/
  `class-ids`/`skill-ids`/`monster-ids`/`structure-ids`, `known-race?` etc.
  to validate an id before calling `compose-character`, and `summary` for
  a plain-data snapshot of the whole catalog's size.

- **Presets** (`kami.isekai.presets`) — `presets`, the single curated list
  (a representative slice, not every combination) that both the `gen-presets`
  script and network-isekai's Asset Hub deploy script consume directly — the one
  place this list is defined, so it can't fall out of sync with itself the
  way it already did once (see CHANGELOG).

`gen-presets` writes `kami.isekai.presets/presets` as standalone
`character.edn` files. network-isekai's default Asset Hub presets
(`isekai.network/assets.html`) are generated this way.

> **`gen-presets` is currently unavailable as a task.** It was
> `kbb -M:gen-presets --out <dir>`; babashka was retired as this workspace's script
> host by ADR-2607173000 and the conversion could not express its
> `(load-file "scripts/gen_presets.cljk")` body, so it was dropped
> (ADR-2608131600). The recovered form is in `scripts/tasks-complex.edn` and the
> script itself is still at `scripts/gen_presets.cljk`; restoring it is a port,
> not a conversion.

## Render adapter (`kami.isekai.render-adapter`)

This library stays "data only" (see above) but a composed entity's `:sprite` vector already IS
the exact primitive vocabulary [kotoba-lang/webgpu](https://github.com/kotoba-lang/webgpu)'s
`kami.sprite-gpu/prims->quads` consumes — the GPU-instanced-quad pipeline network-isekai's games
already draw every frame through. `kami.isekai.render-adapter` is the small (dependency-free)
glue for the other side of that pipeline: `kami.scene2d/frame-quads` wants a whole *scene*
(`{:sprites {tag prims}, ...}`) and a per-frame *snap* (`[{:tag :pos} ...]`), not a single
composed map.

```clojure
(require '[kami.isekai.monsters :as monsters]
         '[kami.isekai.render-adapter :as radapt]
         '[kami.scene2d :as s2])                        ; kotoba-lang/webgpu, sibling dep

(let [{:keys [scene snap]} (radapt/preset->scene "slime" (monsters/compose-slime))]
  (s2/frame-quads scene snap [] 0 640 480))
;; => {:sky {...} :quads [...]}  — pack-instances that straight into a WebGL2/WebGPU draw call
```

`kbb --backend sci scripts/run-task.cljk render-test` proves this actually draws real pixels: a real headless-Chromium/WebGL2 canvas
render of `monsters/compose-slime` through this adapter + `kami.scene2d`/`kami.sprite-gpu`,
`readPixels`-verified (the slime's green body fill + its two dark eye dots are both checked for
on screen, not just "compiles"). Needs a sibling `kotoba-lang/webgpu` checkout (+ its own sibling
`kotoba-lang/expr`, for `kami.wgsl`) next to this repo — see the `:render-test` entry in
`scripts/tasks.edn` for the exact layout and why (kami.playwright's bridge script + the GLSL fixtures it reuses are
read via cwd-relative paths in that repo).

## Develop

```bash
kbb --backend sci scripts/run-task.cljk test           # data gate: every race × class × monster × skill composes to valid data
kbb --backend sci scripts/run-task.cljk render-test    # pixel-verified GPU render proof (see caveat below)
```

Two caveats, both a consequence of babashka's retirement (ADR-2607173000):

- **`gen-presets` is unavailable** — see the Presets section above.
- **`render-test` is registered, but its `:cmd` still shells out to `bb`.** So
  it runs only where babashka happens to be installed, and not on a murakumo
  fleet node. `scripts/tasks.edn` says why it was left that way (the test's
  playwright + cheshire dependencies are JVM-only); the consequence is that the
  task resolves but is not portable, which is a different failure from the
  dropped `gen-presets` and is worth knowing before you rely on it in CI.

## License

Public domain (matches network-isekai's game/asset data).
