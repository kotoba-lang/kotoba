# JUN-482: the device-key seed refuses a stuck entropy source (2026-10-30)

`native/desktop.kotoba` `draw-seed` now refuses its four 64-bit `kernel-rdrand` draws unless they are
pairwise different, and `draw-salt` its two. A refusal takes the existing fail-closed path: the key
request closes with code 2, no seed is stored and no key exists. For a working source two equal
64-bit draws have probability about 2^-61, so the check does not refuse one by chance in practice (a
repetition-count test in the spirit of NIST SP 800-90B 4.4.1).

Both receipts here come from `scripts/build-native-desktop-macos.py --profile consent` on Apple Silicon,
QEMU TCG (`qemu-system-x86_64` c2bfa7fb, OVMF `edk2-x86_64-code.fd` 33090cc0), with the Mac roots of
Amu `63557e92b` passed explicitly (`--compiler-image` / `--packager-image`):

- `positive-native-consent-qemu.json`: this source. `PASS_NATIVE_CONSENT_QEMU`, all 22 events, including
  key-allow (seed non-constant, public key and signature verified, sealed blob), signing and the draft.
- `stuck-native-consent-qemu.json`: the same source with every `(kernel-rdrand)` replaced by a constant
  (a separate detached worktree; QEMU cannot make RDRAND constant), run with `--expect-stuck-entropy`.
  `PASS_NATIVE_CONSENT_STUCK_ENTROPY`: the startup probe sees the repeat, and after Allow and a valid
  passphrase the request closes with code 2, the seed words are all zero and no key exists
  (`stuck-entropy-refused`).

The receipts were made at kotoba main \`834be3a89\`, whose desktop graph had 38 source modules.
\`build-native-desktop-macos.py\` there still expected 37, so for these runs the count was corrected
locally; main has since moved the guard itself (to 40, after further desktop modules). Its
repository-bootstrap route accepts only a 47- or 48-module Amu FULL-MANIFEST while Amu main has 49,
so the roots were passed explicitly.

Not shown: RDSEED in a guest; a physical machine; anything beyond QEMU TCG. Diagnostic, not a release.
