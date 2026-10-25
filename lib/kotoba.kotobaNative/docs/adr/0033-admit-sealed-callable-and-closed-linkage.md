# ADR 0033: Admit sealed callable and closed linkage boundaries

## Decision

Aggregate ABI v7 admits variants whose payload is an admitted record. The
variant remains one word: `pair(case-ordinal,payload-word)`, where a record
payload word is its already admitted recursive pair-chain handle. Schema depth,
case count, arena ownership, and allocation bounds remain unchanged.

Callable indirection is admitted only as a closed ordinal dispatch. A function
reference contains a compiler-assigned ordinal, and the generated dispatcher
selects a statically named function. `apply` walks a pair chain and enters the
same dispatcher with at most four arguments. This gives the language its
bounded varargs operation without creating a machine-code address value or a C
varargs ABI.

External linkage is admitted only after the source owner seals the complete
module graph. Admission evidence contains a SHA-256 graph digest, an explicitly
empty unresolved-symbol set, and `ambient-symbols false`. Native emission still
sees one closed KIR module and emits only statically named direct calls.

## Evidence

Both ISA producers compare record-payload variant lowering byte-for-byte with
the equivalent nested pair program. Machine-IR qualification lowers and encodes
the aggregate boundary, ordinal dispatcher, and bounded `apply` path on x86-64
and AArch64. Contract tests independently reject missing, malformed, ambient,
or unresolved linkage evidence.

## Rejected boundary

Arbitrary code addresses, open-ended variadic parameters, ambient symbol
lookup, and unresolved dynamic linkage remain structurally rejected. They are
not legacy fallbacks and are not implied by this admission.
