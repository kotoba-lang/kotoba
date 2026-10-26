# capability-log-write

Atomic authority package for `log/write`.

- imports: `#{:log-write}`
- effects: `#{:storage-write}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreia2tvn4wsiqplecdauyp5jdejlipajgfdh7jmbiqykznkjaxh37xy`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
