# Production signer set (verification-only): what was run (JUN-813, ADR-0286 Amendment 7)

Date: 2026-11-06. QEMU 10.0.3 TCG on the Mac that holds the keys, `-nic none`. `native-prodsig-qemu.json` is the `prodsig` gate's report
(`PASS_NATIVE_PRODSIG_QEMU`, builder verdict `MACOS_NATIVE_DESKTOP_QEMU_CANDIDATE` from a clean worktree at the PR commit).

**[measured]** production mode (`test = 0`) ADMITS the three golden fixtures (AIUEIMG2 slots 0+1, AIUECAT1 slots 1+2, AIUEFRS1 slots 0+2, signed once
with the real slots) and REFUSES, in each kind: a one-signer header (1), a header signed by the TEST keys (1), a flipped ML-DSA / Ed25519 / manifest byte
(1), a flipped image or body byte (7), and the other kinds presented as this one (2; an AIUECAT1/AIUEFRS1 header sent down the image path is 1, because
`admit` dispatches on header byte 7 and judges magics ending in "1" by its AIUEIMG1 branch, signature first). In test mode the golden fixtures are refused
and a TEST-signed header is admitted. Expected verdicts come from the independent references under the production PUBLIC keys.

**[measured] negative controls** (kernels rebuilt from a mutated `update.kotoba`, run through the same gate; both FAIL it):
- production mode accepts the TEST keys (`ed-word`/`ml-word` ignore the mode): golden image result 1 instead of 15; TEST-signed header 15 instead of 1.
- production mode ignores the signer count (one valid signer admits): `image-one-signer` 15 instead of 1, likewise the flipped-signature cases.
- host test of the tool, mutated copies: no mode check, overwrite without `--replace`, prints a seed, signs under the wrong ML-DSA context, no symlink
  check, no git-work-tree check: each fails `tests/test_aiueos_signer.py` (19 tests pass on the real tool).

**Custody facts [measured]:** `~/.itonami/aiueos-signers` and `slot0..2` are 0700, every file 0600, owner the current user. `~/.itonami` is a symbolic link to
`github/gftdcojp/itonami-state`, which is not a git work tree (no `.git` above it). A scan for the raw, hex, upper-hex and base64 forms of all six seeds found no hit in
the PR files, the scratch directory, the build outputs or the task logs. Public-key sha256 fingerprints are in `fixtures/signers/prod-pubkeys.json`.

**Not verified:** a physical board; the network pull (RTL8168); that the Mac's backups/Time Machine exclude the key directory; any custody separation (there is none).

**Existing gates after the change [measured, builder verdict `MACOS_NATIVE_DESKTOP_QEMU_CANDIDATE`, clean worktree at the PR commit]:** `update2`, `catalog`, `fresh` pass. Their
former "production-mode" case (TEST-signed header, formerly 8) is now refused with 1. Their reports still say `testKeysOnly` / `productionSignerSet: false`: true in the sense that
no production-signed material is used there; the `prodsig` gate is the one that uses it.
