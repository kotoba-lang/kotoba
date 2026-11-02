# Native application request/response data schema — JUN-757

`kekkai.application-message-region/decode` adds the canonical private HTTP
message shape to the native migration. It is a data decoder, not an installed
Mac/OS application, HTTP service, socket policy or consent gate.

## Source boundary

The read-only migration inventory is `kotoba-lang/kekkai-node`,
`src/kekkai/node/access_edge.cljk` and `application.cljk`: request fields are
`messageType`, `requestId`, `serviceName`, `method`, `path`, `headers`, `port`,
`bodyBase64`; response fields are `messageType`, `requestId`, `status`,
`headers`, `bodyBase64`. Canonical request IDs are UUID strings, but this parser
adds no arbitrary short identifier/service/path/header bound. The entire JSON
message remains at most 1MiB. Decoded body remains at most 1MiB, intersected
with the JSON/Base64 overhead; it is not reduced to 512KiB.

The legacy pending-request bound is **256**, distinct from **128** incomplete
assemblies. Neither it nor the existing 2048-part/4MiB aggregate bounds changes.
The legacy pending map matches IDs without retaining peer/service context;
the future native pending owner must not use that as authority. It must bind
actual peer public key, roster generation and final Noise channel, plus service,
port, request identity and lifetime. This unit does not implement that owner.
No legacy Node/JVM runtime is executed or restored.

## API and ownership

`decode(work, workBytes, input, inputCapacity, used, output, outputCapacity)`
returns 1 (request), 2 (response), or -1. Work is a real allocation of at least
8192 bytes; input is a real allocation of at least 1MiB with used 0..1MiB;
output is a real 4096..65536-byte allocation. All three declared allocations
must be disjoint and calls serialized. Shape refusal leaves all bytes untouched.
A processed success or refusal clears all 8192 private work bytes. Success
commits exactly 4096 output bytes, leaving its tail unchanged; refusal leaves
all output unchanged. Inputs are immutable, including unused allocation tails.

The output is an API-created, caller-protected **KPM1 v1** data record:

| Offset | Field |
| --- | --- |
| 0, 4, 8, 12 | u32 magic `0x314d504b`, version 1, kind 1/2, input used |
| 16 | u64 actual input base |
| 24, 28, 32, 36 | u32 port/status, decoded body size, header mask, root mask |
| 64 + 16*(field-1) | nine root field spans: u32 value start, exclusive end, UTF16 units for strings, zero |
| 256 + 16*(header-1) | eight normalized header value spans in the same format |
| remaining bytes | zero |

Root field order is the request list above, followed by `status` as field 9.
Unified header order is `accept`, `content-type`, `if-none-match`, `range`,
`content-length`, `etag`, `last-modified`, `content-range`. Spans include JSON
quotes/containers; consumers use the shared cursor for decoded text. Input
must remain immutable and alive for the entire record lifetime. Neither the
pointer nor a span is an authorization token. No secret key material is copied.
A consumer must not accept an arbitrary caller-forged record as protected state.

The shared `kotoba.json.document-region` now exports a full1MiB cursor:
`skip-space`, `string-end`, `value-end`, `next-character`, `utf16-length`,
`natural-value`, preserving `valid-document`. Actual capacity is explicit;
character stepping narrows the original allocation to at most 12 bytes and
uses the existing strict scalar codec, even across a 64KiB boundary.
`string-end` starts after the opening quote and returns the closing quote;
`value-end` is exclusive. Character result is absolute exclusive end * 2^21
plus Unicode scalar. The original 64KiB cursor remains unchanged.

## Strict admission of data

Known required names match through JSON escapes and duplicate known names
refuse, including escaped duplicates. Request/response fields cannot be mixed.
Unknown root values are syntax checked and ignored without effects. Nesting
remains at most64 with no sibling/node count shortcut. UTF8/surrogates are
strict. Nonempty ID/service/method/path have no invented short field limit.
Port is a plain integer 1..65535 and status 100..599 without numeric coercion.
Method is an ASCII HTTP token. Path begins with a single slash and rejects
controls/backslash. **This is not URL normalization, origin/redirect checking,
configured service/port authorization or endpoint admission.** Those remain
mandatory at the consumer and shared operation broker.

Request headers are only accept/content-type/if-none-match/range. Response
headers are only content-type/content-length/etag/last-modified/content-range.
Names normalize ASCII case and JSON escapes for allowlist/duplicate checks.
Values must be strings without controls except HTAB; no CRLF/NUL/DEL injection.
The body must be canonical RFC4648 Base64, including correct padding and pad
bits, with JSON escapes allowed. The decoder measures the decoded size without
copying arbitrary bodies into a small work buffer. These restrictions preserve
canonical encoder output but intentionally do not reproduce permissive legacy
JS duplicate/numeric/Base64/Unicode coercions.

## Evidence and remaining composition

The source-bound receipt is
[`evidence/native-application-message-20261103/receipt.json`](evidence/native-application-message-20261103/receipt.json).
It retains original native observer receipts and compressed full byte snapshots.
The native component uses the actual ValueRuntime graph and explicit main-derived
compiler candidate, v4 kernel/v7 boot, unchanged code cap/stack/grants. Amu
performs module discovery, checking, compilation and packaging; Python only
stages public vectors, hashes bytes and observes QEMU. GDB writes only the
acknowledgement in a dedicated fixture receipt.

The corpus includes exact1MiB requests and responses, bodies larger than512KiB
after decoding, 70,000-byte IDs/header values, escaped names/Base64, Unicode,
header sets/case/duplicates/directions, malformed syntax, invalid types/numbers,
padding/pad bits, short actual views, aliases, tails and full output capacity.
Each completed case independently compares the **entire 1MiB+1 input, 8193-byte
work and 65537-byte output** with public expectations; separate cursor probes
cross64KiB with an escaped surrogate pair. The old113 frame cases,12 cursor
boundary guards and EDN/HMAC known answers also execute and retain full outputs.
Faults must normally complete the same entire corpus before detection.

Both-role encrypted receive regressions are separate diagnostic executions:
they retain the full1MiB/2048-part receive lifecycle and actual channel binding,
not a dispatch of these new schema records. Schema integration with completed
message lifetime, pending256, directed private-http policy, declared endpoint
and fresh trusted consent is still open. Native Mac backend, actual Mac/6600H
install/launch/peer/revoke/reconnect, protected configuration/entropy/time/floors,
native SSH, all mandatory desktop/distributed-OS/L1 production gates remain
open. Physical input is owner-paused; PXE/SSH/console are preserved. No deploy,
service execution, new approval, production qualification or ad spend occurs.
