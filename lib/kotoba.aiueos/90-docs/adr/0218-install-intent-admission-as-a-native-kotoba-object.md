# ADR-0218 — the install-intent admission becomes a native Kotoba object

- Status: accepted
- Date: 2026-09-15
- Extends ADR-0213 (the first kernel conversion is a retirement) with the
  installer's own decision core, and ADR-0215's mechanism (kernel links
  compiler-emitted objects). Authority for the direction: ADR-0013 (C-free
  hard flip), root ADR-2607241100 (C is mechanism, Kotoba judges).

## What changed

The install intent admission — the DECISION that says yes/no/why-not to an
install on this disk with this intent — now exists twice, by design:

1. `os/aiueos/kotoba/install-intent-admit.kotoba`: the decision core as a
   pure Kotoba object, following the proven `cid-v1-admit` shape (single
   `aiueos-*` export, ABI capped at 5 arguments, checked `kernel-subregion`
   narrowing, `aiueos.sha256` reused). Ten reasons, 0–9, fully implemented:
   admit / expired / digest / model / transport / capacity / flags /
   destructive-flags / serial / length.
2. `os/aiueos/scripts/install-intent.cljk`: the production CLI keeps
   JSON/IO and the interactive flow. The verdict logic is shared by parity,
   not duplicated.

## What it cost: the upstream allowlist row

The object was refused at packaging with
`:kotoba/artifact-target-rejected` ("no admitted symbol"). The cause is
kotoba-native's frozen `kernel-object-entries` table: an `aiueos-*` export
only gets its own `kotoba_aiueos_*` symbol if the name is a registered row
(name → arity → symbol); everything else is refused. This is by design —
the kernel link surface is a closed set.

The fix went upstream, not around:

- kotoba-lang/kotoba-native `7da60185`: both elf64 twins (`.cljc` / `.clj`)
  carry the row `aiueos-install-intent-admit {:arity 2}`. Verified with the
  portable suite (12 tests, 24 assertions, 0 failures — two new: the row is
  admitted, and under its own symbol, not the probe).
- kotoba-lang/amu PR #993: pin advanced 9a98c3e → 7da60185
  (forward-only, compare ahead 4 / behind 0), `deps-lock.edn` regenerated
  by `lock-classpath.cljk`. Two pre-existing reds on the PR
  (browser-matrix windows-2025, windows-arm64) are identical to main's
  (same failing step names on ad12299b) — no new red.

## Evidence

- `install-intent-admit.o` (14,312 bytes) is committed with
  `.inputs/.provenance/.publication` sidecars. Compiles byte-identically
  from three compilations across two different paths; ABI-verified
  (`AIUEOS_KOTOBA_OBJECT_OK`, export `kotoba_aiueos_install_intent_admit`,
  0 imports, 1 relocation).
- Contract `os/aiueos/contracts/install-intent-admit-v1.edn`: 17/17
  vectors green, reasons 0–9 all observed, real SHA-256 digests.
- Parity gate (`test-install-intent-parity.cljk`): same cases through the
  CLI and the object, 6/6 ALL_OK. Tamper was measured red (8 FAIL lines)
  before landing.
- New gate `install-intent-admit-native` (tasks.edn): compile with the
  pinned amu → byte-compare against the committed `.o` → ABI verify.
  Determinism across worktrees measured; `AMU` defaults to `../amu`.
- Final tree (aiueos 81bb663, superproject pin 630ce4b): all four gates
  PASS — native / contract / parity / install-chain 22:22.

## What this does not do

- The kernel does not yet LINK the object (I3 chain untouched): the
  admission still executes via the CLI/KIR on the install USB. Linking it
  into the kernel build (with digest pinning, like relay's two objects) is
  the next tranche and needs the link-size budget re-measured.
- No hardware: I6/I7 unchanged, QEMU evidence only.
- The interactive install flow still runs on Node as install-time
  mechanism (ADR-0099 decision 3, unchanged).
