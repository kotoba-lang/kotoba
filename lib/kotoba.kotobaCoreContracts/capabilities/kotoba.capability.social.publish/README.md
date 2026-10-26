# capability-social-publish

Atomic authority package for `social/publish`.

- imports: `#{:social-publish :social-publish-receipt}`
- effects: `#{:data-egress :external-communication :network-write}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreicwvmvyfnt65xcx3bxcgn25r2pbzy4a65p7fusezvlplhabbrz5f4`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
