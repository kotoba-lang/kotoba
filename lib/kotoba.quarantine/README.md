# quarantine — reversible removal

A tool that removes things chosen by a heuristic **should not have a delete
opcode.** It should move them somewhere it can put them back from, and destroying
those bytes should be a separate, later, explicitly acknowledged operation.

That is the whole library.

```clojure
(require '[quarantine.host :as q])

;; move — returns a run id and a manifest sufficient to restore exactly
(q/quarantine! home [{:path "/Users/me/Library/Caches/foo" :bytes 12345
                      :rule/id :cache/stale}]
               {:now-ms now :policy-id "my.policy.v1"})

;; put it back — mode and mtime included; never overwrites newer state
(q/restore! home run-id)

;; destroy — refused unless acknowledged AND past the retention floor
(q/purge! home run-id {:now-ms now :retention-days 7 :acknowledged? true})

;; reclaim everything already past the floor
(q/gc! home {:now-ms now :retention-days 7 :acknowledged? true})
```

## The guarantees

- **Moves are `rename` only.** A cross-device candidate is *refused*, not
  silently downgraded to copy-then-unlink — that is a delete with extra steps and
  a window where neither copy is authoritative.
- **`restore!` never overwrites.** If something exists at the original path
  again, the item is reported rather than restored. Restoring must not destroy
  newer state.
- **One gate for irreversibility.** `quarantine.core/purge-verdict` is pure and
  is the only thing that can say yes. `purge!` refuses on anything else, so a
  caller cannot reach destruction by passing a different argument shape.
- **A purged run keeps its manifest.** It loses its items and gains
  `:vault/purged-ms`. The only irreversible operation must not also be the only
  untraceable one.
- **Partial failure is described, not rolled back.** A failed item is recorded
  and skipped; an all-or-nothing rollback whose own rollback can fail is worse.

## On `:overwrite-passes` (the "shredder")

Passing `:overwrite-passes n` overwrites each regular file with random bytes
before unlinking. **This does not certify erasure.** On APFS — wear-levelled,
copy-on-write, snapshotted — overwriting a path does not guarantee the old blocks
are unreachable. It removes the data from the obvious place, and that is the only
claim made. `:purge/overwritten?` records that it was *attempted*.

The receipt distinguishes the two cases explicitly, because claiming a secure
erase that did not happen would be the worst possible lie for this library to
tell.

## Layout

```
src/quarantine/core.cljk   pure: manifest, retention arithmetic, purge gate, receipts
src/quarantine/host.cljk   nbb: move / restore / purge / gc / list, ledger append
```

`core` performs no IO, so the rules about what may be destroyed are testable
without a filesystem. `host` does the moving.

## Tests

```sh
npm test        # 26 tests / 76 assertions — real filesystem round trips
kbb -M:test     # the .cljc core on the JVM
```

The round-trip tests move actual files in a temp tree and assert mode and mtime
survive. A reversibility claim tested against a mock is worth nothing.

## Provenance

Extracted from `gftdcojp/ai-gftd-misogi` (ADR-260726 in `com-junkawasaki/root`),
where the pattern was built and verified first.
