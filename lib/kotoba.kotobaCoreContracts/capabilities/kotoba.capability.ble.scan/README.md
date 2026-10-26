# capability-ble-scan

Atomic authority package for `ble/scan`.

- imports: `#{:ble-scan}`
- effects: `#{:personal-data :network-read :sensor-read}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreif5dhzyxaiosk2ieeue6zc34lfwenagzspxh3llukav6h3bt3v624`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
