# Shared security adoption verifier

Each consumer stores `security-adoption.edn` at its repository root and runs:

```sh
kbb -M -m kotoba.security.adoption
```

The version 3 command denies floating or mismatched dependency pins, missing
central control namespaces, undeclared security-sensitive entrypoints, and
exceptions without an owner, reason, and unexpired ISO date. Entrypoints are a
map from namespace to the exact controls it must require. The verifier loads
them and inspects the runtime namespace dependency graph, so merely putting a
control on the classpath cannot satisfy the contract.

The verifier also parses every Clojure-family source file under `src/`. Every
namespace importing `kotoba.security.*` must appear in the entrypoint map, and
its exact imported control set must match the declaration. Hidden importers,
stale declarations, and incomplete or inflated edge declarations fail closed.

Reader conditionals are preserved during parsing, so the inventory is the
union of `:clj`, `:cljs`, and other platform branches rather than whichever
branch happens to execute on the CI JVM.

High-confidence sensitive definitions—encryption, decryption, authorization,
authentication, credentials, private keys, secrets, revocation, key rotation,
backup restore, signature verification, and artifact signing—must also appear
in `:sensitive-operations`. Each operation is bound to controls already required
by its entrypoint namespace. This detects sensitive code that attempts to avoid
the central library entirely.

For effects, use `kotoba.security.effect/guard!`, or the lower-level one-shot
`issue!` and `consume!` pair. Grants are opaque identity objects, bound to an
action/resource/digest tuple, removed before validation, and cannot be replayed
or reused after a claim mismatch. The effect callback runs only after the
central decision predicate accepts.
