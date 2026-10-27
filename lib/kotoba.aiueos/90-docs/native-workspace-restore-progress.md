# Native workspace restore: AWAI-90

AWAI-90 is **in progress**. The opt-in local-draft probe now saves text on a
real guest block device and restores it in a fresh AIUEOS process. It does
not yet restore an Itonami workspace image or run a registered dapp. Keep the
[shared Browser gate](shared-browser-native-progress.md), user-target admission
and signed release/head acceptance open.

The source-bound [receipt and screenshots](evidence/native-draft-restart-20261025/README.md)
record native compilation, reproduced ELF/EFI/media, cold boots, a real
uncommitted-edit power loss, and seven refusal controls. QEMU executes the
AIUEOS kernel directly. That historical receipt used a Linux build host; the
[Mac local-draft receipt](../docs/evidence/aiueos-mac-local-draft-20261026/README.md)
reproduces the exact-source kernel, EFI and media with a Mac native compiler
and passes the same headless restart gate. Neither guest run depends on a
Linux runtime.
The [merged CCF + FS2 Mac root repeat](../docs/evidence/aiueos-mac-ccf-merged-20261026/README.md)
rebuilt that media through the ordinary entry from the updated Amu selfhost
root, passed all 11 restart observations, and passed an additional unattended
Itonami Goal input and screen check. Its compiler and media identities are
recorded separately from the earlier Mac receipt.

The [interactive-fuel repeat](evidence/native-draft-fuel-20261025/README.md)
rebuilds both profiles with the admitted `2^53-1` initial kernel budget and
reads the live fuel counter after boot. Local-draft cold restore and the
normal profile's input/F5-disabled gate both pass. This removes the observed
short-session fuel failure from this diagnostic candidate; idle polling,
finite fuel, canonical workspace restore and release qualification remain
open.

## Implemented local transport probe

`os/aiueos/native/workspace-entry.kotoba` selects `desktop/workspace-main`.
Only that opt-in root enables the draft store. In the Itonami diagnostic card,
F5 commits at most 51 lowercase ASCII/space code points; a cold boot restores
the published generation. The label is `Goal local:`. The normal desktop root
keeps `Goal (RAM):` and F5 has no persistence action.

The probe addresses only an explicitly marked primary-slave ATA device on a
separate legacy controller. Its test fixture is 64 KiB. The guest checks the
marker and declared size, not ATA IDENTIFY capacity or serial; this is not a
physical-device qualification. It never provisions a disk. Sector 0 is read
only; only sectors 1..3 can be written. The boot medium uses q35 SATA with a
temporary overlay and is never selected by this transport. Scratch uses
browser-context bytes 512..2559, beyond renderer/input words 0..84. DMA pages,
the CPU RX snapshot and existing provider/runtime ownership are preserved.

A commit validates the published head and expected generation, writes the
alternate slot, FLUSHes it, reads it back, then publishes, FLUSHes and reads
back the head. The existing native SHA-256 implementation authenticates no
identity: it checks accidental byte corruption in the slot. A malformed
published head/slot refuses; a higher generation that was never published is
ignored. Head and slot reserved bytes must be zero. An entirely empty head
must be all zero, not just have an empty magic word.

This small draft record is a disposable transport diagnostic, **not a new
workspace/image codec**. It is plaintext and admits no private-workspace or
distributed-durability claim. It has no signed anti-rollback authority; an
entire valid disk rollback is undetectable. The gate kills a guest after an
uncommitted edit and supplies an unpublished-slot fixture. It does not yet
inject a torn/failed ATA head write or prove physical power-loss atomicity.

Named observations are stored in the receipt. The native outer refusal codes
used by the gate are `-16` dirty empty head, `-17` invalid slot shape/payload,
`-18` invalid slot digest, `-20` invalid head, `-22` missing/unprovisioned
medium, and `-24` commit refused because the current head or expected
sequence was not admitted. Negative values are read as signed u32 in QMP.

## Existing contracts and the remaining connection

| Owner / issue | Required connection | Current boundary |
|---|---|---|
| AWAI-30, `kotoba-lang` / `osaho` | D2 `world-root × code-environment × open-leases`, canonical bytes, CID-before-decode, published vectors | Hosted `.cljk` codec/vectors exist. No qualified native D2 consumer is used by this root. Do not substitute `document-print` or this draft record. |
| JUN-93, shared Browser/CSSOM | Real shared surface/input/event loop, typed string/document/f64 runtime | The diagnostic still uses Browser-frame2. Saving its text does not qualify the shared Browser. |
| JUN-414, Amu user target | Registered Itonami artifact, CPL3 execution and declared operations | Amu #1574 is open; AIUEOS #505 is draft at the audited heads below. Capability-free result 42 is separate from an Itonami turn. |
| AWAI-86, release contracts | Immutable app release/source/interface/profile identity and fresh target admission | This kernel probe has no app release manifest or promotion/rollback claim. |
| JUN-296/300/299/372 | Cell identity, verified state head/sequence, signer, state/effect/receipt | A local unsigned counter is not a verified Cell head or cross-node state. |
| JUN-145 | Itonami → Kaikei, real commit, empty-runtime restart restore | Remains open until the actual app path uses the above contracts. |

The D2 native adapter must use the existing `kotoba.kir.definition-identity`
owner implementation (via the `kotoba.lang.code-identity` facade),
`cbor.core`, multiformats and the measured
`lang/lisp-machine-image-vectors.edn`. The facade currently delegates to
`osaho/src/kotoba/kir/definition_identity.cljk`; no independent AIUEOS encoder
is introduced. The workspace consumer must bind app release/source/interface/
profile, mon CID × agent Cell, verified head and sequence, schema/migration,
goal/plan and resume position before publishing/restoring any app state.

On restore, verify referenced blocks and identity before decode/admission.
Missing blocks, wrong Cell/mon/agent, old/forked heads, incompatible schema or
profile, and failed migration need named refusal/unresolved receipts. A
higher local disk counter cannot replace those checks. Keys, approvals,
leases and OS/GPU/socket handles must not be restored; external operations
still require fresh trusted per-operation consent on the destination host.
The existing canonical browser broker is not reimplemented in this probe.

Audited owner refs: AIUEOS main `b78635e7c8d0be986444d3f35c322405e4c9806c`,
Amu main `5f829f10c5835cfd347a76d92b6baba1a67edf2a`,
[Amu #1574](https://github.com/kotoba-lang/amu/pull/1574)
`d3f49e21c853683d43eb1d555bc682d0a7cba804`, and
[AIUEOS #505](https://github.com/kotoba-lang/aiueos/pull/505)
`de09efe452c1db0695ee5d73a83772504ac96a6d`.

## Reproduce the component gates

Use the pinned native compiler and owner roots described in
[native desktop/media](native-desktop-media-v1.md). Heavy commands must use
Amu's shared native build queue. Never use hosted bootstrap or a C loader.
`OUT` must be a new scratch directory; no command here accepts a physical
workspace disk.

```sh
python3 "$AMU/scripts/seed/native_build_queue.py" -- \
  python3 os/aiueos/scripts/build-native-desktop.py \
    --amu-source "$AMU" --profile local-draft --output "$OUT"

python3 "$AMU/scripts/seed/native_build_queue.py" -- \
  python3 os/aiueos/scripts/check-native-draft-restart-qemu.py \
    --media "$OUT/media/awai-native.img" --efi "$OUT/kernel/BOOTX64.EFI" \
    --kernel "$OUT/kernel/KERNEL.ELF" --qemu "$QEMU" \
    --firmware "$FIRMWARE" --output "$OBSERVATION"
```

The observer creates only its own marked scratch fixture, sends keyboard
input through QMP, reads actual guest memory/framebuffer and inspects written
bytes. Python does not implement guest save/restore, SHA decisions or the D2
codec. The normal `desktop` profile and existing desktop QEMU input gate must
also pass. Do not promote this component receipt into AWAI-90/JUN-145 completion,
release publication, distributed recovery or physical hardware acceptance.

On Apple Silicon, the ordinary `build-kotoba-native-desktop.sh` entry also
selects this probe with `AIUEOS_NATIVE_DESKTOP_PROFILE=local-draft` and runs
the QEMU gate in the same source-bound invocation. Set the pinned Mac Amu and
Kotoba packager images, owner source root and fresh output as described in
[Mac native build progress](native-macos-selfhost-build.md). The gate checks
that `Goal local:` text appears in the actual QEMU scanout after F5 commit
and cold restore. It requires no Screen Sharing, password or manual key.

For debugging an already running diagnostic VM without screen sharing or a
password, use the [local QMP desktop debugger](native-desktop-headless-debug.md).
