# capability-http-post

Atomic authority package for `http/post`.

- imports: `#{:http-post-headers :http-post}`
- effects: `#{:data-egress :network-write}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreie3bulylbyjelufa36utklje7jc7yajunmzhkfaptdhfof7uml3fu`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
