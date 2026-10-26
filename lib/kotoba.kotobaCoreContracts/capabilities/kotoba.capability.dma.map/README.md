# capability-dma-map

Atomic authority package for `dma/map`.

`kotoba/capability/dma/map.kotoba` is the native provider helper surface. It
centralizes descriptor ownership bits and the x86-64 release fence used before
and after ownership publication. The host-side contract records the required
TX/RX operation order so a NIC provider cannot silently move the doorbell or
OWN write ahead of descriptor contents.

- imports: `#{:dma-map}`
- effects: `#{:memory-access :device-control}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreies4n3abl6d5ei6mfmcel3xsn7lcjqzyn43hboqgk54wsccudtf6u`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
