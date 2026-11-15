# Bounded Native kotoba.value.v1 validation, 2026-11-15

`kotoba.value.native-validate` validates a bounded subset of the existing
`kotoba.value.v1` wire form. It first decodes CBOR and requires byte-identical
re-encoding, then validates recursive type tags and rejects unordered or
duplicate map/set entries. It supports nil, booleans, safe integers, strings,
restricted ASCII keywords, bytes, vectors, lists, sets and maps. It refuses
float, int64, symbols, links, unknown tags and unsupported keyword spellings;
limits are 65,536 wire bytes, 1,024 elements per collection and depth 32.
It returns a validation result, not decoded application values, a CID, a
signature decision, or a policy decision. It does not implement the full
codec and must not silently substitute for it.

On 2026-11-15 Babashka 1.12.218 ran once as a local oracle, using copies of
`.cljk` sources as `.cljc` from repository revision `433b0dd39`: `ipld/value`
SHA-256 `a3eb7235f73ec65c71c6cbd01d91e8e5fbc13e721678ee1b19338b44865fea73`,
`ipld/link` `2cc3f316a817a721976c2f038815ae388ab4e4e3d7ea5795883d8a114780cfc3`,
`cbor/core` `da645900a6f1b2be592609c6cd988ea80ad82126d26a87365a0f332f8c7363f3`,
`multiformats/base32` `210a4d44a1f4ac60d627bc97f52eb3650e374daac14b740423a9928582bac74b`,
`kotoba/lang/text` `4f62e846a620ec49f5c84a69f6788b97cff4e53d4248beb02b4b41434d58a55b`.
The oracle generated `[130 19 130 130 130 5 97 97 130 4 97 98 130 130 5 98
98 98 130 2 7]` for `{:a "b" :bb 7}`, accepted by Native. The oracle was not
added to CI or the Native execution path. Other supported forms have not yet
been cross-checked against a common source corpus.

The 111-case local macOS arm64 Native corpus passed, covering the reference
example, empty map, unordered and duplicate map keys, nonminimal CBOR,
unsupported float including nested use, set order, and a mutated refusal
control. Positive executable SHA-256
`d7dd267413c0ce705f0523d0c31288ae02675c859583a8bd707474a00b8fd294`;
source lock `667d7bce728ee5d75b8b0e20e12112d62c0b6c91a6c387bcaa37c13ce9a3adab`.
The underlying generic CBOR parser runs before the value depth check; its
resource behavior is not qualified for hostile production inputs. Real stored
receipt decoding, signed manifest verification, key authority and policy remain
open and must not rely solely on this initial validator.
