# uikit — design

See `../kotoba-ui/docs/design.md` for the Interface fundamentals taxonomy;
this doc only records what `uikit` adds on top of `kotoba-ui.core`.

## Wrapped components

| kotoba-ui.core component | opts it accepts | uikit default | why |
|---|---|---|---|
| `panel` | `:surface` (`:clear`/`:regular`/`:thick`), `:elevation` (`:flat`/`:raised`/`:overlay`/`:floating`) | `{:surface :clear :elevation :floating}` | mobile cards read as floating over scrolled content |
| `list-view` | `:surface` (`:regular`/`:thick`) | `{:surface :regular}` | matches the component's own plain default — no card-list variant needed |

Every other component (`button`/`toolbar`/`nav-bar`/`sheet`/`alert`/`toggle`/…)
has a fixed glass look in liquid-glass-ui v1 — no `:surface`/`:elevation` opt
exists to differentiate by screen shape, so `uikit` does not wrap them.
Call `kotoba-ui.core` directly for those.

## Future work

If liquid-glass-ui adds a density/screen-shape opt to more components,
`uikit.core` picks up a matching wrapper at that point — not before, to
avoid empty alias wrappers with no actual behavior.
