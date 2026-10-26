# capability-cc-warc-extract

Atomic authority package for `cc/warc-extract`.

- imports: `#{:cc-warc-extract}`
- effects: `#{:network-read :storage-write}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreihrdbnvik6t5uelylmy6izovyhrmm45iea3iwj3sbyvpv2n5mcv2a`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
