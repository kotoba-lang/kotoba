# Flash probe: diagnostic core (JUN-766)

This is a source-level first slice, not an installed Itonami dapp or an
alternative to `f3probe` yet. It contains a pure Kotoba sampling planner,
result classifier and wraparound simulator. `main` runs its native self-test.
It has no disk I/O, UI, consent implementation, dapp registration, cache
invalidation or real-device test. A passing self-test says nothing about the
capacity of either attached SSD. The core is independently designed and does
not implement the `f3probe` algorithm.

The sample plan uses block 0, powers of two below the reported block count,
and the final block. A duplicate final block is intentional and must be
coalesced by the host before any writes. Input is a logical sector count from
2 through 2^62; the list is at most 64 entries. The pure simulator models a
simple wraparound device and detects some aliases within the chosen samples.
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
3. The host coalesces the plan and writes a complete logical block at each
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

The browser is not a raw block-device host. WebUSB is not assumed to grant
access to OS mass-storage devices. The current Itonami native runtime and macOS
bridge have not been shown to provide the exclusive scoped device capability,
trusted consent, USB pass-through or durable-read guarantees above. Therefore
this directory is **not registered** in the installed dapp catalog and no
capability is declared as implemented. Integration needs an actual native host,
trusted UI and a separate destructive QEMU fixture gate; physical-device
qualification comes after that. Do not execute the model against physical
storage.

## Native diagnostic test

Set `AMU` to the existing Amu macOS native CLI executable and `TMPDIR` to a
scratch directory under the workspace, then run `./test-native.sh`. It runs
the Kotoba source using native Amu, and a deliberately broken fixture must
produce a nonzero assertion count. This exercises the actual Kotoba functions,
not a Python copy. It does not test disk I/O or a dapp installation.
