# ADR-0271 — Backup and restore of the user's records

Date: 2026-10-24

## Status

Accepted. Adds the `guest-browser-backup` gate; no new floor. Row H4 ("Backup and restore of user data": back up, wipe, restore; the data reads
back byte for byte) of the ChromeOS-grade scorecard, for the user data this machine has: the settings record and the passkey record.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-backup` prints
`AIUEOS_COMPOSITOR_GUEST_BROWSER_BACKUP_OK`: the sign-out gate is green on the same serial; the settings stage ran with its first-boot clicks
(seven frames equal to the model's), so the data is what the clicks made; the stage copied sectors 1034 (settings) and 1035 (passkey) to their
backup sectors 1036 and 1037, wiped the originals and the machine saw neither (`settings-valid=0 passkey-blank=1`), restored them, and the
SHA-256 of each restored sector equals the one taken before; the settings read back the same (`contrast=1 scale=125 net=1`); and the restored
key has the same public point and still signs and verifies.

## Decision

- `pci.c` gives a four-sector door (1034..1037): a read, and a write that is read back and compared. Nothing else of the volume can be reached
  through it.
- The cycle is C's (`browser_backup_stage`): it is a data operation, with no Kotoba decision in it and no frame to draw.

## Not

"User data" here is two records, not files (there is no file system, F2); the backup sits on the same volume, so it protects against a wipe
or a bad write of the record, not against losing the disk; there is no user interface to ask for it; no off-device copy.
