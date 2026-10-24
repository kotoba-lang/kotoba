# ADR 0001 — byoubu-ui: the mounting layer, and why the dependency arrow points one way

- Status: accepted
- Date: 2026-08-02
- Workspace ADR: `com-junkawasaki/root` `90-docs/adr/2608530000-byoubu-backdrop-catalog.edn`
- Sibling: `kotoba-lang/byoubu` ADR 0001

## Context

`kotoba-lang/byoubu` holds backdrops as data: palettes, scene specs, derived
legibility facts, and tier-0 gradient layer data. None of that is CSS or
hiccup, deliberately — the catalog must stay usable by a consumer that renders
some other way.

Something has to turn it into an element on a page, and that something has to
decide where it sits relative to the design system.

## Decision

A separate repo at design-system tier, depending on `byoubu` and
`kotoba-lang/css` and **nothing else** — in particular not on `shitsuke`,
`liquid-glass-ui` or `kotoba-ui`.

`theme-for` returns the plain theme map `kotoba-ui.core/theme-css` already
takes (`{:accent :accent-dark :appearance :hig :hig-dark}`). Integration is
therefore data, not a dependency: `kotoba-ui` may consume this repo, this repo
consumes neither it nor shitsuke.

Three consequences of that shape are the point of it:

1. An app that does not use the design system can still mount a plate.
2. There is no cycle to reason about when `kotoba-ui` later re-exports
   `backdrop` from its single entry point.
3. Nothing in a browser bundle can reach the kami render stack through this
   repo.

## Why the theme half exists at all

A plate alone gives a page a picture. Every consumer then re-derives the text
color, the accent and the panel opacity for that picture, and at least one gets
it wrong — which is the failure mode of every backdrop asset library. Because
`byoubu.facts` computes those answers from the palette, `theme-for` can hand
them over as one map, and the design system applies them through its existing
override mechanism with no new vocabulary.

The light and dark HIG overrides are set to the *same* values. The backdrop
does not change when the OS switches scheme, so content over it must resolve
the same way in both; letting the OS flip the ink is how you get white text on
a salt flat.

## Rules as data

Every rule is an EDN declaration map rendered by `css.core`, never hand-typed
CSS text — same reasoning as `liquid-glass.style`, which found two real bugs of
the form "a class the component renders, but no rule styles it". There is a
test asserting that every class this component emits has a rule.

Per-backdrop gradients are an **inline style per instance**, not a class per
backdrop: a page with three backdrops gets one stylesheet and three small style
attributes.

## Alternatives considered

**Fold this into `byoubu`.** Rejected: it would put a `css.core` dependency and
CSS/hiccup opinions into the zero-dependency catalog, which is the property
that makes the catalog usable from a plain web app.

**Fold this into `liquid-glass-ui`.** Rejected: that library's subject is
foreground material. It would also invert the dependency — the material would
have to know about backdrops.

**Depend on `shitsuke` for HIG token names.** Rejected: this repo never emits a
`--hig-*` name. It returns override maps in shitsuke's *key* vocabulary
(`{:hig/color {:label ... :tint ...}}`) and lets the design system emit the
variables. A dependency purely to borrow a string constant is not worth the
edge.

**Add a `--ready` class from a `<script>` we ship.** Rejected for now: the fade
class is documented and the SSR-without-JS path is correct (gradients stay).
Shipping script from a styling library is a bigger commitment than the problem
warrants.

## Consequences

- The plate is decorative in the accessibility tree (`aria-hidden`,
  `pointer-events: none`) and drops out under `@media print`.
- `prefers-reduced-motion` removes only the moving tier — the page keeps its
  backdrop and stops moving, rather than losing the design.
- `:poster` / `:loop-src` are wired end to end but there is nothing to point
  them at yet: `byoubu` has rendered no T1/T2 artifacts. Consumers may pass
  their own URLs today.
- `kotoba-ui` re-exporting `backdrop` from its single entry point is a
  follow-up in that repo, not here.
