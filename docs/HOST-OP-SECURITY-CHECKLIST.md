# Host-op security checklist

When adding a new host import / capability to kotoba or aiueos, complete every
item. Skip nothing for "demo only" — demos become production paths.

## Language / contract

- [ ] Register capability id in `kotoba-core-contracts` capability_contract.edn
- [ ] Register `:host/...` kind in `kotoba.lang.capability-values/effect-for-kind`
- [ ] Map op → kind in `kotoba.runtime/op->kind` (and aiueos host-field map if OS-level)
- [ ] Document ABI (params/result) and failure convention (`-1` vs throw)

## Confinement

- [ ] Static gate: ungranted op is `:capability-not-granted` at `check`
- [ ] Runtime gate: unguarded host path must not call the effect (fail closed)
- [ ] If the op takes a resource (URL, path, key, graph id):
  - [ ] Extract resource from guest args before side effects
  - [ ] Enforce `capability-resources` / `resource-permitted?` (URL **prefix** OK for http/file)
  - [ ] For network ops: safe default is allowlist-required
- [ ] Fuel / memory / quota accounted if the op can loop or allocate
- [ ] Receipt on grant and denial

## Tests

- [ ] Positive: granted + in-scope resource succeeds
- [ ] Negative: missing capability denied before effect
- [ ] Negative: out-of-scope resource denied (SSRF/path traversal case)
- [ ] Negative: unguarded instantiate does not ambient-grant the op

## Docs

- [ ] ADR or addendum if the op changes the trust boundary
- [ ] Example policy with least-privilege resources
