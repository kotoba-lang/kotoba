# ADR 0283: implicit recursive record-schema migration

- Status: Accepted
- Date: 2026-08-04
- Depends: provider ADR 0281/0282; compiler ADR 0209/0210

## Context

The twelve nominal recursive EDN packages declared each `EdnKeyValue` twice:
once as an exact descriptor in the namespace schema table and once as a later
`defrecord`. Compiler ADR 0209 made that duplication safe, but the source still
repeated information already owned by the record declaration.

## Decision

1. Depend on compiler ADR 0210's bounded declaration prepass. Each recursive
   variant keeps only `[:ref :namespace/EdnKeyValue]`; the later `defrecord`
   supplies the nominal descriptor before the closed schema graph is validated.
2. Remove all twelve explicit forward descriptors while retaining their closed
   variant tables, nominal identities, literal `nth` projections, and exact
   field types.
3. Preserve compatibility with exact explicit declarations and preserve
   fail-closed incompatible collision behavior in the compiler.
4. Rebuild source provenance while requiring byte-identical Wasm, unchanged
   exports, capability wires, and KIR oracles.

## Evidence

- compiler PR: kotoba-lang/compiler#527
- compiler merge: `fbc436a57a8c5750a8848d17cbac79ceec52f3e3`
- every Wasm digest below is unchanged; only source and provenance identity
  move with the simpler authoring surface.

| Package | Wasm SHA-256 | Source SHA-256 | Provenance seal |
| --- | --- | --- | --- |
| entropy-record-kv-edn | `4131cc31606f7b7be1dd3a5a27a9fecb9b890c09d3ca7ad025441946c7ac35ad` | `c1d9f5f89c2556f4edbcac89b96b448117875469581a3ecbaa9f797ae876b431` | `ff54adbd6d22ea8d78bcd8a3fa09fdf1898dc32cc716a0f9cd05e9dd508cadd2` |
| entropy-w4-host-edn | `604fe3ff74003de8656d0726375c52b60bf5c9d52e4523a630801d8ac1f25fcb` | `d46b7b6e91cd489919a3c21608592e0910a60671b00df71dc02b1f4f603f0259` | `d414b95c44b79619798a849ba8b1be1ffbf993ae45a9053984f80bc8bdb90f4f` |
| git-record-kv-edn | `390b086e373ac321857511dfa70b4866801c18cf2d56e5b7791eb12b9ffd4347` | `6f62ccf556d6fbd30d651abc28b32b7e29ea7bafc2de7f634d48922cb7cefb94` | `3f7d0e352769a4691d898a99c7c66a5df5f187c01a140e442ec88c21c7c79dcd` |
| git-w4-host-edn | `95152251cf0e5c7163fc831bf426da80ed2bc06ad48a19621308b207a25c1fa5` | `9fded4db249b237d848b5aa7b6bcde27d66542bb7031dfec92606cb5f1557832` | `b7a8a81c9cb2792ca698c64ab12c20dc9d638f14d623ce0ff35c047701d56a5e` |
| http-w4-host-edn | `a558ce394b32d6e32887a35483114b95ed08516bdf85e357ab57edca582af8b0` | `098f9476e435b0c29144b30385333321d52d9b93b9bfc859a9980a5a91db33d5` | `d1d8c307b8e7dc3198ca4b9c0e5d19f87caf739c592e850a1dfc30b7a9dd40e1` |
| process-record-kv-edn | `501deb2d2466edb8a4f7da66d6c3c2a2b947184e0fefe55e3c4dbb290d98ebee` | `9dd2ee48a8a470e0337d46713e8affc7ad594d8993205dcddce36cd9b00c2fb4` | `8f58b37cd45ddd0d7f7a0e3d2d8a71b21e0e02e519094c0ad6624ea4ed1fb46f` |
| process-w4-host-edn | `6054506551d860d92f73db49921a338f7a170d9363569162f1558f3acfe27eeb` | `f195d726d4dcbe10e3f1427fc2236098b5fa0cdd56d14a9321d1b1d3063e3849` | `e1d16d4cdb30a80301cf0a527523e8455d39ab7f2798cc9254b930c41781b8be` |
| recursive-record-kv-edn | `a6e24260014d50b8012c70706417a5341a49a65ebb42c31d31d660cc3bfb8143` | `8c933319a1b659b332f34a81f7f2dd044f9a85b618243afb5b96095eace79b3e` | `2155b506db056ac3fcfab039bf5b8a7aaf93897745b941fa82437c59b6ebaabd` |
| scoped-fs-record-kv-edn | `2a6b08309b73d1a826616c01fcd8ac444e5bd93f21d023f99bcaa924dda27670` | `0b3bdf12bd8dc8c57cbdb43a6fd81e44690e4b4e45fc17f25259849555789d66` | `fa60be12201dd444f2ab0221a6d8bd3d3e62b98c9005d75a583e0e7bcb3daf6e` |
| scoped-fs-w4-host-edn | `b8339220a4e01f94e8bdc37466e9f3c9c8dfcd6931f8e8c3ffc2637c273126b9` | `7371bcd0740a625e0bce26812fca12644c3d91940396923ae152d481cb38a1a9` | `228dced5a350efb139f3166f77eadb8f49b36f4ced80a1129a42f22d0950bb4a` |
| secret-record-kv-edn | `5fc25c7169a1f1fb58e9e8c010b21063fab0f4f753d4caf1c0ae0bc4498a9897` | `482e66c044bdc17c8a771a54778bc9261d87d41eab56a7187b1d665b74b394c5` | `f9fc22b32c316eae93494dfde85873fddcb1c1de9e22e8da093ab755bde352b3` |
| secret-w4-host-edn | `3c637641f132b570f0504e85c238a711ee3f3b892875c7e8cf02edff66c11924` | `fa6f566f7e44dd6c746b30b176cc6d86e5df2f049c4cea31fe1055caaad9052c` | `676a962262c49f546d1d490d5b5ca93bc8d3c7d60612c39fe61d8344233aa717` |

The twelve independent KIR `main` oracles remain `-2405`, `-2406`,
`-2502` through `-2510` for the applicable packages, and `-2512`.

## Consequences

Recursive record source now states each nominal shape exactly once. The schema
table shows only recursive relationships, while `defrecord` owns fields and
constructors. This removes the final record-specific visual duplication found
by the syntax-quality review without weakening closed-world validation.
