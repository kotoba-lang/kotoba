# kotobase-federation

Kotobase-specific federation capability over immutable blocks and logical
checkpoints.

The initial extraction contains the replica availability challenge/response
kernel. It is deliberately distinct from the embedded-database meaning of
"peer": federation concerns replicas, signed heads, checkpoint convergence,
and injected transports. It does not own Datom or query semantics.

The availability proof is a replica-to-replica audit, not Filecoin PoRep/PoSt.
The verifier independently resolves the challenged bytes and compares the
salted response. Consensus/ref publication and real transports remain injected
capabilities rather than hidden storage assumptions.

```sh
kbb -M:test
kbb -M:lint
```

## Pure Kotoba: `kotobase.availability`

[`src/kotobase/availability.kotoba`](src/kotobase/availability.kotoba) is the
availability challenge for a guest (root ADR-2610082200 §16). The salted hash
is `hash/sha256` (capability wire id 3) over `block ++ nonce`, so a guest using
it declares `[:cap/call 3]`; the caller passes the block bytes it fetched
instead of a get-fn. `verify` answers 1 ok, 2 failed, 3 missed, 4 malformed,
5 verifier-lacks-replica, in the oracle's order. `kotobase.federation` stays as
the oracle (`migration/availability-v1.edn`).

```bash
NODE_PATH=<node_modules with @noble/hashes> kbb --backend sci \
  --classpath "src:$(kbb -Spath)" scripts/availability-oracle-cases.cljk
```

asks the oracle every question the Kotoba tests assert (13 cases, 2026-10-09).
