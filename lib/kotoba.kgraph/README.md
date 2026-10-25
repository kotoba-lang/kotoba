# kgraph

EAVT datom store — the in-memory data model shared by kotoba and kotobase.

**Tier**: `T1`  **Role**: `library`

Split out of the overloaded core repos by ADR-2607266000 so that each
responsibility has exactly one owner and the dependency direction is
checkable from outside.

## Owns

- `kotoba.kgraph (entity-attribute-value-transaction store)`

## Does not own

- own language semantics
- own persistence
- depend on a compiler

## Depends on

- nothing (contract/leaf tier)

## Test

Two runtimes, one suite. `src/` and `test/` are `.cljc`; the JVM is the last
runtime in this workspace's order, not the only one.

```bash
kbb -M:test                                     # JVM

CP=$(kbb --backend sci tools/portable-classpath.cljk)             # nbb — no JVM, no build
kbb --backend sci --classpath "$CP" test/run_portable.cljk
```

Run the nbb one from somewhere that is not this directory too. A suite run
only from the repo root cannot detect a working-directory assumption, which
is the failure that made this conversion necessary elsewhere:

```bash
cd /tmp && CP=$(nbb ~/…/kgraph/tools/portable-classpath.cljk ~/…/kgraph) \
  && kbb --backend sci --classpath "$CP" ~/…/kgraph/test/run_portable.cljk
```

`tools/portable-classpath.cljk` resolves `datom.core` from the `:git/sha` in
`deps.edn` — nbb has no dependency resolver, and retyping the sha into the
command is how a test run keeps passing against a checkout the pin left
behind.

## Prove the suite can fail

```bash
kbb --backend sci tools/check-mutations.cljk   # pre-flight: each :find occurs exactly once
kbb --backend sci tools/mutate.cljk            # 8 mutations against the JVM half
```

A mutation nothing reddens is reported as a SURVIVOR, which is a finding
about the suite. See the header of `tools/mutations.edn` for what the table
covers and what it does not.
