# Native signed checkpoint via stored snapshot, 2026-11-15

The local macOS arm64 Native fixture verifies the stored test proof's Ed25519
signature and logical commit, requires its physical-root field to equal an
independently caller-supplied trusted physical root, fetches the CID-checked
Kotobase Prolly engine manifest, follows its snapshot link and the snapshot's
SPO root link, and compares the complete bounded plaintext checkpoint to the
signed logical checkpoint. The real stored 61-Pack fixture passes; supplying a
different trusted physical root returns `:untrusted-physical-root`. Existing
missing Pack and bad proof controls remain in the fixture program. The
manifest accepts the source contract's engine versions 1, 2 and 3, and
rejects missing, duplicate and malformed relevant fields and links.

Artifact SHA-256 `8ba7ebaf46e0dceb0c129a2b8c5b7e531ad408043a0eb8d022fa2d53468c4241`;
source lock `9f96af92be9c5e763541e695fc9058cf4edf6bca5ff2f673d40066b3e07819d3`.
This program is local and opt-in, not a CI test. The fixture uses a test key,
identity encryption, and one real SPO leaf. The logical signature does not
sign the physical-root field; the supplied physical root must be authenticated
by an independent publication/authority mechanism. Caller also owns key
binding and immutable archive access. This is not proof of production
publication, encrypted query, policy/receipt or OS-cache-loss recovery.

## Native corpus gate

The original fixture's Pack 0 contains the manifest, snapshot and single SPO
leaf required for this verification. Its pinned 41,181-byte Forest archive
is now included as `test/fixtures/native-snapshot-pack.forest` (SHA-256
`5fefcde7d85a4a6a24b526856b2fa7d65561478b839f6ea9161d15608a1fe0b8`).
The existing Native corpus gate tests the real proof and this Pack together,
including rejection of a different caller-trusted physical root. All 101 cases
passed locally on macOS arm64; the positive executable SHA-256 was
`4850b2879512024b6362125c7923db41cee215b016cc452e96b07c3bf4b249d0`
and its source lock SHA-256 was
`dbfc0b1604379a5f1ec8479523903189e30e778a8de7b47bcb12c4ae3c234b3f`.
This updates the earlier statement that the snapshot test is opt-in only. It
still does not authenticate the physical-root field, issuer's key, or catalog.

## Arrangement schema version admission

The arrangement source selects a decoding codec by snapshot schema version.
The Native checkpoint path implements only the version 2 tagged component
profile, so it now requires integer `schema-version` 2 and refuses version 1,
unknown versions and non-integer values instead of interpreting them as v2.
Version 1 remains unsupported, not invalid under the owning arrangement
contract. The real version 2 fixture succeeds; value-level version 1, 3 and
text controls refuse, and a gate mutation accepting 3 instead of 2 returns the
expected failure. The full 102-case local macOS arm64 corpus passed. Positive
artifact SHA-256 `cef2b8b7c76b20ad7b1241f5b0dacc63890cd8c025a3c9b84c3a3f7fdf73a5f8`;
source lock `273556b888bda7693879b3adf7b94fc2042b82a64862eab0936e279514c05bb3`.

## Missing Pack and wrong public key controls

The combined stored snapshot verification now checks a missing Pack is refused
and a different valid Ed25519 public key returns `:invalid-signature`. A gate
mutation that treats the missing Pack as accepted is caught. The complete
103-case local macOS arm64 Native corpus passed; positive executable SHA-256
`5f9ebc17b62b5d7504fb7fb59c685c0caf85e1da4e551f58de77d5bdaa3b280e`, source
lock `01acb1e4b30cf208f52efbe96df10faf6221c5e49009a500376f8c81aaec6281`.
This demonstrates rejection for the fixture; it does not supply an issuer key
registry or authenticate the caller-provided physical root.
