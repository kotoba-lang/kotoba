# kotoba-lang/character

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-character` Rust crate
(deleted in `kotoba-lang/kami-engine` PR #82, "Remove Rust workspace from kami-engine") as part
of the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

`kami-character` is a MetaHuman-compatible character-creation SDK: parametric face/body/hair
generation, an Epic Games `.dna` binary parser (MetaHuman DNA calibration + FACS action units),
strand-based hair/groom systems, a control-rig DAG, and a hierarchical animation blueprint state
machine. This repo ports the full crate (5514 lines across 15 Rust source files) to pure CLJC
data + functions — no native GPU/IO dependency for the domain logic itself.

## Modules restored (all 15 original Rust files)

| Namespace | From | Purpose |
|---|---|---|
| `character` | `lib.rs` | Root SDK — `generate-character`, re-exports |
| `character.params` | `params.rs` | Parametric `CharacterDef` (face/eyes/nose/mouth/hair/body/...) |
| `character.base-mesh` | `base_mesh.rs` | FLAME-style head mesh, normals, Laplacian smoothing, eyes |
| `character.blendshape` | `blendshape.rs` | Face-shape deformation + 52 ARKit expression targets |
| `character.body` | `body.rs` | Body/clothing mesh + VRM humanoid skeleton |
| `character.material` | `material.rs` | PBR material generation per character part |
| `character.hair` | `hair.rs` | Preset-based strand quad-strip hair mesh |
| `character.export` | `export.rs` | GLB (binary glTF 2.0) exporter |
| `character.dna` | `dna.rs` | Epic Games `.dna` binary parser (big-endian, SoA, vertex-layout indirection) |
| `character.skeletal-mesh` | `skeletal_mesh.rs` | GPU skinned-vertex format + `.ksm` binary |
| `character.groom` | `groom.rs` | Strand hair asset, LOD decimation, hair cards, `.kgr` binary |
| `character.hair-gen` | `hair_gen.rs` | `HairStyle` → strands / cards / polygon-shell mesh |
| `character.control-rig` | `control_rig.rs` | FACS AU → bone-transform DAG evaluator |
| `character.anim-blueprint` | `anim_blueprint.rs` | Animation state machine, blend spaces, transitions |
| `character.metahuman` | `metahuman.rs` | MetaHuman DNA calibration, 46 FACS AUs, LOD0-LOD3, teeth/tongue, extended face rig |

Two supporting utility namespaces (not in the original 15-file list, factored out for reuse
and to keep each ported module small):

- `character.math` — glam-compatible Vec3/Quat/Mat4 math (same conventions as the sibling
  restoration `kotoba-lang/skeleton`'s `skeleton/math.cljc`, reimplemented locally so this repo
  has no hard cross-repo dependency), plus the deterministic `hash-f32` used by the hair/hair-gen/
  metahuman procedural-noise passes.
- `character.bin` — portable binary IO for the `.dna` / `.kgr` / `.ksm` wire formats. Buffers are
  plain Clojure vectors of unsigned bytes (0-255) so the same code runs unchanged on JVM and JS;
  only IEEE754 f32 bit-conversion needs a `#?(:clj ... :cljs ...)` split.

## Notable porting decisions

- **Enums → keywords.** `MaterialId`, `HairPreset`, `ClothingPreset`, `HairType`,
  `MetaHumanLod`, `FacsActionUnit`, etc. are plain keywords (kebab-case).
- **Structs → maps.** `Vertex`, `MeshPart`, `CharacterDef`, `GroomAsset`, `SkinnedVertex`, etc.
  are plain maps with keyword keys; `Vec3`/`Quat` are plain `[x y z]` / `[x y z w]` vectors.
  Rust `u32` wraparound hashing (`wrapping_mul`) is reproduced bit-for-bit via JVM `int`
  two's-complement arithmetic (`unchecked-multiply` + literal two's-complement constants).
- **`.dna`/`.kgr`/`.ksm` binary formats** are fully implemented (parse + serialize + round-trip
  tested) using `character.bin`'s byte-vector cursor, not native byte arrays — portable and
  round-trips correctly through the synthetic DNA fixture ported from the Rust test suite.
- **GLB export** (`character.export/export-glb`) builds a real, valid binary glTF 2.0 container
  (magic, JSON chunk, BIN chunk) as a byte vector; verified via magic-byte + size assertions
  matching the original Rust test.
- **No `serde_json`.** The Rust crate's `to_json`/`from_json` convenience methods (on
  `CharacterDef`, `HairStyle`, `MetaHumanDna`) were intentionally **not** ported — this repo has
  no JSON dependency (zero-dep CLJC), and the underlying data is already plain EDN-serializable
  maps. `character.metahuman-test/test-dna-serialization` covers the equivalent domain-data
  round-trip without the JSON I/O boundary.
- **`ControlRig/apply_to_skeleton`** no longer takes a `kami_skeleton::Skeleton` + `AnimationClip`
  and evaluates world transforms internally (that lived in the separate `kami-skeleton` crate,
  restored independently as `kotoba-lang/skeleton`). `character.control-rig/apply-to-skeleton`
  instead accepts an already-evaluated `world` joint-matrix vector, duck-typing the same
  `{:bones [...]}` / `Bone` map shape as `kotoba-lang/skeleton` without a hard dependency.

## Tests

66 `deftest` forms / 17,843 assertions, 0 failures, 0 errors. Every original Rust
`#[cfg(test)] mod tests` block across the 15 files was ported 1:1 (`dna.rs`'s synthetic DNA
binary fixture, `groom.rs`'s KGR round-trip, `hair_gen.rs`'s 100K-strand benchmark,
`skeletal_mesh.rs`'s KSM round-trip, `control_rig.rs`'s FACS rig evaluation, `anim_blueprint.rs`'s
state-machine transitions, `metahuman.rs`'s LOD/FACS/skeleton checks, `export.rs`'s GLB magic
check, `lib.rs`'s SDK smoke tests). `base_mesh.rs`, `blendshape.rs`, `body.rs`, `material.rs`,
`hair.rs` and `params.rs` had no Rust tests to port — supplementary sanity tests were added for
those six modules given the size of this restoration.

## Develop

```bash
kbb -M:test
```
