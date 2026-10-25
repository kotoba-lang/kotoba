# yakuwari-view

Roles and their live runs → **one display model**, plus hiccup in a class
vocabulary the consuming surface styles itself.

```
src/yakuwari_view/model.cljk    roles + runs -> display model, totals, health
src/yakuwari_view/hiccup.cljk   display model -> plain elements + data-* state
```

## Why it exists

Two surfaces show the same fleet of roles and are on **different design
systems**:

| surface | stack |
|---|---|
| `network-awai/cloud-itonami` — the itonami.cloud operator cockpit | `kotoba-ui.core` + `appkit.core`, HIG tokens |
| `cloud-itonami/cloud-itonami-app` — the local-first workspace | `jp-go-digital-design-system` directly |

A shared *component* would force one of them off its own paved road, and a
component abstracting over both would be a third design system nobody asked
for. So the shared thing is the **projection** — the part that is genuinely
identical — and a documented markup vocabulary. Each surface owns its CSS.

That split is not invented here. The cockpit's own hydration script already
injects `.row` / `.pill` / `.business-card` markup for exactly the dense rows
that cannot be shell components, so this fits the pattern already in place
there.

## It owns no domain truth

| concern | authority |
|---|---|
| is this role well-formed | `yakuwari.spec` |
| does this capability need a human | `yakuwari.policy` |
| how many runs should be live | `yakuwari.reconcile` |
| grouping, health label, totals, markup | here |

If a number here disagrees with `reconcile/plan`, **this repo is wrong**.

## The decisions worth knowing

**An invalid role is displayed as invalid, never dropped.** `reconcile/plan`
calls `spec/validate!`, which throws. Letting that propagate fails a whole
page for one malformed file; catching it and skipping the role renders a fleet
that *looks complete* and silently lacks a role. Both are worse than a card
that says what is wrong with it, so every role appears and `:fleet/problems`
carries the details — the same reasoning as the superproject query plane's
`warn-skipped!`.

**An invalid role still shows the runs it already spawned.** A spec being
unreviewable does not make its live executions invisible; those are the ones
an operator most needs to see.

**`:stalled` outranks `:starved`.** From outside they are identical — nothing
is running — but the fixes are opposite. Stalled work waits on a human and
needs an approval; starved work waits on nothing and needs a dispatcher.
Collapsing them into "not running" hides which.

**Groups are supplied, not inferred from the roles.** A business whose roles
were all deleted is a fact worth showing. Inferring groups would erase it.

**A role whose group nobody declared is surfaced, not dropped.** Otherwise a
typo in one key makes a role vanish from every surface at once. It still
counts toward totals, so those do not quietly shrink.

**`needs-human` is computed from policy, not from the queue.** A role with
sweeping approval requirements and a role with none must not look identical
whenever nothing happens to be waiting.

**`desired` is shown even when zero.** A role deliberately scaled to zero and
a role nobody configured look the same if the figure is hidden when falsy.

**State travels as `data-*`, not as a class per state.** A surface writes one
selector per value instead of one class per combination, and an unrecognised
value still renders — unstyled — rather than disappearing.

**Totals are summed from the rendered cards.** A total cannot disagree with
the rows beneath it.

## Use

```clojure
(require '[yakuwari-view.model :as model]
         '[yakuwari-view.hiccup :as h])

(def projection
  (model/project {:roles     roles          ; plain authored yakuwari maps
                  :runs      runs           ; agent.run maps
                  :groups    businesses     ; display order; empty ones kept
                  :group-key :yakuwari/business
                  :now-ms    (System/currentTimeMillis)}))

(h/fleet projection)                        ; whole tree
(h/group (first (:fleet/groups projection))) ; or place pieces yourself
(h/hil-queue (model/hil-queue projection runs))
(model/needs-attention projection)          ; worst first, healthy omitted
```

`:group-key` rather than `:group-by` on purpose — the latter would shadow
`clojure.core/group-by` inside `project` itself.

## Test

```sh
npm test          # nbb / JS host  (needs a sibling kotoba-lang/yakuwari checkout)
kbb -M:test   # JVM host — must agree exactly
```

28 tests, 57 assertions, both hosts.

## Status

Created 2026-07-30 for superproject ADR-2607300800 (awai business yakuwari
fleet). Consumers land after it: the cockpit pane and the local workspace
surface. Until both exist this library has tests but no production caller, so
treat the markup vocabulary as still cheap to change.
