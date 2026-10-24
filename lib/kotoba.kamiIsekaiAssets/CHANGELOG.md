# Changelog

## Unreleased

- **A third palette variant (`:pixel8`) and a walk-cycle motion helper — a new recolour + a new
  procedural animation, not a raster sprite-sheet renderer.** `kami.isekai.palette/pixel8`
  quantizes any `[r g b]` to its nearest-neighbour swatch in a small fixed 24-colour palette
  (`pixel8-swatches`) sized in the same ballpark as an 8-bit-era console's simultaneous on-screen
  colour count — real nearest-colour palette mapping, not per-channel posterization (which was
  tried mentally and rejected: rounding each channel independently can still land on thousands of
  muddy/off-hue combinations no curated retro palette would ever ship, since each channel is
  quantized blind to what the other two are doing). Wired into `compose-character` as
  `:variant :pixel8` alongside `:watercolor`/`:brainrot`. Separately, `kami.isekai.chargen/walk-cycle`
  adds a walking-in-place motion on top of an already-composed `:sprite` — idle breathing already
  existed by default (the head's `:pulse [0.04 2.0]`), so this closes the other actual gap: a torso
  `:bob` at a faster cadence than that idle breathing, plus a desynced `:sway` on every other
  not-already-animated primitive (accessories, race tells, equipment) so they don't move in exact
  lockstep with the torso. Both effects are `kami.sprite2d`'s existing `:bob`/`:sway` keys (see
  `orgs/kotoba-lang/sprite2d`'s `prim!`) — no new renderer-side work, no new `:anim` vocabulary.
  `walk-cycle` has to find the torso by scanning for the first primitive without a pre-existing
  `:anim` rather than hardcoding `sprite[0]`, because `cheat-aura` prepends two already-`:pulse`'d
  halo circles in front of the torso when `:cheat? true` — hardcoding the index would have given
  the halo a `:bob` and left the actual body motionless. New preset `pixel8-op-protagonist`
  (same base character as `op-protagonist`/`op-protagonist-brainrot` — just `:variant :pixel8`
  piped through `walk-cycle`) demonstrates both together, the same before/after role
  `op-protagonist-brainrot` plays for `brainrot`. This is a recolour of the same vector-primitive
  silhouette and a continuous procedural tween, not literal pixel-art/dot-matrix raster imagery or
  a discrete frame-by-frame sprite sheet — this library still emits zero PNG/GLB/WAV files by
  design (see "Why no real images" above).
- **Second render-adapter case: a real composed PARTY (not just one monster), and a genuine
  formation-clearance bug the first round's world-unit-only math couldn't see.** The first render
  pass (below) only ever proved `render-adapter/preset->scene` (ONE entity, `compose-slime`).
  `presets->scene` (SEVERAL entities, each at its own `:offset`, in one frame — exactly the shape
  `kami.isekai.party/compose-party` produces) existed since day one but had never actually been
  rendered, only shape/unit-checked. Rendering `party/starter-party`'s real 4 members
  (protagonist/knight/mage/rogue) through `presets->scene` → `kami.scene2d/frame-quads` found a
  real, on-screen overlap `test/chargen_test.cljk`'s existing "formation clearance" check missed
  entirely: that check computed each member's "footprint" from `:dx` + radius only, silently
  ignoring `:dy` — so `kami.isekai.chargen`'s mage `:cloak` accessory (which hangs DOWN via `:dy`,
  not sideways via `:dx`) was invisible to it, and the cheat-flagged protagonist's aura visibly
  bled into the mage's cloak in the actual render. Fixed the clearance check to project each
  primitive onto the real slot-to-slot axis (direction-aware, exact for this catalog's
  axis-aligned circle/ellipse/rect/arc primitives) instead of one direction-blind scalar — it now
  correctly flags the old starter-party formation as 54.5 world-units short on that pair — and
  rescaled `kami.isekai.party`'s 4-slot formation ~1.25x to restore real clearance on every pair
  (verified both by the corrected math via `kbb -M:test`, and by re-rendering the real party:
  `test/render_pixel_test.cljk`'s new `starter-party-renders-real-pixels` samples each of the 4
  members' own distinctive on-screen feature — the protagonist's cheat-aura, the mage's staff
  orb, the knight's shield, the rogue's dagger blade — at the exact screen position its own
  formation `:offset` predicts, plus confirms the canvas centre stays background (the 4 aren't
  piled at the origin). Deliberately broke `presets->scene`'s `pos` threading (always place at
  `[0 0]`) to confirm the check discriminates: 5 of 6 assertions failed with real numbers
  (e.g. the protagonist-aura sample went from `(255 255 193)` to plain background `(128 128
  128)`), reverted cleanly, and the render passed again with the original numbers.
  Along the way, found (and documented — NOT fixed here, it lives in the sibling
  `kotoba-lang/webgpu` repo's `kami.sprite-gpu`, out of this repo's scope) that `:rect`-shaped
  primitives render at roughly DOUBLE their intended size through the GPU pipeline relative to
  the Canvas2D reference painter (`kami.sprite2d.cljs`) this catalog's primitive vocabulary was
  designed against — verified directly with a synthetic `[:rect {:w 100 :h 50}]` primitive
  measuring ~202×100 actual on-screen pixels. `:tree-count 0` added to the party test's scene
  config since `kami.scene2d/frame-quads` draws background trees unconditionally otherwise
  (unrelated content that would contaminate "is this background" pixel samples).
- **First real pixel of a kami-isekai-assets composed entity on screen,
  automated and pixel-verified** — closes the biggest maturity gap a
  2026-07 ecosystem audit found: this library's `:sprite` EDN had never
  actually been rendered by anything in ITS OWN test/demo suite
  (network-isekai consumes it, but that's a separate repo/org — its
  Asset Hub deploy step and its `isekai-gallery` game both just write/
  paste `:sprite` data, they don't verify a pixel came out the other
  end). Added `kami.isekai.render-adapter` — small, dependency-free glue
  turning one (or several) composed entities into the `{:scene :snap}`
  shape `kotoba-lang/webgpu`'s `kami.scene2d/frame-quads` expects (the
  actual gap was just that shape mismatch: a composed entity's `:sprite`
  vector already IS the exact primitive vocabulary
  `kami.sprite-gpu/prims->quads` consumes — no new renderer needed,
  reusing the same GPU-instanced-quad pipeline network-isekai's games
  already draw through). `kbb -M:render-test` (new task) renders
  `monsters/compose-slime` through that pipeline in a real headless
  Chromium/WebGL2 canvas (`kami.playwright`, kotoba-lang/webgpu's own
  harness, reused verbatim) and `readPixels`s the result, asserting the
  slime's actual watercolour-green body fill AND its two dark eye-dot
  sub-primitives are both really on screen — confirmed this
  discriminates (not another "didn't throw" placeholder) by deliberately
  breaking the adapter's scene/snap tag agreement (both assertions
  failed with real numbers: green pixel count 53252→717, eye-dot count
  967→0) and restoring it (back to 53252/967, exactly reproducing the
  original numbers). Needs a sibling `kotoba-lang/webgpu` checkout (+
  its own sibling `kotoba-lang/expr`) next to this repo to run — see
  `bb.edn`'s `render-test` task doc.
- **Strengthened the sprite validity gate from shape-checking to numeric
  sanity**: `valid-sprite?` only ever checked "is this a vector of
  `{:circle {}}`-shaped maps" — it would pass a sprite with a negative
  radius, a NaN colour channel, or a colour value miles outside `[0,1]`
  without complaint, since the container shape is still technically
  valid. Added `sane-prim?`/`sane-sprite?` checking every primitive's
  actual `dx`/`dy`/dimension/colour values (portable NaN test via
  `(= n n)`, works identically on JVM and cljs with no `#?(:clj ...)`
  guard needed) and ran it across all 80 race×class combos × 3 seeds
  (240 compositions) plus every monster/structure/tensei composer (16
  more) — clean pass, 0 problems, but locked in as a permanent gate.
  Verified the check genuinely discriminates (not another `map?`-style
  placeholder): confirmed it rejects a negative radius, a NaN colour
  channel, and an out-of-range colour value, and accepts valid data.
  `kbb -M:test` 45/45 (was 43/43).
- **Added `op-protagonist-brainrot`** (30th preset): `palette/brainrot` —
  the "最近流行りのブレインロット" aside from the original request — has
  been implemented and even bug-fixed (a real saturation-direction issue,
  see below) for many rounds, but had never actually been shown anywhere.
  Same character as the existing `op-protagonist` preset (same race/
  class/seed/cheat-aura), just `:variant :brainrot` instead of the
  default `:watercolor` — a deliberate before/after pairing.
- **Fixed a real JVM/ClojureScript divergence in `palette/seeded-jitter`**,
  found proactively (not from a live bug — network-isekai never actually
  runs `kami.isekai.*` in a browser, only via babashka/JVM for static
  generation) by directly comparing `bb` (JVM) against `nbb` (real
  ClojureScript on Node) for identical large seeds. `bit-shift-left` /
  `unsigned-bit-shift-right` truncate to 32 bits *after every operation*
  in JS (ECMA-262 semantics) but run on untruncated 64-bit longs on the
  JVM — for seeds beyond ±2^31 this produced genuinely different jitter
  values on each platform (`2147483647` → `0.9054` fill-color-derived
  JVM output vs `0.9214` in cljs before the fix; confirmed a naive
  input-only 32-bit mask wasn't enough — every intermediate
  `bit-shift-left` step, and `unsigned-bit-shift-right`'s own 64-bit-vs-
  32-bit-wide shift field, both needed explicit masking).

  **Correction to this entry** (caught immediately after committing, while
  regenerating presets to check for a diff): the claim above that "no
  shipped preset's seed is large enough to have hit this" was WRONG.
  `bit-shift-left ... 13` overflows 32 bits for almost any seed with more
  than a handful of significant bits — not just seeds literally beyond
  ±2^31 — so every one of `kami.isekai.presets`' 12 race×class seeds
  (e.g. `(hash [:elf :mage])` = 2039901199, comfortably inside ±2^31)
  ALSO already diverged between bb and nbb before this fix (verified by
  hand for all 12). Nothing currently deployed was *visibly* broken only
  because network-isekai has only ever generated these presets via
  babashka/JVM — but the JVM-side values themselves were already the
  "wrong" (platform-inconsistent) half of the disagreement, not an
  arbitrarily-different-but-equally-valid one. This fix changes the
  skin-tone jitter for all 12 currently-shipped race×class presets to the
  now-cross-platform-correct value — see kami-isekai-assets consumers
  (network-isekai) for the regenerate+redeploy follow-up.

  Verified identical bb/nbb output across 30 random seeds up to ±10^12
  after the fix, plus all 12 real preset seeds. `kbb -M:test` 43/43 (was
  42/42) — added a hardcoded cross-platform lock-in test (can't invoke
  real cljs from `kbb -M:test` itself, so it pins the values both platforms
  already agreed on by hand).
- **Fixed the starter-party formation touching itself**: `compose-party`'s
  4-slot formation only ever verified offsets were *distinct*, not that
  members had real visual clearance. Computed actual per-member primitive
  extents (not a guess) and found `starter-party`'s slot 0 — always
  cheat-flagged by convention, whose aura reaches a 210-unit radius vs. a
  bare character's ~150-175 — had EXACTLY ZERO clearance from its top-row
  neighbour at the old offsets (210+170 half-widths == the 380-unit gap
  between them). Scaled the 4-member formation ~1.35x using starter-
  party's real footprints so every pairwise gap clears with margin.
  Replaced the weak "distinct offset" check with one that computes real
  clearance from actual primitive extents — confirmed it catches the
  original bug by reverting the fix and watching it fail. `kbb -M:test` 42/42
  (was 41/41).
- **Replaced another proxy-assertion placeholder**, same audit instinct
  that found last round's `brainrot` bug: "different seeds can jitter skin
  colour" only checked `(map? (compose-character ...))`, which would pass
  even if jitter were entirely broken. Actually verified: 20 different
  seeds produce 20 distinct skin tones (pal/seeded-jitter works correctly
  for non-zero seeds). Also found and documented a real, non-obvious
  edge case while doing this: `:seed 0` — `compose-character`'s *default*
  when no `:seed` is passed — is a fixed point of the XOR-shift jitter
  formula and always returns exactly 0 jitter, so repeated no-seed calls
  produce identical skin tones. Not a bug (a caller who wants variety
  across N instances needs to pass N distinct non-zero seeds, which
  `kami.isekai.presets` already does), but undocumented and easy to trip
  over — now called out explicitly in `seeded-jitter`'s docstring and
  locked in as a test. `kbb -M:test` 41/41 (was 40/40).
- **Fixed `brainrot` producing the wrong direction of saturation for pale
  colours**: it's supposed to be the loud/saturated remix, but boosted
  each RGB channel around a fixed 0.5 midpoint — for a colour whose
  channels are already all >0.5 (elf/troll skin, both pale), every
  channel got pushed toward 1.0 and clamped together, actually *lowering*
  saturation vs. plain `watercolor` for exactly those two races. Never
  caught because the only test was `not=` (different from watercolor —
  true, just in the wrong direction). Found by actually computing max-min
  saturation per race instead of asserting inequality. Fixed by boosting
  each channel around the colour's OWN mean brightness instead of a fixed
  midpoint — verified numerically saturated for all 10 races now, not
  just the mid-tone ones that happened to already work. `kbb -M:test` 40/40
  (was 39/39), replacing the weak `not=` assertion with a real saturation
  comparison.
- **Fixed real drift, found via a documentation audit**: the README's
  `kbb -M:gen-presets` usage looked accurate, but `scripts/gen_presets.cljk`'s
  own hardcoded preset list was still the v1 set — missing everything
  added across a dozen rounds since (priest, kobold/troll races, ghost/
  wolf/elemental-slimes/wyvern/skeleton, castle/guild-hall/summoning-circle,
  kobold-adventurer/troll-king). network-isekai's separate deploy script
  had its own copy that I kept updating each round; this repo's own copy
  didn't exist as something I was in the habit of touching, so it silently
  fell behind. Root cause wasn't "forgot to update it" so much as "two
  independent copies of the same list is structurally guaranteed to
  drift" — fixed by extracting `kami.isekai.presets/presets` as the one
  place the list lives, consumed directly by both `kbb -M:gen-presets` and
  network-isekai's script (no more copies to fall out of sync). `kbb -M:test`
  39/39 (was 38/38).
- **Motion variety**: the catalog had only ever used 2 of the engine's 4
  `:anim` kinds (`:pulse`/`:sway` — confirmed `:bob`/`:rot` are real via
  `goriketsu/scene.edn`). Fixed the two clearest mismatches:
  `compose-ghost`'s body/head/eyes now `:bob` (float) instead of `:pulse`
  (breathe) — a monster with no legs is the one place "alive and
  breathing" is definitionally wrong. `compose-summoning-circle`'s 8 rune
  ticks now share one `:rot`/`:pivot [0 0]` so the whole ring turns as a
  unit — a static magic circle read as a diagram, not a spell in progress.
  Verified via headless capture (3-frame time-lapse, not just `kbb -M:test`) —
  the rune ring visibly rotates. `kbb -M:test` 38/38 (was 35/35), including a
  check that the catalog now covers all 4 anim kinds.
- **Closed the loop on the drift-detection audit** (3rd consecutive round
  checking for this bug class): `kami.isekai.catalog`'s `monster-ids`/
  `structure-ids` are hand-maintained sets mirroring the actual
  `compose-*` functions in `monsters`/`structures`/`tensei` — the same
  drift shape that bit `status.cljc` twice. Added a JVM-reflection test
  (`ns-publics`, `kbb -M:test` runs on the JVM even though the library itself
  stays `.cljc`-portable) that compares `catalog/monster-ids` and
  `structure-ids` against the actual defined functions. Unlike the last 2
  rounds, this one found *no* existing drift — both sets were already
  accurate — but it's now a permanent guard instead of a one-time manual
  check, so a forgotten catalog entry on the next new monster fails loudly.
- **Fixed data drift**: `kami.isekai.status`'s `race-modifiers`/
  `class-modifiers` are a separate map from `kami.isekai.races`/`classes`
  (mechanical tuning vs. visual data) and had silently drifted — `:troll`
  (added 2 rounds ago) and `:priest` (added last round) were never given
  stat modifiers, so they silently computed as unmodified base stats. Now
  fixed with real tuning (troll: tanky/slow; priest: high MP, low ATK) and
  `compute-stats` throws on an unknown race/class (same fix as
  `races/race`/`classes/class`). `kami.isekai.equipment/class->weapons` had
  the same drift risk in reverse — `:priest` was *correctly* bare-handed by
  omission, but an omitted key and an explicit `[]` no-op identically, so
  "forgotten" and "intentionally bare" were indistinguishable; made the
  entry explicit. Added completeness tests (map keys == the full catalog
  id set) for `status`, `equipment`, and `palette` so a future new race/
  class can't silently ship half-wired again.
- **Fixed a silent-fallback footgun**: `races/race` and `classes/class`
  used to default to `:human`/`:adventurer` on an unknown id instead of
  erroring — a typo (`:elve` for `:elf`) silently shipped a wrong-but-valid
  character with no signal. Both now throw `ex-info` with the full list of
  known ids; `compose-character` propagates the failure. Verified no
  internal caller relied on the fallback (only chargen called these two
  fns, and always with a literal valid keyword) before making the change.
- Added class `:priest` — the dedicated healer every isekai party has,
  distinct from the offensive `:mage`. Bare-handed by default (no entry in
  `equipment/class->weapons` — a priest's tool is holy magic, not a blade),
  a new `:holy-symbol` accessory (chest-height pulsing cross). Pairs
  thematically with `kami.isekai.skills/:holy-heal`.
- Added `kami.isekai.catalog` — one-stop introspection over every race/
  class/skill/monster/structure id (`known-race?` etc., `summary`), for a
  character-creator UI or a script that wants to validate an id before
  calling `compose-character` without importing every namespace.
- Monster variety, now that every named keyword from the original request
  has landed something (shifting from "close a gap" to "add depth"):
  - Added race `:troll` (large, stature 1.35) and `compose-troll` (bare-
    handed brute, reuses the humanoid plan like goblin/orc/skeleton).
  - Added `compose-ghost` — a new standalone ethereal plan (soft glow,
    translucent body, wavy trailing hem, no legs), the archetypal dungeon
    floater alongside slime/wolf's standalone plans.
  - Added named elemental slime variants: `compose-slime-fire`,
    `compose-slime-ice`, `compose-slime-poison` (every isekai slime dungeon
    has a colour per floor).
  - Coverage: 10 races × 7 classes, 13 monsters (was 9×7, 8).
- Added `kami.isekai.tensei` — the genre's namesake moment (異世界転生, the
  one original-request keyword that had zero representation through 4
  rounds of coverage work). `compose-summoning-circle` (ground prop,
  concentric rings + radial rune ticks) + `transition` (the arrival flash —
  kami.audio + kami :fx, same shape as a skills entry).
- Added `kami.isekai.status` — `compute-stats` derives HP/MP/ATK/DEF/SPD/LUK
  from race + class + level, deterministic. 能力/チート were represented
  visually (skills, cheat-aura) but not mechanically — a "status window"
  with numbers is core to the genre. `:cheat? true` applies an 8× multiplier
  (the OP-protagonist trope as numbers). Deliberately kept separate from
  `compose-character` — mechanical data, not auto-merged into the visual
  output, same as `kami.isekai.skills` is its own opt-in catalog.
- Added `kami.isekai.equipment` — weapon/held-item silhouettes (sword,
  dagger, staff, bow, shield, scepter). `compose-character` now applies
  each class's default loadout automatically (knight → sword+shield, mage →
  staff, adventurer → dagger, king → scepter; `:equip? false` opts out) —
  bare-handed characters read as unfinished, this was the biggest visible
  maturity gap in the v1 catalog. Monster composers that reuse a humanoid
  class for the silhouette but don't literally fit the loadout (dragon,
  wyvern) explicitly opt out.
- Added `kami.isekai.structures` — `compose-castle` (keep + flanking turrets
  + banner) and `compose-guild-hall` (adventurer's-guild storefront), the
  world-decoration props (お城/ギルド) that weren't covered by chargen's
  character-only composers. Same output shape ({:sprite ... :render/profile
  ... :tags ...}), optional palette-hue override.
- Added `kami.isekai.party` — `compose-party` arranges character specs into a
  1–5 slot front-line/back-line RPG formation; `starter-party` is the
  archetypal cheat-protagonist/knight/mage/rogue lineup.
- Added races: `:kobold`.
- Added monsters: `compose-kobold-scout`, `compose-wyvern` (lean, bare
  dragon-kin, no crown/cloak), `compose-skeleton` (undead recolour — bone/
  glow instead of the menacing red eyes), `compose-wolf` (standalone
  quadruped plan, pack monster).
- Added skills: `:wind-blade`, `:earth-spike`, `:teleport`, `:summon`.
- Coverage: 9 races × 7 classes, 8 monsters, 9 skills (was 8×7, 4, 5).

## v1 (2026-07-02)

Initial release — races (human/hume/elf/dwarf/orc/goblin/beastman/dragon-kin),
classes (adventurer/knight/mage/merchant/guild-master/king/princess),
monsters (slime/goblin-raider/orc-brute/dragon), skills (fireball/ice-lance/
holy-heal/curse/cheat-aura), watercolour Squaresoft-artisan default palette,
opt-in brainrot variant.
