# capability-secret-use-postgresql-cancel

Atomic authority package for `secret/use-postgresql-cancel`.

- imports: `#{:pg-cancel-register :pg-cancel}`
- effects: `#{:secret :network-write}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreihuljvacpas7hiknwoxfsho5crl4xnud65kfjjqkrcywqcotteq3q`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
