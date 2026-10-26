# capability-identity-keypair

Atomic authority package for `identity/keypair`.

- imports: `#{:gen-keypair}`
- effects: `#{:secret :crypto}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreidkcpvwubutyhbrlu6cc2kib3nnb6xxyic5mphlrzy2m3finsbb7u`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
