# capability-topic-subscribe

Atomic authority package for `topic/subscribe`.

- imports: `#{:topic-take :topic-poll :topic-count}`
- effects: `#{:ipc-read}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreigkvweek5rgl3dunw3wytf5fntsrguqvbs5ggh36pzsrm7rteribq`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
