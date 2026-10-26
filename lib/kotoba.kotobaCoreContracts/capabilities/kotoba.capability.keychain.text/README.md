# capability-keychain-text

Atomic authority package for `keychain/text`.

- imports: `#{:keychain-read :keychain-write}`
- effects: `#{:storage-read :secret :storage-write}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreidnq4zz2tzytf5yk2sbhfkmvyc4o3qm6gkvuqykij37obvf4tkm4a`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
