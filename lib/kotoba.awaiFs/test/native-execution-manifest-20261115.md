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
