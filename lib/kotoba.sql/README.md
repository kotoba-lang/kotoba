# kotoba-lang/sql

Two namespaces with one boundary between them:

| namespace | what it does |
|---|---|
| `kotoba.sql` (facade over `sql.core`) | the EDN -> SQL DSL: it **builds** statements (DDL, INSERT, DROP) as strings. It touches no database. |
| `kotoba.sql.conn` | **executes** statements: the portable replacement for `java.sql` (Connection / Statement / PreparedStatement / ResultSet) and `javax.sql.DataSource`. |

Neighbours, not merged into this repo:

- `kotoba-lang/org-postgresql-wire` is the portable PostgreSQL wire protocol.
  It is **not** wired into `kotoba.sql.conn`: PostgreSQL runs through JDBC on
  the JVM only, and on the kbb engine a non-SQLite datasource refuses with
  `:kotoba.sql.conn/error :unsupported-datasource`.
- `kotoba-lang/capability-component-database` is the atomic authority package
  for component/database. `kotoba.sql.conn` is the mechanism a granted
  database authority is exercised through; it does not decide who holds one.

## `kotoba.sql.conn`

Capability shape: code never reaches a database ambiently. It is handed a
datasource and derives everything else from it: datasource -> connection ->
statement -> result.

- **JVM**: every function delegates 1:1 to the JDBC method named in its
  docstring, on the host object. A consumer rewritten from JDBC interop onto
  these functions behaves as before; errors stay the driver's `SQLException`.
  `sqlite-datasource` builds `org.sqlite.SQLiteDataSource` reflectively and
  falls back to a `DriverManager`-backed DataSource when sqlite-jdbc is not
  on the classpath.
- **kbb engine (Node)**: the same functions run over `node:sqlite`
  (`DatabaseSync` / `StatementSync`). Connections, statements and results
  are JS objects with a `close` method, so `with-open` closes them.
  Connections open with sqlite-jdbc's defaults (foreign_keys 0,
  busy_timeout 3000, double-quoted string literals accepted).
  When Node can't match sqlite-jdbc, the call refuses with
  `ex-info {:kotoba.sql.conn/error <keyword>}`.

Surface: `sqlite-datasource` `driver-manager-datasource` `datasource?`
`connection` `create-statement` `execute!` `prepare` `set-bytes!`
`set-object!` `set-string!` `set-long!` `set-int!` `set-null!`
`execute-update!` `execute-query` `execute-statement!` `add-batch!`
`execute-batch!` `clear-batch!` `next!` `get-string` `get-bytes` `get-long`
`get-int` `get-object` `was-null?` `auto-commit?` `set-auto-commit!`
`commit!` `rollback!` `close!` `closed?` `blob?` `bytes-equal?`
`byte-length` `long-value`, plus `execute` / `query` / `with-transaction`.

Node value types: TEXT is a string, and BLOB is a `Uint8Array`
(`get-bytes` returns a copy). NULL is nil, REAL is a number. INTEGER is a
number when |n| <= 2^53-1; beyond that it is an exact BigInt, so
compare with `str`. On the kbb engine `bytes?` is false for a
`Uint8Array`, so use `blob?`.

Refusals on Node: `:unsupported-datasource` `:connection-closed`
`:statement-closed` `:result-closed` `:no-current-row` `:no-column-read`
`:column-out-of-range` `:no-such-column` `:parameter-out-of-range`
`:unsupported-parameter-type` `:auto-commit-mode` `:update-returns-rows`
`:query-returns-no-rows` `:not-a-number` (and `:not-a-connection` /
`:not-a-statement` / `:not-a-result` / `:not-a-prepared-statement` for a
wrong handle).

Known differences from sqlite-jdbc on Node:

- Reading a column before the first `next!` or after exhaustion refuses
  (`:no-current-row`). sqlite-jdbc answers the first row or NULL there.
- Binding more parameters than the SQL declares refuses at execution, not
  at the `set-*!` call.
- `get-object` of an integral REAL answers a number (`5`), not a Double
  (`5.0`). `get-string` of an integral REAL still answers `"5.0"`.
- `jdbc:sqlite:` URLs with `?` parameters refuse.

## Test

```sh
kbb -M:test
```

JVM oracle: the same scripted workload runs through raw JDBC and through
`kotoba.sql.conn`, and every observation is compared. The JVM answers are
recorded as literals in `test/kotoba/sql/conn_workload.cljk`, and the kbb run
is held to those same values.

```sh
kbb --backend sci scripts/jvm_test.cljk kotoba.sql.conn-oracle-test kotoba.sql.conn-test sql.core-test \
  --jar ~/.m2/repository/org/xerial/sqlite-jdbc/3.53.2.0/sqlite-jdbc-3.53.2.0.jar
```
