# mokuroku-ui

**Renders a [`mokuroku`](https://github.com/kotoba-lang/mokuroku) catalog as a
window.** The other half of the `kotoba-lang/app-*` suite: the kernel decides
what is true, this decides what it looks like.

```clojure
(require '[mokuroku.catalog :as catalog]
         '[mokuroku-ui.core :as mui])

(mui/->page (catalog/view cat)
            {:title "Activity Monitor"
             :columns [:name :cpu :memory]
             :formatters {:cpu mui/percent :memory mui/human-bytes}
             :noun "processes"})
;; => a complete <!doctype html> document
```

Design: [ADR-2608035000](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2608035000-app-standard-application-suite-on-a-shared-catalog-kernel.edn).

## Why this is a separate repo from `mokuroku`

Same reason `byoubu-ui` is separate from `byoubu`: the kernel has to stay
dependency-free. A host that renders through something other than the
kotoba-lang design system — a terminal, a native shell, a WebGPU surface —
still needs sort/filter/selection semantics, and it should not have to pull
`kotoba-ui` to get them. The dependency arrow points one way.

## What an app supplies, and what it must not

An app supplies **what genuinely differs**: which columns to show, how to
render a cell value, what to call a row, and its theme.

```clojure
{:columns            [:name :cpu :memory]     ; default: first 3 sortable attrs
 :formatters         {:cpu mui/percent}       ; by attribute key or by type
 :badge              #(when (:pinned %) "Pinned")
 :noun               "processes"
 :search-placeholder "Search processes"
 :empty-title        "No processes"
 :theme              {:accent "#..." :appearance :auto}}
```

It does **not** supply layout, typography, colour, spacing, or ARIA. Those
come from `kotoba-ui` + `appkit`, and re-deriving them per app is exactly how
nine apps end up looking like nine apps. The shared CSS is seven rules, all
spending `--hig-*` tokens; the only legitimate hex in the whole stack is the
theme's accent.

## Three things it refuses to do

**It never shows an empty cell for an absent value.** A blank reads as either
"no value" or "the renderer broke". `--` says the first one on purpose, and
`human-bytes` returns `nil` for `nil` rather than `0` — a directory with no
size is not a directory of size zero.

**It never shows an empty list for a missing grant.** Before a capability is
granted, the empty state names the capability it is waiting on. An empty
library and a refused grant are otherwise indistinguishable, and only one of
them is the user's to fix.

**It never reports only the visible count.** A limited listing says
`50 of 4,201 shown` — reporting `50 items` would tell the user a folder holds
fifty files when it holds four thousand.

## Measured

`test/mokuroku_ui/core_test.cljk` scores three real `->page` outputs —
populated, multi-selected, and awaiting-grant — with
[`design-quality`](https://github.com/kotoba-lang/design-quality)'s
deterministic 12-axis HIG/WCAG rubric.

Measured 2026-08-04 (design-quality `fb766e2`, kotoba-ui `3a28afc`):
**100.00 on all three, aggregate 100.00.** Floors at 98.0 — raise them when
upstream improves, never lower them to make a regression pass.

Selection is announced twice on purpose: a class for the eye and
`aria-selected` for everything else. They are not redundant — a class tells a
screen reader nothing.

That needed an `:attrs` passthrough on `liquid-glass/list-row`, which did not
exist: passing one was silently dropped, so consuming code read as accessible
while rendering nothing of the sort. It was
[added upstream](https://github.com/kotoba-lang/liquid-glass-ui) rather than
worked around here, because every app in the suite with a selectable list
needs it. The merge contract is the component's own attrs winning, so `:attrs`
can add ARIA but never clobber `:class`, `:role` or `:data-act`.

## Test

```sh
kbb -M:local:test    # sibling checkouts
kbb -M:test          # pinned git deps
kbb -M:lint
```
