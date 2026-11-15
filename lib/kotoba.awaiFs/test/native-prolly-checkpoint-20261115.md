# Native signed checkpoint fixture, 2026-11-15

The macOS arm64 Native fixture reads the previously captured Otehon 61-Pack
snapshot, verifies the relevant CIDs and follows the snapshot's SPO root to a
single leaf containing two plaintext fixture datoms. It reconstructs the
Kotobase logical checkpoint bytes and compares their SHA-256 to the checkpoint
in the verified logical commit. The observed root is
`994bf8778ef21d93f873dd5cfc759a543c0c1fea1066558419933bed649749a9`.
An independently executed Babashka 1.12.218 reference calculation using the
pinned Kotobase canonical contract produced the same value; this was a local
oracle, not a Native runtime or CI dependency.

The fixture uses a test issuer and key, and identity encryption. The combined
verification rejects a changed datom (`:checkpoint-mismatch`), an untrusted
issuer, and invalid leaf bytes. The executable also rejects a missing Pack.
For this run the Native executable SHA-256 was
`8ca8c57d0a845df695979378886b629f924948713ea4b8ab77e931563f216b90`;
the source lock SHA-256 was
`fc3a9ef14c8247d470093e8d01432ee3d9ec2e499187ec16b14d0622c16c19d5`.

This is a bounded fixture, not a general checkpoint verifier: it accepts one
complete plaintext root leaf of up to 256 entries with a restricted ASCII
string/keyword component profile. The caller must verify the leaf CID, prove
that it is the complete snapshot SPO root, apply the correct decryption policy,
and bind the supplied issuer/key to authority. The helper alone does not bind
physical publication to the signed logical root, validate blind index keys,
walk multi-level trees or parent history, or establish production policy,
receipt, restart durability, OS cache loss, or Native qualification.
