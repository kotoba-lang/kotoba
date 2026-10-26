# capability-image-metadata

Atomic authority package for `image/metadata`.

- imports: `#{:image-metadata}`
- effects: `#{:storage-read :personal-data}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreiaektr5t3hpmfpiymaixo7eywvbflykeon7bak5szkp6bvtrsv37e`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
