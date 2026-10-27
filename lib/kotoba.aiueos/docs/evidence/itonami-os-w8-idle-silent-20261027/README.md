# ADR-0275 W8: the idle native desktop sends no frame (QEMU, virtual NIC)

`build-native-desktop-macos.py --profile idle` builds the default desktop (kernel-v3, awai) and runs
`scripts/check-native-idle-silent-qemu.py`: one QEMU run, disk-first, e1000e NIC on a user netdev, traffic captured
(QEMU filter-dump). Result `PASS_NATIVE_IDLE_SILENT_QEMU`: after the desktop's first completed frame, 30 s idle plus keyboard
input produced **0 frames from the guest NIC's MAC**.

Controls, so the 0 means something:
- The capture is proven live in the same run: the host connects to a forwarded port, slirp sends the guest an ARP request
  (source 52:55:0a:00:02:02), and the capture records it (`control`). The guest's own firmware-phase frames (IPv6
  duplicate-address detection, 0 to 2 per run) are also counted when present (this run: 1 before the first completed frame).
- Frame counts are read at four checkpoints (first frame, after idle, after the stimulus, after input), not from pcap
  timestamps (the pcap time base is not the host clock).

Findings that shaped the gate:
- The desktop does **not boot with `virtio-net-pci`** (the loader writes `F` on the debug console and the screen stays black);
  it boots with `e1000e` and `rtl8139`. The loader's sealed PCI configuration does not admit virtio-net. An earlier probe that
  saw 0 frames with virtio-net was a non-booting guest and is not evidence. Admitting virtio-net is open.

Limits: QEMU TCG, virtual NIC, synthetic keys. The desktop has no NIC driver, so this is "emits nothing", not "refuses to
send". It does not qualify a physical NIC, a driver, or any future networked profile (which will need its own gate and
the W1 consent surface). The window between the real first frame and its detection (under one second) is not covered.
