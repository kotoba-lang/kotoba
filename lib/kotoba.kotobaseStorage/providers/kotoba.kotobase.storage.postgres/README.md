# kotobase-storage-postgres

PostgreSQL adapter for `kotobase-storage`. Applications supply a
`javax.sql.DataSource`; the adapter does not impose a connection pool.

Apply `migrations/001_storage.sql`, or use `{:initialize? true}`.
