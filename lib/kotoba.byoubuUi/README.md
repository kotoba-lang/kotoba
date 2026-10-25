# byoubu-ui

**Mounts a [`kotoba-lang/byoubu`](https://github.com/kotoba-lang/byoubu)
backdrop behind page content, and hands the design system the theme that keeps
that content legible on it.**

```clojure
(require '[byoubu-ui.core :as byoubu-ui]
         '[kotoba-ui.core :as kotoba-ui])

;; the plate
(byoubu-ui/backdrop {:backdrop :purple-desert}
  [:h1 "..."])

;; the half that is easy to skip and expensive to skip
(kotoba-ui/theme-css (byoubu-ui/theme-for :purple-desert))
```

`backdrop` alone gives a page a picture. `theme-for` is what makes the accent,
the ink and the browser chrome agree with that picture — accent, appearance,
label color and page background all derived from the backdrop's palette by
`byoubu.facts`, not chosen by hand per page.

Run `kbb --backend sci bin/demo.cljk` and open `docs/demo.html` to see every catalog
backdrop with content on it.

## Where it sits

```
   sky / atmosphere / terrain / postfx / webgpu     the kami stack, untouched
        ▲ byoubu's :render alias only (offline export)
        │
     byoubu            zero runtime deps — catalog, facts, tier-0 plate data
        ▲
     byoubu-ui         this repo: byoubu + kotoba-lang/css
        ▲
     kotoba-ui         may consume this; this consumes neither it nor shitsuke
        ▲
      apps
```

The dependency arrow points one way. `theme-for` returns the plain theme map
`kotoba-ui.core/theme-css` already takes, so integration needs no dependency in
this direction — and an app that does not use the design system at all can
still mount a plate. Nothing here reaches the render stack: that belongs to
`byoubu`'s `:render` alias, not to anything a browser loads.

## What the stylesheet does

One stylesheet for every backdrop, one small inline style per instance. A page
with three backdrops gets three `style` attributes, not three stylesheets.

- The stage owns a stacking context (`isolation: isolate`), so the plate's
  `z-index: 0` never competes with whatever the host page already stacks.
- The plate is `pointer-events: none` and `aria-hidden` — decorative, and it
  must never eat a click or be announced.
- `background-color` is painted under the gradients. Without it a dark plate
  flashes white for one frame on a cold load, which is the most visible way a
  dark backdrop goes wrong.
- A poster or loop starts at `opacity: 0` and is faded in by
  `byoubu__plate-media--ready` once it has decoded. Server-rendered with no JS,
  the class is never added and the gradients stay — a correct page, not a
  broken one.
- `prefers-reduced-motion: reduce` drops **only** the moving tier. The page
  keeps its backdrop; it stops moving.
- `@media print` hides the plate.

Rules are EDN declaration maps rendered by `kotoba-lang/css`, never hand-typed
CSS text — so a test can assert on selectors and declarations as values. There
is a test that every class the component renders has a rule, which is the exact
bug `liquid-glass-ui` found twice in itself.

## Light and dark

`theme-for` sets the light and dark HIG overrides to the same values, on
purpose. The backdrop does not change when the OS switches scheme — the picture
behind the text is the same picture — so content over it must resolve the same
way in both. Letting the OS flip the ink here is how you get white text on a
salt flat.

## Tests

```bash
kbb --backend sci bin/test.cljk        # needs sibling ../byoubu and ../css checkouts
kbb -M:local:test    # JVM
```

## Tiers

```clojure
;; tier 0 only — no assets, paints on first frame
(byoubu-ui/backdrop {:backdrop :purple-desert} content)

;; tier 1 — the catalog's rendered poster fades in over the gradients
(byoubu-ui/backdrop {:backdrop :purple-desert :assets-base "/assets"} content)
```

With `:assets-base`, the poster URL is resolved from `byoubu`'s manifest, so a
page does not keep its own table of backdrop→file. Serve `byoubu`'s
`resources/byoubu/posters/` under that prefix. An explicit `:poster` still wins,
and `:loop-src` takes a video for a moving tier.

## Status

Tiers 0 and 1 are implemented and tested; 24 tests / 113 assertions on both
runtimes. `bin/demo.cljk` renders every catalog backdrop with real content and
a real poster over the gradients — verified in Chrome.

`:loop-src` is wired end to end (element, fade-in, reduced-motion) but the
catalog ships no video: `byoubu` has no T2 renderer. Pass your own URL and it
works.

See `docs/adr/0001-byoubu-ui.md`.
