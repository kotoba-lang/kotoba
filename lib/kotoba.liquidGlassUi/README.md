# liquid-glass-ui

`liquid-glass-ui` is the kotoba-lang shared **"liquid glass" visual skin**: a
translucent, specular-highlighted, blur+saturate material (in the spirit of
Apple's Liquid Glass / iOS 26 design language) built as a thin layer **on top
of [`shitsuke`](../shitsuke)**, kotoba-lang's UI design system (tokens +
hiccup + style + portable re-frame seam + component primitives), with its
Tier B CSS generated as EDN data via [`kotoba-lang/css`](../css) (`css.core`)
rather than hand-typed CSS strings.

liquid-glass-ui does not reimplement interaction, state, or the dual-render
contract — shitsuke already owns that. It owns exactly one thing: **the glass
material** — as its own token group, its own two-tier style layer (built from
`css.core` EDN rule data, not string concatenation), and a set of pure-hiccup
components that wrap (or, where no shitsuke equivalent exists, extend)
`shitsuke.components` with glass classes and a specular-highlight decoration.

```text
liquid-glass-ui = material tokens (blur/saturate/tint/elevation/specular/radius/motion/
                                    accent/ink/focus/status)
                  + style (css.core EDN rules -> CSS vars + component-css, portable, no build step)
                  + 31 components: panel/toolbar/nav-bar/tab-bar/sheet/alert/menu/scrim/list/disclosure
                    + button/icon-button/text-field/text-area/search-field/menu-select/
                      toggle/checkbox/radio/slider/stepper/field
                    + banner/progress-bar/progress-circle/gauge/badge/chip/label/avatar/divider/tooltip
                  on top of shitsuke (tokens/hiccup/style/re-frame/components)
                  + kotoba-lang/css (css.core — EDN-to-CSS rule generation)
```

Component coverage targets the practical subset of SwiftUI's control catalog
a glass DOM/CSS skin can actually express — see `docs/design.md` for the full
per-component table and what's explicitly out of scope (DatePicker/ColorPicker
and friends — native-OS-only widgets a CSS skin can't meaningfully re-skin).

The *contracts around* the material — button variant × size, the keyboard
focus ring, labelled fields, the inline status banner, pointer-gated hover and
the forced-colors fallback — are ported from the Japanese Digital Agency
Design System (DADS) via this workspace's
[`kotoba-lang/jp-go-digital-design-system`](https://github.com/kotoba-lang/jp-go-digital-design-system),
with DADS's numbers kept verbatim (4px/2px/2px focus ring, 44px hit target,
semantic colors). **The material itself is unchanged**: the default variant
and default size emit no class and no rule, so every component written before
this renders byte-identically. See `docs/design.md` § "Ported from the Digital
Agency Design System" and `docs/adr/0004-dads-derived-component-maturity.md`.

Beyond the static material, four opt-in/progressive motion & dynamic-effect
layers (all pure CSS or degrade to the static material with no JS, all
disabled under `prefers-reduced-motion: reduce`): overlay enter/exit
animations (`scrim`/`sheet`/`alert`/`menu`/`tooltip`, plus a
`[data-state="closing"]` exit contract the caller drives), a generated
damped-spring `linear()` settle + squash press-morph
(`liquid-glass.tokens/spring-linear-easing`, upgrading past the baseline
`cubic-bezier` under `@supports`), an optional pointer-tracking specular
highlight (CSS contract + a reference JS enhancer, not a library dependency),
and an SVG `feTurbulence`+`feDisplacementMap` displacement lens
(`lens-filter-defs` + `.liquid-glass--lens`, upgrading under
`@supports (backdrop-filter: url(...))` where the engine actually composites
it). See `docs/design.md` § "Motion & dynamic effects" for the full
per-layer breakdown and honest engine-support notes.

## Boundaries

| layer | role |
|---|---|
| `liquid-glass.tokens` | material token IR (`:liquid-glass/surface` `:elevation` `:specular` `:radius` `:motion` `:accent` `:ink` `:focus` `:status`) + light/dark resolver + `:root` / `@media (prefers-color-scheme: dark)` CSS-var emitter |
| `liquid-glass.style` | `class-name` registry (`liquid-glass__<component>`) + `root-css` (Tier A vars) + `component-rules` (Tier B as EDN `[selector decls]` data; `base-rules-data` / `hover-rules` / `press-rules` / `focus-rules` are the ordered slices) + `component-css` (rendered via `css.core/css` — backdrop-filter+brightness, radial specular overlay, top/bottom rim edge light, default ink text color+shadow, elevation shadow, press motion, pointer-gated hover, two-tone focus ring, reduced-motion + no-backdrop-filter + forced-colors fallbacks) + `layered-css` (the bundle wrapped in the `kotoba.glass` cascade layer — what consumers inject) |
| `liquid-glass.components` | 31 pure-hiccup glass primitives (+ the `field-control-attrs` helper) — see `docs/design.md` for the full table |
| shitsuke (dep) | dual-render contract, `act` interaction convention, `button`/`icon-button`/`toolbar`/`card`/`select` primitives that liquid-glass-ui wraps (`text-field`/`text-area`/`search-field` build their native controls directly — see `docs/design.md` § Controls for the reagent keystroke-loss bug that forced this) |
| `kotoba-lang/css` (dep) | `css.core` — CSS as EDN data (`declarations`/`rule`/`media`/`keyframes`/`css`); liquid-glass-ui is its first real consumer |

## Why a separate repo instead of adding it to shitsuke

`shitsuke` is host-shape (tokens/hiccup/style/state) and intentionally has no
opinion on *what a component looks like* beyond a stable class-name hook.
`liquid-glass-ui` is one visual skin among others a kotoba-lang frontend might
choose (a plain/flat skin, an OS-native skin, etc.) — it belongs in its own
repo so a consumer that wants shitsuke's structure without the glass look
(or a future alternative skin) doesn't pull in glass-specific tokens/CSS. See
`docs/adr/0001-liquid-glass-ui.md`.

## Usage

```clojure
(require '[liquid-glass.style :as ls]
         '[liquid-glass.components :as lg]
         '[shitsuke.hiccup :as h])

;; once per page/app: emit the material CSS (SSR <style> or prepend to main.css).
;; The zero-arity embeds (ls/layered-css) — everything inside @layer kotoba.glass.
(ls/inline-style)

;; pure hiccup, same dual-render contract as shitsuke
(def view
  (lg/panel
   [(lg/toolbar [(lg/icon-button "☰") (lg/badge "3")])
    (lg/tab-bar [[:visual "Visual"] [:edn "EDN"]] :visual)]
   {:surface :thick :elevation :floating}))

(h/->html view)   ; SSR (clj/babashka)
;; browser: the same `view` is returned by a reagent component and mounted via
;; shitsuke.reagent.core/render; state via shitsuke.re-frame.core (unchanged
;; from shitsuke — liquid-glass-ui does not touch the state layer).
```

## Cascade contract (`@layer kotoba.hig, kotoba.glass`)

All library CSS is delivered inside the **`kotoba.glass` cascade layer**
(`liquid-glass.style/layered-css`, the default payload of
`inline-style`/`inline-style-hiccup`), with the order pinned as
`@layer kotoba.hig, kotoba.glass;` (`kotoba.hig` is shitsuke's base layer;
declaring it is harmless if unused). Because unlayered author CSS always
outranks layered author CSS, **your app's own stylesheet wins over this
library's rules regardless of injection order or selector specificity** —
keep app CSS unlayered and override the material with plain selectors.
Never write compound selectors against `liquid-glass__*` classes
(`.liquid-glass__toolbar.app-toolbar { ... }`) to win specificity fights —
that pattern is obsolete. Raw `root-css`/`component-css` remain available
unwrapped for tests and custom layering pipelines. See
`docs/design.md` § "Styling contract".

## `.kotoba` form-A port (ADR-2607270100 §10)

`kotoba/tokens_core.kotoba` ports the pure token → CSS-string pipeline
(`--liquid-glass-*` emission, light `:root` + dark `@media` redeclare).

`kotoba/style_core.kotoba` ports the string-producing core of `style.cljc`:
the class/selector builders (`class-name`, `btn-sel`), every glass-material
declaration **value** (backdrop chain, tint, border, elevation + rim
`box-shadow`, focus halo/ring, transitions, specular gradients, keyframe
transforms, overlay animation shorthands) and the four whole functions whose
entire output is a fixed-shape string (`lens-supports-css`,
`spring-supports-css`, `layered-css`, `inline-style`).

Still `.cljc`: component hiccup wrappers; `spring-linear-easing` (f64 Math);
the `*-rules` vectors and `sel` (collection folds past
`max-heterogeneous-vector-items`); and `component-css` / `base-rules-data` /
`component-rules`, which render through `css.core` — that renderer has its
own `.kotoba` port in kotoba-lang/css, but linking the two needs cross-repo
project linking that does not exist yet.

Consumer APIs are unchanged — this is an oracle-backed experiment ahead of
W4 recursive values, not the final API. Byte-equality is gated by
`test/liquid_glass/kotoba_parity_test.cljk` and
`test/liquid_glass/kotoba_style_parity_test.cljk` (compiler is test-only).

## Tests

```bash
kbb -M:test            # published git shitsuke + css deps
kbb -M:local:test      # local ../shitsuke + ../css overrides
```

## Design

See `docs/design.md` for the token/style/component API,
`docs/adr/0001-liquid-glass-ui.md` for the original decision record,
`docs/adr/0002-css-core-migration-and-ink-token.md` for the `css.core`
migration + `:ink` token addition, and
`docs/adr/0003-motion-and-dynamic-effects.md` for the overlay-motion/spring/
pointer-specular/displacement-lens layer, and
`docs/adr/0004-dads-derived-component-maturity.md` for the DADS-derived
button/focus/field/banner/forced-colors work (including why the deterministic
design-quality audit scored 100.00 both before and after it). Superproject-level decision:
`90-docs/adr/2607011900-kotoba-lang-liquid-glass-ui.md`.
