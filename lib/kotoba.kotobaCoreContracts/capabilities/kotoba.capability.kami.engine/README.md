# capability-kami-engine

Atomic authority package for `kami/engine`.

- imports: `#{:kami-despawn-within! :kami-axis :kami-set-velocity! :kami-nearest-tagged :kami-despawn :kami-tick-n :kami-get-z :kami-get-x :kami-get-y :kami-count-tagged :kami-set-position3! :kami-move-tagged-toward! :kami-set-velocity3! :kami-spawn :kami-rand :kami-set-position!}`
- effects: `#{:simulation-read :randomness :simulation-write}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreidxirwdhcrdzsyz3fanh3qbalae5yugpvm3l76rj2q5tfuh3i27gq`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
