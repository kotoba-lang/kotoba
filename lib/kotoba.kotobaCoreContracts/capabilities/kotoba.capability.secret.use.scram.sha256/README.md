# capability-secret-use-scram-sha256

Atomic authority package for `secret/use-scram-sha256`.

- imports: `#{:scram-sha256}`
- effects: `#{:secret :crypto}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreicv3kxlcmko35fxsrnonf7edsmwmvzjto5qykjsxjwln54w6727d4`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
