# capability-mmio-map

Atomic authority package for `mmio/map`.

`kotoba/capability/mmio/map.kotoba` provides the native width/alignment/range
validator. The admitted device provider keeps the actual 8/16/32-bit intrinsic,
so importing this pure helper cannot create ambient MMIO authority. Every
provider access still carries the region length and relies on Amu's rooted-region
proof before the backend emits it.

- imports: `#{:mmio-map}`
- effects: `#{:memory-access :device-control}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreigeh26tuyndf55r2d3garz4m3dndcgumlalu6x2mnhvhtuctu3l5i`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
