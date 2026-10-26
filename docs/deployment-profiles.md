# Deployment profiles (kotoba language runtime)

See also `kotoba-lang/security/docs/deployment-profiles.md` for the cross-repo
claim table. This file is the language-runtime operator view.

OS distribution is independent of this assurance axis. AIUEOS is the common
OS foundation; AWAI OS is its Awai composition in the same AIUEOS repository.
Choosing it does not select `regulated` or change Kotoba capabilities. See
[AIUEOS distributions](https://github.com/kotoba-lang/aiueos/tree/main/distributions).

| Profile | Default stance |
|---------|----------------|
| `research` | capability confinement + fuel; network allowlist required by default |
| `sensitive-local` | research + no co-tenant secrets on the host |
| `regulated` | evidence packet, key-register admission, SBOM/SLSA |
| `high-assurance` | blocked until formal / side-channel evidence exists |

## Safe defaults (2026-07-17 gap-close)

- `:kotoba.policy/http-require-allowlist` defaults to **true** (opt out with `false`)
- `kgraph-host-functions` 1-arg is fail-closed
- Package admission accepts `--key-register` to reject non-active signers
