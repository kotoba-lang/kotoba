# kotoba-ui

`kotoba-ui` is the **default UI/UX design single require point** for
kotoba-lang frontends: `kotoba-ui.core` requires
[`shitsuke`](../shitsuke) (structure/dual-render contract) and
[`liquid-glass-ui`](../liquid-glass-ui) (Apple-Liquid-Glass-style material
skin) and re-exports their public API as one namespace. A product repo that
requires only `kotoba-ui.core` gets structure + material + all 29 glass
components in one `require`.

On top of the aliases, `kotoba-ui` owns the two layers the stack was missing
(consumers used to hand-write 400+ lines of ad-hoc page CSS without them):

- **`kotoba-ui.shell`** — pure-hiccup HIG layout scaffolds (`app-shell`,
  `hero`, `section`, `grid`, `stack`, `spacer`, `page`) whose structural CSS
  lives inside `@layer kotoba.hig` and references only `--hig-*` tokens.
  Every scaffold's opts map also accepts `:id` / `:class` (string or
  vector, merged with the shell class) / `:attrs` (any other attribute
  map: data-*, aria-*, role, ...) on its root element — pass these instead
  of mirroring shell CSS in app CSS when you need a JS/CSS hook.
- **`kotoba-ui.theme`** — one theme map (`{:accent "#RRGGBB"
  :appearance :auto|:light|:dark ...}`) as the *only* styling entry;
  `theme-css` emits the complete page CSS (HIG + glass + shell, cascade
  layers in canonical order).
- **`kotoba-ui.core/->page`** — the one-call SSR entry: doctype + full
  document (meta, title, theme CSS, `data-appearance`) from hiccup.

**Before building any frontend on this stack, read
[`docs/agent-guide.md`](docs/agent-guide.md)** — the paved-road recipe
(stack diagram, the 8 non-negotiable rules, a complete worked example, and
a do/don't table distilled from real production failures).

Everything else in `kotoba-ui.core` is a direct alias
(`(def button liquid-glass.components/button)`, …) of a shitsuke or
liquid-glass var — a thin composition layer, not a new design system: see
`docs/adr/0001-kotoba-ui.md` and the superproject decision
`90-docs/adr/2607022800-kotoba-lang-default-uiux-appkit-uikit-interface-fundamentals.md`.

## Not to be confused with `orgs/kotoba-lang/ui`

`orgs/kotoba-lang/ui` (package `kotoba.ui`) is a **pre-existing, unrelated**
repo: kami-engine's WebGPU game-canvas HUD overlay renderer (EDN spec → DOM
overlay, browser-only ClojureScript). It predates this repo, has its own
CI-green test suite, and is not touched or reused by `kotoba-ui`. The name
similarity is coincidental — `kotoba-ui` (this repo) is the default *design
system* entry point; `ui` (that repo) is a *game HUD* renderer.

## Usage

```clojure
(require '[kotoba-ui.core :as ui])

;; a complete refined page in one call — layout from shell, styling from
;; one theme map (see docs/agent-guide.md for the full worked example):
(ui/->page {:title "App" :theme {:accent "#FF3CAC" :appearance :dark}}
           (ui/app-shell {:nav (ui/nav-bar "App")}
                         (ui/hero {:title "Hello" :tagline "One call."
                                   :actions [(ui/button "Go" {:act :go})]})
                         (ui/section {:title "Cards"}
                                     (ui/grid (ui/panel [[:p "a"]])
                                              (ui/panel [[:p "b"]])))))

;; or piecemeal:
(def view
  (ui/panel [(ui/toolbar [(ui/icon-button "☰") (ui/badge "3")])
             (ui/tab-bar [[:visual "Visual"] [:edn "EDN"]] :visual)]
            {:surface :thick :elevation :floating}))

(ui/->html view)                 ; SSR fragment
;; once per page/app: (ui/theme-css {...}) — layer order + HIG vars/base +
;; glass material + shell structure (or (ui/inline-style) for glass only)
```

## Design

See `docs/design.md` for the Apple *Interface fundamentals* taxonomy this
repo's docs (and, downstream, `appkit`/`uikit`) are organized around, and
`docs/adr/0001-kotoba-ui.md` for the per-repo design record. Component-level
API detail lives in `liquid-glass-ui/docs/design.md` — `kotoba-ui.core` does
not duplicate it, only re-exports it.

## `.kotoba` form-A port (ADR-2607270100 §10)

`kotoba/theme_core.kotoba` ports the pure string core this composition layer
owns: `hex->rgba` (accent → glass rgba), accent CSS-var declaration lines,
cascade layer-order/wrap, shell class-name and layout constants. Full
`theme-css` composition (joining shitsuke + liquid-glass + shell host
outputs) stays on the `.cljc` side. Consumer APIs are unchanged — oracle-backed
experiment ahead of W4, not the final API. Byte-equality is gated by
`test/kotoba_ui/kotoba_parity_test.cljk` (compiler is test-only).

## Tests

```bash
kbb -M:test            # published git shitsuke + liquid-glass-ui deps
kbb -M:local:test      # local ../shitsuke + ../liquid-glass-ui overrides
```

`:test` includes a **design-quality self-scoring gate**
(`test/kotoba_ui/design_quality_gate_test.cljk`): representative pages are
rendered with `->page` and scored against
[kotoba-lang/design-quality](https://github.com/kotoba-lang/design-quality)'s
deterministic HIG/WCAG audit (ADR-2607132300 — an unmeasured metric is
theater); the suite fails if the output regresses below the measured floor.
It needs a `../design-quality` sibling checkout (CI clones it alongside
shitsuke / liquid-glass-ui). See `docs/agent-guide.md` §4 for scoring your
own app's pages.
