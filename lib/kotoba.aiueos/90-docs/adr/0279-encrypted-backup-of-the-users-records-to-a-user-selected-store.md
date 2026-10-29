# ADR-0279 — Encrypted backup of the user's records to a user-selected store (W6)

Date: 2026-10-28

## Status

Proposed (design only, nothing in this ADR is implemented). W6 of ADR-0275: "encrypted backup to a user-selected store; restore on a fresh
volume". It extends ADR-0271 (backup and restore of the user's records, on the same volume, in the C compositor guest) to the native desktop,
and it keeps ADR-0277 (the device key is never exported). Open owner questions are listed at the end; until they are answered the first
slice below is what can be built without them. Every row is `:spec` until its gate prints green.

## Facts this design starts from

- The native desktop's user records are two: the Goal draft (sectors 1..3 of the dedicated 64 KiB scratch medium, `draft_store`) and the
  sealed device-key record (sector 4, ADR-0277 and kotoba#959..#979). There is no file system and no settings record in the native desktop.
- Its only block device is that scratch medium (ATA PIO, primary slave, identified by its exact size). It has no second disk driver, no
  network driver (W8: the desktop emits nothing), no USB mass storage.
- The guest has SHA-256/512, Ed25519 (sign and verify) and the passphrase-sealing construction of `aiueos.keyseal`. It has no AEAD cipher
  (no AES, no ChaCha20-Poly1305). `keyseal` seals exactly 32 bytes by xor with a derived key; it is not a bulk cipher.
- ADR-0271's cycle (copy, wipe, restore, compare hashes) is done in C inside the compositor guest and stays on the same volume; it
  protects against a bad write, not against losing the disk, and has no user interface.

## Decisions

1. **What is backed up.** The records of the user: the Goal draft record (and, later, settings and app state when they exist). **The device
   key's seed is never in a backup, and the sealed key record (sector 4) is excluded by default**: a copy of the sealed blob elsewhere is an
   offline guessing target with no attempt counter or delay, and a restored key would not be "the same device". After a restore on a fresh
   volume the user creates (or unlocks) a key as on first run. An owner decision may later allow including the sealed blob; that is a separate,
   explicit consent.
2. **A backup is an operation with consent.** Backup and restore are each a consent request of their own kind (ADR-0275 W1 surface; the
   text comes from the operation descriptor once W5 exists, static until then): service "backup medium", endpoint "none, a block device the
   user attached", action "write an encrypted copy of the records" / "replace the records from the backup", data "the Goal draft". Deny writes
   nothing; Allow for backup does not authorise restore and vice versa; a restore over a volume that already holds newer records is a
   second, explicit confirmation.
3. **First store: a second provisioned block medium.** The first slice's "user-selected store" is a second ATA medium identified like the
   scratch medium (marker plus exact size), selected by the user attaching it and by the consent panel naming it. A network or cloud store needs
   W4/W5 (a driver that is off by default and enabled by an approved operation, the descriptor path) and is sequenced after them.
4. **Encryption on the device, with a backup passphrase.** A backup is encrypted before it leaves the records' volume, under a key derived from a
   backup passphrase (the same passphrase UX and the same attempt counting and delay as the key; ADR-0278). Construction (to be reviewed, not a
   new primitive): a fresh 16-byte salt and a 16-byte nonce from rdrand; `K = iterated SHA-512` as in `keyseal`; `Kenc = K[0..32)`,
   `Kmac = K[32..64)`; ciphertext = plaintext xor `SHA-512(Kenc || nonce || counter)` blocks; tag = `SHA-512(Kmac || nonce || ciphertext)`
   (encrypt-then-MAC); the tag is checked, in constant-time accumulation, before any plaintext is released. This is a SHA-512 counter-mode stream
   with a MAC, adequate for a few hundred bytes of records and not a replacement for a reviewed AEAD; porting ChaCha20-Poly1305 or AES-GCM to the
   guest is its own issue and the format carries a version byte so it can be replaced.
5. **Format.** One record per sector run: header (magic, version, length, salt, nonce), ciphertext, tag; every other byte zero. The backup medium
   holds nothing in the clear, including no hash of the plaintext (a hash would let an observer confirm a guess of the draft).
6. **Restore** reads and checks the tag first, then writes the records with the same write, FLUSH, read back and compare rule as the key slot, and
   only then reports success. A wrong passphrase, a changed byte, a truncated or wrong-version backup is refused with a visible reason and
   changes nothing on the target volume.

## What the gates must show (each with a negative control)

(a) a backup without consent leaves both media byte-identical; (b) after a consented backup the backup medium contains neither the draft text
nor the passphrase (searched byte-wise); (c) wipe the records, restore on a fresh volume: the draft reads back byte for byte; (d) a wrong
passphrase is refused and the volume is unchanged; (e) one flipped byte in the backup (ciphertext, tag, header each) is refused; (f) a restore
over newer records needs the second confirmation and, denied, changes nothing; (g) the sealed key record and the seed are not in the backup
and are not restored. QEMU TCG with a test-fixture disk and synthetic input only; this proves no human consent and no physical-media behaviour.

## Not decided here (owner questions)

1. Where a backup goes beyond a locally attached medium (a user-selected network or storage service, its endpoint origin and data categories);
   that needs W4/W5 first.
2. Whether the backup passphrase is the key's passphrase or a separate one (a separate one avoids tying recovery of records to the key).
3. Whether the stream-and-MAC construction of decision 4 is acceptable for the first slice, or the first slice waits for a reviewed AEAD.
4. Versions or a single slot; and whether the sealed key record may ever be included.
