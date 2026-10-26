# capability-corpus-publish

Atomic authority package for `corpus/publish`.

- imports: `#{:corpus-publish}`
- effects: `#{:data-egress :external-communication :network-write}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreidqbk6e7ywom6gg4g2zu3ppjm5l4qrz5mrzlces3vzz4xy4wavhju`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
