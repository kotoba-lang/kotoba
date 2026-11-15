# Stored execution manifest canonical value, 2026-11-15

The preserved hosted Otehon governed GiB fixture was read through
`recover-bound-ref` for its `allow` group. A one-off Babashka 1.12.218
extraction enumerated 1,038 addressed blocks, decoded values with the owning
`ipld.value/decode-value`, and found one execution manifest with the expected
version, data-commit and signature fields. Its 642 canonical bytes have CID
`bafyreidnfkxjdiausylnk7dqbftse7uulbx72mtcdw7njhgxfc63lfmdoe` and SHA-256
`6d2aae91a0149616d57c700967227e94586ffd32621dbed49cd728bdb5958371`.
The bytes are retained in `test/fixtures/native-execution-manifest.value`.
The reference decoder itself checks canonical re-encoding; the recovered
Forest reader checks the selected CID. The source experiment uses fixture
keys and identity transforms.

Extraction was local and read-only: Awai OS revision
`6ab4e28cad87caee01ea6774bbbb01264c76dac5`; Awai apex revision
`70ce27b8deb2e38727c3f5f0c71e3c0773d16845`; extraction script SHA-256
`cc8ec653545b0171e588015634b44e1a89e510cd5717e3e5c4c18cbbf24e8603`.
`otehon.ipld-forest`, `otehon.forest`, `otehon.storage`, and `awai.fs.car`
source hashes respectively were
`cb199a7bd3a0feda98ed2cfec95d2274c33fb6795d66b1b7761e2d61ba95792e`,
`e70032bf879806b3fb0d246f9e4bb8eae356407cd03c1ec12b44361108003dd0`,
`8b60c98ea047f0755980f845eef6ea8ea829a225bf676ee733651e6aa949d655`,
`b4233a14b1ffc22920223faaa451c9d99888d180519757cc4d30c86ddcd8553e`.
No reference runtime is used by the Native gate.

The Native gate reads those exact bytes with bounded FS2, checks the SHA-256
corresponding to the known CID, and applies the restricted canonical value
validator. Changed bytes and a forced validator refusal are caught. All 113
local macOS arm64 corpus cases passed. Positive executable SHA-256
`5383f303708cffc76e9ec3cd3106bd46aa60a6cd27ad565012b64c85a35cd0d2`;
source lock `9b51e6e13f2193681c855e20ce33c425765b965fcda9957670aac9f79851b738`.
This proves bounded byte canonicality and identity for this fixture only. It
does not parse the manifest fields in Native, check the signature, validate
its issuer registry, bind its location, evaluate policy or establish durable
publication. The receipt is persisted in Prolly datoms and has not yet been
independently decoded by this Native test.

## Native fixture signature verification

The Native `awai.fs.execution-manifest/verify` validates the bounded canonical
value and exact nine-field execution-manifest shape for the observed raw
64-integer signature profile. It removes `:signature`, re-encodes the value,
computes its DAG-CBOR CID and checks Ed25519 over the UTF-8 CID string. It
also requires the caller's expected data root, policy CID and authority epoch.
The actual stored fixture yields payload CID
`bafyreihygobs4lf6sjtx64ausw5ywi3j7nnsbdhb6sjhqjyflzscmjb6nq`. Babashka
1.12.218 independently reconstructed the unsigned bytes; Node 26.0.0 verified
the same stored signature with the fixture public key independently derived
from the known fixture seed. They are local references, not Native/CI runtime
dependencies. The source execution identity and contract at Kotobase revision
`c194a7d` have SHA-256
`9f7a05874e427f305c4d9d2cfc8679ead86f67d1e79ac423a2e8c8e488c0fe04` and
`06eed9b0601ea8d82570523c52f30005b3dc05bb1ffb5071f16749a3e9ef6510`;
the Otehon fixture signing source SHA-256 is
`b396c68621caf109c500bdb307e216b082b70e170475f1b20f048975ae220896`.

Changed signature, a different valid key, policy, data root and epoch were
refused, with separate negative controls. The full 118-case local macOS arm64
Native corpus passed. Positive executable SHA-256
`4f89a7983c6f80544bfd17413c0b9413e78051ee25f86142f94ab8d26b0014d2`;
source lock `d62c1bd1377533b3aa9a0915b6c7d205a518eb16f031260210b85af0ab52794d`.

This supersedes the earlier statement that the fixture signature had not been
checked in Native. It does not authenticate the caller's key, tenant, epoch,
policy or root; establish registry membership, freshness, rollback protection,
location binding or policy evaluation; or decode the separate receipt datoms.
The current registry-key signature envelope is a different profile and is
not supported by this raw-vector fixture verifier. Generic value parser
resource behavior remains unqualified for hostile production input.
