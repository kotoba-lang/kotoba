# capability-pci-config

Atomic authority package for `pci/config`.

- imports: `#{:pci-config}`
- effects: `#{:device-control}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreih7yldsopdyqnvxbfpper2iaupahvm6dsyoczrn5sdaepapis2zey`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
