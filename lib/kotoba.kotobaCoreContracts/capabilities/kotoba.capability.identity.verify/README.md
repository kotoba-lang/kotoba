# capability-identity-verify

Atomic authority package for `identity/verify`.

- imports: `#{:verify}`
- effects: `#{:crypto}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreihhb6p7hxdjzjyvbpaurlj2c2qyk5rlpmcxgctonocurgyjgv3hgu`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
