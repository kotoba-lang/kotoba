# capability-clipboard-text

Atomic authority package for `clipboard/text`.

- imports: `#{:clipboard-write-str :clipboard-write :clipboard-read}`
- effects: `#{:personal-data :device-write :device-read}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreiaxbofwaxy67dxkumckokaaoewmr6w3lfuuahz2kpgzrlica3yl6e`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
