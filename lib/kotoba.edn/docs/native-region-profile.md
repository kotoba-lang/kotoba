# Caller-owned EDN region profile — JUN-757

`kotoba.edn.region` is an opt-in byte-region reader in the shared EDN owner.
It does not replace the string/document facade, implement the complete EDN
language, or confer trust on parsed data. Its current consumer is the native
Kekkai signed-roster adapter. No product-local EDN evaluator is introduced.
The facade was not measured as unsupported in this unit; the new interface
expresses the consumer's caller-owned region and no-allocation contract.

`parse(work,actual-work-bytes,input,actual-input-bytes)` returns1 or0. Work
requires98304 bytes; input is0..65536 immutable bytes, disjoint from work.
Calls are serialized and the indexed source must stay immutable. Shape
refusals preserve work. Processed failures clear all98304 bytes; success
indexes the source and leaves the remainder of work zero. Header fields are
magic1162104370, phase2, node count and source length at0/4/8/12. Each16-byte
node at1024 holds kind/start/length/after-subtree. Kinds1..9 are map, vector,
keyword, string, i64, nil, true, false, list. String spans exclude quotes and
keyword spans exclude the colon; container spans include their delimiters.
Public accessors validate the header and node index. Caller ownership, not a
forgeable header, protects the index.

The bounded grammar admits keyword-key maps with no duplicate byte-identical
keys, vectors/lists, keywords, quoted strings, decimal i64, nil/true/false,
ASCII separators/commas and semicolon comments. Raw string controls refuse.
UTF8 must use scalar values: invalid continuations, overlong encodings,
UTF8 surrogates and values above U+10FFFF refuse, including inside comments.
Strings decode the listed EDN escapes and paired `\u` surrogates. Comparisons
use decoded scalars without Unicode normalization or case folding. Decimal
integers reject overflow and leading zeros; i64 minimum is supported.
Tags/discards/sets/symbols/floats/ratios/namespace maps are outside this profile
and refuse. Its restricted keyword spelling is not a universal symbol reader.

The limits are4096 nodes and64 nesting levels. Siblings use a self tail call;
only bounded nesting recurses across reader functions. An earlier mutual
container/container-step loop exhausted the existing native stack while
reading the declared maximum node/edge cases. QMP observed HLT=1 at
RIP0x149ae7/RSP0x410088 after53 completed EDN cases. This failed candidate is
retained; the correction keeps the node/depth/stack and compiler limits.

`integer-value` and the string-comparison helpers are byte queries, not
admission capabilities. `sequence-has` queries a validated keyword/integer
sequence span and supports the `:any` port keyword for its consumer. Raw span
helpers do not make unparsed input trusted. Consumers must bind source and
index, validate their schema and protect state/authority independently.

The native Kekkai gate exercises55 direct EDN inputs, full i64 values,
UTF8/escape/duplicate/trailing-form refusals,65536-byte input,4096 nodes and
depth bounds. Separate native faults target UTF8, duplicate keys, integer
overflow and failure-work clearing. See the source-bound receipt in
`lib/kotoba.kekkai/docs/evidence/native-os-roster-20261102/receipt.json`.
This is a kernel diagnostic, not complete EDN/facade/library or product ABI
qualification. Python stages literal public test bytes and independently
signs/hashes them; native Amu owns module discovery/compilation and Kotoba
owns parsing, state transitions and assertions.
