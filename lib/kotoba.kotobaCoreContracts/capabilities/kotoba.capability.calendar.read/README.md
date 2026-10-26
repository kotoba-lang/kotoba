# capability-calendar-read

Atomic authority package for `calendar/read`.

- imports: `#{}`
- effects: `#{:storage-read :personal-data}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreianwq3237kfalo2fq7iyyz5malxuq5xc5dutdmwefpgfn4stvttfe`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
