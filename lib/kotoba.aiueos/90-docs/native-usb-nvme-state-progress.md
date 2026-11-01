# Native USB input and NVMe state (AWAI-120 / AWAI-121 / AWAI-90)

The opt-in `input-state` profile uses Itonami's installed local dapps, native
xHCI boot HID ingress and a separate FAT32 `\EFI\ITONAMI\STATE.BIN`.
It keeps the PXE development path; it does not change the default entry,
firmware boot order or the installed OS image. Physical qualification remains
open, as do USB hubs, composite receivers, Bluetooth and general HID reports.

Run the existing signed Mac-native builder with `--profile input-state --distribution awai` and its usual pinned Amu, QEMU, firmware and owner roots.
The builder runs `check-native-input-state-qemu.py` against its exact media.
It disables PS/2 (`i8042=off`) and attaches QEMU xHCI, USB keyboard/mouse and
an independent NVMe FAT32 fixture. A passing PS/2 gate alone does not qualify
USB. QEMU's injected keys do not prove human consent or physical hardware.

## Input boundary

The bounded host handles two direct-root boot keyboard/mouse interfaces,
32/64-byte xHCI contexts, command/event/transfer ring cycles and BIOS ownership
handoff. It refuses scratchpad-requiring controllers, out-of-window registers,
non-boot HID, hubs and unhandled descriptors. Modified chords remain unhandled
by the current lower-case Goal editor. Rollover/error reports and held keys
are rejected. A modal transition quarantines keyboard reports until release;
queued keys cannot approve a newly opened operation. Relative mouse movement
and button edges use the existing desktop reducer.

## Persistence boundary

Boot reads an existing state file; it never creates or reformats it. F5 in
Itonami creates a missing 20KiB state file on a usable FAT32 ESP and saves the
bounded state. GPT header/entry-array CRCs, volume bounds, FAT agreement,
contiguous aligned allocation and disjointness from BOOTX64.EFI / UPDATE.BIN
are checked. An existing malformed state file is not replaced. The firmware
may repair one invalid GPT header, so the CRC refusal fixture invalidates both
primary and backup headers before boot.

The five 4KiB records hold the provisioning marker, publication head, two
alternating 512-byte hashed slots, and the passphrase-sealed key. Slots store
Goal, run/token and CID state, and the last signed Aozora post, signature and
public key. Aozora publishing remains unimplemented. Writes flush and read
back the inactive slot before publishing the head. Uncommitted edits and a
complete but unpublished slot cannot become committed state. A corrupt
published slot refuses rather than rolling back silently. Restored keys stay
locked; approval, leases, raw seeds and passphrases never restore from a slot.

This is the existing plaintext diagnostic draft codec with a v3 app snapshot,
not the canonical D2 workspace codec, signed Cell head, encrypted backup or
production recovery. FAT allocation interrupted before directory publication
may leak clusters. No physical power-loss or 6600H persistence qualification
is claimed by the QEMU gate.

## Private memory ownership

Owned page 9 is reserved for host state, never named by a DMA descriptor:

| Range within page 9 | Owner |
| --- | --- |
| 0..1535 | xHCI host state / previous reports |
| 1536..3583 | draft slot, hash and readback scratch |
| 3584..3995 | profile 6 NVMe/ESP controller state (words 600..702) |

USB DMA owns pages 0..3, NVMe DMA 4..8, RTL8168 DMA 10..13 and update staging
14. Browser-context 2048..3071 is crypto scratch. Effects 12800..15943 is
retained draw-list cache, not free scratch. The tests must exercise signing,
redraw and a subsequent save to catch aliases between these owners.

## Verification

See the source-bound receipt under `docs/evidence/awai120-usb-nvme-state-20261101/`
for completed checks. Source, QEMU qualification, PR/CI, merge, PXE boot and
physical-device acceptance are tracked separately in AWAI-120 and AWAI-121.
