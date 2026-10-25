# appkit

`appkit` is the **desktop / dense-data platform binding** on top of
[`kotoba-ui`](../kotoba-ui), part of kotoba-lang's default UI/UX design
(`90-docs/adr/2607022800-kotoba-lang-default-uiux-appkit-uikit-interface-fundamentals.md`).
Mirrors Apple's AppKit role against SwiftUI (`kotoba-ui.core` plays the
SwiftUI-equivalent role here): screen-shape-specific *defaults*, not a new
component catalog.

## What it actually wraps

Of `kotoba-ui.core`'s 32 components, only `panel` (`:surface`/`:elevation`)
and `list-view` (`:surface`) take an opt that varies by screen shape in
liquid-glass-ui v1 — everything else (`toolbar`/`nav-bar`/`sheet`/`alert`/
`button`/…) has a fixed glass look with nothing to differentiate, so `appkit`
wraps only those two and leaves the rest to be called on `kotoba-ui.core`
directly.

| fn | default opts | rationale |
|---|---|---|
| `panel` | `{:surface :thick :elevation :flat}` | desktop panes read as flush/embedded, legible over dense content, no shadow since panes sit side-by-side rather than stacked |
| `list-view` | `{:surface :thick}` | same legibility rationale as panel |

Caller-supplied opts always win (`merge default opts`), same contract as
every liquid-glass-ui component wrap.

## Quickstart

New here? [`docs/operator-quickstart.md`](docs/operator-quickstart.md) goes
from a clean checkout to a rendered page you can open, and shows appkit's
whole contract — defaults applied, caller opts still winning —
in the markup of that page.

## Usage

```clojure
(require '[kotoba-ui.core :as ui]
         '[appkit.core :as app])

(app/panel [(ui/toolbar [(ui/icon-button "☰")])
            (app/list-view [(ui/list-row "Row 1") (ui/list-row "Row 2")])])
```

## Target consumers (provisional, see superproject ADR)

kotoba EDA flow workbench, slides editor, itonami.cloud cockpit,
kotobase.net console — dense/desktop-first product surfaces.

## Tests

```bash
kbb -M:test                               # JVM
kbb -M:local:test                         # local ../kotoba-ui override
kbb --backend sci test/appkit/cljs_runner.cljk              # the same suite on cljs (nbb)
kbb --backend sci test/appkit/cljs_runner.cljk :local:test  # …with the local override
```

appkit is `.cljc` and its consumers are browsers, so the suite runs on both.
The cljs runner loads the same `appkit.core-test` under `cljs.test` on the
classpath `kbb -Spath` resolves (no hand-written sibling list); the three
`#?(:clj …)` tests (the variance-point sweep, the public-var census, the
`with-redefs` probe) exist only on the JVM side, so its count is smaller on
purpose. A JVM-only regression — a `#?(:clj …)` around a wrapper, a
`clojure.java.*` require, a reader conditional whose `:cljs` branch drifts —
keeps `kbb -M:test` green and is caught only here.

## Building an app? Read the agent guide first

The canonical paved-road recipe for building refined, Apple-HIG-quality pages
with this stack (HIG semantic tokens via `shitsuke.hig`, the
`@layer kotoba.hig, kotoba.glass` cascade contract — unlayered app CSS always
wins, `kotoba-ui.shell` layout scaffolds, single theme map, `->page`) lives in
[`kotoba-ui/docs/agent-guide.md`](../kotoba-ui/docs/agent-guide.md)
(ADR-2607122200). Apps require `kotoba-ui.core` plus this binding — never
`liquid-glass.*` / `shitsuke.*` directly.
