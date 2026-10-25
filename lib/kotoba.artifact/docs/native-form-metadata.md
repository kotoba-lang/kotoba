# Native Form metadata candidate

`kotoba.artifact.data` stores compiler metadata as the existing typed
`:form/r` tree. A 51-field ABI, 36-slot table and multi-megabyte code payload
are metadata; converting them to guest `:document` values would violate its
32-item, 4096-node, depth-8 and 65536-byte bounds. Those bounds remain intact.
The explicit `value-to-document` bridge checks them before encoding the
small headers consumed by the owning ELF object library.

`kotoba.artifact.form-seal` carries the existing core canonicalization and
seal rules over that tree. The existing `core.kotoba` implementation stays
unchanged. Form's implementation is supplied and source-pinned by the native
compiler project; this change adds no engine/compiler repository to this
contract's default dependency manifest. Consumer lock/provider integration
and neutral Form ownership still need review before release.

Actual AArch64 Linux native execution passed:

- 51-field metadata, byte equality/inequality including nested maps and
  differing byte lengths, and replacement in an unordered input map;
- canonical bytes against unchanged artifact.core and five literal goldens:
  key order, shared-namespace lifting, set normalization, lists and bytes;
- real native SHA-256 empty/abc vectors, valid seal acceptance, and refusal
  after changing one byte without resealing.

No C/JVM/Node compiler or C loader produced these test executables. They
were compiled by the measured Amu core and framed by its native FS2 packager.
The current Form byte-equality correction in Amu is required and is pinned
in the consumer source evidence.

This remains an optional draft API, not full-domain artifact qualification.
F64 canonical rendering, full control/UTF16/equal-canonical-key behavior,
source/lock/Definition-CID integration, public profile/verifier and complete
compiler/CLI admission remain open. Unsupported rendering traps rather than
inventing a digest. Positive small fixtures do not close those gates.
