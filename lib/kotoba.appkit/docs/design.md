# appkit — design

See `../kotoba-ui/docs/design.md` for the Interface fundamentals taxonomy;
this doc only records what `appkit` adds on top of `kotoba-ui.core`.

## Wrapped components

| kotoba-ui.core component | opts it accepts | appkit default | why |
|---|---|---|---|
| `panel` | `:surface` (`:clear`/`:regular`/`:thick`), `:elevation` (`:flat`/`:raised`/`:overlay`/`:floating`) | `{:surface :thick :elevation :flat}` | dense desktop panes read as flush/embedded panels, not floating cards |
| `list-view` | `:surface` (`:regular`/`:thick`) | `{:surface :thick}` | same legibility rationale |

Every other component (`button`/`toolbar`/`nav-bar`/`sheet`/`alert`/`toggle`/…)
has a fixed glass look in liquid-glass-ui v1 — no `:surface`/`:elevation` opt
exists to differentiate by screen shape, so `appkit` does not wrap them.
Call `kotoba-ui.core` directly for those.

## Future work

If liquid-glass-ui adds a density/screen-shape opt to more components
(`toolbar` compact/regular, `nav-bar` density, etc.), `appkit.core` picks up
a matching wrapper at that point — not before, to avoid empty alias wrappers
with no actual behavior.
