# liquid-glass-ui — design

Layer-by-layer API reference. For the *why* see `docs/adr/0001-liquid-glass-ui.md`;
for the superproject-level decision see
`90-docs/adr/2607011900-kotoba-lang-liquid-glass-ui.md`.

## Layer 1 — `liquid-glass.tokens`

Token IR, same shape/merge semantics as `shitsuke.tokens` (group -> token ->
CSS-string value or nested map of CSS props), but with glass-specific groups:

```clojure
{:liquid-glass/surface     {<variant> {:blur ... :saturate ... :tint ... :border ...}}
 :liquid-glass/elevation   {<level>   {:shadow ...}}
 :liquid-glass/specular    {<part>    {...}}
 :liquid-glass/radius      {<size>    <css-length>}
 :liquid-glass/motion      {<phase>   {:duration ... :easing ...}}
 :liquid-glass/accent      {:tint ... :tint-strong ...}
 :liquid-glass/lens        {:frequency ... :scale ... :octaves ...}
 :liquid-glass/ink         {:default ... :shadow ... :on-accent ...}
 :liquid-glass/focus       {:ring-width ... :ring-offset ... :ring-color ...
                            :halo-width ... :halo-color ...}
 :liquid-glass/status      {:error ... :warning ... :success ... :info ...}}
```

- `default-tokens` — v1 **light-scheme** material. Three surface variants:
  `:clear` (barely-there — scrims/tooltips), `:regular` (default control
  surface), `:thick` (toolbars/sheets over busy content). Four elevation
  levels: `:flat` / `:raised` / `:overlay` / `:floating`. `:accent` is a
  translucent tint used for "on/checked/filled" states (toggle-on, checkbox/
  radio-checked, slider/progress fill) so those states still read as glass
  rather than a flat swatch (same value in light and dark — override it
  yourself if a themed consumer needs a different accent per scheme). `:ink`
  is the default text color + a soft counter-shadow for text sitting on the
  material (dark ink + a light shadow in the light scheme; light ink + a dark
  shadow in dark) — see the "Text legibility" note below.
  `:focus` is the keyboard focus ring (DADS-derived, see § Ported from the
  Digital Agency Design System) and `:status` the semantic ink for the
  required marker, field error text and `banner` accent.
- `dark-tokens` — a **partial** override map (`:surface` tint/border,
  `:specular` opacity, `:ink`, and `:status` — the entries that actually
  change when the content behind the glass goes dark; blur/saturate/radius/
  motion are scheme-independent and are simply not redeclared, and `:focus` is
  deliberately scheme-independent too — see § Keyboard focus for why).
- `deep-merge` — re-exported from `shitsuke.tokens` (same right-biased
  recursive merge; overrides compose identically across both token sets).
- `(resolve-tokens overrides)` / `(resolve-dark-tokens dark-overrides)` —
  default/dark tokens deep-merged with a partial override map.
- `(css-variables overrides?)` — `:root { --liquid-glass-<group>-<name>: ...; }`.
- `(dark-css-variables dark-overrides?)` — the same, wrapped in
  `@media (prefers-color-scheme: dark) { :root { ... } }`, **redeclaring the
  same custom-property names** (not `-dark`-suffixed variants) so components
  only ever reference one var per concept.

## Layer 2 — `liquid-glass.style`

Two-tier, same split as `shitsuke.style`:

- **Tier A** (`root-css`) — portable CSS custom properties: light `:root` +
  dark media-query override, from `liquid-glass.tokens`.
- **Tier B** (`component-css` / `component-rules`) — the actual glass
  material rules, scoped to `liquid-glass__<component>` classes. Generated
  from **EDN declaration data** via [`kotoba-lang/css`](https://github.com/kotoba-lang/css)
  (`css.core`) rather than hand-typed CSS strings — liquid-glass-ui is
  `css.core`'s first real consumer. `component-rules` returns the raw
  `[selector decls-map]` pairs; `component-css` renders them (plus the
  `@keyframes` map, the `@supports` fallback/upgrade blocks — no
  backdrop-filter, spring `linear()`, displacement lens — and, last so it
  out-cascades them all, the `@media (prefers-reduced-motion: reduce)`
  guard) to the CSS string via `css.core/css`. Unlike
  shitsuke (whose component visuals are deferred to a shadow-css `:pages`
  build that isn't wired up yet), liquid-glass-ui ships Tier B as a plain CSS
  string: no build step needed to see the material; the same string works
  inlined in SSR or concatenated into a browser build's `main.css`. Every
  declaration references `var(--liquid-glass-...)` only — never a literal
  color/blur value — so `root-css` overrides (including the dark-mode block)
  always apply.

  **Why data instead of strings**: two real bugs found while building this
  repo were exactly the "wrote a class, forgot the rule" shape — `panel--flat`'s
  shadow rule, and the `:specular :rim` tokens (defined, never referenced).
  Hand-typed CSS strings don't catch that; `component-rules` being actual
  data means a test can assert against it directly instead of regex-scraping
  rendered text — see e.g. `components-test/every-elevation-shadow-carries-both-rim-vars-test`,
  which walks every rule's `:box-shadow` and fails if an elevation shadow is
  ever added without the rim insets (this test caught a real instance: the
  `slider` thumb's vendor-prefixed pseudo-elements were hand-written outside
  the shared helper and had elevation but no rim, until fixed).

  Every glass surface gets the same three material ingredients plus a
  default text treatment, built by four private declaration-map helpers
  (`backdrop-decls`/`glass-bg-decls`/`glass-shadow-decls`/`ink-decls`)
  instead of ~15 hand-typed copies, so a component can't end up with only
  some of them:
  1. **backdrop-filter**: `blur` + `saturate` from its surface tier's tokens,
     plus a fixed `brightness(1.05)` lift — a flat blur reads as smudged
     glass, not lit glass.
  2. **specular overlay** (shared `::before`): a soft `radial-gradient`
     highlight anchored near the top-left, not a flat linear sheen — reads as
     a light source catching a curved surface.
  3. **rim light** (folded into every `box-shadow`, alongside the elevation
     shadow): a bright 1px inset line on the top edge, a much dimmer one on
     the bottom (the `:liquid-glass/specular :rim` token — asymmetric on
     purpose, light from above). This is the detail that turns a flat
     translucent rectangle into something that reads as an actual lit glass
     edge.
  4. **ink** (`color` + `text-shadow` from `:liquid-glass/ink`): applied on a
     broader selector list than the specular treatment (`ink-components` in
     `liquid-glass.style` — every top-level component root that can carry
     text, including `toggle`/`checkbox`/`radio`'s outer `<label>`, not just
     their inner glass box). `color`/`text-shadow` are inherited CSS
     properties, so setting them once here reaches every nested span
     (`checkbox-text`, `list-row-content`, …) without a rule per sub-element.
     **Text legibility**: this replaces the browser default of inheriting
     whatever ancestor color happened to be in scope — which is what
     silently produced illegible text before this token existed (a consumer
     had no way to know their page's own dark-on-light text would render as
     dark-on-translucent-dark inside a glass panel without duplicating a
     color override themselves). It does **not** attempt content-aware
     adaptive tinting (sampling what's actually behind the glass and picking
     a contrasting color) — that needs either JS or GPU compositing, is
     explicitly out of scope for a static CSS material (see "Future work"),
     and `ink` only follows the OS `prefers-color-scheme` signal, the same
     one that already drives the surface tint. A consumer whose own
     background genuinely conflicts with that (e.g. a light-scheme page with
     a deliberately dark hero photo behind a glass panel, as this repo's own
     `docs/index.html` showcase does against its colorful gradient) sets
     `color`/`text-shadow` on their own more-specific selector to override it,
     same as overriding any other CSS default.
- `(class-name component)` → `"liquid-glass__<component>"` (also accepts
  `"panel--thick"`-shaped modifier names).
- `(layered-css css?)` — the full bundle (`root-css` + `component-css`)
  wrapped in the `kotoba.glass` cascade layer, preceded by the
  `@layer kotoba.hig, kotoba.glass;` order declaration. **This is the string
  consumers inject** — see "Styling contract" below for the cascade
  guarantees. `root-css`/`component-css` stay public unwrapped for tests and
  pipelines that do their own layering.
- `(inline-style css?)` / `(inline-style-hiccup css?)` — `<style>` wrapper for
  SSR embedding (defaults to the layered bundle, `layered-css`).

## Layer 3 — `liquid-glass.components`

Pure-hiccup glass primitives (`.cljc`, no reagent import — same dual-render
contract as shitsuke). liquid-glass-ui owns **no** interaction/state logic:
components either wrap the matching `shitsuke.components` fn (keeping its
exact `act`/opts contract) or, where shitsuke has no equivalent, are a small
hiccup literal following the same `data-act` convention. Coverage targets the
practical subset of SwiftUI's control catalog a glass DOM/CSS skin can
actually express — see "Explicitly out of scope" below for what isn't here
and why.

**Structural / navigation**

| fn | based on | shape |
|---|---|---|
| `panel` | `shitsuke.components/card` | `(body opts?)` — `:surface` (`:clear`\|`:regular`\|`:thick`), `:elevation` (`:flat`\|`:raised`\|`:overlay`\|`:floating`) |
| `toolbar` | `shitsuke.components/toolbar` | `(actions opts?)` — floating action bar |
| `nav-bar` | — | `(title opts?)` — `:leading`/`:trailing` (hiccup), page-header bar |
| `tab-bar` | (shitsuke `mode-tabs` shape, reimplemented glass-only) | `(tabs current opts?)` — `tabs` = `[ [id label] … ]`; doubles as a SwiftUI `Picker(.segmented)` |
| `sheet` | — | `(body opts?)` — `:label`, bottom-anchored modal surface |
| `alert` | — | `(body opts?)` — `:label`, centered modal dialog (distinct from `sheet`) |
| `menu` | — | `(items opts?)` — `items` = `[{:label :act :disabled?} …]`, popover action list |
| `scrim` | — | `(opts?)` — full-viewport dismiss backdrop for `sheet`/`alert` |
| `list-view` / `list-row` | — | `(rows opts?)` / `(content opts?)` — `:surface`, row `:act`/`:trailing` |
| `disclosure` | — | `(summary body opts?)` — native `<details>`/`<summary>` (SwiftUI `DisclosureGroup`), no JS needed |

**Controls**

| fn | based on | shape |
|---|---|---|
| `button` / `icon-button` | `shitsuke.components/button` / `icon-button` | shitsuke opts (`:act`, `:disabled`, `:title`, `:type`, `:class`) plus the DADS-ported `:variant`, `:size`, `:href`, `:attrs` — see § Buttons |
| `text-field` / `text-area` | — (native `<input>`/`<textarea>` built directly; formerly `shitsuke.components/input`/`textarea`, see below) | `(opts wrap-opts?)` — full attr passthrough (`:value` `:placeholder` `:type` `:on-input`/`:on-change` `:on-key-down` `:disabled` `:aria-label` `:aria-describedby` `:maxLength` `:min` `:rows` `:act` ...); `:class` on the wrapper via wrap-opts |
| `search-field` | (text-field + leading glyph) | same opts as `text-field` |

> **Why text-field/text-area stopped delegating to shitsuke**: shitsuke's
> `input`/`textarea` emit `:value` + `:on-input`, but reagent's
> async-rendering-safe controlled-input path only engages for `:value` +
> `:on-change` — under reagent's rAF-batched rendering React restores the DOM
> to the stale rendered value after every keystroke, so typing faster than
> the app re-renders **loses every keystroke but the last** (found live in
> net-babiniku on every text field). The controls are now built directly:
> stable shape (`[:div.liquid-glass__<c> [:input attrs] specular]`, the
> control always at the same index), full attr passthrough, and a caller
> `:on-input` is attached as `:on-change` (same native `input` event, same
> per-keystroke `(.. e -target -value)` semantics — but reagent's fix
> engages). `:value` also rides as an attribute on `text-area` (shitsuke
> passed it as element content, which React only reads at mount — the
> textarea silently stopped following app state).
| `menu-select` | `shitsuke.components/select` | `(options opts?)` — same opts as shitsuke `select` |
| `toggle` | — | `(opts?)` — `:checked`, `:on-change`/`:act`, `:disabled` (native `<input type=checkbox>`, glass track+thumb sibling) |
| `checkbox` / `radio` | — | `(label? opts?)` — `radio` groups via `:group` (same-named native `name`) |
| `slider` | — | `(opts?)` — native `<input type=range>`, glass track+thumb via vendor pseudo-elements |
| `stepper` | built from `icon-button` | `(value opts?)` — `:dec-act`/`:inc-act` |
| `field` | DADS `form-control-label` | `(opts control)` — `:id` `:label` `:requirement` `:required?` `:status` `:support` `:error`; pair with `field-control-attrs` — see § Labelled fields |
| `field-control-attrs` | — | `(opts)` → the `:id`/`:aria-describedby`/`:aria-invalid`/`:aria-required` the control must carry |

**Feedback / content**

| fn | based on | shape |
|---|---|---|
| `banner` | DADS `notification-banner` | `(body opts?)` — `:type` (`:info`\|`:success`\|`:warning`\|`:error`), `:heading`/`:heading-level`, `:timestamp`, `:actions`, `:type-label`, `:attrs`; inline and non-blocking, unlike `alert` |
| `progress-bar` | — | `(value opts?)` — `:max` (default 100), determinate linear fill |
| `progress-circle` | — | `(opts?)` — indeterminate spinner |
| `gauge` | — | `(value opts?)` — `:max` (default 100), determinate ring (SwiftUI `Gauge`) via an inline conic-gradient |
| `badge` | — | `(label opts?)` — small pill counter |
| `chip` | — | `(label opts?)` — `:act`, `:on-remove-act` (dismiss ×) — filter/tag chip |
| `label` | — | `(icon text opts?)` — SwiftUI `Label`-shaped icon+text row |
| `avatar` | — | `(content opts?)` — `:src`/`:alt` for an image, else initials/hiccup |
| `divider` | — | `()` — hairline `<hr>` |
| `tooltip` | — | `(text opts?)` — positioning is the consumer's responsibility |

Every component whose top-level element *is* the glass surface (`panel`,
`button`, `toolbar`, `sheet`, `text-field`, `menu-select`, `nav-bar`, `alert`,
`menu`, `list-view`, `stepper`, `chip`, `disclosure`, …) appends a `liquid-glass__specular` marker
span as its last child (`display:none` by default — the static sheen is the CSS
`::before` overlay). The span is the stable hook the optional pointer-tracking
enhancement now targets (see "Motion & dynamic effects" § Pointer-tracking
specular); without that script it stays hidden, is not required for the static
visual, and removing/ignoring it changes nothing.
`lens-filter-defs` is the one non-control export: a 0×0 inline `<svg>`
carrying the `#liquid-glass-lens` displacement filter definition, emitted once
per page by consumers opting into the `.liquid-glass--lens` treatment. Compound controls whose glass surface
is a small *nested* box (`toggle`/`checkbox`/`radio` — the surface is the
track/box `<span>` inside a `<label>`) skip the marker span; see the
`liquid-glass.components` namespace docstring for why.

### Explicitly out of scope

Native-OS-only pickers that a CSS/DOM glass skin cannot meaningfully re-skin
without either losing platform-native affordances or requiring a JS calendar/
color-grid widget (real scope creep for a style layer, not a control layer):
`DatePicker`, `ColorPicker`. Also out: `OutlineGroup` (nested multi-level tree
disclosure — `disclosure` covers the single-level `DisclosureGroup` case; a
tree needs recursive state a "portable, zero deps" component can't own),
`ShareLink` (OS share-sheet integration, platform-specific). Positioning
logic for `menu`/`tooltip` (anchor-to-trigger, viewport-edge flipping) is
deliberately left to the consumer — it needs either JS or CSS
anchor-positioning, neither of which this repo's "portable `.cljc`, zero
deps" contract can own without picking a specific runtime.

## Ported from the Digital Agency Design System (DADS)

The material is ours; several of the *contracts around* it are not. They come
from the Japanese Digital Agency's design system, via this workspace's
[`kotoba-lang/jp-go-digital-design-system`](https://github.com/kotoba-lang/jp-go-digital-design-system)
port of it (MIT, © デジタル庁). DADS is a government design system whose job is
to be usable by everyone on anything, so it has already answered the questions
a visual skin tends to skip. Nothing below changes what the glass looks like —
the default variant and default size emit no class and no rule, so every
component written before this renders byte-identically.

See ADR [0004](adr/0004-dads-derived-component-maturity.md) for the decision
and the full provenance.

### Buttons — variant × size

| axis | values | DADS spelling |
|---|---|---|
| `:variant` | `:outline` (default, silent) · `:solid-fill` · `:text` | `data-type` |
| `:size` | `:lg` · `:md` (default, silent) · `:sm` · `:xs` | `data-size` |

`:solid-fill` tints the *same material* with the accent instead of replacing
it with an opaque swatch — a primary action still refracts what is behind it.
`:text` drops the surface entirely (no tint, no backdrop cost, no shadow),
because a tertiary action inside a glass panel should not stack a second sheet
of glass on the first.

**The size scale is the part that mattered.** `:sm` (36px) and `:xs` (28px)
paint a compact control but keep a full 44px *touch* target, via a transparent
`::after` centred on the button — DADS's technique, verbatim. Before it the
library had one size, and the only way to get a smaller button was for a
consumer to override `min-height`, which silently destroyed the tap target.
The two compact sizes are also the only ones that set `overflow: visible`: the
base rule clips to the border box, and a clipped `::after` receives no pointer
events, so the expander would have been inert.

> **Naming collision worth knowing about.** DADS spells the *variant* `type`;
> this library spells the *HTML type attribute* `:type` (inherited from
> shitsuke). Porting markup from jp-go-digital-design-system means
> `:type :outline` becomes `:variant :outline`.

`:href` renders an `<a>` instead of a `<button>`, built by retagging
shitsuke's hiccup so the class/`data-act`/`title` contract has one source. A
disabled link renders with **no `href` at all** — that, not an attribute, is
what makes it unactivatable and unfocusable — plus `role="link"` +
`aria-disabled="true"` so it is still announced as the disabled link it is.
`:attrs` is arbitrary attribute passthrough merged *under* the component's own
attrs, so it can annotate but never clobber (the contract `list-row` already
had).

The style layer covers `:disabled` **and** `[aria-disabled="true"]`, as DADS
does: pass `:attrs {:aria-disabled "true"}` instead of `:disabled` when a
disabled control must stay focusable and therefore discoverable by a screen
reader.

### Labelled fields

`field` + `field-control-attrs`, from DADS `form-control-label`. This library
shipped six form controls and no way to label any of them, so every consumer
hand-rolled a `<label>` and the support/error text — the part that has to be
*announced* — was routinely left unassociated: markup that reads as accessible
and is not.

```clojure
(let [f {:id "email" :label "Email" :requirement "Required" :required? true
         :support "We'll send a confirmation here."
         :error (when invalid? "That address isn't valid.")}]
  (field f (text-field (merge (field-control-attrs f)
                              {:value v :on-input on-input}))))
```

`field-control-attrs` derives `email-support` / `email-error` from `:id` and
returns the `:aria-describedby` (in reading order), `:aria-invalid` and
`:aria-required` the control has to carry. It stays a separate fn rather than
having `field` rewrite the control's hiccup: the controls nest their native
element (`text-field` is `[:div [:input] specular]`), so injection would mean
walking a tree and guessing which node is the control — brittle exactly where
being wrong is silent. Setting `:error` also renders `role="alert"` (so a
validation failure is announced when it appears) and flips `data-invalid` on
the wrapper, which colors the control's edge.

Two details taken from DADS because it documents getting them wrong:
`__requirement` is colored only when `:required?` is true (the *optional*
marker must not be red), and `:status` is a neutral state badge, **not** a
required marker.

### Keyboard focus — a two-tone ring on every interactive surface

Before this, the only `:focus-visible` rule in the entire stylesheet was the
toggle track. Buttons, tabs, menu items, list rows, chips, disclosure
summaries, sliders and select rendered focus as *nothing* — WCAG 2.4.7 Focus
Visible, level A.

> Worth stating for anyone measuring this library: the deterministic
> design-quality audit scored the showcase **100.00, converged** both before
> and after. Its focus axis is a regex for the string `:focus-visible`
> anywhere in the page source, and that one toggle rule satisfied it. A
> passing axis is not a passing component. The gate that actually holds this
> is `every-interactive-surface-has-a-focus-ring-test`, which asserts against
> the `focus-rules` **data** — an earlier version of that test grepped the
> rendered sheet and kept passing when the button's rule was deleted, because
> the selector also appears in the forced-colors block.

The ring is DADS's, numbers included: a 4px `#000000` outline at 2px offset
over a 2px `#ffd43d` halo, the two meeting with no gap. Two tones rather than
one because this material floats over *arbitrary* content — a single-color
ring is invisible whenever the backdrop matches it; black covers light
backdrops, yellow covers dark ones. That is also why `:liquid-glass/focus` is
deliberately **not** redeclared in `dark-tokens`: flipping the outline to
white in dark mode would make both tones light and lose the guarantee.

The halo is emitted as the first `box-shadow` layer *followed by the surface's
own elevation and rim*, because `box-shadow` replaces rather than composes — a
bare halo would delete the glass edge on focus, for exactly the users who need
the strongest visual anchor.

### `@media (hover: hover)` and cascade order

Every `:hover` rule is now behind a hover-capable-pointer query, as all of
DADS's are. A touchscreen has no way to send "pointer left", so an unguarded
`:hover` sticks until the next tap elsewhere: the glass button floats up
(translateY + brighter backdrop + overlay elevation) and stays there, reading
as a stuck or selected control — precisely wrong for a material whose whole
affordance is that it responds and settles.

This makes cascade order load-bearing, since all four slices have equal
specificity. `component-css` emits **base → `@media (hover: hover)` → press /
disabled → focus**, which is why `press-rules` is split out of `button-rules`:
if `:active` stayed before the hover block, hover would win while the pointer
is both hovering and pressing and the press morph would never be visible on a
mouse. `component-rules` returns all four concatenated in that order as the
data view; `hover-rules`, `press-rules`, `focus-rules` and `base-rules-data`
are public so a consumer doing its own rendering can preserve the order.

### `@media (forced-colors: active)`

This material is built almost entirely from things Windows High Contrast /
forced-colors mode either strips or cannot see: `backdrop-filter` is ignored,
`box-shadow` — the elevation *and* the rim edge light, i.e. the entire glass
edge — is forced to `none`, and `text-shadow` is dropped. What survives
untouched is the specular `::before`, a `mix-blend-mode: overlay` radial
gradient, a decoration that in this mode paints a light wash over content it
no longer sits behind. Unhandled, the result is controls with no edge under a
haze: the users who most need contrast got the least.

So the block drops the backdrop and the specular, hands the surface to the
system palette (`Canvas` / `ButtonBorder` / `ButtonText`, `Highlight` for
checked and filled state), and — the one that matters most — replaces
`opacity: .45` on disabled controls with `GrayText`. Opacity is *not* part of
the forced palette, so a dimmed-by-opacity control stays dimmed **and** gets
recolored, which is how disabled controls become unreadable rather than merely
quiet. DADS handles the same case the same way.

## Styling contract

A consumer emits `liquid-glass.style/layered-css` once per page/app (SSR
`<style>` via `inline-style`/`inline-style-hiccup`, or prepended into a
browser build's CSS output, mirroring `slides.build`'s handling of
`shitsuke.tokens/css-variables`). Components never carry inline visual style
— only stable classes + `var(...)` references, so overriding the material (a
themed consumer, a different surface tint) is a token-override problem, not a
component-code problem.

### Cascade layer: `@layer kotoba.hig, kotoba.glass`

All library CSS ships inside the **`kotoba.glass` cascade layer**, preceded
by the order declaration `@layer kotoba.hig, kotoba.glass;` (`kotoba.hig` is
shitsuke's base layer — declared here so the relative order is pinned when
both are on a page; harmless if unused). The contract:

- **App CSS stays unlayered — and therefore always wins.** Per the CSS
  cascade, unlayered author styles outrank all layered author styles
  regardless of source order or selector specificity. It no longer matters
  that this library's `<style>` is injected at runtime *after* the app's.
- **Apps must never write compound selectors against `liquid-glass__*` to
  win specificity fights anymore.** A plain `.liquid-glass__toolbar { ... }`
  (or the app's own class) in unlayered app CSS beats the library's layered
  rule outright — the ~100 lines of `.liquid-glass__toolbar.app-toolbar`-style
  compound overrides net-babiniku carried are exactly the pattern this
  retires.
- Within the bundle nothing changes: the internal cascade tricks
  (`@supports` upgrades, the trailing `prefers-reduced-motion` guard) keep
  their relative order inside the layer, and nested at-rules are valid inside
  `@layer`.
- `root-css`/`component-css` remain available unwrapped for tests, data-level
  assertions, and consumers with their own layer scheme — but injecting them
  raw re-opens the specificity war; prefer `layered-css`.

## Motion & dynamic effects

Four opt-in/progressive layers on top of the static material. Shared rules:
every duration/easing/offset/opacity is a `--liquid-glass-*` token (the CSS
stays EDN data through `css.core`; the only string-built pieces are the same
at-rule wrappers the file already used); every feature is either pure CSS or
degrades to the static material with no JS; and the
`prefers-reduced-motion: reduce` guard — emitted as the **last** block of
`component-css` so it out-cascades the equal-specificity `@supports`
upgrades — disables all of it.

### 1. Overlay enter/exit (`:liquid-glass/motion :overlay-enter` / `:overlay-exit`)

`scrim` fades in; `sheet`/`alert` fade + `translateY(12px)` + `scale(.98)` →
rest; `menu` fades + `scaleY(.9)` from `top center`; `tooltip` fades. Pure
CSS `@keyframes` applied on element *presence* — the enter animation runs on
insertion/first paint (SSR-friendly: a server-rendered overlay, a `<details>`
opening, a node appended by any framework — no mount hook needed). Offsets/
scales are tokens referenced *inside* the keyframes
(`--liquid-glass-motion-overlay-enter-distance`/`-scale`/`-scale-y`);
durations/easings ride the `animation` shorthand
(`enter` 300ms decelerate, `exit` 200ms accelerate). `alert`'s keyframes fold
the base centering `translate(-50%,-50%)` into every frame because an
animation's transform replaces the rule transform.

**Exit contract — `[data-state="closing"]`**: this library owns no open/close
state, so exit cannot be "run CSS when the node leaves" (there is no such CSS
trigger). Instead each overlay ships a matching exit rule on
`[data-state="closing"]` with `both` fill: the **caller** sets
`el.dataset.state = "closing"`, waits for `animationend`, then removes the
element. Removing it without the attribute is also fine — it just leaves
without the exit animation.

### 2. Spring settle + press morph (`:liquid-glass/motion :spring`, `:press :scale-x/:scale-y`)

`--liquid-glass-motion-spring-easing` carries a CSS `linear(...)`
approximation of a damped spring (one overshoot to ~1.12, settling to 1),
*generated* by the pure fn `liquid-glass.tokens/spring-linear-easing`
(ζ=0.55, ω=13, 16 evenly-spaced samples of the analytic under-damped step
response) rather than pasted as a magic literal. Structure: the default rules
keep the v1 `cubic-bezier` press/settle transitions; a
`@supports (transition-timing-function: linear(0, 1))` block upgrades the
transform settle of `button`/`icon-button` (release from press bounces past
rest), the `toggle` thumb slide, and the `disclosure` chevron flip. Press
morph: `:active` on buttons is now a squash —
`scaleX(var(--…-press-scale-x)) scaleY(var(--…-press-scale-y))`
(1.02/.95) instead of a flat `scale(.97)` — glass giving under a fingertip.

### 3. Pointer-tracking specular (optional JS, reference implementation)

The enhancement the `liquid-glass__specular` span was reserved for ("a
pointer/device-motion-driven highlight position" — Future work, below). This
repo does not ship the script as a library export — a JS runtime dependency
would break the "portable `.cljc`, zero deps" core, and the whole point of
the progressive-enhancement contract below is that a consumer can write (or
omit) their own — but `liquid-glass.demo/specular-script` (a `^:private` plain
string constant, `src/liquid_glass/demo.cljk`) is a working ~70-line
dependency-free reference implementation, inlined into the GitHub Pages
showcase the same way `inline-style` inlines the stylesheet. Copy it, or
write an equivalent against the same contract. It attaches **one**
document-level,
rAF-throttled `pointermove` listener; for the glass element under the pointer
(`closest(selector)` — the selector comes from the script tag's
`data-lg-selector` attribute, emitted by `liquid-glass.style/specular-selector`
so there is no hand-copied class list in JS, or is derived from the marker
spans in the document when absent) it writes `--liquid-glass-pointer-x`/`-y`
(0–1 relative to the element rect) and toggles `[data-lg-pointer]`.

CSS side: the script adds `.liquid-glass-js` to `<html>`, and only under that
class does the span become a `radial-gradient` highlight positioned at
`calc(var(--liquid-glass-pointer-x,.5)*100%)` /
`…-pointer-y…` (size/opacity are the `:liquid-glass/specular :pointer`
tokens, dimmed in dark scheme), `pointer-events:none`, transitioning only
`opacity`. Without the script **nothing** changes — the span keeps its
`display:none` default. Reduced motion is respected twice: the script refuses
to attach when `(prefers-reduced-motion: reduce)` matches, and the CSS guard
re-hides the highlight even if some other script added the class.

### 4. SVG displacement lens (`.liquid-glass--lens` + `lens-filter-defs`)

An optional refraction treatment: `(lens-filter-defs)` emits (once per page)
a 0×0 inline SVG `<filter id="liquid-glass-lens">` — `feTurbulence`
(`baseFrequency` = `:liquid-glass/lens :frequency`, 0.008) into
`feDisplacementMap` (`scale` = `:lens :scale`, 8px — a lens, not water). SVG
filter-primitive attributes cannot read CSS custom properties, so
`lens-filter-defs` resolves the tokens at hiccup-emit time (pass an override
map to retune); the same values are still emitted as `--liquid-glass-lens-*`
vars for documentation/override symmetry.

**Engine support, honestly**: `backdrop-filter: url(#…)` is the only way to
refract the *backdrop*, and it is not portable. Chromium applies it
(partially — compositing caveats, and it is not cheap, which is why the demo
applies the class to exactly one showcase panel); Safari does not (and
WebKit's `-webkit-backdrop-filter` ignores `url()`); Firefox does not. The
portable slice is therefore structured as: the base `.liquid-glass--lens`
rule is the plain regular-surface blur, and a
`@supports (backdrop-filter: url(#liquid-glass-lens))` block appends
`url(#liquid-glass-lens)` to the *full* blur+saturate+brightness chain — so
even an engine that parses `url()` but drops it at paint time (a case
`@supports` cannot detect) still renders the plain glass rather than losing
the backdrop. True cross-engine refraction remains the GPU path (Future
work).

## Future work (explicitly out of v1 scope)

- **Shadow-css `:pages` extraction** of Tier B as an alternative to the plain
  CSS string, once shitsuke's own component shadow-css wiring lands (today
  neither repo relies on it — see shitsuke ADR 2606301900's "negative"
  consequence).
- **True refraction / continuous-corner ("squircle") rendering** via a
  `liquid-glass.gpu` namespace on `kotoba-lang/webgpu`'s WGSL DSL, for
  canvas-rendered surfaces (`kami-engine`'s `kotoba.ui` HUD, `kobo`/`kuro`
  editor panes) where a real background-sampling distortion shader is
  possible and DOM `backdrop-filter` cannot express it. The `liquid-glass__specular`
  span and the `:liquid-glass/specular` token group are the seam this attaches
  to; the DOM/CSS half of that seam is now occupied by the pointer-tracking
  highlight (see "Motion & dynamic effects" §3, and §4 for the honest limits
  of `backdrop-filter: url()` displacement) — the GPU-composited refraction
  half stays future work until a concrete canvas-context consumer needs it.
- **Device-motion-driven specular** (tilt highlight via `deviceorientation`)
  — the CSS contract (`--liquid-glass-pointer-x/-y`) already supports it; a
  second tiny writer script is all it would take.
- **Manual light/dark override hook** (a `[data-lg-theme="dark"]` selector
  block alongside the `prefers-color-scheme` media query) for apps that need
  a user-facing theme toggle rather than following the OS setting — not added
  until a consumer needs it.
