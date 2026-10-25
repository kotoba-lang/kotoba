# shitsuke — design

This is the layer-by-layer API reference for `shitsuke`. For the *why* see
`docs/adr/0001-shitsuke-design-system.md`; for the superproject-level decision
see `90-docs/adr/<ts>-shitsuke-design-system.md`.

## Layer 1 — `shitsuke.tokens`

Token IR (web-CSS-oriented, forward-compatible with `office-style`'s `:style-ir`
and `slides.design`'s `:slides/theme`):

```clojure
{:shitsuke/colors     {<token> <css-color>}            ; "#496B9A" (with #)
 :shitsuke/type       {<token> {:font-family ... :font-size ... :font-weight ... :color ...}}
 :shitsuke/spacing    {<token> <css-length>}           ; "16px"
 :shitsuke/motion     {<token> {:duration ... :easing ...}}
 :shitsuke/breakpoints {<token> <px>}}
```

API:
- `default-tokens` — the v1 token set.
- `(deep-merge & maps)` — right-biased recursive merge (ported from `slides.design`).
- `(resolve-tokens overrides)` — `default-tokens` deep-merged with a partial override map.
- `(css-variables overrides?)` — emit `:root { --shitsuke-<group>-<name>: ...; }` CSS string.
  Nested maps (e.g. `:shitsuke/type`) expand to per-prop vars
  (`--shitsuke-type-title-font-size`).
- `(normalize-hex s)` — slides.design stores colors without `#`; this prepends `#` if absent.
- `(from-slides-design deck-design)` — adapter: build a shitsuke token-override map from a
  `slides.design` deck design (`:slides/theme` colors/fonts + `:slides/text-styles`).

## Layer — `shitsuke.hig`

Apple-HIG semantic token layer + base CSS. Additive to `shitsuke.tokens`
(v1 `--shitsuke-*` vars are untouched); only `tokens/deep-merge` is reused.

Token groups (one map, `default-hig-tokens`; `dark-hig-tokens` is the partial
dark override for color/palette):

```clojure
{:hig/font     {:text <stack> :display <stack> :mono <stack>}
 ;; the three font stacks as first-class tokens: --hig-font-text /
 ;; --hig-font-display / --hig-font-mono. Overriding a stack here re-fonts
 ;; every text style (and code/pre + .hig-mono) that references it.
 :hig/text     {<style> {:font-family ... :font-size ... :line-height ... :font-weight ...}}
 ;; the 11 Apple text styles: :large-title :title1 :title2 :title3 :headline
 ;; :body :callout :subheadline :footnote :caption1 :caption2,
 ;; PLUS the opt-in display scale above :large-title: :display3 :display2
 ;; :display1 (see "Display scale" below).
 ;; >= 20px use the SF Pro Display stack, < 20px the SF Pro Text stack;
 ;; per-style :font-family values are var(--hig-font-display) /
 ;; var(--hig-font-text) references into :hig/font (resolved values unchanged).
 :hig/color    {<token> <css-color>}   ; UIKit semantic colors (:label, :separator,
                                       ; :system-background, ..., :tint = accent/theme
                                       ; override point)
 :hig/palette  {<token> <css-color>}   ; system palette (:red ... :gray6)
 :hig/spacing  {:1 "4px" ... :10 "64px" :content-margin "16px"}  ; 4pt grid
 :hig/radius   {:xs "6px" :sm "10px" :md "14px" :lg "20px" :xl "28px" :capsule "999px"}
 :hig/hairline "0.5px"}
```

Var naming: `--hig-<group>-<token>` (`--hig-font-mono`, `--hig-color-label`,
`--hig-radius-md`, `--hig-spacing-content-margin`, `--hig-hairline`); nested
text styles expand per-prop (`--hig-text-body-font-size`).

### Display scale — `:display1/2/3` (fluid, opt-in)

Hero/marketing sizes above `:large-title` — the web analogue of the larger
display styles some Apple platforms add (visionOS/tvOS extra-large titles).
Source data is `display-text-styles` (order: `display-style-order`, largest
first), merged into `:hig/text`; all three are weight 700 on the display
stack with **fluid** `clamp()` font sizes, so apps never hand-write viewport
math for hero type:

| style       | font-size                        | at max | line-height       | letter-spacing |
|-------------|----------------------------------|--------|-------------------|----------------|
| `:display3` | `clamp(40px, 5vw + 8px, 64px)`   | 64px   | `calc(1em + 4px)` | `-0.02em`      |
| `:display2` | `clamp(30px, 3.75vw + 6px, 48px)`| 48px   | `calc(1em + 4px)` | `-0.015em`     |
| `:display1` | `clamp(25px, 3.125vw + 5px, 40px)`| 40px  | `calc(1em + 4px)` | `-0.01em`      |

Fluid formula (max size `M`): `clamp(5M/8, (5M/64)vw + M/8, M)` — min is
62.5% of max, ramping linearly from min at a 640px viewport to max at 1120px.
Line-height `calc(1em + 4px)` tracks the fluid size and equals the design
pairs at max (64/68, 48/52, 40/44). Values are pure data (plain CSS strings
in the token map), emitted as `--hig-text-display3-*` etc.

Opt-in only: `base-css` keeps `h1` at `:large-title`; use `.hig-display1/2/3`
utility classes (or the vars) explicitly for hero/marketing type.

API:
- `semantic-colors` / `system-palette` — token → `{:light <css> :dark <css>}` source data.
- `(resolve-hig-tokens overrides?)` / `(resolve-dark-hig-tokens overrides?)` — deep-merged token maps.
- `(css-variables overrides?)` — `:root { --hig-...: ...; }` (light).
- `(dark-css-variables overrides? dark-overrides?)` — dark vars three ways:
  `@media (prefers-color-scheme: dark)` + `:root[data-appearance="dark"]`
  (page forces dark via attribute) + `:root[data-appearance="light"]`
  (light reset, so forced light out-specifies the dark media query).
- `layer-order-css` — `"@layer kotoba.hig, kotoba.glass;"`.
- `(base-css overrides?)` — element defaults (body/h1–h4/p/small/code/a/hr/
  `::selection`/`:focus-visible`/reduced-motion) in `@layer kotoba.hig`;
  code/pre consume `var(--hig-font-mono)` (no inlined stack).
- `text-style-classes` — `.hig-display3` … `.hig-display1` (fluid display
  scale) and `.hig-large-title` … `.hig-caption2` utilities plus `.hig-mono`
  (mono stack + footnote size, the code/pre typography treatment), also
  layered.
- `(hig-css overrides? dark-overrides?)` — the full bundle in order:
  layer order → vars → dark vars → base CSS → text-style classes.
- `(inline-style css?)` / `(inline-style-hiccup css?)` — `<style>` string /
  `[:style [:hiccup/raw css]]` (mirrors `shitsuke.style`).

Cascade-layer contract: `kotoba.hig` (this base) < `kotoba.glass`
(liquid-glass-ui's material layer) < **unlayered app CSS** — an app never has
to fight the design system's specificity; its own rules always win. Forced
appearance: set `data-appearance="dark"` / `"light"` on the root element to
override the OS `prefers-color-scheme` preference (`color-scheme` follows the
attribute too).

## Layer 2 — `shitsuke.hiccup`

Dependency-free hiccup → HTML string renderer (`.cljc`, babashka-safe). The SSR
twin of the reagent view contract.

- `(esc s)` — escape `& < > "`.
- `(->html node)` — render a hiccup node (or seq of nodes) to an HTML string.

Supported: `[:tag attrs? & children]`, `:div.a.b#id` tag sugar, `:class` as
string/vec, boolean attrs (`true` → bare, `false` → dropped), strings (escaped),
numbers, nil (skipped), seqs (flattened), `[:hiccup/raw "<svg/>"]` (trusted, not
escaped). Void tags (`img`/`input`/`br`/…) emit no closing tag.

**`<textarea>` special case:** a `:value` attribute on `:textarea` renders as
*escaped element content* and no `value=` attribute is emitted
(`[:textarea {:value "a<b"}]` → `<textarea>a&lt;b</textarea>`). Real HTML has
no value attribute on textarea; the live (reagent/React) side of the
dual-render contract needs `:value` as an attribute (value-as-child is read
only at mount), so the SSR twin translates — pre-filled SSR textareas keep
working from the same hiccup data.

## Layer 3 — `shitsuke.style`

- `(class-name component)` → `"shitsuke__<component>"` (stable scoped class; the
  shadow-css extraction anchor and the hiccup `:class`).
- `(root-css overrides?)` → `:root{...}` CSS string from tokens.
- `(inline-style css?)` → `<style>…</style>` string for SSR embedding.
- `(inline-style-hiccup css?)` → `[:style [:hiccup/raw css]]` (raw so CSS survives
  `->html` unescaped).

## Layer 4 — `shitsuke.re-frame` / `.core`

`shitsuke.re-frame` — the mini runtime (7 functions, mirrors `wasm-ui`'s
`kotoba.wasm.re-frame`): `app-db`, `clear!`, `reg-event-db`, `reg-sub`,
`dispatch`, `dispatch-sync`, `subscribe`. `subscribe` returns an `IDeref` whose
`deref` recomputes synchronously against `app-db` (no reaction graph).

`shitsuke.re-frame.core` — the host seam. App code requires
`[shitsuke.re-frame.core :as rf]` (NOT `re-frame.core` directly):
- `:cljs` → real `re-frame 1.4.3` (`reg-event-db`/`reg-sub` via referred macros;
  `dispatch`/`dispatch-sync`/`subscribe`/`clear!`/`app-db` via re-exported vars).
- `:clj` → the mini runtime.

**Portable subset (app code MUST stay within):** `reg-event-db`, `reg-sub`,
`dispatch`, `dispatch-sync`, `subscribe`, `clear!`, `app-db`. MUST NOT use:
`reg-event-fx`, `reg-fx`, `reg-cofx`, `inject-cofx`, interceptors, subscription
chaining (`<-`). Pinned by `test/shitsuke/re_frame_test.cljk`.

## Layer 5 — `shitsuke.reagent.core`

Host seam for the view layer. Views are pure hiccup data (no reagent import).
- `:cljs` → real `reagent 1.2.0` (`as-element`, `rdom/render`).
- `:clj` → `shitsuke.hiccup/->html` (`as-element` is identity; `render` returns the string).

`(render hic)` mounts (cljs) / serialises (clj) the hiccup.

## Layer 6 — `shitsuke.components`

Pure-hiccup primitives returning `[:tag {:class "shitsuke__<component>" …} …]`:

| fn | shape |
|---|---|
| `button` / `icon-button` | `(label opts?)` — `:act`, `:disabled`, `:title`, `:type` |
| `field` | `(label-text control opts?)` — label + control row |
| `input` | `(opts)` — `:id`, `:value`, `:placeholder`, `:type`, `:on-input`/`:on-change`, `:act`, `:class`, + full attr passthrough |
| `textarea` | `(opts)` — same as `input` plus `:rows` (default 6, no `:type`) |
| `select` | `(options opts)` — `options` = `[ [value label] … ]`, `:value`, `:on-change`, `:act` |
| `card` | `(body opts?)` — `:class`, `:id` |
| `toolbar` | `(actions opts?)` — horizontal action row |
| `mode-tabs` | `(tabs current opts?)` — `tabs` = `[ [id label] … ]` |
| `thumb` | `(body active? opts?)` — `:act` |
| `pane` | `(hidden? body)` — visibility-toggled pane |

`act` is the portable interaction attribute (a keyword). On cljs the caller
wraps it into `:on-click #(rf/dispatch [act …])`; on SSR the caller emits
`data-act="<act>"` and a thin enhancer dispatches on click (mangaka
`wire-lang-switch!` pattern).

**Controlled-input `:on-change` contract (`input`/`textarea`):** the caller
API accepts `:on-input`, but the emitted hiccup carries the handler as
`:on-change`. React's `onChange` on text controls fires on the native `input`
event — identical per-keystroke semantics — and the rename is what engages
reagent's async-rendering-safe controlled-input path
(`reagent.impl.input/input-render-setup`), which only activates for
`value` + `onChange`. With `:value` + `:on-input`, reagent's rAF-batched
rendering makes React restore the DOM to the stale last-rendered value after
every input event, losing all but the last keystroke at normal typing speed
(root-caused downstream in liquid-glass-ui PR #3 / net-babiniku, reagent
1.2.0 + React 18). An explicit caller `:on-change` always wins; when both are
given, `:on-input` is kept as-is alongside. `textarea` passes `:value` as an
*attribute* (value-as-child is read by React only at mount, after which the
field silently stops following app state); `shitsuke.hiccup/->html` translates
it back to element content for SSR (see Layer 2). Both controls pass all
other caller attrs through untouched (`:disabled`, `:aria-*`, `:maxLength`,
`:on-key-down`, …) and return pure data — equal opts give `=` hiccup.

## Styling contract (shadow-css :pages build)

A consumer's `:pages` build (e.g. `slides.build`) adds `shitsuke.components` to
`shadow.css.build`'s `:include` so the `(css …)` markers materialise scoped
rules for `shitsuke__*` classes. `:root` vars come from
`shitsuke.style/root-css` (Tier A, portable). Components never carry inline
visual CSS — only stable class names + `var(--shitsuke-…)` references.
