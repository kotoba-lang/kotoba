# uikit

`uikit` is the **touch / mobile / card-first platform binding** on top of
[`kotoba-ui`](../kotoba-ui), part of kotoba-lang's default UI/UX design
(`90-docs/adr/2607022800-kotoba-lang-default-uiux-appkit-uikit-interface-fundamentals.md`).
Mirrors Apple's UIKit role against SwiftUI (`kotoba-ui.core` plays the
SwiftUI-equivalent role here): screen-shape-specific *defaults*, not a new
component catalog.

## What it actually wraps

Of `kotoba-ui.core`'s 32 components, only `panel` (`:surface`/`:elevation`)
and `list-view` (`:surface`) take an opt that varies by screen shape in
liquid-glass-ui v1 — everything else (`toolbar`/`nav-bar`/`sheet`/`alert`/
`button`/…) has a fixed glass look with nothing to differentiate, so `uikit`
wraps only those two and leaves the rest to be called on `kotoba-ui.core`
directly.

| fn | default opts | rationale |
|---|---|---|
| `panel` | `{:surface :clear :elevation :floating}` | mobile cards read as floating over scrolled content, single-column stacked |
| `list-view` | `{:surface :regular}` | matches the component's own plain default — no card-list variant needed on mobile |

Caller-supplied opts always win (`merge default opts`), same contract as
every liquid-glass-ui component wrap.

## Usage

```clojure
(require '[kotoba-ui.core :as ui]
         '[uikit.core :as tk])

(tk/panel [(ui/label nil "Score") (ui/badge "3")])
```

## Target consumers (provisional, see superproject ADR)

gftd.ai (chat), isekai.network (AI game platform, card-based game showcase) —
touch/mobile-first product surfaces.

## Tests

```bash
kbb -M:test
kbb -M:local:test   # local ../kotoba-ui override
```

## Building an app? Read the agent guide first

The canonical paved-road recipe for building refined, Apple-HIG-quality pages
with this stack (HIG semantic tokens via `shitsuke.hig`, the
`@layer kotoba.hig, kotoba.glass` cascade contract — unlayered app CSS always
wins, `kotoba-ui.shell` layout scaffolds, single theme map, `->page`) lives in
[`kotoba-ui/docs/agent-guide.md`](../kotoba-ui/docs/agent-guide.md)
(ADR-2607122200). Apps require `kotoba-ui.core` plus this binding — never
`liquid-glass.*` / `shitsuke.*` directly.
