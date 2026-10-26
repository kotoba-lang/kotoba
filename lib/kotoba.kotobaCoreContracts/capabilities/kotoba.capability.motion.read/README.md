# capability-motion-read

Atomic authority package for `motion/read`.

- imports: `#{:motion-read}`
- effects: `#{:personal-data :sensor-read}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreibwyyumt55iyiy7ycqdnnksj44i2hslssjkmmae52uag7tmoztcbe`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
