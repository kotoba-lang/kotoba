# ADR 0274 — Itonami OS is an AIUEOS distribution

- Status: accepted direction, owner instruction 2026-10-26. Candidate metadata selection implemented; full distribution release remains separately qualified.
- Display name: **Itonami OS** (owner instruction, renamed from AWAI OS on the same date; distribution ID `awai`, repository, kernel and ABI are unchanged). This file name keeps `awai-os` for link stability.
- Tracking: [AWAI-84](https://linear.app/kotobalabs/issue/AWAI-84), [AWAI-89](https://linear.app/kotobalabs/issue/AWAI-89), [AWAI-92](https://linear.app/kotobalabs/issue/AWAI-92).

## Decision

**AIUEOS is the common OS foundation. Itonami OS is the Awai Network distribution
of AIUEOS, maintained in the same `kotoba-lang/aiueos` repository.**
The distribution ID is `awai`; the general foundation ID remains `aiueos`.
Do not create another OS repository, kernel, syscall ABI or permission system.

| Owner / name | Responsibility |
|---|---|
| `kotoba-lang` / Kotoba | Reusable language, libraries and implementation/tooling ecosystem |
| Amu / Kototama | Compiler/target generation and the common execution/state/authority-budget/receipt contracts |
| AIUEOS | Shared OS, boot, device/memory/process enforcement and reusable desktop mechanisms |
| `network-awai` / Awai Network | Distributed network, node/service composition, governance/operations and product distribution |
| Itonami OS | Awai-oriented AIUEOS distribution: identity/display name, intended component set, defaults and release composition |
| Awai Node / Itonami | Logical host and agent workspace components, also available on other qualified OS hosts |

AIUEOS remains useful independently of Awai membership. Running Itonami OS is not
required to participate from another qualified host. OS distribution, node,
Cell, principal, hardware and network are different identities. Murakumo
continues to name dedicated hardware and its separately described compute
service, rather than every machine's OS.

## Same core, explicit composition

Generic OS fixes belong in the common core. Awai-specific branding, component
selection/defaults and integration documentation belong in `distributions/awai`.
The default `aiueos` distribution and `awai` use the same native core build path.
Distribution is independent of ISA/target, runtime class, security/assurance
profile and diagnostic entry (`desktop`, local draft, user target, etc.).
Selecting a distribution must not silently select an unqualified target or
route to a legacy compiler/runtime.

The current native desktop builder stages the static descriptor and pins its
size/digest in the existing candidate record. `--distribution awai` changes
composition metadata only: the same input core produces the same kernel, EFI,
font and diagnostic boot media. Intended Itonami, Awai Node and Console
components still require their own immutable release/artifact references and
admission; the descriptor does not install or qualify them.

The distribution release must bind the common core/source revision,
distribution configuration digest, component release IDs/digests, target/host
profile and qualification receipts in the **existing OS manifest/signing/update authority**.
App releases retain their separate app authority (AWAI-86); the public catalog
(AWAI-92) carries verified references to both rather than mixing their trust
roots. Composition may produce different final release bytes without
creating a different kernel lineage. No new signer/trust root, update channel,
VM semantics or app identity is created by this naming decision.

## Preserve authority and evidence

Distribution selection grants no capability, node enrollment, Cell membership,
service endpoint approval or inference access. Reuse canonical admission,
signer and client-runtime/broker contracts. Keep app UI/workflow/state local
to the user and the app origin static. Network, model and artifact operations
continue to require their existing operation-specific trusted consent.

Retain `aiueos.*` namespaces, repository, CLI compatibility, syscall/profile
IDs and historical receipts. App release/source/interface/profile identity,
mon CID × agent Cell and verified head survive a distribution choice; fresh
host admission still applies. Distribution ID alone is not migration authority.
Do not rewrite old signed manifests/CIDs or relabel a NixOS installer / Linux
VM monitor preview as an AIUEOS-based Itonami OS image.

Browser/CSSOM (JUN-93), user target (JUN-414), workspace image (AWAI-90/JUN-145),
release (AWAI-86/92), independent node recovery and physical hardware acceptance
retain their own states. A same-core candidate build proves neither all those
components nor a released Itonami OS installer.

## Migration

1. Establish this common-core/distribution distinction in both owner docs and
   Awai's public-source guides, preserving existing runtime evidence.
2. Select `aiueos` or `awai` at composition time and bind the descriptor bytes
   alongside the common core candidate. Unknown IDs refuse before building.
3. Connect admitted Itonami/Node/Console component releases to the Awai preset
   through the existing release contract; qualify actual workflows and restore.
4. Publish a verified distribution release/download through AWAI-92 only when
   the existing target, signature, rollback and compatibility gates pass.

See [distribution inputs and usage](../../distributions/README.md).
