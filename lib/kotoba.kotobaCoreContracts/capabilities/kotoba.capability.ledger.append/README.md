# capability-ledger-append

Atomic authority package for `ledger/append`.

- imports: `#{:host-i64-roundtrip}`
- effects: `#{:integrity-record :storage-write}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreicbn6qf7ruclpja2dx7ll4qzxtui5lps7fffsnvtjudthoxhobqgm`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
