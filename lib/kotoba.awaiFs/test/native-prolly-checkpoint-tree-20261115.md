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
