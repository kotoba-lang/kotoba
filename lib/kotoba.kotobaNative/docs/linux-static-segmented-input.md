# Segmented byte result source

Proposed kind 10 returns list<bytes> from string requests on fs/app-data
wire 35, READ/RANGE only. One complete operation retains one opened descriptor.
Partitioning occurs after the full trusted internal span and FS2 acknowledgement,
so paths are never reopened per chunk.

intern-chunks-fragment computes K with bounded subtraction and preflights
K+1 descriptors and N+K item words. Every chunk obeys byte/vector limits and
65536; the outer count is bounded too. All item/descriptor stores complete
before either counter publishes a handle. No aggregate 65536-byte limit,
truncated success or string conversion is substituted. Profiles exceeding
the existing 65536-byte string/bytes value bounds now refuse in planning.

The earlier raw byte fragments were unexecuted source. Static inspection
found x86 s0..s4 aliases t4..t8. All byte fragments now save complete C3 state,
use the distinct ctx/t0..t8/a1..a4 core, and restore state before publishing
outputs. Around request charging, descriptor facts are saved, s0 is restored
for state operands, then ctx is recovered BEFORE popping t4. Both ISA maps
are read as data. No generator or assembler was executed.

The paired Amu logical-buffer/input source preserves the 1 MiB/8 MiB domain
without oversized language values. Default pool/arena budgets do not prove
those workloads fit. Real resource evidence, general list/record/runtime
admission, exact decisions/artifacts, canonical GMIR and both ISA lowering,
full parent/caller/parser/hash/output integration and actual self-rebuild
remain open. No tests were added/run or implementation executed. No profile,
lock/CID, workflow/protection, live service or production route is activated.
