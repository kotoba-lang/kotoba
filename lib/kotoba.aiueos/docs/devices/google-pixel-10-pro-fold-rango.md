# Google Pixel 10 Pro Fold ("rango"): device inventory and driver design

Status: design. Nothing here boots, and nothing has been installed on the device.
Tracked as JUN-862. The machine-readable form is `spec/devices/google-rango.edn`.

## Scope

This records what the device is and what aiueos would need to drive its touch
screens, Wi-Fi, Bluetooth and the rest. It does not install aiueos, unlock the
bootloader, or change the device. README.md still says there is no Android
profile and AArch64 stops at a bootstrap (UEFI loader plus a freestanding kernel with
`TTBR0_EL1` and enforced W^X); that stays true after this document.

Every value is tagged `measured`, `inferred` or `unverified`, the same way as the EDN.
Measurements were read with `adb shell` on 2026-11-06 from a locked, stock unit.
Per-unit identifiers are not recorded.

## What the device is (measured)

| | |
|---|---|
| SoC | Google Tensor G5, board `laguna`, arm64-v8a |
| CPU | 8 cores, implementer 0x41 (Arm); part ids 0xd80 x2, 0xd82 x1, 0xd87 x5. Inferred from Arm's part-number assignment: 2 Cortex-A520, 1 Cortex-X4, 5 Cortex-A725 |
| RAM | 15,948,932 KiB |
| OS | Android 17 (SDK 37), kernel 6.6.127-android15-8, 4 KiB pages |
| Boot | A/B (slot `_a`), Treble, bootloader locked, verified boot green, bootloader `deepspace-17.4-16119390` |
| Displays | inner 2076x2152, outer 1080x2364, both 120 Hz |
| GPU | PowerVR (from `ro.hardware.egl`); model unverified |
| Storage | UFS LUNs `sda`..`sdd`; the UFS class is inferred from the SCSI block devices |

The partition list (`abl`, `bl31`, `tzsw`, `gsa_*`, `pvmfw`, `boot`, `init_boot`,
`dtbo`, `super`, `modem`, ...) points to Google's Android bootloader with
fastboot, not UEFI. No ESP or UEFI variable store was observed. This is inferred,
and it matters: the existing AArch64 loader is a UEFI application.

## Touch screens (measured, mapping inferred)

| Controller | Bus | Axes | Slots | Display |
|---|---|---|---|---|
| `fst2` | SPI (`spi19`) | X 0..20759, Y 0..21519, pressure 0..127, tilt | 14 | inner (inferred: axes are 10x 2076x2152) |
| `synaptics_tcm_touch` | SPI (`spi20`) | X 0..10799, Y 0..23639, pressure 0..255 | 10 | outer (inferred: axes are 10x 1080x2364) |

Both report direct-input multitouch and the Synaptics one also reports a wake key.
Google's touch stack sits behind `goog_touch_interface` and `touch_offload`
(both seen under `/sys/class`), so the controllers may not be the only layer a
driver has to match. The firmware and register protocol for each controller are
unverified.

## Wi-Fi and Bluetooth

Wi-Fi: interfaces `wlan0`, `wlan1`; features include STA, P2P, hotspot, Aware,
RTT, Passpoint, PNO, and STA+STA and STA+AP concurrency. The unit was associated
at 802.11ax; that is one connection and not a statement of the radio's limit.
The chip, its bus and its firmware were **not** identified: an unprivileged shell
cannot read `device/uevent`. Wi-Fi 7 is not claimed.

Bluetooth: classic and LE, channel sounding, A2DP offload, and a wide LE Audio
and HID profile set. The controller and its transport were **not** identified.

These gaps cannot be closed from an unrooted, locked device. The public Android
kernel and Pixel module sources, or a rooted debug build, are the next sources.
Whether the Tensor G5 sources are published at the same completeness as earlier
generations is unverified.

## Driver design

### Layers

1. **Device profile** (data). `spec/devices/google-rango.edn`. A driver reads its
   base addresses, IRQs, bus and firmware names from here once those are measured.
2. **Driver contract** (Kotoba). Per subsystem, the judgment: what a valid touch
   report is, when a scan result is admitted, which firmware blob is acceptable.
   This follows the repository rule that Kotoba judges and C only marshals.
3. **Bus layer** (SPI, PCIe or SDIO, UFS, MMIO). Mechanism only.

Nothing in layers 2 and 3 exists for this device. The x86-64 drivers use virtio
in QEMU and real PCI; this device has neither, so the bus layer is new work.

### Order

| Step | Drivers | Why this order | Gate |
|---|---|---|---|
| 0 | boot path, serial or fastboot console, GIC, generic timer | nothing else can be observed without it | AArch64 kernel reaches a console on the device |
| 1 | UFS, outer display, outer touch (`synaptics_tcm_touch`), power key | smallest set that shows and accepts input | tap coordinates printed on the outer display |
| 2 | inner display, inner touch (`fst2`), hinge-angle sensor, posture change | the fold is what is specific to this device | window moves between displays on fold and unfold |
| 3 | Wi-Fi, Bluetooth | firmware loading, regulatory data and a security boundary; hardest | scan, then join a WPA2/WPA3 network, then HCI inquiry |
| deferred | cellular, camera, GPU, NFC, UWB, GNSS, fingerprint, haptics, TPU | none is needed to prove the OS | |

Step 0 is the dependency of everything. The README's own gaps stand first:
the AArch64 kernel has no scheduler, userspace or syscall path yet.

### Wi-Fi and Bluetooth specifics

- **Firmware:** both radios need vendor firmware. aiueos must treat a firmware
  blob as an external artifact: pinned source, digest verified before use, and
  a missing digest recorded as "unverified". It must not load an unpinned blob.
- **Consent:** joining a network or pairing a device is a capability decision for
  `grant`, not for the driver. The driver reports; `grant` decides; aiueos enforces.
- **Regulatory domain:** Wi-Fi transmit power and channels are bound to a country.
  The default must be the most restrictive set until a domain is established.
- **Bluetooth security:** pairing keys are stored in sealed storage
  (`docs/sealed-storage.md`), never in plain files.

### Touch specifics

- Report parsing is judgment and belongs in Kotoba: slot bounds, coordinate range
  against the measured axes, pressure range, palm and tool-type handling.
- Coordinates are scaled to the display from the measured axis maximum, not from
  an assumed 10x factor. The 10x is the inference used only to pick the display.
- A driver rejects any report outside the ranges above and logs the reason.

## Verification plan

| Claim | Evidence required |
|---|---|
| Profile matches the device | re-run the `adb` reads in this document and diff the values |
| Parser handles touch reports | QEMU test with recorded `getevent` traces from this device, then a device run |
| Wi-Fi works | join of a real AP on the device, with the firmware digest recorded |
| Bluetooth works | HCI reset and a LE scan on the device |

QEMU results and device results are recorded separately. A QEMU pass is not a
device pass.

## Open items

- Identify the Wi-Fi chip, Bluetooth controller, panel controllers and GPU model.
- Whether the bootloader can be unlocked (`oem_unlock_allowed` was not readable) and what
  that costs: unlocking wipes user data, so it needs an explicit owner decision.
- A boot path for the AArch64 loader, which assumes UEFI, on a non-UEFI bootloader.
- Whether the public sources for Tensor G5 cover the touch, Wi-Fi and Bluetooth drivers.
