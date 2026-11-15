# Native Forest checkpoint traversal, 2026-11-15

`awai.fs.prolly-checkpoint-tree/root` walks CID-checked Forest blocks using a
bounded pending queue, collects supported plaintext leaf datoms, and computes
one canonical checkpoint. It rejects read and decode errors, malformed child
links, duplicate logical datoms, more than 256 nodes, depth 32 or more, more
than 256 datoms per leaf, and more than 1024 total datoms. These bounds are
implementation limits, not approved production limits. Caller supplies a
trusted root and must ensure archive immutability and appropriate decryption.

Local macOS arm64 Native fixture: the real stored single SPO leaf matches the
checkpoint in the signed fixture commit. A synthetic internal node whose
second child is not a Prolly leaf is rejected; adding the same leaf twice is
rejected as duplicate datoms; removing a Pack causes the existing test to
fail. Native executable SHA-256
`062fab098250ffbeaeb9a689d5b2a474002c9ffec787b8d5b6df46c65bea7207`,
source lock `02f1f1bdb113a30ccfc3306b932755b33cb1b43a6cc924ab913cbfb1e90935bf`.

No successful real multi-leaf tree has been validated yet. This is not an
authenticated snapshot publication, a full structural validation of Prolly
key ranges, encrypted value handling, policy evaluation, or a general
production Datalog checkpoint verification. A signed checkpoint comparison
still requires the caller to bind the issuer, root and storage to authority.

## Two-leaf synthetic Forest, later on 2026-11-15

Split the two actual fixture entries into separate plaintext leaves, created a
synthetic two-child root, and stored the three CID-addressed blocks in
`test/fixtures/native-two-leaf.forest` (1,087 bytes; SHA-256
`811e65afc12e358e1cc8a9c5e4b9f938ce7f330ff41d3232c5ad12d3821749ee`).
The root is `bafyreihm5mmdalgjj53fkb7dbo5d7tdlfvrdegu37vo6zlgks367kfwetm`.
Native traversal returned the same signed checkpoint as the original fixture.
The synthetic branch uses arbitrary separators, not independently validated
Prolly key ranges; it does not establish production tree integrity or
publication. Initial Zstd output required an unsupported table mode; the
fixture uses raw Zstd frames. Local Node and zstd generated the fixture; they
are not Native runtime dependencies. The 61-Pack fixture and this test remain
local/opt-in rather than CI. This supersedes the earlier statement above that
no multi-leaf success had been observed. Native executable SHA-256
`b14f76df1aea8a2510f64ebe60b2f1b8225ca9c9824c6cf31e012fec1acfa4d1`,
source lock SHA-256
`5a5661b3fb5acdc19af0ef59cd68de7301c87317c10e351e1f737bf3a5d911ff`.
