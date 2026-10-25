# kotobase-storage-sqlite

Embedded SQLite backend for the provider-neutral `kotobase-storage` contract.
It stores immutable CID blocks and linearizable mutable refs in one local
database file. It does not require a Kotobase peer.

```clojure
(require '[kotobase.storage.sqlite :as sqlite]
         '[kotobase.engine :as kotobase])

(def storage (sqlite/open {:path "./kotobase.db"}))

(def database
  (kotobase/open
   {:storage storage
    :encrypt-fn identity
    :decrypt-fn identity
    :blind-fn pr-str
    :visible? (constantly true)}))
```

The adapter enables WAL, configures each connection with a busy timeout, wraps
batch block insertion and collision validation in a transaction, and implements
ref compare-and-set with one atomic SQLite statement.

Use `:datasource` to provide a custom `javax.sql.DataSource`, or `:path` for the
built-in unpooled Xerial datasource. Apply `migrations/001_storage.sql`
yourself and set `:initialize? false` when schema lifecycle is managed outside
the application.

This provider is for embedded/local SQLite. Cloudflare D1 shares much of
SQLite's SQL model but has a remote Worker API and different transaction and
consistency boundaries, so it remains the separate `kotobase-storage-d1`
provider.

Run the real file-backed conformance and engine persistence tests:

```sh
kbb -M:test
```

