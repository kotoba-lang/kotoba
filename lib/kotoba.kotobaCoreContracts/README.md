# kotoba-core-contracts

CLJC/EDN authority for Kotoba source classification, package contracts, and
runtime boundary data.

This repo owns semantic contracts used by the launcher/runtime:

- `resources/kotoba/lang/source_contract.edn`
- `resources/kotoba/runtime/capability_contract.edn`
- `resources/kotoba/runtime/boundary_contract.edn` — judgment-free boundary
  encoding descriptor (`:kotoba.lisp-machine/boundary-v1`, shapes only; see
  `kotoba-lang/kotoba-lang` `docs/adr/ADR-kotoba-lisp-machine-contract-decisions.md` D1)
- `src/kotoba/core/contracts.cljk`
- `src/kotoba/core/actor_capability.cljk` — actor responsibility to bounded
  `actor:host` authority, envelope emission, and host-neutral revalidation
- `src/kotoba/core/capability_repository.cljk` — one capability per repository
  catalog and conformance rules
- `src/kotoba/lang/package_contract.cljk`
- `src/kotoba/lang/package_registry.cljk`
- `src/kotoba/lang/package_registry_network.cljk`
- `lang/package-conformance/`

Launchers and native/Wasm adapters consume these contracts. They do not own
source kind semantics, package validation/registry semantics, capability ids,
or host import ABI shape.

## Test

```sh
kbb -M:test
```

## Atomic capability packages

An authority capability has its own logical package and admission boundary.
The maintained sources now co-locate in `capabilities/kotoba.capability.*`;
`capabilities/catalog.json` maps each dotted source ID and exact old repository
alias to that subtree. Composition capabilities remain in Tamaki and never
receive HostCaps directly. The authority's own default dependency/classpath
closure is unchanged; providers are explicit opt-in package roots.

Capability imports follow Kotoba's Unison-like semantic identity boundary:
the repository name and Radicle RID are discovery aliases, while
`:capability/definition-cid` is CIDv1 over a canonical DAG-CBOR definition
block containing the exact ABI, imports, effects, default policy and artifact
format. Renaming or moving a repository preserves identity; changing authority
semantics creates a new CID. The hash rules are themselves pinned by
`:capability/hash-contract-cid`.

```sh
kbb -M -m scaffold-capability-repos /absolute/output/root
```

The generator refuses to overwrite an existing directory. Generated packages
are contract-only until a reviewed, signed, content-addressed Wasm component
is published.

## Reference-implemented providers

Atomic packages may advance from `:contract-only` to `:reference-implemented`
when they publish:

- `artifacts/*.wasm` with matching `:sha256`
- `:exports` describing actor:host field ABI
- `:signature :reference-unsigned` (or a real signature map) for the pure-compute
  allowlist (`math/sin`, `math/cos`, `hash/sha256`, …)

Definition CIDs do **not** change when a package gains a reference provider —
provider status and digests are outside the semantic definition block.
Production signing remains a separate ceremony.

See [the source co-location decision](docs/adr/0002-capability-source-monorepo.md)
for verified source/history mappings, semantic CID aliases, the unregistered
package refusals and the distinction between source lookup and admission.


## Target-neutral and distributed stack architecture

Owns existing source/package/capability boundaries. Target-neutral execution descriptors currently in abi are the planned migration candidate, after full export/consumer inventory and a versioned contract. This repository does not absorb language, VM or protocol semantics. Existing codec/crypto/I/O dependencies must be measured per entrypoint before claiming a contract-only closure.

See the [owner integration guide and dependency direction](docs/stack-architecture.md),
[composition metadata](spec/stack-integration.edn), and
[whole-stack refactor procedure](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-refactor-procedure.md).
The direction is adopted; runtime contract migration and qualification remain
explicit, separately verified work. Tier labels are responsibility axes, not
a single dependency ranking.

## Implemented neutral / target-profile boundary

`kotoba.core.execution` owns bounded semantic ability, stream, plan, policy and
approval data, plus explicitly versioned neutral v2 identity/lease validators.
Its complete source closure has no requires and imports no WIT, engines, DB,
network or consensus. `:target` in an ability is a resource selector.

`kotoba.abi.component` owns Component worlds/imports/admission/authority fences
and the unchanged mixed v1 identity/lease codecs. `kotoba.abi.contract` preserves
all 46 existing exports as compatibility aliases. New consumers choose an
explicit entrypoint. No v1 block, signature, WIT output or existing runtime
admission shape is rewritten automatically. V2 identities reference the CID of
a target-owned binding; hosts must verify its bytes, profile, interface and
artifact before granting authority. A v2 block needs a new CID/signature.

Component v1/v2 bindings are implemented here; unknown targets/profiles refuse.
Native/Script/EVM bindings must be owned and qualified by their selected backend,
not encoded as nil WIT fields. V2 runtime admission is not enabled by this API
refactor, and this is not Q9 source migration or target qualification.

## Explicit v2 execution

See [execution v2](docs/execution-v2.md) and [owner contract](spec/execution-v2.edn).
New target bindings, authority-issued invocation/leases and authenticated admission
are explicit APIs; existing v1 runtime defaults remain compatible.
