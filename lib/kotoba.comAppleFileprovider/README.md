# com-apple-fileprovider

**Cloud Itonami Drive in Finder, with policy outside Swift.**

This repository contains the narrow native adapter required by Apple's File
Provider framework and a portable Clojure policy model. macOS owns placeholders,
materialisation and Finder integration; Cloud Itonami owns storage, encryption,
sharing, conflict handling and synchronization decisions.

```
Finder / File Provider
  KotobaDriveFileProvider.appex       Swift callback adapter
    HTTP on 127.0.0.1 + ephemeral bearer
      cloud-itonami-app               encrypted Drive API
        kotoba-lang/envelope          client-side AEAD and key envelopes
```

The Swift boundary does not contain sync or eviction policy. Those rules live in
`fileprovider.model` (`.cljc`) and use two independent controls:

- schedule: `continuous`, `manual`, or `paused`;
- residency: `online-only`, `automatic`, or `pinned` (always available offline).

An item with a pending local edit, an unverified remote copy, or pinned residency
cannot be evicted. File Provider and Cloud Itonami consume the same commands and
badge vocabulary from that model.

## Contents

- `Sources/KotobaFileProvider`: typed localhost bridge and an
  `NSFileProviderReplicatedExtension` implementation.
- `Host` and `Extension`: minimal host app, extension entrypoint, Info.plists and
  entitlements.
- `project.yml`: reproducible Xcode project input; generated `.xcodeproj` is not
  committed.
- `src/fileprovider/model.cljk`: portable schedule/residency state machine.

The bridge accepts only `localhost` or `127.0.0.1`. Its bearer is injected into
the shared app group by the host process; it is never compiled into the app.

## Verify

```sh
kbb --backend sci --classpath src:test test/run_tests.cljk   # or: kbb -M:test
swift test
xcodegen generate
xcodebuild -project KotobaFileProvider.xcodeproj -scheme KotobaDrive \
  -configuration Debug -derivedDataPath DerivedData \
  CODE_SIGNING_ALLOWED=NO build
```

`docs/operator-quickstart.md` walks these commands in order, with the output
each one produced and the two places where a green result does not mean what it
looks like. The policy suite's own discrimination is kept honest from outside
this repository: eleven regressions of `model.cljc` are registered in the
superproject's `scripts/maturity-loop/mutations.edn`, which applies each one and
fails if the suite stays green.

The unsigned build verifies the complete host + embedded extension structure.
Finder activation additionally requires signing with an Apple team whose
profile grants the File Provider and app-group entitlements. The host registers
the `Cloud Itonami Drive` domain with `NSFileProviderManager` when launched.

## Native boundary

Apple loads a File Provider as a signed app extension; there is no portable
protocol substitute for that entrypoint. Swift here is therefore a platform
shim only. The crypto and policy libraries are owned under `kotoba-lang` and are
runtime-portable; removing Finder integration removes this Swift target without
changing Drive semantics.

## License

Apache-2.0.
