# kotoba-lang/ddl

The closed structural-validation subset is also available as native `.kotoba`
in `ddl.bounded-validate`. Its canonical integer schema is bounded to three
tables, four columns, and two foreign keys; malformed encodings fail closed and
the kernel compiles directly to restricted JavaScript and Wasm without a JVM
runtime. SQL text, string identifiers, open type syntax, key member lists,
schema diff, and migration emission remain in the portable `.cljc` domain.

[![CI](https://github.com/kotoba-lang/ddl/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/ddl/actions/workflows/ci.yml)

Handle **relational DDL schemas as EDN/Clojure data** in portable Clojure — every
namespace is `.cljc`, with **zero third-party runtime deps**, so it runs on the JVM,
ClojureScript, and Clojure-on-WASM hosts (SCI). A database schema is plain data you
can `assoc`, `diff`, store in Datomic, or generate; the library adds structural
validation, CREATE TABLE SQL I/O, and a pure schema-diff / migration emitter around it.

Sibling of other reusable kotoba-lang contract kernels such as
[`kotoba-lang/bpmn`](https://github.com/kotoba-lang/bpmn) and
[`kotoba-lang/dmn`](https://github.com/kotoba-lang/dmn).

## Why a shared library

The reusable schema model lives in `kotoba-lang/ddl`. It carries no domain
schema and no engine bindings; those remain host-injected ports.

## The model: DDL as EDN (`ddl.model`)

Tables are name-keyed maps; columns are ordered vectors; primary-key and
foreign-keys are first-class fields:

```clojure
{:ddl/tables
 {"users" {:ddl/name "users"
           :ddl/columns [{:ddl/name "id"    :ddl/type "INTEGER"      :ddl/nullable false :ddl/pk true  :ddl/default nil}
                         {:ddl/name "email" :ddl/type "VARCHAR(255)" :ddl/nullable false :ddl/pk false :ddl/default nil}]
           :ddl/primary-key ["id"]
           :ddl/foreign-keys [{:ddl/columns ["org_id"]
                               :ddl/ref-table "orgs"
                               :ddl/ref-columns ["id"]}]}}}
```

A threading-friendly builder:

```clojure
(require '[ddl.model :as m])

(def schema
  (-> (m/schema)
      (m/add-table
        (m/table "users"
                 [(m/column "id"    "INTEGER"      :nullable false :pk true)
                  (m/column "email" "VARCHAR(255)" :nullable false)]))))

(m/get-table schema "users")   ;=> the users table map
(m/table-names schema)         ;=> #{"users"}
```

## Validation (`ddl.validate`)

`problems` returns a vector of `{:ddl/severity :ddl/code :ddl/id :ddl/msg}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[ddl.validate :as v])
(v/valid? schema)        ;=> true
(v/problems broken)      ;=> [{:ddl/severity :error :ddl/code :fk/dangling …}]
```

Errors: dangling FK reference, duplicate column name, empty column type.
Warnings: table has no primary key.

## SQL I/O (`ddl.ddl`)

```clojure
(require '[ddl.ddl :as ddlio])
(ddlio/parse-str (slurp "schema.sql"))   ; CREATE TABLE SQL → schema map
(ddlio/emit-str schema)                  ; schema map → CREATE TABLE SQL (round-trips)
```

Zero-dep and portable: a **minimal tokeniser** covers CREATE TABLE with:
- `IF NOT EXISTS` clause
- Column defs: `name TYPE [NOT NULL] [PRIMARY KEY] [DEFAULT <lit>]`
- Types with precision/scale: `VARCHAR(255)`, `NUMERIC(10,2)`
- Table-level: `PRIMARY KEY (cols)`, `FOREIGN KEY (cols) REFERENCES t (cols)`
- `--` line comments; `;`-terminated statements; case-insensitive keywords

## Schema diff and migrations (`ddl.execute`)

```clojure
(require '[ddl.execute :as ex])

(def ops (ex/diff old-schema new-schema))
;; => [{:ddl/op :add-column :ddl/table "users" :ddl/column {:ddl/name "phone" …}}
;;     {:ddl/op :drop-table :ddl/table "tmp_cache"}]

(ex/emit-migration ops)
;; => "ALTER TABLE users ADD COLUMN phone VARCHAR(20);\nDROP TABLE tmp_cache;"
```

Op types: `:create-table`, `:drop-table`, `:add-column`, `:drop-column`, `:alter-column`.
`emit-migration` turns ops into `ALTER TABLE / CREATE TABLE / DROP TABLE` SQL.

## Test

```
kbb -M:test
```
