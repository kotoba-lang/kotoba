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

The bounded host handles two boot keyboard/mouse interfaces, directly or
through one USB2 hub with up to8 ports,
32/64-byte xHCI contexts, command/event/transfer ring cycles and BIOS ownership
handoff and up to two 4KiB scratchpad buffers. If the first controller
initializes but accepts no HID, it is halted before the next controller is
tried with the shared DMA memory. At most two controllers are tried; devices
across two simultaneously active controllers are not supported. Per-host port
state and enumeration-stage diagnostics distinguish empty ports from failures. It refuses controllers requiring
more than two scratchpads, out-of-window registers,
non-boot HID, nested/USB3 hubs and unhandled descriptors. Modified chords remain unhandled
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

USB rings and contexts own pages 0..2; scratchpads own pages 3 and 14.
NVMe DMA owns 4..8 and RTL8168 DMA owns 10..13. Profile 6 refuses signed
remote update/install commands (5/6), since their staging page 14 belongs to
xHCI in this profile. Other profiles retain the existing update path. Browser-context 2048..3071 is crypto scratch. Effects 12800..15943 is
retained draw-list cache, not free scratch. The tests must exercise signing,
redraw and a subsequent save to catch aliases between these owners.

## Verification

See the source-bound receipt under `docs/evidence/awai120-usb-nvme-state-20261101/`
for completed checks. Source, QEMU qualification, PR/CI, merge, PXE boot and
physical-device acceptance are tracked separately in AWAI-120 and AWAI-121.

## 6600H first PXE measurements

The 2026-11-01 candidate completed its one-shot PXE transfer and reached the
Itonami desktop. NVMe Identify, ESP walking and installed-image hashing passed.
The first USB driver returned 3 with zero devices. Its successor's capability
logs identified AMD 1022:161d, HCSPARAMS2 `0x140000f1` (two scratchpads),
64-byte contexts, doorbells `0x2000` and runtime registers `0x1000`.
That measured requirement motivated the bounded scratchpad allocation above.
These measurements do not establish physical keyboard/mouse input or state
save/restore. See `physical-first-boot.json`; later receipts must record the
successor's physical results separately.

The scratchpad successor subsequently initialized on the 6600H (`c140=15`)
but reported zero accepted HID devices. The owner confirms wired USB devices
are connected directly. Signed debug keys independently verified NVMe Goal
`aba` save and restore across two CF9 resets; an unsaved `z` was discarded.
The actual saved/restored Goal pixel regions match. This is hardware-reset
Goal persistence, not physical HID input, full power loss, or physical
key/outbox restoration. See `physical-goal-restore.json` and its five frames.

The controller-selection successor found the wired devices on AMD 1022:161e
at 05:00.4 after halting the empty 05:00.3 host. One boot HID enumerated;
another port failed Address Device with completion code 4. The next candidate
uses a fresh PIT channel2 mode0 one-shot for at least12ms of reset/address
recovery, restoring gate/speaker control even on timeout. It logs the accepted
HID kind with the port stage. The USB 2.0 timing rationale is also described by
[Microsoft's USB driver team](https://techcommunity.microsoft.com/blog/microsoftusbblog/how-does-usb-stack-enumerate-a-device/270685/).
The interactive netlog PXE variant omits the opt-in90s hardware watchdog;
it has no install flag and leaves the prior server fallback intact.

## USB2 hub composition and code cap

A directly plugged mouse can still be behind the 6600H's observed Genesys
05e3:0610 hub. The bounded hub path powers/resets ports, waits for recovery,
sets child route strings and, for low/full-speed children of a high-speed hub,
sets the parent TT slot/port. It supports one hub and at most two HID devices;
there is no hub hotplug, nesting or general report-HID admission. EP0 is first
read at8 bytes; a valid full-speed max-packet change is evaluated before the
full descriptor. The QEMU gate adds a root keyboard and USB2-hub child mouse.

The USB structure layout stays inside pages0..2:

| Bytes within USB DMA window | Owner |
| --- | --- |
| 0..6143 | Three complete64-byte-stride output contexts |
| 6144..8191 | Keyboard/mouse EP0 and interrupt rings |
| 8192..10303 | Complete33-context input context |
| 10304..10815 | Hub EP0 ring |
| 10816..11071 | 16-entry event ring |
| 11072..11327 | Command ring |
| 11328..11519 | DCBAA, ERST and scratchpad pointer array |
| 11520..11647 | Two64-byte report buffers |
| 11648..12159 | Descriptor buffer |

Scratchpads remain at pages3/14. Hub private state uses page9 words288..343,
after previous reports256..271 and before the draft scratch starting at1536
bytes. Input-context clearing stops at10304, so it cannot wipe the hub ring.

The shared desktop graph exceeded the existing2MiB kernel-v3 text cap while
linking the unused diagnostic `native/kernel` through legacy wrapper functions.
The product desktop roots now omit that unused import/wrapper while retaining
their actual main, eight typed ValueRuntime exports and domain admission.
The pinned native kernel-v3 backend still owns the controlled fault shim;
`native/kernel`, its diagnostic entry and compiler/ABI are unchanged. Product
closures are pinned at36 modules. This source composition does not extend
CPL3 or full-OS qualification; normal desktop, ATA restore and offline-dapps
regressions are recorded separately alongside the input/hub gate.
