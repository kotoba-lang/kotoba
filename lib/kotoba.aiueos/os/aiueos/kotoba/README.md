# Kotoba native kernel input

`kernel-probe.o` is the byte-for-byte output of the merged
`kotoba-lang/compiler` commit
`624d8f4e8adb2596b1151f22f843a9a73e797cb3` for the checked-in Kotoba sources:

```clojure
(defn main [] 42)
```

It was produced with:

```sh
bin/kotoba-compiler compile /path/to/aiueos/os/aiueos/kotoba/kernel-probe.kotoba \
  --target x86_64-aiueos-kernel-v1 \
  --output kernel-probe.o
```

SHA-256:
`10d91712fccd887e68f9caa25413c8fa2c783968e72b1bead4025c6a294ffa42`.

`ime-romaji.o` is the guest IME conversion (ADR-0090). It exports
`kotoba_aiueos_ime_commit`. Two latin bytes in; Unicode codepoint or 0
out. Vector: 107 (`k`) then 97 (`a`) must return 12363 (U+304B). Echoing
the latin bytes is leftover `:latin-leak`. Compiled at amu pin
`9cf3a0ac07a1fb0d735a460230a7e5e9c97bc6a7` with kotoba-native allow-list
entry `aiueos-ime-commit`. Pinned SHA-256 is
`ee11f50c9dfb30d03c820bead466b2f1bf18e4e64f3a2bfda98f5a5dd5d4ca34`.
Not mozc. Not hosted JVM IME. Default UEFI smoke still uses synthetic
input; `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-input` (ADR-0093) consumes a
virtio-keyboard used-ring event.

`wm-hit.o` is the guest WM hit-test (ADR-0091). It exports
`kotoba_aiueos_wm_hit`. Four i64 in (`n`, `front`, `px`, `py`); window id
or 0 out. Vectors match hosted `boot-desktop` rects: one-surface refuses;
overlap at (100,80) with front=2 returns 2; (40,40) with front=2 returns 1;
raise front=1 at overlap returns 1. Compiled at the same amu pin with
allow-list entry `aiueos-wm-hit`. Pinned SHA-256 is
`70fac07783c5b2841b76d9d599c03a97a44d290a8ad977f48aa5af39b21efc7f`.
Not hosted JVM WM. Native Phase 6 compositor leftover remains.

`scanout-bind.o` is the guest scanout-bind decision (ADR-0095). It
exports `kotoba_aiueos_scanout_bind`. Two i64 in (resource count,
enabled-mode count); bind count or 0 out. Vectors: one resource
refuses; one enabled mode refuses; two and two returns 2. Compiled
at the same amu pin. The native allow-list row `aiueos-scanout-bind`
must live in `elf64.clj` because the JVM loads `.clj` ahead of
`.cljc`. Pinned SHA-256 is
`5ca924dff9fe42620f2313d16f8f62018d9bfbf588c7b142383066cce65d8305`.
Not hosted JVM WM. One scanout when Kotoba admits two is leftover
`:one-scanout`.

`broker-admit.o` is the guest permission-broker decision (ADR-0096). It
exports `kotoba_aiueos_broker_admit`. Two i64 in (op, granted-op);
1 admit or 0 refuse. op 1 = clipboard, op 2 = file-picker. Vectors:
clipboard requested and granted returns 1; picker on a clipboard-only
grant returns 0. Compiled at the same amu pin. The native allow-list
row `aiueos-broker-admit` must live in `elf64.clj` because the JVM
loads `.clj` ahead of `.cljc`. Pinned SHA-256 is
`713bdc8e4c3d41ea9602fe9184741c15bd7a7b71d6f1b688a766a2d83714a48f`.
Not hosted JVM WM. Picker admitted on a clipboard-only grant is leftover
`:always-grant`.

`session-restore.o` is the guest session-restore decision (ADR-0098). It
exports `kotoba_aiueos_session_restore`. One i64 in (packed session
word); restored front window id or 0 out. Vectors: packed 2 returns 2;
packed 0 returns 0; packed 3 returns 0. Compiled at the same amu pin.
The native allow-list row `aiueos-session-restore` must live in
`elf64.clj` because the JVM loads `.clj` ahead of `.cljc`. Pinned
SHA-256 is `1983e5fa9026b2a356a4c43f6fa84630f6261ebd50c9939c4d657a326659048b`.
Not hosted JVM WM. Restore that always returns 2 is leftover
`:always-front`.

Run `scripts/reproduce-kotoba-kernel-object.sh /path/to/compiler` to compile the
checked-in source with that west-pinned compiler checkout and compare both
objects byte-for-byte. This pinned object is temporary cross-repository CI
input and may only be updated from a reviewed compiler artifact. The aiueos
verifier validates every supplied object before link and forbids host imports
or dynamic/runtime dependencies.

`sha256.o` implements the complete application-admission SHA-256 path in
Kotoba. Its five-argument kernel ABI accepts the message, its length, a
32-byte output, and a caller-owned bounded workspace. `kernel-load-u8-16k`
admits at most 16 KiB while the public function narrows application input to
12 KiB; the function requires 352 bytes from its caller-owned workspace and
workspace/output stores retain the ordinary 512-byte compiler
bound. The wrapper replenishes ten million fuel units and compiler-lowered
tail recursion reuses a fixed native stack frame across blocks and rounds.
Its pinned SHA-256 is
`ad28e7d83d6e582df2dacf802e915fc9532fc99e141e174e7bf8642191db2c29`.

`digest-equal.o` performs the fixed 32-byte SHA-256 comparison in Kotoba. It
always reads and accumulates all 32 byte differences before deciding, uses the
compiler's 512-byte bounded load primitive, and exports
`kotoba_aiueos_digest_equal`. Its pinned SHA-256 is
`6d005bf596ff10343377d9c243d473437fa272559b7f9130cba47cc4cd80d3aa`.

`app-catalog-valid.o` validates the authenticated aiuefs application catalog
in Kotoba: canonical header and IDs, one-to-four entries, 12 KiB extent bounds,
signer policy, capacity, and all data/signature/catalog collision pairs. Its
five-argument ABI receives catalog bytes, capacity, and an 8-byte routing
receipt containing the already-bounded catalog sectors. Its pinned SHA-256 is
`bf990c3775bd1351627daa669a124adad8e194710dc41d93f0c1b2ccfdacd927`.

`app-lookup-plan.o` scans every admitted packed metadata record for a 16-byte
application ID, validates `ready` and the 12 KiB length bound, and returns only
a packed one-based index/length plan. C dereferences the selected object after
rechecking that plan's public bounds. Its pinned SHA-256 is
`aa8ecea382820707638aa24e49226dbab243c95dc2a28ebfe3fac3a4dffe1a6c`.

`user-elf-valid.o` owns user-process ELF admission: the ELF64/x86-64 header,
the fixed RX and RW+NX load segments, all image bounds, and the 88-byte native
runtime context ABI. C only copies the admitted fixed-layout segments into a
new address space and maps them. Its pinned SHA-256 is
`b363aa7608f95c5fee37ddb95961c7e7524ca307f4d7407c4c25ca05435426ab`.

`user-context-build.o` constructs the complete 160-byte ring-3 interrupt
return frame in the final bytes of a bounded 4 KiB kernel stack. Kotoba owns
zeroed registers, RIP/RDI, user CS/SS, IF and user RSP; the C scheduler stores
only the returned frame pointer. Its pinned SHA-256 is
`8e743cba708c79e6800d5c0f26c68dfefe055179f2bef8e24753012a4bc21e5b`.

`kernel-context-build.o` is the kernel-selector twin: the same 160-byte frame
in the same bounded 4 KiB stack, for tasks `iret` enters at ring 0. CS 0x08,
SS 0x10, and an RSP that is the top of that very stack rather than a separate
user stack -- eight bytes below the ring-3 frame, because `iret` lands in an
ordinary C function and must reproduce the `RSP % 16 == 8` that `call` leaves.
It computes the 16-byte alignment rather than assuming it, and its byte split
is exact over the whole unsigned range. Its pinned SHA-256 is
`PENDING_DIGEST`.

`page-mapping-plan.o` owns per-process virtual-page selection, private-page
isolation, user RX versus RW+NX permission classes, bounded image-page sizes,
duplicate-map rejection, and executable-entry admission. C translates the
admitted permission class to x86-64 PTE bits and installs physical pages. Its
pinned SHA-256 is
`c492472360f4632a5f4e0457ef3f2dd867306a36ea8ba3415cdb4463c78106b5`.

`process-create-plan.o` scans the complete eight-slot native process table and
owns domain validation and duplicate rejection, deterministic free-slot
selection, and non-zero 16-bit generation advancement including wrap. Its
recipe stages identity/address-space, execution, result, task binding, and
active publication around native resource acquisition. Its pinned SHA-256 is
`487d01555529e78c2df4321c467c807886b7ec7fa7a8f073701aed6e1ebf5f57`.

`process-teardown-plan.o` enforces the native teardown state machine: a reaped
task must revoke its owner's capabilities before its address space is
reclaimed, and only then may its descriptor become inactive. It also enforces
the domain-specific minimum revocation evidence and returns the final
execution/ownership/task/active/result clear recipe before reclaim is
committed. Its pinned SHA-256 is
`0a82d0757a24557e6b82de2ef195a712b5f489e0fb9acbe227ed2d9f62aecb13`.

`task-slot-plan.o` reads the complete nine-slot native scheduler table and
owns deterministic non-kernel slot allocation, non-zero generation advance
with wrap, stack-presence exclusion, and inactive-with-stack release
admission. Allocation plans carry the pointer/counter/CR3/service/generation/
active initialization recipe; release plans preserve generation and carry the
pointer/counter/CR3/service clear recipe. C only allocates/frees stack pages
and transactionally applies the admitted recipe. Its pinned SHA-256 is
`084118840d07e6e4db568215dac1e7c064b437de78f9c9043aa98a67469e077f`.

`scheduler-dispatch-plan.o` owns timer-tick exit-to-reaped admission and the
bounded round-robin selection of the next active task, including selection
against the post-reap table state. Its recipe drives reap, current-task and
switch counters, user-domain/kernel-stack publication, CR3 switching, and
outgoing context/counter updates. A restarted service retains its reconstructed
context instead of being overwritten by the interrupted frame. C applies those
admitted native mutations. Its pinned SHA-256 is
`b23dbea5125611ad041a16c548a083d94f0c4571ba68f5436e3feff16a099006`.

`task-exit-route.o` performs a complete bounded task-table scan for a requested
user domain, rejects kernel/invalid domains and duplicate active owners, and
returns the unique task slot eligible for an exit request. C only commits the
exit-request bit on that admitted slot. Its pinned SHA-256 is
`dbf1dacb2d4a2fc0adf49134cbd6b973fa3a85e780f3d2b242a9baacb28799d2`.

`service-task-transition.o` connects lifecycle candidates to native task state.
It returns the complete generation/restart/action commit plan plus an explicit
state/context/task mutation recipe, admitting spawn
only for inactive services with no assigned slot, restart/query only for a live task, and terminate
only for a non-current live task. C executes the admitted allocation, context
reset, or release without reconstructing lifecycle state or mutation intent.
Its pinned SHA-256 is
`a6b70f28d7b63a64b9b0ff0b66eba0e465a65caa39b0413f34eef5245d32d466`.

`rsa2048.o` implements RSA-2048 public exponent 65537 and the complete
PKCS#1 v1.5 SHA-256 encoded-message comparison in Kotoba. Its five-argument
kernel ABI accepts a 256-byte signature, 32-byte digest, and caller-owned
workspace. The public function requires 1284 bytes; compiler-emitted 4 KiB
load/store guards and a 250-million-unit fuel receipt bound every access and
loop. Its pinned SHA-256 is
`97a6c6b1f4c3f3569bf8d40423db924d291aa0b6f10cd7bace79f54e193387a6`.

`journal-plan.o` is produced by the same compiler revision from
`journal-plan.kotoba`. It exports the four-argument SysV function
`kotoba_aiueos_journal_plan`. Given validity and sequence values for both
bounded journal slots, Kotoba selects the latest committed slot and returns the
next sequence, alternate write slot, and recovery flag as a packed 64-bit plan.
The C substrate retains bounded virtio I/O and validates the returned plan
before replay or mutation. Its pinned SHA-256 is
`c24c7bdab170d65624c1ee2cb939b949c94750b651f59b5aa7d4bc192ec62df6`.

`fnv1a.o` moves every checksum used by the superblock, journal record,
transaction payload, and mutable object validators into Kotoba. Its
`kotoba_aiueos_fnv1a(base, length)` export uses `kernel-load-u8`, whose compiler
lowering rejects null bases, lengths above 512 bytes, and unsigned indices at
or beyond the supplied length before touching memory. Invalid access traps;
there is no host import or ambient address-space API. Each public call receives
an independent 1024-fuel budget, sufficient for the admitted 512-byte maximum.

`journal-record-valid.o` and `object-transaction-valid.o` construct
little-endian 32-bit fields from checked byte loads and perform magic,
version/state, length, sequence, and checksum validation in Kotoba. C supplies
only the address of its packed record and the exact structure size; invalid
records return false before replay or mutation.
`object-transaction-route.o` additionally returns the checksum-validated object
class and target sector as one route receipt. Native virtio-blk code consumes
that receipt for service/domain apply and recovery instead of branching on raw
transaction fields. Its SHA-256 is
`ab98299f535a2d0752135032b960d7830cca8aee4cdfff8a2f4952d897cfe3dd`.

`superblock-valid.o` owns filesystem magic, header shape, object bounds, and
payload checksum validation. `mutable-object-valid.o` owns materialized object
magic/metadata/checksum validation and bounded byte equality against the
committed transaction. Together these complete the storage read-side
validation path in Kotoba; C retains sector I/O and passes exact buffer sizes.
The validator uses a non-recursive fixed-stack FNV and unrolled 16-byte
comparison, including the user-object readback and boot replay paths.

`journal-record-build.o` and `mutable-object-build.o` use the checked
`kernel-store-u8` lowering. Null, oversized, and out-of-bounds writes trap
before mutation. Kotoba now serializes journal/transaction metadata, sequence
payloads, checksums, mutable-object metadata, and transaction bytes. C clears
the sector, invokes the builder, and owns only the subsequent virtio-blk I/O.
The mutable builder copies the committed payload with fixed-stack unrolled
stores, so service and user transactions share the same Kotoba materializer.

The PCI planners validate real hardware-derived inputs: vendor capability
length/BAR/32-bit range, probed BAR extent shape, and MSI-X table/PBA regions.
Config-space reads, BAR probing writes, MMIO mapping, and interrupt programming
remain in C; their derived bounds must pass Kotoba before use.

`syscall-range-valid` owns the bounded half-open range decision used by both
CPL0 bootstrap and CPL3 log-write syscalls. It rejects empty, out-of-window,
high-half, and wrapping pointer/length pairs before the native syscall layer
can consume user memory. Interrupt entry and capability dispatch remain native.

`user-smoke.kotoba` is compiled with the least-privilege
`user-runtime-policy.edn`. Its admitted `cap-call 2` through `cap-call 5` lower to the compiler's
aiueos runtime-v2 trampoline and native syscall 5. The loader installs a
domain-owned object-read/service-send handle at context offset 80 only after authenticating
the ELF; the static context otherwise contains no handle or kernel address.
Both catalog processes read service-registry object 0 and send payload 42 to
their domain-bound persistent service mailbox before returning 42. The kernel
independently checks type, rights, owner, operation, object index, mailbox
capacity, recipient mapping, and payload bound on every call. Service tasks
consume both messages under their reserved CR3s and remain active after all
user address spaces and stacks are reclaimed.

`copy-in` then transfers an admitted payload into a 256-byte kernel-owned
buffer. Both source and destination accesses use the compiler's trapping
bounded-byte operations, recursion consumes replenished freestanding fuel, and
the syscall records a Kotoba FNV hash of only the copied bytes. Oversized calls
are rejected before either buffer is touched.

`capability-plan` derives the only admissible 63-bit handle from a table slot,
generation, type, active bit, rights, and the requested type/rights. The same
planner issues and checks handles. Revocation clears active state and advances
the generation before reissue, so stale, wrong-type, and insufficient-rights
handles cannot alias the live slot.
Generation exhaustion retires a slot instead of wrapping to an older identity.

`value-handle-plan` is the C-free decision core for the future CPL3
ValueRuntime table. It admits only four closed operations (allocate, resolve,
cid-of, release), caps the table at 4,096 live handles, requires an observed
entry to be exactly live before access or release, and advances allocation
monotonically through handle 4,096. Release never rewinds `next-handle`, so a
stale word cannot acquire a new meaning. The returned packed recipe contains
the selected handle, next monotonic handle, and post-operation live count; the
process-local mechanism must recheck and apply it under one lock. This planner
does not read CAS blocks and does not grant object authority. Persistence and
hydration remain behind the typed aiueos capability broker.

`value-handle-arena` is the first stateful mechanism behind that decision. It
owns one process RW/NX 4 KiB page, a versioned 64-byte header, and 63 physical
slots. Logical handles still advance monotonically from 1 through 4,096;
released physical slots may be recycled only because every lookup compares
the newly stored logical handle, so an old word remains invalid. The object
initializes, installs, resolves, returns a CID token, and releases under its
own bounded u32 lock. Lock acquisition and release compile to the new Kotoba
`kernel-compare-exchange-u32` intrinsic, whose x86 implementation checks the
complete base/length/index window before emitting `LOCK CMPXCHG`. The exported
object has no imports. Its value/CID tokens are opaque provider descriptors,
not pointers and not capabilities.

`value-runtime-dispatch` links that arena, the bounded SHA-256/digest verifier,
and the sealed provider transport into a C-free Kotoba object.
It accepts only a fixed 96-byte normalized request plus a trusted transport
profile, validates the exact 4 KiB capability-table entry (slot, generation,
type, active state, rights, owner domain, and reconstructed handle), and routes
local operations directly to the arena. Persistence requests enqueue the
existing typed provider routes—wire 15 for `intern`, wire 14 for `hydrate`—and
retain the request-originated expected digest from bytes 24..55 before returning
only a bounded ticket. Local operations require that digest range to be zero.
User phase=1 completion is rejected.
Its exact native export has no imports and retains the arena's bounded
`LOCK CMPXCHG` state transition.

`value-runtime-entry` closes the next boundary without C. Assembly supplies a
trusted packed profile containing the current process domain and request
offset. Kotoba admits a 104-byte subregion of the current process's private
4 KiB page, rejects offsets beyond 3,992 and non-zero reserved suffix bytes,
copies request bytes 0..55 into a kernel-owned 96-byte scratch envelope, and
zeroes bytes 56..95. The expected digest occupies raw bytes 24..55 and the
presented capability handle at raw bytes 56..63 is
decoded as a separate scalar and is never copied into the normalized request.
The closed seven-module object then enters `value-runtime-dispatch`; it has one
exact export, no imports, bounded loads/stores, and the arena atomic operation.

`native/value-runtime-kernel.kotoba` links that complete graph into the pure
Kotoba native kernel image beside its boot entry. The transport-only
deterministic ELF64 image has ten closed modules. Linking ValueRuntime-owned
copies of the already qualified pure-Kotoba SHA-256 and fixed-work digest
comparison with
`value-runtime-cas-verify` produces a thirteen-module image with an
`aiueos_kernel_entry` boot entry, the ValueRuntime entry/domain/provider/CAS
exports, no imports, and no C/foreign object receipt. This is
the production ownership direction; the larger C kernel remains a QEMU
compatibility/regression fixture and is not evidence for this image.

`value-runtime-syscall-plan` owns the return-state decision required before a
pure-kernel `SYSCALL` shim may call that entry. It admits only syscall 5, a
trusted domain 1..32767, a canonical low-half user pointer whose 104-byte
envelope stays within one page, and canonical low-half user RIP/RSP. Its only
positive result is the packed trusted entry profile; assembly need not repeat
or reinterpret those security predicates.

The x86 pure-kernel packager now supplies the privilege substrate that planner
will return through: a closed GDT, TSS with RSP0, and page-aligned 64 KiB
kernel stack in the image's sole RW segment. Its boot shim switches to that
stack, reloads the GDT and all segment selectors, loads TR, and only then calls
Kotoba `main`. The C-free ELF/embedded-UEFI image traverses this path under
OVMF/QEMU and reaches the existing `M` marker.

`value-runtime-domain` gives the scheduler a narrow publication boundary. It
accepts only domains 1..32767 and invokes the kernel-only
`kernel-publish-current-domain` intrinsic, which writes the scalar to private
context offset `0x110`. Kotoba code is not given the context address or a raw
unbounded store. This domain is authority ownership used to choose runtime
state; it is deliberately distinct from ValueCID, Handle, and RAM address.

The closed x86 image now installs EFER.SCE, STAR, LSTAR and FMASK when—and only
when—the artifact exports both the five-word planner and five-word normalized
entry. LSTAR saves user return state, switches to TSS.RSP0, calls the compiled
Kotoba planner, skips the entry on rejection, or supplies the image-owned
scratch/capability-table/arena regions on admission. Before `sysretq` it
whitelists user arithmetic flags and IF and clears privileged RFLAGS state.
The verifier independently decodes both native call displacements and proves
they name the compiled Kotoba exports.

The current `kernel/syscall.c` dispatcher remains unqualified and unchanged.
The remaining native work is canonical value/descriptor binding after digest
verification and positive/negative CPL3 QEMU semantic vectors. Until those
identity and execution vectors exist, production native
ValueRuntime admission remains closed.

The live capability table is no longer a permanently zeroed placeholder.
`value-runtime-capability-table` derives its address through a zero-argument
kernel intrinsic, so mutation callers cannot redirect writes. Slot zero is an
atomic table lock shared with dispatch admission; issue publishes active last,
revoke clears it first, and generation/type/rights/owner plus the exact handle
are checked under the same lock. This closes torn reissue/stale-generation
races without turning a capability into a CID, Handle, or pointer.

The integrated image exports only the policy boundary, not that raw mutator.
Provider status is a private active+generation word at context `0x138`.
Scheduler grants admit exactly hydrate=1, intern=4, or their union=5 and bind
the current provider generation into each table record. Dispatch compares it
again, so provider stop/restart invalidates prior authority immediately.

`value-runtime-provider-transport` owns an image-private 512-byte queue at
context offset `0x400`. Seven fixed 64-byte slots move atomically through free,
pending, and claimed states. Submit stores ticket, route, trusted domain,
capability handle, and the request-originated 32-byte digest, then publishes
state last. The trusted provider claim export
returns packed ticket/route/domain metadata; completion succeeds only for that
claimed triple, hashes the returned block in the image-private CAS scratch at
`0x600`, compares all digest bytes, and only then installs into the
image-private arena at `0x2000`.
Wrong-route/domain completion leaves the claim live, lock contention and queue
exhaustion fail closed, tickets never wrap or reuse, and no user pointer enters
the queue. A digest mismatch also leaves the claim live. The next boundary must
parse the verified block as canonical `kotoba.value.v1` and bind the opaque
completion descriptor to that decoded value.

`value-runtime-cas-verify` is the next C-free mechanism. It hashes a bounded
1..12,288-byte provider block with `value-runtime-sha256.kotoba`, compares all
32 digest bytes with `value-runtime-digest-equal.kotoba`, and is linked into the
kernel root as an exact
five-word native export. The 160,024-byte image has no imports or foreign-code
receipt. The 104-byte request envelope supplies the expectation, entry and
queue retain it, and completion must pass this verifier before Handle install.
Canonical `kotoba.value.v1` validation and descriptor binding remain mandatory
after this request-bound integrity gate.

`capability-mutation-plan.o` admits issue, recursive revoke, and derivation
parent binding as explicit recipes. Native code applies type/state/owner/parent
publication, generation retirement, and pending-transfer invalidation only
after validating the complete recipe. Its pinned SHA-256 is
`c3f09111a488919f53fec08623fef28ed99e714d2cc3e70f929d4cca61f2f277`.
The state also carries a 16-bit owner domain and each request carries its
caller domain. Owner equality is decided inside the planner, before payload
copy, so kernel and user slots cannot be used across their security domains.

`service-lifecycle` owns supervisor spawn, restart, and termination decisions.
It emits a packed action plus generation/restart state; a failure advances the
generation and restart count only while both remain bounded and the configured
budget is not exhausted. The native scheduler consumes that plan to allocate,
replace, or release a generic descriptor-driven task context; it does not
duplicate lifecycle admission in C. The pinned object SHA-256 is
`cd6d9c57cd4dd94839ef1a255c6d82b6c1b231c08aa1f7de86ab8c0029720816`.
Spawn accepts both a new zero-generation descriptor and a validated persisted
generation, allowing journal replay to recreate service tasks without resetting
their durable lifecycle counters.

`service-registry-build` serializes the two bounded scheduler service states
into a versioned 16-byte registry inside the journal transaction. It writes all
transaction and journal metadata and checksums with bounded stores. The native
virtio-blk substrate supplies the observed states, commits the journal before
materialization, and verifies readback/replay. Its pinned object SHA-256 is
`9ce4cef685204533e2fe92a5a08d1ec86f4c8299b1e39e16284484222fb1910c`.
After the common Kotoba transaction checksum validator passes,
`service-registry-state` validates the complete `SRV1` routing/schema contract
and returns either indexed state.
Its fixed-stack object SHA-256 is
`d73f13de0d86a4af46e33516b8b0f6358b5d477307c61d40624b971f34c15f3e`,
so the native substrate no longer parses service registry payload bytes.

`user-object-journal-build` defines the compiler-checked journal schema for
domain-owned objects. User tasks submit capability 4 writes and read capability
5 receipts; the kernel task commits domains 4/5 through independent dual slots
44–47 into objects 42/43. Recovery replays each domain's highest valid sequence
before new user code is admitted. Its pinned object SHA-256 is
`c3e1b1090493ecc07c4e6c8839900abef2e8e7cdcdf900dfe605f478086853bf`.
The paired fixed-stack validator is
`0f2015e53ed083741687abfbaff72edf8a525947b9fc753cacc7a1bf10faf46f` and
the value decoder is
`bd1de2777d75e02968939d2b7bc74e84dc16a8a9431fe36bd2c2170d6866fad3`;
all three use bounded loads/stores without recursive calls. The decoder is
called only after the complete domain-routed journal contract passes, so C no
longer parses user payloads.

## Why these objects pack fields into one `i64`

47 of the 59 objects here take apart an integer with `bit-and`/`quot` on the way
in, or build one with `+`/`*` on the way out, or both. Read on its own that
looks like the way one writes Kotoba. It is not. It is what **this ABI** is.

The C kernel declares every one of them as a function of words:

```c
extern uint64_t kotoba_aiueos_capability_plan(uint64_t slot, uint64_t generation,
                                              uint64_t type, uint64_t state,
                                              uint64_t request);
```

One `uint64_t` comes back. A capability decision has more than one field in it —
slot, generation, type, rights — so the fields are packed into that one word at
the boundary, and the caller's fields are unpacked from theirs. The packing is
**at the edge in both directions**: in `capability-plan`,
`scheduler-dispatch-plan`, `task-slot-plan` and `journal-record-build`, read
while writing this note, every `bit-and`/`quot` takes a parameter apart on entry
and every `+`/`*` builds the return value on exit — nothing packs a word only to
unpack it again inside. That was not checked across all 47.

Two things follow, and they are easy to get backwards:

- **This is not a backend gap — though the backend is narrower than "records
  work now".** The native admission gate
  (`only-native-word-typed-features?` in `kotoba-lang/kotoba-kir`) takes record
  fields from `#{:i64 :bool :string :keyword}` and admits `record-new`/
  `record-get` in exactly one shape: `record-get`'s value operand must be a
  directly-nested `record-new` of the same schema. A record that escapes — is
  returned, stored, or passed on — is not admitted, and neither are maps,
  variants, typed sets, heterogeneous vectors, or generic options/results. So an
  object here can name its fields at the point it projects them, and no further.
  Even where a record does fit, the return still flattens to one word, because
  the flattening is demanded by the C declaration and not by the compiler.
- **So do not copy this shape into Kotoba that is not on this ABI.** Ordinary
  Kotoba has maps, sets, records and recursive values, and the rest of the
  workspace has already moved the other way — murakumo's T5.3 removed base-N
  packing from its planners in favour of records. Code written to a constraint
  has to say so, or the next reader mistakes it for the style
  (superproject `ADR-2608650000`).

**Removal condition.** These stop packing when the C↔Kotoba kernel ABI carries
more than one word per call — a multi-word return convention, or an
out-parameter written through a bounded store the way `sha256` already writes
its 32-byte digest. That is a change to the ADR-0015 split between decision-free
C mechanism and Kotoba decision, not a compiler upgrade to wait for.

**Why one symbol per object, and hence the duplication.** A kernel object
exports one symbol and cannot call another (ADR-0030), so shared guards are
repeated rather than factored — the two IPv4 checksums (ADR-0021) and the three
`cpuid` objects are the worked examples.
