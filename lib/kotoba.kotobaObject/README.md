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

The canonical ELF64 source candidate is `src/kotoba/object/elf64.kotoba`.
Its seven public functions return explicit bytes/error/field records. Read
[the complete API and migration record](docs/elf64-kotoba-port.md) before
connecting a native consumer; native admission and byte/refusal qualification
remain open.
The complete PE32+ candidate is `src/kotoba/object/pe32plus.kotoba`, with
shared natural-number arithmetic in `unsigned.kotoba`;
see [the PE32+ API and source record](docs/pe32plus-kotoba-port.md).
The complete Mach-O candidate is `src/kotoba/object/macho64.kotoba`;
see [the Mach-O API and source record](docs/macho64-kotoba-port.md).

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

## Canonical native migration

Tracking is [JUN-201](https://linear.app/kotobalabs/issue/JUN-201) and
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200) in Kotoba Labs.
Canonical source, build and CDCI are migrating to Kotoba / Amu selfhost.
The target build/execution/CI closure is Kotoba / Amu selfhost only.
The obsolete JVM/Clojure compatibility-loader workflow is removed from this
candidate; its remote state was already disabled manually, and its CLJK
compatibility-loader prerequisite is retired. No replacement
native gate is claimed until the complete compiler/consumer closure exists;
no native gate is activated or declared successful here.

ELF64 includes every public record encoder, integer range and bounded padding.
The PE32+ and Mach-O candidates cover their complete image/object boundaries.
Whole-component native admission, Definition CIDs,
byte/refusal behavior, consumer API integration and reviewed pins remain open.
Existing hosted sources and drivers remain migration inventory, not a
required final oracle.

See [native CDCI retirement](docs/native-cdci-retirement.md) for the exact
source/blob provenance, unchanged corpus and open acceptance. Historical
KBB/JVM commands do not establish an Amu-produced native compiler or library.
