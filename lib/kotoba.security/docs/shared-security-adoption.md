# Shared security library adoption

Security controls shared by Kotoba repositories live in `kotoba-lang/security`.
Direct consumers must pin the full immutable commit recorded in
`policy/shared-security-adoption.edn`; branches, tags, abbreviated SHAs, and
duplicated local implementations do not satisfy this contract.

The machine-readable adoption register records every direct consumer and its
rollout PR. All eight authoritative stack repositories are consumers.
`kotoba-lang` loads the controls in release admission, and `kagitaba` loads
them in sealed-import admission. Their repository tests fail if the immutable
pin drifts or those runtime control namespaces no longer load.

An open PR is not completed adoption. The register may use `:adopted` only
after consumer verification has passed, or a pre-existing unrelated CI failure
has been reproduced and documented, the PR is merged, and the resulting main
commit is recorded. Long-running platform jobs may finish after merge, but
their state at merge must remain visible rather than being represented as a
pass.
