# ADR 0282: recursive EDN type-directed `nth` migration

- Status: Accepted
- Date: 2026-08-04
- Depends: provider ADR 0246–0255/0260/0265–0268/0281; compiler ADR 0206

## Context

Sixteen recursive EDN packages still projected the two children of every pair
with `hetero-vector-at` and a repeated complete descriptor. Compiler ADR 0206
already infers that descriptor from a variant arm and lowers ordinary literal
`nth` to the same checked operation. The provider source had not adopted the
existing language surface.

## Decision

1. Replace all 32 explicit projections with `(nth p 0)` and `(nth p 1)`.
2. Add no syntax and no runtime representation. Literal indexes remain checked
   against the inferred heterogeneous descriptor; dynamic indexes and defaults
   remain rejected when the child types differ.
3. Rebuild all sixteen packages with compiler merge
   `92b9bb87b80fa2242ec724099faa65f7ece217ad` and preserve their exact Wasm
   bytes, exports, capability wires, and KIR oracles.
4. Keep source tripwires requiring both idiomatic projections and forbidding
   the raw operation.

## Evidence

Every Wasm digest below is unchanged after rebuilding. Source digests and
provenance seals changed because the authored expression changed.

| Package | Wasm SHA-256 | Source SHA-256 | Provenance seal |
| --- | --- | --- | --- |
| entropy-record-kv-edn | `4131cc31606f7b7be1dd3a5a27a9fecb9b890c09d3ca7ad025441946c7ac35ad` | `f72004d44cab3749e3b70f1c6ff1f6503c0fbdd796bc1e1ac339bbab7465a32e` | `ba4c7241a8b9d4092a4366f39313614b42e5f00e9dc3ef97438a39a738185d2e` |
| entropy-w4-host-edn | `604fe3ff74003de8656d0726375c52b60bf5c9d52e4523a630801d8ac1f25fcb` | `495d540eca826d160bd698a9284be066d5d76ecdd517e4b1d3f41efa85d69905` | `d79f91e700368f551597951d5cb46be9cb9f2eed401aa31e6240d017934a711d` |
| git-record-kv-edn | `390b086e373ac321857511dfa70b4866801c18cf2d56e5b7791eb12b9ffd4347` | `c76bc826345f063dc70130db23d9ce4674958c2fa8125f7a51a7a458c1b5b7df` | `a2e6a10d5742a907f4a3f7e42be3df04d01cad2945901c9de3f028cd1e453155` |
| git-w4-host-edn | `95152251cf0e5c7163fc831bf426da80ed2bc06ad48a19621308b207a25c1fa5` | `ed90adb87d09fb87424d899a7c2292786a87da727000a5bc389c075c83f9ce3a` | `acdd32306d72a144f9d94693521f86fd1d0de278163fc9571f4f675298c28853` |
| http-w4-host-edn | `a558ce394b32d6e32887a35483114b95ed08516bdf85e357ab57edca582af8b0` | `2078ff1ed3846c44b4bb7b65b7fec6a1eb2744f2afa0d454bfc0f8b627bb68d3` | `e910f1ed77f81cabbfbe12ce647dbff599236065d6bfbd6c4dea935521b19ef6` |
| process-record-kv-edn | `501deb2d2466edb8a4f7da66d6c3c2a2b947184e0fefe55e3c4dbb290d98ebee` | `57829abbcdabf5fd179e24032ac5c75a4e3a7098ef0b312dd516b6db78e6e6c5` | `2ea5d42520e987415c3bf6b5fc2fb5f9468de3841a678098419da0488eb2c0e4` |
| process-w4-host-edn | `6054506551d860d92f73db49921a338f7a170d9363569162f1558f3acfe27eeb` | `d0cb50fcb5bdfedf8ced7b369a3444df5c4f91d6a510a0dcddfe830d0e45893c` | `99bed9f74b7efcf447a7adc4856585af518284754f9ec5740e2629d1ebae0e8e` |
| recursive-headers-edn | `7b074e203bc400c6a391119701051222ace431080768cb3f07bc3a38dbb4c1a1` | `f77802b13fa151c5b6974d42a785e243698c47362a6d830387ccc78437340e79` | `6280265fca7cd20b7429f9f0508f8467a21355bf58909610f7205e95448d0a94` |
| recursive-http-edn | `d2a07804f5cd798d2b8e7342ea8a345648964e8fc4131bd8ce656fdefd9627cd` | `e75347883165e04867172c80b71ca5a64ad2c148a8df9fb4fcb9706b4f71a500` | `4839c549626fa52e7763ee683e00f5dc6ca4dc463e3b3501707ebfe4c2130276` |
| recursive-kv-edn | `540e939d4838ce3d89669f4839da6ac64194961502cb9b6435478f35506f1861` | `765ceeeea14df357eb47cbb712d07a472ef03e996b37369472ef777455e17974` | `f1ca09916bb839170bcdb775238aebf11b776b20d0d1badb0418a75e91eac50b` |
| recursive-kv4-edn | `8e69b0867d3ad6fe31eda555ac4716d2b4694160e611e22663834d96246cb138` | `1f8339b4efb34d28d4c779ad35a9748a22dfa3b63bca631d3b3b0d2ca134d97f` | `9ee12fcfed8ca220dbe189fc4d4e2df6b376aad06f2d0161abb106521b30db54` |
| recursive-record-kv-edn | `a6e24260014d50b8012c70706417a5341a49a65ebb42c31d31d660cc3bfb8143` | `4545354a6fa88f640adf21c2b9bdd3dc436d588f84f44369d98e82fdc4f072cb` | `a723972e110d10adf53431b1a1ff4b7a853049a761ca6ab05dcbf2134701cbcb` |
| scoped-fs-record-kv-edn | `2a6b08309b73d1a826616c01fcd8ac444e5bd93f21d023f99bcaa924dda27670` | `ab5f45a147ee183512e24f5f7d84e0a28a23257d189baffeee81330b4918fdff` | `6dffe932b75c4274b4d3a5f1855c14bca74d18b5a80cbe8e9dc0aa6a80a84c36` |
| scoped-fs-w4-host-edn | `b8339220a4e01f94e8bdc37466e9f3c9c8dfcd6931f8e8c3ffc2637c273126b9` | `21c92bdee828416293965aaca01a945af4cd5dd8aeb9410700176d84a91cf3c3` | `0c7fcacc0406c0159e864d7de049e4ae70a5ad7ed95339b7fa8bd1ae35058a5e` |
| secret-record-kv-edn | `5fc25c7169a1f1fb58e9e8c010b21063fab0f4f753d4caf1c0ae0bc4498a9897` | `e9ff6fde6d91b4d420fb84aad057cb4c98ae48b96a6b7403ef9b6ac2b3e9d5db` | `1d5a0a3d338cf16bb2a012f7ce9ae4aba03f43428c77c1ee4056bd7ace7d589f` |
| secret-w4-host-edn | `3c637641f132b570f0504e85c238a711ee3f3b892875c7e8cf02edff66c11924` | `0ca4b6700d13bdce920b67447f40fc6db444d0a631f3b0cbcddaa2784efe9cee` | `08ea6e80fd045aec47d58cd360115f9077413a5972015811e9f2b3612abbb25f` |

Independent KIR `main` oracles remain `-2401` through `-2406`, `-2502`
through `-2510` for the applicable packages, and `-2512` for scoped-fs host
read/write.

## Consequences

Authored provider `.kotoba` source now contains zero `record-new`,
`record-get`, or `hetero-vector-at` calls. The recursive printer reads as data
access rather than compiler plumbing, while the compiler still enforces the
exact child descriptor and literal-index bound.
