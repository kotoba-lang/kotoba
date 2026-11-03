# AWAI-122 stage 3: signed image pulled and verified on the 6600H (2026-10-31)

Board: AMD 6600H (Realtek RTL8168, direct cable to the operator's Mac, en15 10.77.0.1). Debug desktop image
`--netlog v1 --watchdog v1`, PXE-served (image SHA-256 `3de25fa2…b357c75e`, KERNEL.ELF `9496d4c3…2349291ca`).

## Boot

- `c118 0000000007010f07`: the verifier self-test passed on hardware (accept 15, tampered manifest 1, tampered image 7).
- `c100..c115`: NVMe probe and ESP loader hash as in stage 2 (unchanged).

## Pulls (one boot, remote command 5, `aiueos-image.py serve` on the Mac)

The served payload is this build's packaged EFI before the RX fix (`pkg-h1/image.efi`, 6,062,592 bytes,
SHA-256 `55f51dd70da4b7b50010d246bbfc6b6f0f1a1cfded1b334089f866f0e533a0c5`), signed as version 2.

| served image | result | taken | KDBG |
|---|---|---|---|
| signed with the image-signing key | 15 verified | 6,062,592 of 6,062,592 bytes, 0 repeated requests, 5,922 datagrams in 13.3 s | `c120 …0f`, `c124..c127` = `55f51dd7…e533a0c5` (equals the signed image's SHA-256), `c005 …0f` |
| same manifest signed with another key (the AWAI-119 remote key) | 1 signature refused | 0 image bytes (only the header was requested) | `c120 …01`, `c005 …01` |
| valid header, one image byte flipped (offset 3,000,000) | 7 digest differs | 6,062,592 bytes | `c120 …07`, `c124..c127` = `5f5e1c15…0cad4f9e` (the SHA-256 of the tampered payload, recomputed on the Mac) |

In the wrong-key row `c121` and `c124..c127` are not printed again: words 181..207 are written only after the
signature verifies, so the board still holds the previous pull's values.

## RX stall found and fixed

Before the fix, the stage 2 build on main and the first stage 3 builds answered no signed command (not even
ping), while the AWAI-119 image still received them. RX diagnostics (KDBG `c00f` frames seen | last frame,
`c00e` RX descriptor | ChipCmd | RxConfig) showed one frame seen for the whole boot and the descriptor
owned by the NIC (`c0000600`, ChipCmd `0c`, RxConfig `cf0a`): a broadcast arriving while the single
descriptor was the kernel's raised RxDescUnavail during the ~10 s of NVMe/ESP work before the first poll,
and the RTL8168 stopped receiving. `rx-release` now clears IntrStatus (0x3E); afterwards ping, three pulls
and every later frame were received.

`kdbg.log`: this boot's KDBG records from 14:53:40 to 14:54:45 (the repeated `c000`/`c00e`/`c00f`
heartbeats listed once each).

Not covered: the image is not written (stage 4); Ed25519 only; no rollback protection beyond version >= 1.
