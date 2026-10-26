# capability-topic-publish

Atomic authority package for `topic/publish`.

- imports: `#{:topic-publish}`
- effects: `#{:ipc-write}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreif6xz5i6b3xwmjkrtjkqapicrvaaw4grje6ftlq4plogta3y7os7y`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
