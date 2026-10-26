# capability-net-connect

Atomic authority package for `net/connect`.

- imports: `#{:transport-connect}`
- effects: `#{:network-write}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreihms4lg3hwgdxuhb7ukxslmae2ah3m3fex5gwjua4oqg26mwq2spi`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
