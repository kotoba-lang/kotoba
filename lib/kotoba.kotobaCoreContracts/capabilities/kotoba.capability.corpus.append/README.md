# capability-corpus-append

Atomic authority package for `corpus/append`.

- imports: `#{:corpus-append}`
- effects: `#{:storage-write}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreifx4pqnfagcbn63jkfcds36gwnmxt5yatc7ynmjzbm53iqv5jbice`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
