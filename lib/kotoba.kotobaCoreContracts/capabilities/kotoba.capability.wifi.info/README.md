# capability-wifi-info

Atomic authority package for `wifi/info`.

- imports: `#{:wifi-info}`
- effects: `#{:personal-data :network-read}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreigvcwfcziiysfpgvdnldbyfx732bwcmth7yknuo5vgvdp6l2gwr6q`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
