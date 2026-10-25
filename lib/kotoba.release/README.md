# Kotoba release assurance

Fail-closed release admission and signed-tag verification for Kotoba artifacts.

This repository is an assurance consumer of the language contract. It does not
define language semantics. Callers pass the version policy from
`kotoba-lang/kotoba-lang` to `kotoba.release.tag/verify`; release publication
requests are evaluated by `kotoba.release.admission/evaluate` or admitted with
`kotoba.release.admission/admit!`.

```sh
kbb -M:test
kbb -M:lint
```

## Portability — one namespace of three

`kotoba.release.admission` is `.cljc` as of 2026-08-18 and runs under nbb:

```sh
kbb --backend sci --classpath src:test:<security>/src test/run_portable.cljk
```

Nothing in it was ever JVM-bound. It has no interop, no I/O and no host
service — it merges maps, calls eight `kotoba.security.*` evaluators that are
themselves `.cljc`, and collects the keywords they disagree on. The `.clj`
extension was an accident that made an admission decision unavailable to every
runtime but the JVM.

**`kotoba.release.tag` and `kotoba.release.cli` are still `.clj`, and that is a
constraint rather than unfinished work.** `tag/verify` asks
`kotoba.lang.version-policy/parse-semver` whether a version string is a semver.
That namespace is `.clj` in `kotoba-lang/kotoba-lang` and imports `java.time`.
The two ways past it are to change that repository — which is not this one — or
to parse the semver here, which `resources/repository-rules.edn` forbids
(`:must-not [:define-language-semantics …]`) and which would leave two
definitions of a valid Kotoba version free to drift apart. `java.util.Base64`
was never the blocker; `kotoba.bytes/base64-decode` is portable and
`ed25519.core` is already `.cljc`. See `tag.clj`'s docstring, which also records
a second thing to establish before that file moves: `canonical-body` is
`pr-str` over the envelope and that string is what gets signed.

`kotoba.release.cli` is the offline sign/verify entry point — stdin, `slurp`,
`System/exit` — and is host work by definition.

Operational signing is offline and fail-closed. The Ed25519 seed is accepted
only on stdin; the signer DID embedded in the envelope must already be active in
the separate trust document.

```sh
kagi get kotoba-language-release-ed25519 --compartment personal |
  kbb -M:tag sign --policy version-policy.edn --trust release-trust.edn \
    --envelope unsigned.edn > signed.edn

kbb -M:tag verify --policy version-policy.edn --trust release-trust.edn \
  --envelope signed.edn
```

## Mutation testing

```sh
kbb --backend sci tools/check-mutations.cljk   # every :find occurs exactly once
kbb --backend sci tools/mutate.cljk            # apply each, report what reddened
```

`tools/mutations.edn` states its scope: the admission decision, not release
assurance as a whole and not the `kotoba.security.*` evaluators it consults.
