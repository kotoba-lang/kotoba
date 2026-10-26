# capability-media-library

Atomic authority package for `media/library`.

- imports: `#{:media-library}`
- effects: `#{:storage-read :personal-data}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreihptf3oorxghrywq5mxelzpucotmjgbg7mhnwmzfdi7rtu3trbpxy`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
