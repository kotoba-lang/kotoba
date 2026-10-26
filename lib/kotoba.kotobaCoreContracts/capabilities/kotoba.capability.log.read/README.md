# capability-log-read

Atomic authority package for `log/read`.

- imports: `#{:log-read}`
- effects: `#{:storage-read}`
- default policy: `:autonomous`
- semantic definition CID: `bafyreieqy2xrn2pxccxc4waj66iqhrflczkpmmuner2dpjlm6skyebixbe`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
