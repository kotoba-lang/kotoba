# capability-component-database

Atomic authority package for `component/database`.

- imports: `#{:pg-pool-release :pg-execute-params2 :db-close :pg-pool-drain :pg-pool-open :db-write :pg-close-statement :pg-copy-out :pg-copy-in :pg-open-scram-cancellable-random :pg-session-reset :pg-query :pg-close-portal :pg-pool-stats :pg-pool-query :pg-open-scram :pg-close-scram :pg-prepare :db-open :pg-simple-query :pg-fetch-portal :pg-execute-params :pg-prepare-typed :pg-pool-acquire :pg-pool-close :pg-execute-batch :pg-open :pg-query-state :db-exchange :pg-open-scram-random :db-read :pg-cancel-authority-use :pg-pool-health :pg-bind-portal}`
- effects: `#{:data-egress :storage-read :network-read :storage-write :network-write}`
- default policy: `:approval-required`
- semantic definition CID: `bafyreicvcxirmbjz754mx3t6o3jkb25ngmf5ghb5evptkb4rqkrrbtjqa4`
- hash contract CID: `bafkreiflhj3fslsbh7okdas2fzlhmogai64x6p3lkla6gtr7berbp7ftvi`
- provider status: `contract-only`

The repository name is a discovery alias. The semantic definition CID
is the immutable import identity. Importing it does not grant runtime
authority: Tamaki must request it explicitly and Kototama must admit
the sealed envelope.

```sh
kbb -M:test
```
