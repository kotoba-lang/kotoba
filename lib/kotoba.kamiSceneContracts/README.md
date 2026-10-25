# kami-scene-contracts

EDN authority for KAMI scene-domain data.

This repo owns copied scene-domain resources from `kami-*-scene/data/*.edn`.
The old engine `data/*.edn` files are retired mirrors; if any remain, they must
match this authority exactly.

`kami.scene.contracts/authority-manifest` exposes the authority resource path,
legacy engine fixture path, byte count, and sha256 for every contract. Engine
`data/*.edn` files are never semantic authority.

Run:

```sh
kbb -M:test
kbb -M:authority-manifest
kbb -M:check-engine-mirror ../kami-engine
kbb -M:check-engine-fixtures ../kami-engine
```

Regenerate legacy engine fixtures from this authority repo:

```sh
kbb -M:sync-engine-fixtures ../kami-engine
```
