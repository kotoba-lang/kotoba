# ADR-0122 — A K16 pulls a release, not a repository

Date: 2026-08-30

## Status

Accepted and executable as the AIUEOS decision layer. Physical K16 HTTPS
artifact fetching and the native OS-slot writer remain unimplemented, so this
ADR does not call the current PXE route a secure automatic update.

## Context

The current K16 qualification image is fetched by UEFI PXE/TFTP and writes no
internal disk. That makes a failed experiment recoverable by rebooting and
serving the previous image, but it does not authenticate the downloaded EFI,
enforce a monotonic release sequence, or prove an SSD rollback. A hash in the
Mac-side build receipt detects accidental drift only after a trusted operator
compares it; it is not a device trust root.

AIUEOS already has three relevant pieces. `grant.publisher` admits threshold
signatures, revocation, monotonic sequence and freshness. `grant.ota` binds the
admission to one manifest and its observed artifact digests. The release-image
builder preserves a recovery ESP and proves apply/corruption rollback in QEMU.
None of those pieces had a K16-specific composition saying which evidence must
pass before a candidate becomes the running OS.

## Decision

`aiueos.os-update` is that composition.

1. A release is for `x86_64/gmktec-k16` and names exactly loader, kernel and
   initramfs artifacts.
2. Each artifact is an immutable `https://ipfs.kotobase.net/ipfs/{cid}` object
   with exact byte count and SHA-256. The device never runs `git pull`.
3. Publisher admission happens before a fetch plan exists. The same admission,
   manifest identity and observed digests are rechecked at every later step.
4. Bytes go only to the inactive OS slot. The previous slot remains intact;
   activation is ordered after flush and full readback.
5. The candidate receives one trial boot. Commit requires boot, storage,
   direct HTTPS, Murakumo node registration and inference evidence. A false
   signal rolls back immediately; missing evidence rolls back after 120 s.

Models retain their independent CID/A/B channel. A model release cannot force
an OS reboot and an OS release does not duplicate the frequently changing
weights.

## Executable evidence

`aiueos.os-update-test` exercises the full admitted path and independently
rejects rollback sequence, insufficient signatures, wrong machine, HTTP or a
foreign host, incomplete artifact sets, missing bytes, digest substitution,
loss of the previous slot, explicit health failure and health timeout. It also
proves that an unconfirmed candidate receives at most one trial boot.

## Remaining boundary

The physical adapters are still red. The K16 kernel can currently make the
small direct Murakumo HTTPS request, but it cannot yet stream an OS release
from Kotobase into a native NVMe OS slot. The current PXE image is also not
anchored by enrolled Secure Boot keys. Landing the decision and its negative
tests prevents those mechanisms from inventing weaker rules, but does not make
TFTP authenticated or authorize a write to the K16's Windows SSD.
