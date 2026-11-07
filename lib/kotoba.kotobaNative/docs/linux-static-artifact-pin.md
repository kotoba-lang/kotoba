# Select owning artifact main's canonical core

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200), Kotoba Labs.

This candidate advances native's existing artifact dependency from
`af43fc8fa43edb12361828e26456f75b12ab40be` to
`b6e3ab59611e747dcc9a72c4152cb59384951190`, freshly read owning main.
The old standalone native pin lacks canonical `core.kotoba`; this target
contains the owning merged source from artifact #68, blob
`ff7f780734f55b730505023522a3c76b11cb46d9`, SHA-256
`f5b7fcd84bcf148fad70a645f12395939c112ab7a7534ac825e739b2662e13a4`.
No staged artifact checkout source is substituted into the dependency pin.

Amu main `7872d10f587a2d4a0b92bc124037915e34c0cf26` selects
`ce6f82d398467ba5504c8d377b47a8ca2dc185c3` in both its deps and root lock.
That revision is one commit after owning main, changing only
`runtime_identity.cljk`'s C-loader source identity constant. Its canonical
core is the identical blob above. This namespace does not import that loader
identity module. Root pin/lock normalization remains separate work; no Amu
lock is changed here and no C-loader identity requirement is added to native.

## Reviewed source surface

The immutable old-to-target range is 246 commits and 33 changed paths.
The file inventory includes hosted `.cljc`/`.clj` to `.cljk` changes,
canonical core/source-identity modules, content/descriptor/execution/runtime
identity work, dependency/configuration and documentation changes, legacy
test infrastructure, license material and removal of tracked cache files.
The selected source review is the complete imported core namespace and its
manifest/caller boundary; it does not claim all other artifact components
are migrated or qualified.

Native source imports only `kotoba.artifact.core`, with calls to
`valid-seal?`. The canonical module has no namespace imports and retains all
five public functions: canonical-bytes, edn-safe, seal, sha256, valid-seal?.
All five take one document argument. All 22 canonical function definitions
are retained, including container/scalar canonicalization and the complete
digest comparison; no caller-precomputed seal shadow is used.

A source-only feature reader selected the old/target `:clj` and `:cljs`
branches and compared all six function forms for each: no added, removed or
changed definition. It also compared all 22 target `:kotoba` reading function
forms with the target canonical `.kotoba` file: no difference. This is a
source preservation observation, not executed compatibility evidence. No
host oracle or legacy runtime was invoked.

The target dependency manifest adds contract/ABI/test/multiformat/IPLD floors
and updates osaho/text/bytes/error metadata. Those namespaces are not imported
by canonical core. Its actual effect dependency is `hash/sha256`, retained as
a real native capability. The owning route/profile proposals are
[Amu #1440](https://github.com/kotoba-lang/amu/pull/1440) and
[Kotoba #805](https://github.com/kotoba-lang/kotoba-lang/pull/805); both are
draft/unmerged. Their source presence is not provider availability.

The current static graph reader includes fourteen native modules (including
the complete filesystem framing module), owning candidate ELF64 and this
exact canonical artifact core: 16 sources, 33 schemas, 558 imported calls,
439 record uses and 585 explicit type argument positions, with no
source-contract findings. The hash capability remains
explicitly unqualified. Artifact/core's 200-line/22-function source inventory
has balanced delimiters, matching call arities, known heads and no local
data-as-function calls. These checks do not perform native type admission.

## Qualification still open

The selected core source itself documents digest-domain differences involving
other control characters in strings, floating-point text, native versus
UTF-16 key ordering and distinct map keys with equal canonical text. They
are also present in Amu's selected core, not resolved by aligning a
pin or comparing source forms. Full-domain artifact/seal behavior must be
resolved and qualified under the owning format contract; do not narrow valid
input, silently change the digest protocol or replace real seal validation.

Native admission, actual hash provider/decision artifact, byte/refusal/resource
behavior, Definition CIDs, owning ELF64 #8 landing/pin integration, required
ABI/helper closure and whole compiler self-rebuild remain open. This pin
change provides the canonical dependency in a draft; it does not qualify an
executable packager, a compiler or CDCI.

No compiler, dependency resolver, generator/encoder, artifact/digest/runtime
or test was executed. Only source files, source hashes, feature forms, Git
ancestry and remote metadata were read. Shared artifact staged WIP and all
other checkouts remain preserved. No workflow/protection or service changed.
