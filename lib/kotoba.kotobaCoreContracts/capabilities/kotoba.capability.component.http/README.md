# capability-component-http

Atomic authority package for `component/http`.

- imports: `#{:http-open :http-close :http-write :http-read :http-get}`
- effects: `#{:data-egress :network-read :network-write}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreicr2bcxbqzyhbzlxrojt2cfjwprqfhj2h5bxvmusoavi3cu5kpd7i`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
