# Native Huffman weight validation, 2026-11-15

`zstd.huffman-tree/complete` bounds explicit weights and restores the implicit final weight by requiring the residual contribution to be a power of two. It rejects invalid weights, an empty tree, excessive depth and invalid rank-one counts. It does not construct a prefix lookup table or decode literals.

Native macOS fixture test reads the actual Otehon Prolly leaf's compressed weight stream and verifies all 248 completed weights against the earlier one-time libzstd 1.5.7 `HUF_readStats` oracle: SHA-256 `1b43db0f11c2b2163d0e44d34e6dbc60cd75585021cebbf869fac529b9170a4c`, tree log 9. It rejects a weight of 13 and `[2 2]`, and continues to reject missing Pack and invalid FSE input. Executable SHA-256 `418eb7cc280331b4cbcea7cbd8ac493c86f5efae0dd80d29dc0c420a072f3b7b`; source lock `4e9502c4900f3bbb006010911665782b5886c5884e4208a7882ddeab47268eb0`. Scratch outputs retained under `.agent-output/native-huffman-tree-20261115/`.

The focused test is not part of CI. The fixture is not Native-authenticated, and leaf decompression, Datalog querying, actual policy and OS-cache-loss recovery remain unverified.
