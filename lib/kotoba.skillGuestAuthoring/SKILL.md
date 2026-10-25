---
name: guest-authoring
description: >-
  Write, check and land a `.kotoba` guest without inventing a limit that is not
  there. Use BEFORE concluding that Kotoba cannot express something, before
  choosing a compile target, and before quoting any capability's readiness.
  Triggers on ".kotoba", "amu compile", "amu check", "capability kit",
  "surface-status", "is this supported in Kotoba", "native backend", "JVM-free".
---

# Authoring a Kotoba guest

## The one rule this package exists for

**"Kotoba cannot do X" is two different sentences, and they are not
distinguishable by trying.**

| | |
|---|---|
| a **safety invariant** | permanent. Widening it takes an ADR and fail-closed enforcement. |
| a **backend that has not caught up** | temporary. Writing around it permanently is the bug. |

Both arrive as the same rejection. An agent that does not separate them writes
a module in a self-imposed dialect, adds a comment explaining the style, and
that comment outlives the gap by months — and the next agent copies it.

**Never decide which one you are looking at from the compiler's answer. Read
the disposition.**

## Procedure

### 1. Ask the authority, not the compiler

Read `lang/surface-status.edn` in `kotoba-lang/kotoba-lang`. Its
`:dispositions` map declares the vocabulary, and the entry for what you were
refused lives under `:invariants` (or the surface map that names it). That
entry's `:disposition` is the answer:

| `:disposition` | what it means for your code |
|---|---|
| `:intentional-security-constraint` | permanent. Design around it and say so. |
| `:intentional-semantic-simplification` | permanent. Determinism/portability. |
| `:implemented-partial` | it EXISTS. Check which backends. |
| `:not-yet-implemented` | **not a prohibition.** A gap. |

Where an entry carries a `:shielding-axis`, that names the property the
restriction protects — some axes have a stated widening path and some
(code identity, static checkability) never open.

**Do not quote a disposition from any document, including this one.** Read the
file. Every value in this workspace that was ever copied into prose went stale,
including into the repo-wide AGENTS.md more than once.

### 2. Ask which backends, not whether

Read `resources/kotoba/lang/capability-kits/*.edn` in `kotoba-lang/amu` and
look at each kit's `:qualification` map.

- The key set **differs per kit**. Do not summarise across kits.
- `pending` is not "nobody tried" — kits record measured refusals with reasons.
- Read them with an EDN reader, not `grep`. Line wrapping silently truncates
  `grep -A`/`cut` output, and a truncated read of a readiness table is
  indistinguishable from a complete one.

```bash
kbb --backend sci --classpath ".:scripts/nbb_compat" -e '
(ns x (:require [clojure.edn :as edn] ["fs" :as fs] ["path" :as p]))
(def dir "orgs/kotoba-lang/amu/resources/kotoba/lang/capability-kits")
(doseq [f (sort (fs/readdirSync dir))]
  (println (.padEnd (subs f 0 (- (count f) 4)) 22)
           (pr-str (:qualification (edn/read-string (fs/readFileSync (p/join dir f) "utf8"))))))'
```

### 3. Pick the target from where it runs, not from habit

`bin/amu` runs some targets under **nbb, with no JVM**, and falls back to
`clojure` for the rest. Check which by reading `bin/amu`'s own eligibility
predicate rather than assuming; a target that spawns `clojure` starts a JVM,
and this workspace's build/acceptance rules refuse a JVM-free claim built that
way.

For anything that runs in a browser or a Worker, prefer the wasm browser target
over emitting JS or CLJS text: the latter two are the ones that start a JVM,
and one of them emits source that still needs a toolchain to become a page.

### 4. Check, then RUN

`amu check` returning `:ok true` is not "it works".

Measured: a value whose type is wrong for `document-bool` passes `check` and
fails when the export is executed (`value is not a boolean`, at the value
phase). The rule that follows:

- `and` / `or` / `=` produce integers unless annotated. Anything reaching a
  `document-bool` must be folded through `if` — including `(if (= t :no) true false)`.
- Run the export. A guest that has only been `check`ed has not been run.

### 5. Do not restate a limit you did not measure today

When you write around a temporary gap, put the reason and the removal
condition in the module header:

```clojure
;; This module stays inside one-word values because the native backend's
;; admission gate does not admit <shape> yet (:not-yet-implemented as of
;; <date>, <authority file>). It is NOT the Kotoba style. When the gate
;; admits it, this restriction goes.
```

Without that line the next reader copies the shape as the house style. With
it, the workaround has an expiry.

## Inputs

| | |
|---|---|
| a workspace checkout | `kotoba-lang/kotoba-lang`, `kotoba-lang/amu`, `kotoba-lang/kotoba-kir` |
| `nbb` | to read EDN authorities with a reader |
| the refusal you received | the compiler/runtime message, verbatim |

## Outputs

| | |
|---|---|
| a disposition | `:intentional-*` / `:implemented-partial` / `:not-yet-implemented`, read today |
| a backend answer | per-kit `:qualification`, not a summary across kits |
| either a design | that accepts a permanent invariant, and says so |
| or a bounded workaround | with the gap, the date, the authority and the removal condition in the header |

## Non-goals

This package computes nothing and runs no resident. It never carries a copy of
a readiness value; every number it would state is a number that would go stale.
Where the answer is a measurement, it points at the measurement.
