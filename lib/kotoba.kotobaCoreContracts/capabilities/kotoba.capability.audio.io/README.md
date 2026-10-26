# capability-audio-io

Atomic authority package for `audio/io`.

- imports: `#{:audio-play :audio-record}`
- effects: `#{:personal-data :sensor-read :device-write}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreifi36bkriel3h276si25f7gqmmboglsptf4fuyickq4r3ksgpueuy`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
