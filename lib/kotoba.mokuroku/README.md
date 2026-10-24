# mokuroku（目録）

**The catalog kernel the `kotoba-lang/app-*` suite shares.**

Activity Monitor is a catalog of processes. Finder is a catalog of files.
Photos is a catalog of images. Music is a catalog of tracks. Strip the chrome
and all four are the same program:

```text
capability-gated source
  → items
  → sort / filter / group / search
  → selection
  → inspector projection
  → command proposal   (executed by the host, never here)
```

`mokuroku` is that program, once. It has **no dependencies, no host effects and
no UI**: every namespace is `.cljc` (JVM / SCI / ClojureScript / GraalVM /
kotoba-WASM), and the pieces that touch the world — reading a directory,
listing processes, playing a track — are protocols the host implements over a
`capability-*` package.

Design: [ADR-2608035000](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2608035000-app-standard-application-suite-on-a-shared-catalog-kernel.edn).

## Surface

| namespace | role |
|---|---|
| `mokuroku.item` | the unit a catalog lists: id, kind, label, flat scalar attrs |
| `mokuroku.source` | `ISource` protocol + descriptor (columns, commands, capability) + memory source |
| `mokuroku.query` | sort / filter / group / free-text search — total and deterministic |
| `mokuroku.selection` | selection by **id**, reconciled across refreshes |
| `mokuroku.inspector` | single / multi / empty projection of what is selected |
| `mokuroku.command` | command **proposals**, bounded by what the source accepts |
| `mokuroku.catalog` | the four composed into one value, plus `view` |

```clojure
(require '[mokuroku.catalog :as catalog]
         '[mokuroku.source :as source])

(-> (catalog/catalog my-source)
    catalog/refresh
    (catalog/search "kei")
    (catalog/sort-by-attribute :size)
    (catalog/select "file-3")
    catalog/view)
;; => {:view/descriptor … :view/result … :view/selection …
;;     :view/inspector … :view/commands … :view/problems …}
```

## Three decisions worth knowing before you use it

**Selection is a set of ids, never indices.** Every source in this suite
changes underneath the view — a process exits, a file is written, an import
finishes. Index-based selection silently retargets when that happens: the user
picks row 3, the list re-sorts, and the delete lands on someone else.
`selection/reconcile` runs on every refresh and reports `:selection/dropped`,
so the visible failure is "the row is gone", not "the wrong row was acted on".

**Sorting is a total order, always.** Attribute comparators are not total on
their own — ties, mixed types, missing values — so every comparison falls
through to the item id. Without that, the same query answers differently on
JVM and ClojureScript, because ties resolve to whatever the underlying
collection happened to do. Missing values sort last ascending, which is what a
file listing wants.

**Commands are proposals.** `mokuroku` holds no capability and calls nothing.
`catalog/propose` returns a value describing what was asked for, which
capability would authorise it, and whether it needs confirmation. Whether it
happens is the host's decision, gated by the grant that made the source
readable in the first place. Same split as `kotoba-lang/koyomi` between
drafting an event and inviting anyone to it.

## The bounded Kotoba profile

`src/mokuroku/bounded.kotoba` and `bounded_validate.kotoba` are the
capability-free `.kotoba` profile: at most 8 keyword-identified items, an i64
sort rank, and a `[:set :keyword]` selection. It exists to prove the one
property the whole suite leans on — `reconcile` yields the intersection of the
selection with what the source now holds, so a command proposal can never name
a target that no longer exists.

`test/mokuroku/bounded_conformance.kotoba` runs both polarities: the selection
must be reported *unsound* before reconcile and *sound* after, so the oracle
cannot be satisfied by a validator that always answers one way.

The `.cljc` model stays authoritative for text search, mixed-type comparison,
grouping and commands; those domains are not silently narrowed to what the
bounded profile can express.

> **Subset note.** `=` is i64-valued here, not bool — it is only directly
> usable as an `if` condition, so a `:bool` function must fold it through
> `(if … true false)`. Same family as the `or`-returns-i64 gotcha recorded for
> the `css` port. Tree shape is carried as `:item/parent` rather than nesting
> because the profile has no recursive value yet (ADR-2607279200 W4); that is
> a worked-around limitation, not the intended programming model.

## Test

```sh
kbb -M:test          # 13 tests, 58 assertions

mkdir -p target/kotoba
kbb -M:kotoba compile test/mokuroku/bounded_conformance.kotoba \
  --source-path src --target js-browser --output target/kotoba/mokuroku.mjs
kbb -M:kotoba compile test/mokuroku/bounded_conformance.kotoba \
  --source-path src --target wasm32-browser --output target/kotoba/mokuroku.wasm
compiler_src="$(kbb -Spath -M:kotoba | tr ':' '\n' | grep '/compiler/' | head -1)"
kbb --backend sci scripts/verify-kotoba.cljk target/kotoba/mokuroku.mjs \
  target/kotoba/mokuroku.wasm "$(dirname "$compiler_src")/runtime/browser-host.mjs"
```
