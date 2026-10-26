# capability-notify-show

Atomic authority package for `notify/show`.

- imports: `#{:notify-show}`
- effects: `#{:user-attention :external-communication}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreie2kkq346o26m4p6prvbty3tbyv3wts3pw3eymvjildgjniw5v7he`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
