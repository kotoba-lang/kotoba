# capability-graph-kotoba

Atomic authority package for `graph/kotoba`.

- imports: `#{:kgraph-assert! :kgraph-retract! :kgraph-query :kgraph-get-objects}`
- effects: `#{:storage-read :storage-write}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreickhutw3mtv7lx3meut2fttyy3zhotjssfwetzbk2h3vbsh2jijx4`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
