# Hosted CI retirement — 2026-10-22

The current owner contract permits Amu selfhost / Kotoba-native execution
and a controller on the same native route. The previous dual JVM/CLJS gate
is obsolete.

## Removed registration

- `.github/workflows/ci.yml`, source blob
  `bc2763b97b8119278b8ab660430e65b700607135`, 51 lines.
- Two declared jobs: `test` (JDK 17 and 21 matrix, Clojure tests/lint), and
  `cljs` (Node 22, global NBB install, hosted runner).
- No replacement placeholder or success gate is added.

The removal leaves no repository workflow. Main was unprotected with no
required check contexts and no branch rules at the recorded baseline
`944466b05ffbb210e375baa4b9bcd0b6abab06da`. No protection or rules change is
part of this patch.

## Preserved data and open evidence

All `src/`, `test/`, `kotoba/`, runner and dependency-descriptor content is
unchanged by this retirement. Published vectors, padding/length sweeps,
long/empty-key HMAC cases and sibling SHA-384/512/subpath corpus remain port
inputs. Hosted oracles are historical data, not new native prerequisites.

AGENTS.md and README now state the canonical source/runtime contract and
separate complete namespace migration from native admission. This cleanup
adds or runs no tests and builds or executes no project implementation.

Native controller implementation, full runtime closure, corpus execution,
immutable artifact receipts and downstream integration remain open. Removal
of an obsolete gate is not evidence that a replacement is qualified.
