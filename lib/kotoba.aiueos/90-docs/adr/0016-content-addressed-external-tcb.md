# ADR-0016 — Content-addressed external TCB, and the Nix-shaped properties aiueos does and does not have

- Status: accepted
- Date: 2026-08-01
- Root authority: `com-junkawasaki/root` ADR-2608012050 (Nix-shaped supply-chain
  properties across the workspace). This ADR is the aiueos-repo half; it owns
  the inventory format and the checker.

## Context

The question that started this: *does aiueos consider or integrate Nix-like
design?* The literal answer is no — "nix" occurs zero times anywhere in this
repository. The useful answer is that several properties Nix is known for were
reached here independently, from capability security and evidence gates rather
than from build purity, and that the ones still missing are missing in
different degrees. Naming which is which is the point of this ADR, because
"we already do reproducible builds" was close enough to true to stop anyone
from looking at the part that was not.

Already true, arrived at from the evidence side:

- **reproducible artifacts** — `scripts/build-hvt-guest.cljk` and
  `build-hvt-kotoba-guest.cljs` regenerate their fixtures and require
  byte-identical output; release media honour `SOURCE_DATE_EPOCH`;
- **digest-gated admission** — `:aiueos/wasm-sha256` plus an Ed25519
  identity↔artifact binding (ADR-0003/0012) in the hosted profile, SHA-256 +
  RSA-2048 catalog/ELF/journal admission in the bare-metal profile (ADR-0013);
- **declarative configuration with deny-by-default** — EDN manifests, grants
  resolved by `aiueos.policy`, boot order derived from the provider graph;
- **atomic update with rollback** — primary ESP plus a byte-identical recovery
  partition, `apply-update`, QEMU-gated rollback of a corrupted update.

Not true, and the gap this ADR closes: **the external half of the trusted
computing base was recorded but never checked.** `aiueos.tcb/validate` counted
`:tcb/external` and validated nothing in it. Two errors had accumulated behind
that:

1. `io.github.kotoba-lang/security` was recorded as `:source :local-root
   :path "../security"` — a *path*, which addresses nothing — while `deps.edn`
   had already moved to `:git/sha "49fc4ce…"`. `docs/tcb-inventory.md` described
   this as an honestly-recorded assurance gap; it had become a stale record of a
   gap that no longer existed in the form described.
2. `io.github.kotoba-lang/abi` — a runtime dependency in `deps.edn`'s `:deps`,
   therefore on the classpath, therefore inside the TCB — appeared in the
   inventory not at all.

A record that cannot be wrong about the thing it records is not evidence.

## Decision

### 1. `:tcb/external` is content-addressed, and the checker enforces it

Inventory version 2. Each entry declares a `:source` and is pinned by content:

| `:source` | content address |
| --- | --- |
| `:maven` | `:sha256` of the resolved jar |
| `:git` | `:git-sha` — git's own content address for the tree |
| `:platform` | none is possible from inside this repository; must carry an explicit `:assurance-gap` |

`aiueos.tcb/validate` enforces three fail-closed invariants:

1. **no unpinned dependency** — an entry with neither a content address nor a
   declared `:assurance-gap` is an error;
2. **no silent drift** — the inventory's version/commit must equal `deps.edn`'s,
   and the shared security commit must additionally equal
   `security-adoption.edn`'s. Three files record one fact; they may not
   disagree;
3. **no dependency outside the inventory** — every coordinate in `deps.edn`'s
   `:deps` must appear in `:tcb/external`.

Running the pre-change inventory against the new checker reports six errors.
Three are consequences of the format change itself — the old entries declared no
`:source` at all, so they cannot be content-addressed. The other three are the
substantive ones, and are the evidence that these checks are load-bearing rather
than decorative:

```
{:kind :external-unknown-source, :coordinate "io.github.kotoba-lang/security", :source :local-root}
{:kind :external-undeclared,     :coordinate "io.github.kotoba-lang/abi"}
{:kind :unsupported-version,     :actual 1}
```

The security entry surfaces as `:external-unknown-source` rather than as a
commit mismatch because a `:local-root` path is rejected before any comparison
with `deps.edn` — a path is not a weaker content address, it is not one.

The jar digest check cannot be skipped by an unresolved environment: the jars
must already be resolved for the JVM running the check to have started. This is
deliberately the *weakest* environmental assumption available — it holds in CI
without adding a CI step, since `kbb -M:test` runs `aiueos.tcb-test`.

### 2. Git commits are accepted as content addresses, with the caveat stated

A git commit id addresses its tree, so `:git-sha` is a content address, not a
version label. It is a SHA-1 one. This is accepted for now — the alternative,
a canonical SHA-256 tree digest, is not free: the `~/.gitlibs` checkout contains
`.git`, so a naive whole-directory digest is non-deterministic, and a correct
one needs a defined canonicalisation. Recorded as future work, not pretended
away. It is also what Nix's own `fetchGit` does before `narHash`.

### 3. The transitive closure is recorded as `:tcb/classpath` (added 2026-08-01)

`:tcb/external` records what this repository *declares*. It cannot see what
those declarations drag in. `:tcb/classpath` records the jars actually loaded,
each by SHA-256 — the closure `deps.edn` alone cannot express.

Measured: `org.clojure/clojure`, `spec.alpha` and `core.specs.alpha` are on
every runtime classpath here and are named by no `:deps` entry. And the version
matters — the shared security package declares clojure **1.12.4** while
**1.12.5** is what actually loads. A declaration-level record would have said
1.12.4 and been wrong, which is the argument for recording the closure rather
than inferring it.

Verification is deliberately **asymmetric**: a jar on the classpath and not in
the inventory is an error, and a recorded jar whose bytes changed is drift, but
recorded-but-absent is *not* an error. The check runs under more than one alias
(`:tcb-check` loads five jars, `:test` nine); requiring a bijection would force
the inventory to describe one alias and fail under the other, which teaches
people to skip the gate. `:scope :test` marks the jars that are classpath
members only under `:test` and remain outside the TCB by `:tcb/excluded`.

### 4. The platform floor is unpinnable, but the disagreement about it is checked (2026-08-03)

**`java.base`** cannot be content-addressed from inside this repository, so it
carries `:minimum-version 25` and `:assurance-gap
:platform-runtime-not-content-addressed`. That much is unchanged.

What changed is the second-order problem this ADR originally only wrote down:
`.github/workflows/ci.yml` provisions temurin 21, which does not satisfy the
declared floor, and nothing detected it. **Whether the floor or the runner is
wrong is still an owner decision** — the checker does not pick a side and does
not turn CI red for the disagreement existing. It requires the disagreement to
be *recorded accurately while it exists*:

| state | `aiueos.tcb/validate` |
| --- | --- |
| runner below floor, `:floor-unmet-by-ci` absent | `:platform-floor-contradiction-unrecorded` |
| runner meets floor, `:floor-unmet-by-ci` present | `:platform-floor-contradiction-stale` |
| record names versions the workflow does not provision | `:platform-floor-contradiction-drift` |

Raising the runner to ≥ 25 and lowering the floor to 21 both fail until the
record is deleted, so the entry cannot rot into a comment about a contradiction
someone already fixed. The versions are read from the workflow with a regex
rather than a YAML parser: the value wanted is one scalar under a fixed key,
and a YAML dependency would put a parser inside the TCB this inventory exists
to bound.

### 4b. The checker is in the inventory it checks (2026-08-03)

`src/aiueos/tcb.cljk` was not in `:tcb/files`. Every other authority in this
repository — including `sbom.clj`, added a day earlier — is digest-recorded, so
editing it requires an inventory update in the same commit. The one file
exempt from that discipline was the file that *enforces* it: weakening a check
left no trace anywhere. It is now recorded as `:tcb-inventory-authority`.
There is no fixpoint problem, because the digest of the source lives in the
sibling EDN rather than in the source.

### 5. What is deliberately not adopted

The bare-metal object store stays **name-addressed**. `:kotoba-app-catalog`
looks applications up by a 16-byte id (`"app/hello"`) and uses SHA-256 for
admission only. Making it content-addressed — digest→bytes as the primary
table, id→digest as a second — would yield multi-version coexistence and a
generation list for free, but the store is `:capacity 4` with a 12 KiB
per-application ceiling and a `:rollback-window 1`; the addressing scheme is not
what constrains it today. Revisit after those bounds move, not before.

## Consequences

- The inventory is now a record that fails when it is wrong, in both halves.
- Advancing any runtime dependency requires updating the inventory in the same
  commit — deliberate friction, and the same discipline `:tcb/files` already
  imposes on in-repository sources.
- `deps.edn`, `security-adoption.edn` and the inventory are now mutually
  checked, so the shared security pin cannot advance in one and not the others.
  The recent revert of that pin (#138) is exactly the situation this covers.
- SBOM/SLSA provenance for release artifacts (`docs/deployment-profiles.md`,
  `regulated`) remains unimplemented. Reproducible byte-identical builds and a
  content-addressed dependency record are its two inputs, and both now exist.
