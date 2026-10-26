# aiueos Deployment Profiles

Status: enforced baseline
Date: 2026-07-01

aiueos is a containment architecture. A deployment profile states which
additional claims a deployment is allowed to make beyond Phase-0 containment.

AIUEOS also has [product distributions](../distributions/README.md): `aiueos`
is the common OS and `awai` is Itonami OS, the same-core Awai Network composition.
Distribution is a separate axis from the security profiles below, ISA/target,
runtime class and diagnostic entry. Selecting Itonami OS does not select
`regulated`, add a grant or satisfy any evidence requirement below. Historical
hosted requirements here remain migration inventory under current native-only
build rules.

## Profile Summary

| Profile | Intended use | Allowed claim |
|---|---|---|
| `research` | local experiments, demos, early integration | capability containment only |
| `sensitive-local` | single-tenant local systems with sensitive data | containment plus host hardening and encrypted audit/data |
| `regulated` | systems needing auditable governance and crypto boundaries | containment plus evidence, key lifecycle, SBOM/SLSA, provider policy |
| `high-assurance` | future verified/sensitive deployments | blocked until formal and side-channel evidence exists |

## `research`

Required:

- deny-by-default manifest policy;
- Wasm fuel and memory limits;
- append-only audit enabled;
- clear non-claim of FIPS, side-channel resistance, and formal verification.

Not claimed:

- side-channel resistance;
- FIPS validation;
- hard real-time scheduling;
- production key lifecycle;
- release evidence packet completeness.

## `sensitive-local`

Required:

- all `research` controls;
- no untrusted co-tenant execution on the host;
- encrypted audit logs or encrypted audit storage;
- sealed audit format version, external audit key id, positive retention
  period, and a dated successful restore exercise;
- externally retained signed audit chain head and truncation exercise;
- sealed component-state format, per-component key separation, monotonic
  version, bounded snapshots, restore and deletion exercises;
- bounded Chicory interrupt watchdog configuration and dated infinite-loop
  overrun evidence;
- authenticated network-topic protocol v1, bounded wire size, sealed durable
  replay checkpoint and dated partition/rejoin evidence;
- strong OS entropy provider identity, exact health-test set, 4096-byte API
  bound and dated provider attestation;
- no deterministic `random()` for secrets, keys, nonces, or tokens;
- explicit operator review of granted `:network`, `:secrets`, and
  `:persistent-write` capabilities.
- a versioned side-channel decision covering timing, cache and Spectre classes,
  with enforced baseline mitigations and named residual-risk acceptance.

Not claimed:

- FIPS validation unless `regulated` provider evidence is also present;
- side-channel resistance against privileged local attackers.

## `regulated`

Required:

- all `sensitive-local` controls;
- key lifecycle register with active/retired/revoked/compromised states;
- signer expiry and revocation checks;
- root-signed monotonic lifecycle epoch, sealed checkpoint, delegation scope,
  convergence exercise and compromise-recovery exercise;
- SBOM and SLSA/in-toto provenance for release artifacts, produced by
  `kbb -M:attest <artifact-digest> <source-commit> [builder] [--isolated]`
  (`aiueos.sbom`, ADR-0017). Components are derived from the TCB inventory
  rather than a second scan, so the two cannot disagree; `:tcb-drift-check?` is
  the inventory check's real verdict, and `:provenance/isolated-builder?` is
  required from the caller rather than defaulted to true. The documents are
  EDN matching `kotoba.security.supply-chain/evaluate-attestations`, not
  in-toto/DSSE envelopes yet, and the release pipeline does not call the
  generator automatically;
- package/component verification evidence;
- the digest of the versioned TCB inventory and a successful drift check;
- monitoring and incident-response exercise evidence;
- FIPS provider policy when a FIPS claim is made.

Not claimed:

- FIPS validation without named module certificate and boundary evidence;
- production PQC migration without hybrid envelope evidence.

## `high-assurance`

Blocked until evidence exists for:

- side-channel threat model and mitigations;
- formal verification or equivalent high-assurance argument for the broker and
  host ABI;
- hardened TCB boundary;
- reproducible, signed, independently verified release pipeline;
- PQ/hybrid key wrapping for long-retention private data.

No release should use this profile today.

## Release Note Requirement

Every release note or deployment report must name one profile and list the
non-claims that remain true for that profile. If the profile is omitted, the
deployment defaults to `research`.

PID-1 enforces this policy before invoking the component launcher. Explicit
profiles use `:aiueos/deployment-profile` and a
`:aiueos/profile-evidence` map with `:profile/version 1`. Missing controls,
unknown profiles, unsupported evidence versions, and every
`high-assurance` request fail closed. This admission record asserts that
required controls were supplied; independent evidence verification remains a
release-gate responsibility.

Production at-rest storage is defined in `docs/sealed-storage.md`. Audit
records and component snapshots are AES-256-GCM sealed under external,
purpose-separated keys. Signed external audit heads prove completeness;
component identity and monotonic state versions prevent substitution and
rollback.

The side-channel decision schema is enforced at the same PID-1 boundary.
`sensitive-local` requires single tenancy and constant-time cryptography;
`regulated` additionally requires SMT disablement, core isolation, and
speculation controls. The normative baseline and residual risks are recorded
in `docs/threat-models/side-channels-v1.md`.

Execution remains explicitly non-real-time, but it is no longer unbounded:
the normalized manifest retains a wall deadline (maximum 30 seconds), and the
host wraps both Chicory instantiation and `main` in a dedicated interruptible
worker. A timeout is a failed run and boot cannot proceed. Production evidence
must name this engine, bound its deadline and termination grace, and date a
successful overrun test.

## Timing profiles

Timing is independent from the security profiles above. The default
`:aiueos/timing-profile :best-effort` preserves current behavior. An image may
name `:hard-real-time` only as the separate
`x86_64-aiueos-rt-kernel-v1` native artifact defined by
`os/aiueos/contracts/rt-kernel-v1.edn`. Linux, the JVM, GC and hosted adapters
are not fallback paths for that artifact. The existing native-kernel receipt
is explicitly `best-effort` and `rtos_qualified=false`; this is currently a
contract, not a claim that an existing AIUEOS image has qualified as an RTOS.

`aiueos-plc-v1` is an application profile above that separate RT kernel. Its
engineering path compiles the admitted IEC 61131-3 Structured Text subset to a
static `x86_64-aiueos-user-v1` ELF; deployed machines do not interpret ST. A
PLC build is not deployable until its receipt binds the qualified RT kernel,
exact I/O map and response-time admission analysis. Input snapshot, shadow
output, watchdog and atomic commit are the only program capabilities. The
native QEMU gate now proves bounded P-256 admission and tamper rejection, then
100 absolute-tick releases of the same generated ELF at CPL3, capability
syscalls, fixed-priority interrupt preemption, replenishment, those
transactions and safe-state failures. It reports logical ticks, not
milliseconds. Production signing authority, long-duration soak and physical
timing qualification remain open; their receipt fields fail closed. The
normative contract is
`os/aiueos/contracts/plc-runtime-v1.edn`.

Cross-machine topic samples use `aiueos.network-topic` protocol v1. Ed25519
binds channel, publisher, topic, sequence, epoch and value. Registry topic
allow-lists authorize publishers; sequence checkpoints prevent replay across
restart; partition backlogs apply contiguously and atomically. See
`docs/network-topic-protocol.md`.

Security entropy uses the versioned profile in `docs/entropy-profile.md`.
Production admission requires the strong OS source, concrete provider and
algorithm names, all three online health checks, and the exact request bound.
FIPS claims additionally bind this provider to the named validated boundary.

Regulated signing authority uses `docs/key-lifecycle.md`. The deployment binds
the root fingerprint and current epoch digest; the launcher refuses unsigned,
rolled-back, skipped, forked, expired or delegation-invalid lifecycle updates
before manifest verification.

## Confidential-VM postures: TDX and SEV-SNP (2026-09-15)

aiueos can now detect and self-report as a confidential guest, and the
monitor (`kotoba-lang/vmm`) can admit or refuse such a launch by decision —
but no profile above yet claims TEE protection, and this file is where a
claim would have to appear first.

What exists (measured):

- `os/aiueos/kotoba/tee-guest-detect.kotoba` — the guest's own decision:
  TDX = CPUID leaf 0x21 virtualised AND the mapped firmware window in the
  0xFE000000–4 GiB TDVF region; SEV-SNP = SEV (Fn8000_001F EDX 31) AND SNP
  (EDX 11) bits. Route and test: `test/aiueos/tee_guest_detect_test.cljk`
  (16 assertions green on the JVM amu→KIR route).
- `kotoba-lang/vmm` `tee_core` — launch admission, hypercall decoding,
  PSC error naming, port-I/O device model for both profiles; green on JVM
  and kbb (see that repo's README for the boundary).

What does not exist yet, stated plainly:

- no `.o`: the detect object has no C call site (`kernel/cpu.c` probe) and
  no compiled artifact pinned in `build-uefi.sh`; linking it is a kernel
  change in its own commit;
- no mechanism: `aiueos.hvt` issues no KVM_SEV_*/KVM_TDX_* ioctls; a TEE
  launch on a non-TEE host must (and does, at the decision layer) refuse;
- no attestation handling: TDREPORT / SNP report verification, quote
  verification keys, and the secrets/CPUID page consumption are
  unimplemented and unmeasured.

Therefore: no deployment may claim confidential-computing protection.
Until the mechanism exists and the attestation path is measured, TDX and
SEV-SNP presence changes nothing in this table.
