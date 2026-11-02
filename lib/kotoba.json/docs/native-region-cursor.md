# Native byte-region JSON cursor — JUN-757

`kotoba.json.region` supplies allocation-free byte cursors for native protocol
consumers. It does not replace or qualify the document/string facade. The
input is an immutable actual region0..65536 bytes, with at most64 nested
containers. Sibling iteration self-tail-calls and does not allocate an AST,
so the former EDN4096-node index capacity is not imposed on JSON siblings.
There is no IO, heap, state ownership or operation-approval capability.

`skip-space` recognizes only JSON's four ASCII whitespace bytes.
`string-end(input,count,at)` starts after an opening quote and returns the
closing-quote index or-1. It rejects raw controls and malformed UTF8/escapes.
`next-character(input,count,at,end)` returns exclusive-next-byte*2^21+scalar
or-1. Shared `kotoba.edn.region/next-character` supplies strict Unicode scalar
and UTF8 handling; JSON adds escaped slash. Lone surrogates, overlong UTF8,
surrogate UTF8 and values above U+10FFFF refuse rather than replace. This is
an intentional Unicode-scalar profile, not a claim to admit every escaped
surrogate string accepted by JavaScript JSON.parse.

`raw-step` decodes a raw UTF8 span, treating a literal backslash as a byte
rather than an escape. `utf16-length` counts one unit for BMP scalars and two
for astral scalars; its raw flag chooses raw UTF8 or JSON-escaped contents.
It is a span counter, not a complete JSON string validator. `string-end`
separately owns quote/control syntax and callers must retain validated spans.

`value-end(input,count,at,depth)` consumes one JSON value and returns its
exclusive end or-1. Start with depth0 for a whole document, or the number of
already-open containers for a nested value. The caller supplies a non-whitespace
value start and owns delimiters/trailing-document checks. Objects/arrays,
strings, null/booleans and JSON number grammar (sign, fraction, exponent) are
checked. Trailing commas, missing separators, comments and non-JSON numbers
refuse. Unknown object fields can be skipped without interpreting their values.
Duplicate-member policy belongs to the consuming schema, not this cursor.

`natural-value(input,count,start,end,limit)` accepts plain decimal naturals
0..limit (limit0..2147483647), refusing leading zeros, signs, fractions,
exponents and overflow. It does not implement JavaScript numeric coercion.
The Kekkai chunk consumer uses it for version and bounded part indices/counts.

The source-bound Kekkai application-frame corpus executes113 native cases,
plus12 direct cursor-boundary guards, including raw/escaped Unicode and slash,160 UTF16-unit boundaries, malformed
UTF8/escapes, selected-field numeric refusals, unknown JSON fraction/exponent
syntax,64/65 nesting and a65536-byte array with more than32000 siblings.
There is no host parser evaluating native outputs. Whole-output native hashes,
actual return pairs, input-preservation and buffer checks are retained in the
Kekkai application-frame receipt. These are region-cursor/consumer results;
complete JSON facade parity, larger/segmented application documents and the
full installed desktop/app closure remain separate qualification work.
