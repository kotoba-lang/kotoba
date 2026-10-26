# Kotobase SDK

One query client for Kotobase from TypeScript, Python, Rust, and PHP.

The SDKs share one wire contract and expose the same six read-only query
families:

- Datomic-shaped Datalog
- openCypher
- Apache TinkerPop Gremlin bytecode
- Ontotext GraphDB/RDF4J read-query compatibility
- GraphQL
- SPARQL

The client does not translate one query language into another. It sends a
versioned JSON query envelope to Kotobase, where the request is dispatched to
the existing language engine. This keeps parsing and query semantics on the
server and makes authentication, errors, timeouts, provenance, and result
metadata consistent in every host language.

```ts
import { KotobaseClient } from "@net-kotobase/sdk";

const db = new KotobaseClient({
  endpoint: "https://kotobase.net",
  token: process.env.KOTOBASE_TOKEN,
});

const result = await db.cypher(
  "MATCH (n:users) WHERE n.role = $role RETURN n.name",
  { parameters: { role: "admin" } },
);
console.log(result.data);
```

```python
from kotobase import KotobaseClient

db = KotobaseClient("https://kotobase.net", token="...")
result = db.sparql("SELECT ?s WHERE { ?s <urn:kotobase:role> \"admin\" }")
print(result.data)
```

```python
# GraphDB queries are SPARQL. The initial deployment mounts the read-only
# repository named "default".
result = db.graphdb(
    "SELECT ?s WHERE { ?s ?p ?o } LIMIT 10",
    database="default",
)
```

```rust
use net_kotobase::{KotobaseClient, RequestOptions};

let db = KotobaseClient::new("https://kotobase.net").with_token("...");
let result = db
    .datalog(
        "{:find [?n] :where [[?e :person/name ?n]]}",
        RequestOptions::default(),
    )
    .await?;
println!("{}", result.data);
```

```php
use NetKotobase\KotobaseClient;

$db = new KotobaseClient('https://kotobase.net', token: '...');
$result = $db->graphql('{ users { name } }');
var_dump($result->data);
```

## Repository layout

| Path | Purpose |
|---|---|
| `spec/openapi.yaml` | Authoritative `query.execute` HTTP contract |
| `spec/graphdb-openapi.yaml` | Native GraphDB/RDF4J query subset contract |
| `packages/typescript` | Browser, Node.js, Deno, and edge client |
| `packages/python` | Python 3.9+ client |
| `packages/rust` | Async Rust client |
| `packages/php` | PHP 8.1+ client |
| `gateway` | Cloudflare Worker dispatching the unified endpoint |
| `docs/adr` | Architecture decisions and server integration plan |

## Wire endpoint

All clients call:

```text
POST /xrpc/ai.gftd.apps.kotobase.query.execute
Content-Type: application/json
Authorization: Bearer <token>
```

See [`spec/openapi.yaml`](spec/openapi.yaml) for request, result, and error
shapes. Servers that have not installed the query gateway will return a normal
`404`; the SDK does not pretend that an unavailable engine is usable.

## Status

The portable clients and the separately deployed query gateway live here.
The gateway owns only the exact `query.execute` route and dispatches to the
existing, independently deployed query engines; see
[`ADR-0001`](docs/adr/0001-unified-query-envelope.md).

Production route: `https://kotobase.net/xrpc/ai.gftd.apps.kotobase.query.execute`.
The gateway requires an existing Kotobase credential and was deployed on
2026-08-01 as Cloudflare Worker `net-kotobase-query-gateway`.

GraphDB-compatible clients can use
`https://graphdb.kotobase.net/repositories/default`. This is a read-only RDF4J
query endpoint subset, not compatibility with GraphDB management, updates,
inference configuration, plugins, or Workbench APIs. See
[`ADR-0002`](docs/adr/0002-graphdb-query-compatibility.md).

## License

[Apache License 2.0](LICENSE). Package manifests use the SPDX identifier
`Apache-2.0`, and the repository includes the complete official license text.
