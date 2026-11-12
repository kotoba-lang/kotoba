# Segmented request source candidate

Kind 11 proposes list<bytes>/list<bytes> on fs/app-data wire 35/provider 5/
handler 7, WRITE/APPEND plus proposed FS2 stage-member (16/Q). C1 grants and owning op-49 form checks still
precede target access. There is no new wire/grant or generic provider route.
All sixteen original forms remain. Q is a proposed extension only under
kind 11; kind 1/8/9/10 reject it before path access, with no legacy token.

read-chunks-fragment uses the alias-safe C3 boundary. It resolves the outer
list, then every inner bytes handle/window, checks each length and all byte
words, and guards aggregate i64 addition before allocation. It asks the same
sealed op-6 pool policy, rechecks remaining budget by subtraction, then copies
the complete raw request span. Both passes are synchronous; the pure owning
decision cannot mutate the list. Six private words at 1704..1744 retain only
current-call metadata and are written before use.

The original WRITE/APPEND now receives one complete span and retains one file
descriptor throughout its full write loop. Path UTF8 checks apply to kind 11
as to kind 8; payload bytes stay arbitrary. Results use the existing segmented
converter. No chunk-sized reopen, truncating success, oversized language byte
value or new aggregate limit is introduced. Actual pool/arena budget remains
a qualification obligation.

Stage-member tail is 1..6 octal mode digits, NUL, raw payload. It validates
mode before creation, exclusively opens a no-follow 0600 file, fchmods before
bytes, writes all bytes, fsyncs and checks close through the SAME descriptor.
Mode 0000/0400 therefore does not require a now forbidden reopen. Only full
success acknowledges payload "1"; denied scope answers "0". Unlike ordinary
WRITE/APPEND this is a durable staging operation, not an echo. No original
form's meaning changes. Detailed native stage failure diagnostics remain
unqualified, as do actual exclusive/permission/durability/refusal behavior.

The paired IO source prepares all seven public names and ordered private
output-set publication. Native terminal-trap cleanup is still UNQUALIFIED:
an exit_group trap does not execute a source Result cleanup branch. Exact
updated C1/handler artifacts, full list/record/runtime/GMIR/lowering admission,
actual crash/permission/scope/resource/refusal/corpus evidence, complete
callers/Definition CIDs/owning mains/locks and self-rebuild remain open.

No tests added/run; no compiler/generator/assembler/provider/implementation
executed. No workflow/protection/profile/lock/CID/live service or production
route activation occurs.
