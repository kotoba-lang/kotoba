# ADR 0002 — backdrops enter the single entry point

- Status: accepted
- Date: 2026-08-02
- Upstream: `kotoba-lang/byoubu`, `kotoba-lang/byoubu-ui`
- Workspace ADR: `com-junkawasaki/root` `90-docs/adr/2608530000-byoubu-backdrop-catalog.edn`

## Context

`liquid-glass` is a material designed on the assumption that something is
behind it — blur, saturate, specular, a two-tone rim. Until now this stack
shipped nothing that could be behind it, so the most expensive layer rendered
against a flat fill. `kotoba-lang/byoubu` now holds backdrops as data and
`byoubu-ui` mounts them.

Rule 1 of the agent guide is that apps require `kotoba-ui.core` only. A
backdrop reachable only by requiring `byoubu-ui` directly would be exactly the
`kotoba_ui/product.cljc` failure again: a namespace on main that nothing could
reach under rule 1, so consumers either reached around core or built green
against an uncommitted local alias.

## Decision

Add `byoubu-ui` as a dependency and re-export `backdrop`, `backdrop-theme`,
`backdrop-facts`, `backdrop-poster-url`, `backdrop-glass-surface`, `backdrops`
and `backdrop-css` from `kotoba-ui.core`.

Beyond the aliases, `kotoba-ui.theme` gains `resolve-theme`: a theme map may
now name a `:backdrop`, and every public entry point resolves it first. So

    (kotoba-ui/theme-css {:backdrop :purple-desert})

produces a page whose accent, label ink, `data-appearance` and
`<meta theme-color>` all come from that backdrop's measured palette. Explicit
keys still win, so `{:backdrop :purple-desert :accent "#ff0000"}` keeps the red
accent and takes the derived appearance.

The plate stylesheet is appended to the bundle **only when the theme names a
backdrop** — a page without one should not carry stacking, print and
reduced-motion rules for an element it never renders. Per-backdrop gradients
are an inline style on the instance, never part of the bundle, so a page with
three backdrops still gets one stylesheet.

## Consequences

- One map is enough. The alternative — an app deriving ink and accent for its
  own backdrop — is the failure mode every backdrop asset library has.
- `kotoba-ui` consumers now transitively carry `byoubu` (zero-dep) and
  `byoubu-ui` (byoubu + css, which was already here). Nothing pulls the kami
  render stack: that lives behind `byoubu`'s `:render` alias.
- The dependency arrow stays one-way. `byoubu-ui` does not depend on
  `kotoba-ui`, `shitsuke` or `liquid-glass-ui`; it returns the theme map they
  already understand. Adding a backdrop upstream needs no change here.
- Verified: the existing suite plus 8 new backdrop tests, 37 tests / 239
  assertions, and the design-quality gate still scores 100.0 against its
  floor of 98.0.
