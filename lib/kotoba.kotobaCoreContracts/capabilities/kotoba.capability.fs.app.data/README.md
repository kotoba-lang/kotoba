# capability-fs-app-data

Atomic authority package for `fs/app-data`.

- imports: `#{:fs-read :fs-write :fs-write-atomic}`
- effects: `#{:storage-read :storage-write}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreihsqjdfmgg7j7sptihq6ukmgqazfjd6xilfsbaw4i7lixld3bpvyq`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
