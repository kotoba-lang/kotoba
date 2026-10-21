# ADR 0001: Async filesystem preserves the synchronous capability boundary

- Status: accepted
- Date: 2026-08-30

`IAsyncFilesystem` adds eventual read, write, list, exists, and delete without
adding ambient filesystem authority. `async-host-filesystem` requires the same
absolute existing root, canonical symlink confinement, path vocabulary, and
per-operation byte bound as `host-filesystem`.

The JVM implementation dispatches the already-proven synchronous capability
through `CompletableFuture`; Node uses `fs.promises` after the same canonical
path proof. Failures retain stable `:fs/*` types through eventual wrappers.

This is asynchronous host I/O, not a scheduler or cancellation claim. Task
lifetime and cancellation belong to the structured scope/provider that invokes
the capability.
