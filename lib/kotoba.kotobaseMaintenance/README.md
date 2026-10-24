# kotobase-maintenance

Portable background lifecycle state for Kotobase databases.

This capability owns retention roots, page-bounded restore state, and resumable
task checkpoints. Its functions return immutable IPLD values and declarative
state transitions. Provider calls, clocks, queues, Worker `waitUntil`, cron,
and credentials belong to the deployment host.

Maintenance is outside the foreground transaction and query path. Backup,
restore, GC, compaction, or projection work may be retried without changing
logical Datom semantics.

The code was extracted from `kotobase-peer`. Provider-specific execution will
move to storage adapters or `net-kotobase`; portable lifecycle rules remain
here.

```sh
kbb -M:test
kbb -M:lint
```
