# ADR-0266 — The launcher row shows the network state

Date: 2026-10-24

## Status

Accepted. Extends the `guest-browser-clock` gate (ADR-0264); no new floor. Row C9 ("Status area: network, power, clock") of the
ChromeOS-grade scorecard gains its second third in the QEMU-level evidence and stays `:partial`: clock and network are real
statuses, the power state is not.

ADR-0264 said the desktop stages run before the network comes up. That was wrong: `aiueos_pci_enumerate` (the virtio-net ARP
exchange and the ICMP echo) runs earlier in `aiueos_kernel_main` than the desktop flow, so the state is known when the clock
stage runs.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-clock` prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_CLOCK_OK`: the text-edit gate is green on the same serial, the profile attaches a virtio NIC
(SLIRP, no host network), the third frame (`net=3`) draws ONLINE in the launcher row and equals the frame model's, and the
first two frames are the ADR-0264 ones. A NIC attached with a state other than 3 is red (`nic-attached-but-not-online`).

## Decision

- Surface word 1969 is the network state (0 = nothing reported, nothing drawn): 1 no adapter (OFFLINE), 2 an adapter whose ARP
  exchange completed but whose ICMP echo did not (LINK), 3 both (ONLINE). C reads `aiueos_virtio_net_ready` and
  `aiueos_ipv4_ready` for the third clock frame; Kotoba draws the word in the ink from (vw - 160, 6), left of the clock.
- The model states all three words independently (`clock-frame n=3..5`: 89, 86 and 88 ops).

## Not

A live state: it is the state the boot enumeration left, not refreshed when a cable moves; no Wi-Fi, no address shown, no
power or battery (the kernel has no DSDT / battery device reader), no menu to act on the state.
