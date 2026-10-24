# kotobase-projection

Portable, storage-neutral derived query artifacts for Kotobase.

New opaque packs and ciphertext use raw CIDs. See the
[codec migration and compatibility notes](docs/opaque-object-codecs.md).

This capability owns materialized query bundles, query statistics, and the
atomic publication shape that binds derived artifacts to one immutable base
manifest and logical epoch. It returns immutable values and declarative block,
object, and head effects; it does not execute provider I/O.

It is optional. A Kotobase engine can transact and query without this package,
and a projection failure must not invalidate an already committed logical
checkpoint. Hosts that require base-plus-projection atomicity publish the
combined epoch root produced here.

Differential Datalog maintenance consumes injected `query-fn` and
`transact-effective-fn` functions. The projection runtime therefore does not
depend on a particular database engine; its conformance tests use the legacy
peer implementation only as a test oracle.

The code was extracted from `kotobase-peer`. New projection behavior belongs
here; the old namespaces are compatibility surfaces during migration.

```sh
kbb -M:test
kbb -M:lint
```
