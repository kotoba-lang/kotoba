# ADR 0001: Kotoba source authority for bounded SHACL validation

Status: accepted

## Decision

`src/shacl.kotoba` is the sole production source. Clojure is used only to host
the compiler and tests; it is not a production runtime. Portable behavior is
qualified through the reference evaluator, restricted JavaScript, and
instantiated typed Wasm.

The former CLJC behavior is represented with canonical documents: nested paths,
scalar/vector value normalization, count constraints, datatype matching, `:in`
membership, node-kind validation, and ordered errors. `document-equal?` supplies
structural membership for arbitrary admitted documents.

The old unbounded variadic `node-shape` call becomes a single vector argument.
That vector, each input document, and the error vector use the language's bounded
document profile. More than 32 accumulated errors is rejected instead of being
silently truncated. Observable results and fail-closed behavior define
cross-target conformance.

## Ownership

Kotoba owns pure validation and capability admission. RDF graph loading, remote
resolution, SPARQL execution, persistence, and other effects remain outside this
pure module and require explicit providers.
