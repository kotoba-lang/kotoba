# ADR 0002: Capability-driven VRM compositor

- Status: Accepted
- Date: 2026-07-11
- Authority: `kotoba-lang/kisekae`

## Decision

`kisekae` is the canonical character-composition library. A character remains
an EDN spec; VRM/GLB bytes are derived output. Composition is represented by a
portable CLJC plan and may be executed by a browser CLJS host or a Murakumo
worker. URLs and CIDs identify resources but never grant authority.

The capability kinds are:

| Kind | Resource scope | Authorizes |
|---|---|---|
| `:vrm/asset-read` | asset URL/CID set | fetch and parse base/donor assets |
| `:vrm/compose` | character spec ID | decompose, remove/add meshes, unify skeleton and rebind skins |
| `:vrm/preview` | character spec ID | expose composed data to a renderer |
| `:vrm/export` | output URL/CID | encode VRM 1.0/GLB bytes |
| `:vrm/publish` | destination collection/CID namespace | send an artifact to Murakumo/Kotobase/IPFS |

Capabilities are concrete values shaped as `{:cap/kind … :cap/resource …
:cap/provenance […]}`. The host obtains them after CACAO grant and local-policy
intersection. `kisekae.capability` consumes and narrows them; credentials are
never placed in a character spec or compositor plan.

## Composition pipeline

```text
character spec + scoped capabilities
  → asset fetch/parse
  → part decomposition
  → base humanoid selection
  → remove overridden meshes
  → donor skin rebind to base skeleton
  → append selected meshes/materials/textures
  → apply material and expression defaults
  → CLJS live preview
  → deterministic VRM 1.0 export
  → optional Murakumo publish/CID receipt
```

Body selection is not a normal part override. `:op/set-base` changes the base
avatar and therefore the canonical humanoid skeleton. Hair, face, outfit and
accessory use `:op/add-part`. This avoids pretending that an incompatible body
can be swapped without rerigging every skin.

## Runtime ownership

- `kisekae.spec`, `edit`, `build`, `capability`, `compositor`: pure CLJC.
- `org-vrmc-vrm`: parse/decompose/compose/export engine.
- Browser host: CLJS fetch, `three-vrm` preview, expression manager, and direct
  WebGPU executor integration. No authority is inferred from browser access.
- Kotoba Wasm: optional sandboxed guest logic that emits edit/plan intent.
- Murakumo: authorized remote execution, Mac mini/GPU scheduling, CID output.

## Failure policy

Unknown operations, missing assets, incompatible part categories, invalid
expressions, missing capabilities and out-of-scope output destinations fail
explicitly. No placeholder `sample://` source may be presented as a composed
asset and no silent fallback is allowed.
