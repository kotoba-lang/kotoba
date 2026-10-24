# kotoba-object

Target-neutral object-file construction contracts for Kotoba.

`kotoba-object` owns the byte-level records used to construct object and
executable containers. It deliberately does not own compiler lowering, target
ABI policy, entry shims, memory maps, or linker policy.

The contracts are `kotoba.object.elf64`, a validated ELF64 little-endian record
encoder, `kotoba.object.pe32plus`, a validated PE32+ record/image encoder, and
`kotoba.object.macho64`, a validated Mach-O 64-bit relocatable-object encoder.
Backends supply target decisions as data and use the returned byte vectors when
assembling a complete image.

```clojure
(require '[kotoba.object.elf64 :as elf64])

(elf64/encode-header
 {:type :executable
  :machine :x86-64
  :entry 0x401000
  :program-header-offset 64
  :program-header-count 2
  :section-header-offset 0x3000
  :section-header-count 4
  :section-name-index 3})
```

## Boundary

- owned here: ELF/PE/Mach-O identification, headers, load commands,
  program/section records,
  symbols, typed Mach-O relocations, RELA/data-directory records,
  little-endian integer encoding,
  bounded padding
- owned by code generators/backends: instruction bytes, relocations to request,
  ABI shims, virtual addresses, section layout, capability/runtime policy
- owned by orchestration: selecting ELF versus Mach-O/PE/Wasm and writing files

The Mach-O contract emits compact ARM64 and x86-64 `MH_OBJECT` files with typed
sections, symbols, external relocations, and platform build-version metadata.

## Development

Canonical source, build and CDCI are migrating to Kotoba / Amu selfhost.
The old Clojure/JVM workflow and its CLJK compatibility-loader prerequisite
are retired. Complete object encoders and their positive/refusal/resource
corpus still need canonical integration and native qualification; no native
gate is activated or declared successful here. The old hosted sources and
drivers remain migration inventory, not a required final oracle.

See [native CDCI retirement](docs/native-cdci-retirement.md) for the exact
source/blob provenance, unchanged corpus and open acceptance. Historical
KBB/JVM commands do not establish an Amu-produced native compiler or library.
