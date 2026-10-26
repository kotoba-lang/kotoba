# Apple Silicon native desktop distribution parity (2026-10-26)

The AIUEOS branch at `b633735837617d33ec343e71f64aea0a7007c5df`
was built twice from the same Amu #1595 source and canonical owner roots on
Apple Silicon. The ordinary `build-kotoba-native-desktop.sh` entry selected
`AIUEOS_DISTRIBUTION=aiueos` and `AIUEOS_DISTRIBUTION=awai` in separate new
private workspaces. Each invocation ran inside Amu's native build queue.
The compiler and Kotoba packager emitted the font, 31-module kernel, EFI and
8 MiB GPT/FAT16 media. Both exact media images booted QEMU through private
QMP standard I/O with no VNC, password or network and passed 12 desktop
input events, including visible Itonami Goal text.

The [parity readback](parity.json) verifies the two distinct static
`distribution.json` descriptors against repository bytes, both build and
QEMU receipts, the image files' hashes, and byte-identical compiler, packager,
font, kernel, EFI and media identities. The common media SHA-256 is
`fc05960f497ef6c6896055d0f450304ac661416edf4d81054b0f1616b7e8f398`.
The reusable observer is
[`check-native-distribution-parity.py`](../../../os/aiueos/scripts/check-native-distribution-parity.py):

```sh
python3 os/aiueos/scripts/check-native-distribution-parity.py \
  "$AIUEOS_BUILD" "$AWAI_BUILD" --output "$NEW_RECEIPT"
```

Replaying it on the two retained builds returned
`PASS_NATIVE_DISTRIBUTION_PARITY` and the same media SHA. A one-byte change
to the copied AWAI descriptor returned `copied descriptor mismatch`; a
one-byte change at media offset 4096 returned `artifact or QEMU pin mismatch`.
Neither failure wrote a PASS receipt. Python reads and compares evidence; it
does not compile or package the OS.
The [AIUEOS build](aiueos-build.json), [AWAI build](awai-build.json),
[AIUEOS guest](aiueos-qemu.json), [AWAI guest](awai-qemu.json), and
[AWAI Itonami screenshot](awai-itonami-goal-ab.png) are retained for review.

The selected distribution changes static metadata; the two builds used the
same executable image bytes. This is a Mac native diagnostic desktop/QEMU
result. It does not qualify a release, physical machine, user-v3 agent loop,
trusted approval, or the full ChromeOS scorecard.
