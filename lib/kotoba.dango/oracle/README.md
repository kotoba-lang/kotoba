# dango cljc oracle

`dango` as portable `.cljc`, with no other library in this repository. It is an oracle and the Otehon implementation, **outside the native route**: native builds, gates and runtimes do not depend on it, and nothing falls back to it. The `.kotoba` wire verifiers stay the native path.

| Part | Files |
| --- | --- |
| Chain, caveats, shape | `src/dango/` |
| The value codec dango needs (`kotoba.value.v1` subset) and CID | `src/dango/value.cljc`, `cid.cljc` |
| Scope lattice, SHA-2, Ed25519 | `src/authority`, `sha2`, `ed25519`, `x25519`: copies of this repository's `.cljk`, without the `ns` attribute map |
| Revoked-CID store | `src/authority/revocation.cljc`: set semantics, canonical wire vector, distribution merge; `verify` reads it as `:revoked` |

It also adds web3 roots. `chain/root-for-external-signer` has a wallet or passkey sign `chain/root-message`, which names the root CID and cannot pass as a login. The verifier checks it through a trusted `:root-verifier` the host supplies. ERC-191, ERC-1271 and WebAuthn checks belong in that function, not here.

## Check

```bash
clojure -M -e '(load-file "test/run.cljc")'
```

```bash
nbb test/run.cljc
```

`test/dango/vectors_data.cljc` pins bytes, signatures and CIDs from the `.cljk` reference. A difference is a finding: report it, don't align it.

`test/run.cljc` prints its counts and exits nonzero when anything fails or errors, so a CI job can rely on the exit code directly.

## Limits

- The portable Ed25519 is not written to be constant-time, so a signer holding a valuable key should use the platform's.
- 120 assertions (baseline on main before this change measured 90). nbb: 120 pass, 0 fail; JVM: 120 pass, 0 fail. nbb takes about 3 minutes, JVM about 1 minute. Babashka takes about an hour (interpreted Ed25519); this revision's bb run is pending.
- No token format stability promise exists beyond these vectors. The revocation store covers data semantics, wire form and merge only — persistence, freshness and distribution transport stay the host's job. Per-surface facts and the OS broker are not built.
