# capability-system-metrics

Atomic authority package for `system/metrics`.

- imports: `#{:system-metrics}`
- effects: `#{:system-read}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreiekxo23beylwworwhhe7l3mqyca5kqxltycim44ekv7efwddn5ib4`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
