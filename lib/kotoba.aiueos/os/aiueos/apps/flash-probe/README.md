# Flash probe: diagnostic core (JUN-766)

The target is an Itonami dapp running locally on Amu native selfhost. This
is a source-level first slice, not an installed dapp or an alternative to
`f3probe` yet. It contains a pure Kotoba sampling planner,
result classifier, wraparound simulator, and a separate in-memory write/read
backend. `main` runs its native self-test.
A separate native FS2 test writes a bounded serialized model to ordinary
files and reads those files back. It has no raw disk I/O, UI, consent
implementation, dapp registration, cache invalidation or real-device test. A passing self-test says nothing about the
capacity of either attached SSD. The core is independently designed and does
not implement the `f3probe` algorithm.

The sample plan uses block 0, powers of two below the reported block count,
and the final block, omitting it when it duplicates a power of two. Input is a logical sector count from
2 through 2^62; the list is at most 64 entries. The pure simulator models a
simple wraparound device and detects some aliases within the chosen samples.
The in-memory backend writes and subsequently reads four words per simulated
block, including a wrapping model. The FS2 fixture persists those simulated
blocks to regular files, reads them back and applies the same verification.
Wraparound is simulated before the file write; it is not a virtual block
device. Neither test models physical caches or raw block I/O.
Other fake controllers, caches, remapping, faults, and capacities can evade the
plan. A matched sample run is **inconclusive**, never a genuine/16 TB verdict
or an estimate of usable capacity. A mismatch indicates observed corruption,
not proof of fraud. I/O error, incomplete execution, and invalid input cannot
become success. Independently selected data or a full fill/readback is needed
for broader evidence; reliability over time needs separate testing.

## Host contract before device access can exist

1. A privileged local host enumerates devices and reports a session-bound,
   stable identity, whole-device size and logical block geometry. The UI shows
   the exact device, size, transport and that the probe overwrites data. The
   host denies internal/system, mounted, busy, unknown or changed devices and
   must not interpret a stale BSD or Linux device number as identity.
2. A fresh trusted human choice binds the destructive operation, exact device,
   geometry and session. It is single-use, never supplied by the dapp itself;
   cancellation, disconnect, identity/geometry change, timeout or restart
   invalidates it. No write occurs until exclusive access and this choice are
   confirmed. Release exclusive access on every failure.
3. The host validates the plan and writes a complete logical block at each
   address using independently generated, per-run unpredictable data bound to
   the address. It validates offsets and checked byte-size arithmetic before
   each I/O. It then flushes, closes and reopens the **same** device, verifies
   identity again, and reads every block back from the device. A flush failure,
   short read/write, reset, remount, identity change or unavailable cache
   bypass ends the test as error/inconclusive. The host cannot claim cache
   bypass merely because close/reopen succeeded.
4. Report requested/completed samples, mismatches, I/O failures and whether
   persistence/cache conditions were verified. A clean sample report remains
   inconclusive. Retain no contents from the drive and send nothing remotely.

The existing public Amu macOS native CLI runs a single pure guest and denies
guest filesystem and process capabilities; its FS2 development provider is
scoped to regular files. Neither currently provides the scoped raw block-device
capability, target-bound trusted consent, exclusive access or durable-read
guarantees above. The intended host is therefore a new native Amu capability
broker and native local UI or CLI approval flow, not a browser application.
This directory is **not registered** as an installed dapp and no capability
is declared as implemented. Integration needs the native host capability,
trusted interaction and a separate destructive fixture gate; physical-device
qualification comes after that. Do not execute the model against physical
storage.

## Native diagnostic test

Set `AMU` to the existing Amu macOS native CLI executable and `TMPDIR` to a
scratch directory under the workspace, then run `./test-native.sh`. It runs
the Kotoba source using native Amu, and a deliberately broken fixture must
produce a nonzero assertion count. This exercises the actual Kotoba functions,
not a Python copy. It does not test disk I/O or a dapp installation.

## Native scoped regular-file exercise

Set `AIUEOS_AMU_SOURCE` to the exact Amu checkout pinned in
`scripts/native-ci-inputs.json` and `TMPDIR` to workspace scratch, then run
`./test-file-native.sh`. The existing native generator assembles the checked-in
planner and fixture into Kotoba, compiles and signs it with the pinned native
Amu root and packager, and runs it with FD3 scoped to its own new temporary
directory. The guest writes and reads ordinary regular files, accepting a
nonwrapping model and detecting a wrapping model; a write-corruption mutant
must exit 1 without producing the success output. The runner removes the
fixture files. The test neither calls fsync nor defeats the OS cache; it is
not evidence of durability, virtual block I/O, or physical capacity.
