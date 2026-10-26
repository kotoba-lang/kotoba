# capability-process-list

Atomic authority package for `process/list`.

- imports: `#{:process-list}`
- effects: `#{:personal-data :system-read}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreihqyss6vswxjwjrfeafcuuzphbtzzlyxzbssk3tmut5r3w5ldqlra`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
