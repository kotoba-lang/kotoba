# ADR-0017 — SBOM and SLSA-style provenance, derived from the TCB inventory

- Status: accepted
- Date: 2026-08-01
- Related: ADR-0016 (content-addressed TCB), `docs/deployment-profiles.md`
  (`regulated`), `com-junkawasaki/root` ADR-2608012050

## Context

`aiueos.deployment-profile` has required `:sbom-digest` and
`:provenance-digest` from `:regulated` evidence since it was written, and
`kotoba.security.supply-chain/evaluate-attestations` — in the shared security
package this repository already pins — has been able to judge those documents
for just as long.

Nothing produced them. The only values that ever reached the checks were the
strings `"sha256:sbom"` and `"sha256:provenance"` in
`deployment_profile_test.cljc`. Two more required keys were in the same state:
`:tcb-inventory-digest` and `:tcb-drift-check?` were satisfied by literals
rather than by the inventory.

This is the third instance of one pattern in this repository, after ADR-0016's
uncheckable `:tcb/external` and the transitive closure it later added: **a
control exists, its evaluator exists, and the evidence it consumes is a
placeholder.** The evaluator passing says nothing in that state.

## Decision

`aiueos.sbom` produces both documents for a built artifact, and the evidence
map the regulated profile asks for.

### Components are the TCB inventory, not a second scan

`qualification/tcb-inventory.edn` is already content-addressed in all three of
its halves — in-repository sources, declared dependencies, and the loaded
classpath closure. That *is* an SBOM component list. Deriving the SBOM from it
means the two cannot disagree, and the inventory's own fail-closed drift check
is what keeps the SBOM honest.

A second discovery pass would have been the obvious implementation and the
wrong one: it would drift from the inventory, and nothing would notice.

A dependency with no content address (`java.base`) carries its
`:component/assurance-gap` into the SBOM. An SBOM that silently omits the
caveat is worse than one that omits the component.

### Nothing in the documents is asserted where it can be computed

- `:sbom/generator-digest` is the digest of `src/aiueos/sbom.cljk`, so a changed
  generator cannot quietly produce the same claim. That file is now in
  `:tcb/files` as `:release-attestation-authority` — compromising it falsifies
  production evidence, which is exactly the inventory's stated scope.
- `:tcb-drift-check?` is the inventory check's real verdict. Evidence for a
  drifted tree reports `false` rather than claiming a check that did not pass.
  This was not theoretical: adding this namespace drifted the inventory, and
  the test asserting the evidence caught it before anything was committed.
- `:provenance/isolated-builder?` is **required from the caller and never
  defaulted to true**. `aiueos.sbom` cannot verify the build environment, and
  hardcoding the value would make every local build claim an isolated builder —
  the failure mode the document exists to rule out. A test asserts the default
  is `false` and that the evaluator rejects it.

### One canonical signed form, not two

Signing is Ed25519 over the canonical document form owned by
`aiueos.key-lifecycle`, generalized from its lifecycle bundle so an attestation
and a bundle sign the same way. A second canonicalizer would be a
signature-confusion hazard, not a convenience.

The production key stays offline: `-main` emits unsigned documents and the
caller signs them, the same split the release-receipt signing already uses.
Tests sign with an ephemeral keypair, as the release-receipt signing gate does.

### The artifact digest is an input

`kbb -M:attest <artifact-digest> <source-commit> [builder] [--isolated]`.
The digest is the release build receipt's `disk.sha256`. It is passed in rather
than parsed out of `aiueos-x86_64-build-receipt.json`: this namespace is in the
TCB inventory, and a hand-rolled JSON reader inside it would be new parsing
surface for no benefit.

## Consequences

- `:regulated` supply-chain evidence is computed. The four keys that were
  literals — `:sbom-digest`, `:provenance-digest`, `:tcb-inventory-digest`,
  `:tcb-drift-check?` — now come from the inventory and the documents.
- Changing any TCB source changes the SBOM, so a release attestation is only
  reproducible from a tree whose inventory check passes.
- Nine tests cover the round trip through the shared evaluator plus six
  fail-closed cases: unsigned, wrong artifact, provenance detached from its
  SBOM, and an unisolated builder.

## Not done

- **Wiring into the release pipeline — blocked on a workflow edit, not on
  design.** `os/aiueos/scripts/build-release-image.sh` does not call
  `kbb -M:attest`, and no gate requires an attestation to exist for a
  release. The generator is ready. The blocker is that the only job which
  builds release media — `bare-metal-uefi` — provisions no JDK, and
  `.github/workflows/` cannot be edited by a token without the `workflow`
  scope. Writing the call into the shell script alone would produce a step that
  never runs in CI, which is the unexercised-surface failure this ADR exists to
  remove.

  The edit is small enough to state exactly. In `bare-metal-uefi`, after the
  release-media step:

  ```yaml
      - uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "21"        # or 25 — see ADR-0016 §4, unresolved
      - uses: DeLaGuardo/setup-clojure@13.4
        with:
          cli: latest
      - name: Attest the release media
        run: |
          receipt=$(os/aiueos/scripts/build-release-image.sh)
          digest=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["disk"]["sha256"])' "$receipt")
          kbb -M:attest "sha256:$digest" "$GITHUB_SHA" "github-actions" --isolated \
            > "$RUNNER_TEMP/release-attestation.edn"
  ```

  `--isolated` is only truthful on a hosted runner; a local build must omit it,
  which is why `provenance` requires the flag rather than defaulting it.

  Once that runs, `evaluate-reproducibility` (below) becomes reachable too: a
  second invocation of the same script in the same job yields the second
  artifact digest the evaluator wants, and `SOURCE_DATE_EPOCH` already makes the
  media deterministic.
- **In-toto envelope format — not queued, declined for now.** These are EDN
  documents matching the shared evaluator's contract, not in-toto/DSSE
  statements. The earlier wording ("a serialization concern on top of the same
  content") made it sound merely pending. The reason it is not done is a
  trade-off, and leaving it unstated invites someone to do it: DSSE payloads
  are JSON, this repository has no JSON library, and both ways of getting one
  are worse than the gap. Adding a dependency expands the TCB — which the
  inventory would correctly force us to record — for a format nothing in this
  workspace reads; hand-rolling a writer puts new serialization surface inside
  a namespace that already refuses hand-rolled JSON *parsing* for the same
  reason (`aiueos.sbom/-main`'s docstring). Emitting a standard envelope with
  no verifier consuming it would be a second unexercised surface, which is the
  exact shape of the placeholder problem this ADR exists to remove. Worth doing
  when an actual external verifier (cosign, slsa-verifier) enters the release
  path — and then with a round-trip verifier and the DSSE PAE test vector in
  the same commit.
- **`evaluate-reproducibility`.** The other half of
  `kotoba.security.supply-chain` still has no evidence here: it wants two
  artifact digests from independent builds. The release media are already
  byte-comparison gated (ADR-0013), so the input exists; connecting it is
  follow-up.
