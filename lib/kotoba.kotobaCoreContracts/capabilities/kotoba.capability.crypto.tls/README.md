# capability-crypto-tls

Atomic authority package for `crypto/tls`.

- imports: `#{:tls-server-end-point :tls-open}`
- effects: `#{:secret :network-write :crypto}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreigdvsgjdztxnklhnwn3c4mcl4vn7r4gz3hkxh2ryqlgvo6xb3lwq4`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
