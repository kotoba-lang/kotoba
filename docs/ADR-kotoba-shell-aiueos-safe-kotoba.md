# ADR — kotoba-shell: Tauri の kotoba 版と aiueos / safe Kotoba の責務分離

Status: Proposed
Date: 2026-06-28

## 1. 一行で

**kotoba-shell は Tauri 相当の「アプリ外殻」ではあるが、セキュリティ
モデルは Tauri 互換ではなく kotoba の capability confinement を正本にする。**

`kotoba-shell` は macOS / iOS / Android に配布できる WebView/native shell
であり、`aiueos` はその中で capability component 群を検証・起動する
OS substrate、safe Kotoba / `kotoba wasm` は shell / aiueos に投入される
Kotoba コードを安全な Wasm component にする実行ロジック層である。

```text
kotoba              = language + database + semantic substrate
kotoba wasm         = Kotoba -> Wasm component + safe language gate
aiueos              = component OS / broker / capability graph
kotoba-shell        = app shell / WebView / native capability provider / packager
```

この ADR ではこの語彙を決定事項として扱う。`kotoba` は app shell や
compiler crate の名前ではなく、言語・database・意味空間の正本である。
`kotoba wasm` / safe Kotoba はその意味を実行可能にする層で、`kotoba-clj`
は当面の実装 crate 名として残る。
`aiueos` は実行可能 component 群を OS として扱う層で、capability broker /
component supervisor / audit graph を担う。

短く言えば:

```text
kotoba      : what is meant
kotoba wasm : how kotoba becomes executable
aiueos      : how executable components live together as an OS
```

この整理では、kotoba は単なる DSL ではなく database と言語を同じ意味空間
に置く substrate である。`kotoba wasm` / safe Kotoba はその意味を
executable Wasm component に落とす層であり、aiueos は component 群を OS として
検証・接続・監査する層である。

## 2. 背景

現状の manimani は Tauri v2 を native shell とし、ClojureScript UI と
`.cljc` 共有コアを持つ。これは実用上よいが、Tauri の権限モデルは
kotoba の「意味づけされた capability component graph」とは別物である。

欲しいものは「Tauri を Clojure で書き直す」ではなく、以下を kotoba の
正本モデルで束ねる app runtime である。

- app manifest は EDN。
- UI は CLJS / WebView。
- アプリロジックは safe Kotoba profile から Wasm component。
- native 権限は capability として明示授与。
- 実行・拒否・権限解決は audit される。
- macOS / iOS / Android に配布できる。

## 3. 決定

`kotoba-shell` を新しいアプリ配布・実行単位として定義する。

```text
kotoba-shell
  ├─ EDN app manifest
  ├─ CLJS UI bundle
  ├─ safe Kotoba compiled wasm components
  ├─ aiueos system graph
  ├─ native capability providers
  └─ platform packager
```

最小 manifest:

```edn
{:kotoba.app/id "jp.co.gftd.manimani"
 :kotoba.app/name "manimani"

 :ui {:kind :cljs
      :entry "src/manimani/app.cljs"
      :build :shadow-cljs}

 :components
 [{:id :policy
   :source "src/manimani/policy.kotoba"
   :safe true
   :exports [classify decide]
   :imports []}
  {:id :agent
   :source "src/manimani/agent.kotoba"
   :safe true
   :exports [step]
   :imports [:ledger/read :ledger/append :llm/infer]}]

 :capabilities
 {:ledger/read   {:scope "facts/*.edn"}
  :ledger/append {:scope "facts/events.edn"}
  :keychain/read {:keys [:edn-key]}
  :notify/show   {}
  :http/egress   {:allow ["https://kotobase.net/*"]}
  :contacts/read {:platforms #{:ios :android :macos}}
  :calendar/read {:platforms #{:ios :android :macos}}
  :sms/read      {:platforms #{:android}}}

 :storage {:kind :append-edn
           :encrypted true
           :sync :kotobase}

 :targets #{:macos :ios :android}}
```

## 4. 責務分離

### 4.1 kotoba-shell

アプリ外殻。Tauri に対応する層。

責務:

- WebView / window / menu / app lifecycle。
- macOS `.app`、iOS Xcode project、Android Gradle project の生成。
- platform permission / entitlement / signing / bundle metadata。
- JS bridge: CLJS UI から native capability を呼ぶ。
- native capability provider: fs、keychain、notification、contacts、
  calendar、Android SMS、http、clipboard など。
- aiueos broker の埋め込み、または aiueos system graph の起動委譲。

非責務:

- untrusted CLJ の安全性判定。
- component 間 capability graph の意味論。
- Wasm guest の権限推論。
- 汎用 OS / microVM / driver runtime。

### 4.2 aiueos

capability-secure component OS。kotoba-shell の中で使われる下位 substrate。

責務:

- system graph / manifest / policy の検証。
- broker による verify -> safe-check -> compile -> run。
- capability linking。
- effect/trust policy。
- topic bus / host ABI / audit。
- surface provider 抽象: browser、robot、cloud、将来の shell。

`kotoba-shell` から見ると、aiueos は「アプリ内 component supervisor」である。
Tauri で言えば plugin permission layer と command dispatcher に近いが、
意味論はより強く、deny-by-default の capability graph を持つ。

### 4.3 kotoba wasm / safe Kotoba

Kotoba 言語実装層。`kotoba wasm` は公開 CLI / build path、safe Kotoba は
`compile_safe_kotoba` 系の capability-confined profile、`kotoba-clj` は
当面の実装 crate 名として扱う。

責務:

- unsafe form の拒否: eval、require、reflection、ambient IO、
  raw memory primitive など。
- effect gate: 宣言された effect と実際の used effect の照合。
- capability gate: code が要求する import が policy に含まれること。
- memory / fuel / output size limits を wasm module に反映。
- deterministic build / reproducible wasm。

`kotoba-shell` から見ると、`kotoba wasm` / safe Kotoba は「アプリに同梱できる
component を作るための compiler + language admission gate」である。

Self-hosting の方針として、言語・admission gate・policy 推論の意味論は
可能な範囲から Kotoba 自体へ移す。Rust は当面 bootstrap compiler /
Wasm emitter / host substrate として残るが、`kotoba-clj/selfhost` の
`safe_analyzer.kotoba` のように、safe Kotoba の effect/capability/policy
解析を Kotoba で書き、Wasm component として実行し、Rust 実装と照合する
slice を正本化していく。shell/release evidence も同じ方針で EDN-first に
寄せる。JSON は CI / store helper / third-party tooling の interop format
として残すが、Kotoba 内部の canonical shape は EDN map として読める・書ける
ことを gate にする。

## 5. 依存方向

依存は一方向に固定する。

```text
kotoba-shell
  depends on aiueos
  depends on kotoba-runtime
  depends on kotoba wasm / safe Kotoba profile
  depends on kotoba-edn / kotoba-crypto / kotoba-datomic as needed

aiueos
  depends on kotoba-edn
  optionally depends on kotoba wasm / safe Kotoba profile / wasm runtime

kotoba wasm / safe Kotoba
  depends on kotoba-edn
  emits wasm component
  does not depend on kotoba-shell
  progressively self-hosts language/admission semantics in Kotoba
```

禁止:

- `kotoba wasm` / safe Kotoba compiler が shell API を知ること。
- `aiueos` が iOS/Android/macOS packaging を知ること。
- `kotoba-shell` が safe Kotoba の検査を迂回して Kotoba component を実行すること。

## 6. 実行フロー

```text
kotoba app dev
  read app.kotoba.edn
  build CLJS UI
  for each :safe component:
    kotoba wasm safe check
    infer/minimal policy
    compile safe Kotoba -> wasm component
  aiueos verify system graph
  launch shell host
  expose native capabilities as aiueos providers
  open WebView

CLJS UI
  -> kotoba.shell/invoke
  -> aiueos broker
  -> capability provider or wasm component
  -> audited result
```

## 7. Surface model

aiueos already has surface provider direction (`browser`, `robot`, `cloud`).
`kotoba-shell` adds a new surface:

```edn
{:aiueos/surface :shell
 :aiueos/providers
 [{:id :shell/fs-app-data     :exports #{:fs/read :fs/write :fs/append}}
  {:id :shell/keychain        :exports #{:keychain/read :keychain/write}}
  {:id :shell/notification    :exports #{:notify/show}}
  {:id :shell/contacts        :exports #{:contacts/read}}
  {:id :shell/calendar        :exports #{:calendar/read}}
  {:id :shell/android-sms     :exports #{:sms/read}
   :platforms #{:android}}]}
```

The shell surface is not a privileged escape hatch. It is a named provider set
whose exports must be granted by policy and audited by the broker.

## 8. Tauri との違い

| 項目 | Tauri | kotoba-shell |
|---|---|---|
| app manifest | JSON/TOML + Rust commands | EDN kotoba app manifest |
| UI | arbitrary web frontend | CLJS first, web-compatible |
| native calls | command/plugin | capability provider |
| permission | Tauri capability files | aiueos/kotoba capability graph |
| untrusted code | app-defined | safe Kotoba -> wasm component only |
| audit | app-defined | append-only aiueos/kotoba audit |
| packaging | strong | must implement |

kotoba-shell should borrow Tauri's practical packaging shape, not its authority
model.

## 9. Portable aiueos runner integration

`kotoba-shell` owns the user-facing app boundary. `aiueos` remains the component
OS / broker underneath it. For portable desktop distribution, kotoba-shell
therefore treats aiueos as two explicit release flavors:

```text
aiueos-core
  build:   --no-default-features
  purpose: manifest / policy / graph / audit / verify / inspect
  runtime: no embedded wasm-runtime
  UX:      safe preflight and release evidence

aiueos-runner
  build:   default features, including wasm-runtime
  purpose: run/up Wasm components from signed manifests
  runtime: embedded in the app artifact; no global wasmtime or Node install
  UX:      actual app launch
```

This split is intentional. A user should not need to install Node, wasmtime CLI,
Homebrew, or a system service for a packaged kotoba-shell app. The packaged app
may include an aiueos-runner binary or link an equivalent embedded runtime, but
that runtime is part of the artifact and is governed by the same signing and
audit gates as the shell.

The CLI surface records this as:

```text
kotoba shell build/export/release-check/signing-check/submission-check
  -> generate target release evidence
  -> include aiueos shell surface metadata
  -> require signing / notarization / reputation evidence before promotion
```

## 10. Apple and Windows security gates

Portable does not mean bypassing platform trust systems. The release pipeline
must make operating-system enforcement explicit:

### macOS

macOS distribution outside the Mac App Store is gated by Developer ID signing,
hardened runtime, notarization, and stapling.

Required generated artifacts:

- `kotoba-shell.entitlements`
- `sign-macos.sh`
- `notarize-macos.sh`
- `app-store-connect-macos.json`
- `kotoba-shell-signing-plan.json`
- `kotoba-shell-evidence-profile.edn`
- `kotoba-shell-evidence-profile.json` for external tooling interop

Required environment:

- `KOTOBA_APPLE_CODESIGN_IDENTITY`
- `KOTOBA_NOTARY_PROFILE`

Local ad-hoc signing is acceptable only for development. Public distribution
requires Developer ID signing and notarization evidence.

### Windows

Windows has no Apple-style notarization equivalent. The release gate is
Authenticode signing plus Microsoft Defender SmartScreen download reputation.

Required generated artifacts:

- WebView2/WPF host scaffold:
  `kotoba-shell-windows.csproj`, `src/App.xaml`,
  `src/MainWindow.xaml`, `src/MainWindow.xaml.cs`
- `windows-security-review.md`
- `sign-windows.sh`
- `smartscreen-windows.sh`
- `kotoba-shell-signing-plan.json`
- `kotoba-shell-evidence-profile.edn`
- `kotoba-shell-evidence-profile.json` for external tooling interop

Required environment:

- `KOTOBA_WINDOWS_CERT_PATH`
- `KOTOBA_WINDOWS_CERT_PASS`
- `KOTOBA_WINDOWS_TIMESTAMP_URL`
- `KOTOBA_WINDOWS_DOWNLOAD_URL`

The pipeline cannot promise SmartScreen will never warn. It can require stable
publisher identity, timestamped Authenticode signatures, stable HTTPS download
origin, and release evidence that monitors first-run SmartScreen warnings until
publisher / artifact reputation is established.

## 11. Implemented release pipeline slice

The current executable slice in `crates/kotoba-shell` implements:

- `Target::Windows` in the shell target model.
- `kotoba shell build --target windows`, producing staged UI/release metadata
  plus a minimal WebView2/WPF host scaffold with bridge and readiness markers.
- `kotoba shell export --target windows`, producing signing and SmartScreen
  review artifacts.
- `kotoba shell export --target macos|windows`, producing
  `aiueos-portable-plan.json`, `build-aiueos-core.bb`, and
  `build-aiueos-runner.bb`.
- `kotoba shell verify --target windows`, verifying staged UI and aiueos shell
  metadata.
- `kotoba shell release-check --target windows`, checking generated artifacts
  and credential environment readiness.
- `kotoba shell signing-check --target windows`, executing `sign-windows.sh`
  when Authenticode credentials are present.
- `kotoba shell submission-check --target windows`, executing
  `smartscreen-windows.sh` to gate stable HTTPS download/reputation evidence.

macOS release export/check already generates and validates signing,
notarization, entitlement, updater, and evidence metadata. The missing proof is
credential-backed execution against real Apple / Windows release credentials,
not the local artifact generation path.

The aiueos portable helper scripts are executable release artifacts. They build
`aiueos-core` with `--no-default-features` and `aiueos-runner` with default
features, stage `bin/aiueos`, `app/`, and `state/`, and emit zip archives under
`target/kotoba-shell/aiueos-portable` or `KOTOBA_AIUEOS_DIST`.

## 9. MVP

MVP は Tauri 互換全体ではなく、manimani を dogfood できる最小面にする。

```text
crates/kotoba-shell
  CLI:
    kotoba shell check <app.kotoba.edn>
    kotoba shell plan  <app.kotoba.edn>
    kotoba shell dev   <app.kotoba.edn>
    kotoba shell build <app.kotoba.edn> --target <target>
    kotoba shell broker-check <app.kotoba.edn> --target <target> [--command <command> --audit-log <audit.jsonl>]
    kotoba shell supervisor-check <app.kotoba.edn> --target <target> [--run --arg <i64> --auth-grant <resource:ability> --kqe-quad <graph,subject,predicate,object> --llm-echo --kototama-app-components <manifest.edn>]
    kotoba shell export <app.kotoba.edn> --target <target>
    kotoba shell doctor-check --target <target> [--probe]
    kotoba shell runtime-check --target <target> <project-dir>
    kotoba shell release-check --target <target> <release-dir>
    kotoba shell adapter-check --target <target> <host-adapters-manifest>
    kotoba shell updater-finalize --target <target> <updater-manifest> --artifact <artifact> --url <url> --signature-file <signature>
    kotoba shell updater-check --target <target> <updater-manifest>
    kotoba shell coverage [--json --evidence <coverage-evidence.json>]
    kotoba shell coverage-check [--min-functional <pct> --min-release-maturity <pct> --evidence <coverage-check-evidence.json>]

  target:
    macos .app build first
    android Gradle/WebView scaffold second
    ios WKWebView scaffold third

  providers:
    fs/app-data
    keychain
    notify
    http/egress allowlist
    clipboard

examples/manimani-shell
  app.kotoba.edn
  CLJS UI
  policy.kotoba safe component
  agent.kotoba safe component
```

`--kototama-app-components` is a legacy option name for shipped safe Kotoba app
component manifests.

Android/iOS の contacts/calendar/SMS は MVP 後。SMS は Android のみ。

## 10. Implemented slice

2026-06-29 時点の実装済み slice:

- `crates/kotoba-shell`: manifest parser, safe Kotoba admission, target-aware
  capability plan, native scaffold generator。
- `kotoba shell check/plan/dev/build/broker-check/supervisor-check/export/verify/sdk-check/runtime-check/runtime-matrix-check/device-farm-check/windows-runtime-contract-check/release-check/signing-check/submission-check/provider-contract-check/plugin-check/plugin-sdk-check/plugin-load-check/compatibility-check/compatibility-migration-check/surface-check/surface-parity-check/adapter-check/evidence-check/updater-finalize/updater-check/updater-feed-check/coverage`。
- `kotoba shell coverage --json --evidence` emits a machine-readable
  `kotoba-shell.coverage.v0` assessment that separates functional coverage from
  release maturity and lists Tauri-baseline gaps. The generated
  `coverage-evidence.json` has `status: Passed` when the assessment itself was
  produced successfully, and CI/release evidence profiles require it alongside
  runtime, adapter, signing, and submission evidence.
- `kotoba shell coverage-check --min-functional 70 --min-release-maturity 45`
  emits `kotoba-shell.coverage-check.v0` evidence and fails CI/release promotion
  when the current Tauri-baseline coverage or release maturity drops below the
  configured threshold.
- macOS: WKWebView dev runner, minimal `.app` bundle, local codesign verify,
  JS/native bridge, `fs/app-data`, `notify/show`, clipboard text read/write,
  `http/fetch`, keychain text read/write/delete, contacts/calendar read
  providers, runtime audit, stale signature cleanup before bundle rebuild。
- iOS: WKWebView scaffold, generated minimal Xcode project, `Info.plist`,
  bundled UI assets, shell permission metadata, target-aware provider catalog,
  contacts/calendar usage descriptions, UserNotifications, UIPasteboard,
  URLSession, Keychain Services, and Contacts/EventKit providers, entitlement
  template, Xcode export option template。
- Android: Gradle/WebView scaffold, Java bridge, bundled UI assets, shell
  permission metadata, target-aware provider catalog, Android permission review
  manifest, generated manifest permissions including contacts/calendar,
  NotificationManager, ClipboardManager, HttpURLConnection, Android Keystore
  AES/GCM keychain, ContactsContract/CalendarContract read providers, runtime
  permission request/retry flow for notification/contacts/calendar, generated
  `local.properties`/`gradle.properties`, generated `gradlew` helper that
  prefers a cached Gradle 8.14.3 or `KOTOBA_GRADLE`, SDK path detection, and
  JDK/Gradle detection for `kotoba shell sdk-check`。
- Provider contracts: `kotoba shell provider-contract-check` emits
  `kotoba-shell.provider-contract-check.v0` evidence by resolving the target
  manifest capabilities into a provider catalog, verifying command surfaces for
  each provider, and rejecting capabilities without provider linkage. The catalog
  is now derived from `kotoba-clj/selfhost/aiueos_provider_catalog.edn`, with
  JSON retained as an exported interop projection. The executable provider
  oracle lives in `kotoba-clj/selfhost/aiueos_provider_catalog.kotoba`; Rust
  compiles and checks that bundled Kotoba source instead of generating it.
  Required provider command coverage, capability-family matching, and the
  provider oracle's universe projection are also derived from that seed's
  target-gated provider entries and `matches` patterns. Provider catalog digest
  symbol codes are stored in the seed's `digest` map rather than a Rust-only
  table. It includes the aiueos ledger/audit provider for
  `ledger/append` alongside shell providers for notification, clipboard, HTTP,
  keychain, contacts, and calendar. Generated
  macOS, iOS, Android, and Windows native hosts now implement
  `ledger/append` as a capability-gated local append-only JSONL ledger under app
  data. `kotoba shell ledger-replay-check` replays that JSONL into a replica,
  validates supported ledger/audit schemas, and emits
  `kotoba-shell.ledger-replay-check.v0` release evidence. `kotoba shell
  ledger-remote-check` validates hosted HTTPS replication endpoint shape,
  optionally probes it, and emits `kotoba-shell.ledger-remote-check.v0` release
  evidence; remaining aiueos audit maturity is production hosted endpoint pass
  evidence, not the local provider, replay path, or release gate wiring.
- Plugin contracts: `kotoba-shell-plugins.json` records the builtin provider
  plugin registry derived from the same capability catalog. `kotoba shell
  plugin-check --evidence` emits `kotoba-shell.plugin-check.v0` evidence by
  verifying plugin id, target, commands, and deny-by-default permission metadata.
  Release export also writes `kototama-plugin-contract.component.wasm` plus
  `kototama-plugin-contract.edn` / `.json` from
  `kotoba-clj/selfhost/plugin_contract.kotoba`; plugin-check executes that
  shipped oracle when present and release
  `evidence-check` requires its bundled oracle markers for plugin promotion
  evidence. This keeps plugin discovery below the kotoba capability graph
  rather than granting ambient Tauri-style native authority.
- Plugin SDK compatibility: `kotoba-shell-plugin-sdk.json` records the external
  plugin ABI version, external plugin manifest schema, required fields, host
  bridge/audit semantics, and a sample plugin manifest. `kotoba shell
  plugin-sdk-check --evidence` emits `kotoba-shell.plugin-sdk-check.v0`
  evidence. `kotoba-shell-plugin-bundles.json` records manifest-gated external
  plugin bundle admission: target, ABI, command namespace, deny-by-default
  permission, local artifact path, sha256, and detached signature file.
  `kotoba shell plugin-load-check --evidence` emits
  `kotoba-shell.plugin-load-check.v0` evidence after verifying the artifact
  exists, the sha256 matches, the signature file is present, and the artifact
  can be compiled, instantiated, and invoked through the sample `example/echo`
  command export by the embedded wasmtime sandbox with fuel. The loader records
  an allowlist for host imports and the sample plugin calls
  `env.kotoba_host_audit`, which is linked only when the manifest permits it.
  Plugin SDK/load checks use the same shipped `plugin_contract.kotoba` oracle to
  bind schema, ABI, permission-mode, loader-mode, audit-import, and required
  field-count invariants to Kotoba-owned release evidence. The companion
  `plugin_contract.edn` seed records the same export values for data-level
  conformance and shell checks read expected plugin oracle exports from that
  seed instead of reconstructing them from plugin JSON in Rust.
  Broader host imports and third-party plugin execution remain pending, but
  release promotion now has sandbox admission, sample command invocation, and
  host-audit import evidence instead of only an SDK schema.
- Compatibility policy: `kotoba-shell-compatibility.json` records shell/plugin
  ABI, schema compatibility rules, supported release channels, minimum
  deprecation notice, and migration-test requirements. `kotoba shell
  compatibility-check --evidence` emits `kotoba-shell.compatibility-check.v0`
  evidence. Release export also writes
  `kototama-compatibility-contract.component.wasm` plus
  `kototama-compatibility-contract.edn` / `.json` from
  `compatibility_contract.kotoba`; compatibility-check executes that shipped
  oracle when present and release `evidence-check` requires its bundled oracle
  markers for compatibility promotion evidence. `kotoba shell
  compatibility-migration-check` consumes previous/current compatibility
  manifests, verifies same-major policy continuity, ABI preservation, retained
  channels and known schemas, and emits
  `kotoba-shell.compatibility-migration-check.v0` evidence. This is still alpha
  policy, but schema/ABI churn and old/new migration continuity are visible to
  release promotion through Kotoba-owned contract evidence.
- App surface contract: `kotoba-shell-app-surface.json` records the WebView
  engine/bridge, primary window contract, menu/tray contract, lifecycle events,
  and capability bindings. `kotoba shell surface-check --evidence` emits
  `kotoba-shell.app-surface-check.v0` evidence so window/menu/tray/lifecycle
  coverage is part of release promotion instead of checklist prose only.
  `kotoba shell surface-parity-check --evidence` consumes multiple target
  app-surface manifests and verifies that their bridge runtime and provider
  portable command sets match. Release profiles invoke it with required
  macOS/iOS/Android/Windows targets, so promotion has a static four-target
  parity gate before device-level behavioral parity is available. macOS
  now backs this contract with a native `NSMenu`, `NSStatusItem`, lifecycle
  delegate markers, and `KOTOBA_SHELL_SURFACE_READY` runtime evidence.
  Windows now generates a WebView2/WPF host scaffold, static verify checks, and
  `kotoba shell windows-runtime-contract-check` evidence for `run.ps1`,
  WebView2, `WebMessageReceived`, `window.kotobaShell`, readiness markers,
  lifecycle markers, updater bridge, and ledger append bridge; Windows runner
  execution evidence is still pending until the host is executed on Windows.
- Native host contract: generated macOS/iOS/Android/Windows host projects bundle
  `kototama-native-host-contract.component.wasm` plus manifest metadata from
  `native_host_contract.kotoba`. `kotoba shell native-host-contract-check`
  executes the shipped oracle and verifies bridge/runtime, provider-command,
  capability gate, command-surface, and target dispatch digests. Expected oracle
  exports are read from `native_host_contract.edn`, leaving Rust to parse/check
  the seed instead of owning a duplicate target digest table.
- Runtime check contract: generated projects also bundle
  `kototama-runtime-contract.component.wasm` from `runtime_contract.kotoba`.
  Runtime-check oracle expectations are read from `runtime_contract.edn`, so
  Rust no longer owns the runtime-check schema/field/target command-plan export
  table.
- SDK contract: generated projects bundle `kototama-sdk-contract.component.wasm`
  from `sdk_contract.kotoba`. SDK oracle expectations are read from
  `sdk_contract.edn`, so Rust no longer owns the SDK schema/project-file/command
  digest export table.
- Compatibility/app-components contracts: compatibility and safe app component
  checks execute `compatibility_contract.kotoba` and
  `app_components_contract.kotoba`, with expected oracle exports read from
  companion EDN seeds instead of being reconstructed from JSON fields in Rust.
- Updater contracts: updater manifest, updater channel, updater UI, and updater
  lifecycle checks execute their Kotoba oracles with expected exports read from
  companion EDN seeds instead of being reconstructed from updater JSON fields in
  Rust.
- Evidence promotion now derives plugin, compatibility, updater, and
  updater-lifecycle required oracle markers from the same EDN contract seeds,
  reducing the duplicate Rust-owned `oracle:name:value` marker tables.
- Release/signing/submission contracts: release export bundles
  `release_contract.kotoba`, `release_target_contract.kotoba`,
  `signing_contract.kotoba`, and `submission_contract.kotoba` as executable
  Kotoba oracles. Their expected schema, file/script/env, signing, and
  submission exports are read from companion EDN seeds, so Rust no longer
  reconstructs those expected values from release JSON and target helper tables.
- Release metadata: `kotoba-shell-release.json`,
  `kotoba-shell-permissions.json`, `kotoba-shell-capabilities.edn`,
  `aiueos-shell-surface.json`, `aiueos-shell-surface.edn`,
  `kotoba-shell-plugins.json`, `kotoba-shell-plugin-sdk.json`,
  `kotoba-shell-compatibility.json`,
  `kotoba-shell-app-surface.json`, Apple entitlements,
  Android permission XML, release checklist, updater manifest, Apple/Play Store
  disclosure metadata, production signing plan, target signing helper scripts,
  evidence profile manifest, macOS notarization helper script, iOS App Store
  Connect upload helper, and Android Google Play upload helper。
  Signing/submission helper scripts are generated executable,
  `kotoba shell release-check --evidence <release-metadata-ready-evidence.json>`
  verifies exported metadata plus credential environment readiness with
  explicit pass/fail/skip status and release-profile evidence,
  and `kotoba shell signing-check` verifies or executes target signing helpers
  with EDN or JSON evidence, selected by the evidence file extension。
  `kotoba shell submission-check` verifies notarization/store metadata and can
  execute supported submission helpers with EDN or JSON evidence。
  `kotoba shell credential-execution-check --kind signing|submission` rejects
  ready-only or dry-run signing/submission reports and emits
  `kotoba-shell.credential-execution-check.v0` evidence for actual helper
  execution. Optional `--artifact` and `--output` arguments strengthen the gate
  by requiring the executed helper command to reference the release artifact or
  produced output and by requiring those paths to exist.
  `kotoba shell evidence-check --profile ci|android-release|store-release`
  aggregates EDN/JSON gate evidence and can require profile-specific reports to
  be `Passed` before CI/release promotion。Known required evidence also validates
  its expected schema, including coverage, coverage-check, runtime doctor,
  release metadata, SDK build, runtime launch, adapter, supervisor, combined
  adapter/supervisor, signing/submission readiness, signing/submission execution,
  and updater readiness reports, so a stale or wrong EDN/JSON artifact cannot
  satisfy promotion only by setting `status: Passed`。`kotoba-shell-evidence-profile.edn`
  is the EDN-first generated CI/release promotion profile in the release bundle,
  `kotoba-shell-evidence-profile.json` is retained for external tooling interop,
  and either can be consumed with `evidence-check --profile-file ... --profile release`。
  The profile embeds `kotoba-clj/selfhost/shell_evidence_profile.edn` as
  `selfhostProjection` so the Kotoba-owned evidence/profile seed is checked
  against the Rust bootstrap output. Release export also writes the companion
  `shell_evidence_profile.kotoba` safe Kotoba Wasm oracle as
  `kototama-shell-evidence-profile.component.wasm` with EDN/JSON manifests.
  `kotoba shell selfhost-profile-check --profile-oracle-manifest
  <release-dir>/kototama-shell-evidence-profile.edn` executes that shipped
  Kototama oracle, checking profile/command/evidence counts and structure
  digests against the EDN seed before emitting
  `kotoba-shell.selfhost-profile-check.v0` evidence. CI/release profiles require
  `selfhost-profile-ready-evidence` before promotion, and `evidence-check`
  requires that evidence to prove the bundled oracle path, component source
  marker, component sha marker, and profile/command/evidence digests rather than
  accepting a check-time Rust bootstrap compile.
  `kotoba shell provider-contract-check` also compiles and runs the bundled safe
  Kotoba provider/surface oracle from
  `kotoba-clj/selfhost/aiueos_provider_catalog.kotoba`, checking the provider
  universe's family count, command count, portable command count, and
  status-class count before accepting provider contract evidence.
  The same oracle now checks per-provider scores encoding command counts,
  portable command counts, and shell/audit status codes, plus a catalog digest
  that covers provider order, family id, capability, status, and command
  sequence, so provider mapping invariants begin to move out of Rust-only JSON
  construction. Release export
  writes this oracle as `kototama-provider-surface-policy.component.wasm` plus
  EDN/JSON manifests, and `provider-contract-check --provider-oracle-manifest`
  can execute the shipped kototama artifact. CLI release evidence for provider
  contract, app surface, and app surface parity requires this manifest so those
  gates cannot emit release evidence from a check-time Rust bootstrap compile.
  `evidence-check` requires provider evidence to include the bundled oracle
  marker, component source marker, component sha marker, and provider score
  markers before accepting `provider-contract-evidence` in release profiles.
  The app-surface and app-surface parity gates use the same provider/surface
  oracle, and release evidence must prove that they used the shipped kototama
  oracle artifact.
  `kotoba shell kototama-wasm-check` (legacy command name) compiles the bundled
  Kotoba selfhost analyzer to a Wasm Component, and release export writes the
  legacy-named `kototama-selfhost-analyzer.component.wasm` plus
  `kototama-selfhost-analyzer.edn` / `.json` manifests. The check can validate
  the bundled manifest and artifact sha256, ABI probe, and capability import
  surface, emits `kotoba-shell.kototama-wasm-check.v0`, and CLI release evidence
  requires the shipped analyzer manifest so shell readiness depends on a real
  safe Kotoba Wasm artifact rather than Rust metadata alone. Safe app components
  declared in `app.kotoba.edn` are also exported under the legacy release path
  `kototama/components/*.wasm` with `kototama-app-components.edn`; `kotoba shell
  kototama-app-components-check` (legacy command name) verifies those shipped artifacts, the
  `selfhost/kotoba` admission gate marker, and the analyzer ABI. The check
  report carries those values as structured fields on the report and each
  component entry, so promotion tooling does not need to parse free-form check
  strings. `evidence-check` treats those fields as part of the required
  contract for `kototama-app-components-ready-evidence`, not only optional
  metadata. Release export also writes
  `kototama-app-components-contract.component.wasm` plus
  `kototama-app-components-contract.edn` / `.json` manifests from
  `app_components_contract.kotoba`; `kototama-app-components-check` requires
  that sibling oracle and executes it to validate schema/admission/analyzer ABI
  digests, digest modulus, and required manifest/component field counts before
  emitting release evidence. `evidence-check` requires those bundled oracle
  markers for `kototama-app-components-ready-evidence`. It also records and
  verifies `sourceSha256` for each component, so a
  stale shipped Wasm artifact cannot be promoted after the corresponding Kotoba
  source changes. The app component manifest is also bound to the bundled
  `kototama-selfhost-analyzer.component.wasm` by `analyzerComponentSha256`, so
  app artifacts cannot be promoted against a different selfhost analyzer than
  the one shipped in the same release directory. The manifest also carries a
  `componentContractDigest` over ordered component ids, artifact paths, source,
  policy and artifact hashes, exports, imports, and byte sizes. Each component policy is
  regenerated by the selfhost analyzer and checked against `policySha256`, so
  release evidence proves the shipped artifact used the least policy for the
  current Kotoba source. The checker also recompiles the component through the
  selfhost analyzer and compares the resulting Wasm sha256 with the shipped
  artifact, so a manifest with updated artifact hashes still fails unless the
  bytes are reproducible from Kotoba source and policy. Promotion profiles require
  `kototama-app-components-ready-evidence`.
  The aiueos supervisor dry-run can consume that same
  `kototama-app-components.edn` via `--kototama-app-components`, so runtime
  evidence can execute the shipped safe Kotoba Wasm artifact instead of compiling
  source again during the dry-run. CLI `supervisor-check --run --evidence`
  requires that manifest, leaving source-compile dry-runs as a development-only
  path. The dry-run report also carries the shipped artifact sha256, source
  sha256, policy sha256, admission gate, analyzer ABI, and analyzer component
  sha256, preserving the same source -> policy -> Wasm chain in runtime evidence.
  safe Kotoba analysis and compilation have also moved to selfhost-first
  operation: public `infer_effects*`, `minimal_policy*`, `unused_grants*`,
  `compile_safe_kotoba*` APIs (with legacy `compile_safe_clj*` aliases) and
  `compile_safe_file*` APIs plus the `kotoba wasm
  safe-build` / `safe-policy` commands run the bundled Kotoba analyzer by
  default when component support is enabled. Rust remains the bootstrap
  reader/emitter/fallback path, while covered subset, literal type,
  effect-declaration, least-policy, over-grant, and capability-resource
  admission decisions come from the Kotoba analyzer before Wasm emission.
  `kotoba shell updater-check --evidence <updater-ready-evidence.json>` verifies
  updater manifest structure, artifact sha256, signature, and URL publication
  readiness, and release profiles require this evidence. Release export also
  writes `kototama-updater-contract.component.wasm`,
  `kototama-updater-channel-contract.component.wasm`, and
  `kototama-updater-ui-contract.component.wasm`, plus
  `kototama-updater-lifecycle-contract.component.wasm`, with EDN/JSON manifests
  from `updater_contract.kotoba`, `updater_channel_contract.kotoba`,
  `updater_ui_contract.kotoba`, and `updater_lifecycle_contract.kotoba`;
  updater-check, updater-channel-check, and updater-ui-check execute that
  shipped oracle when present, and release `evidence-check` requires its bundled
  oracle markers for updater manifest, channel-policy, updater UI,
  bundle/install, and publication promotion evidence。
  Store promotion gates follow the same selfhost path: release export writes
  `kototama-signing-contract.component.wasm` and
  `kototama-submission-contract.component.wasm` from `signing_contract.kotoba`
  and `submission_contract.kotoba`; `signing-check` and `submission-check`
  execute those shipped oracles when present, and release `evidence-check`
  requires their bundled markers for signing/submission readiness evidence.
  Release metadata follows the same path through
  `kototama-release-contract.component.wasm` and
  `kototama-release-target-contract.component.wasm` from
  `release_contract.kotoba` and `release_target_contract.kotoba`;
  `release-check` executes that shipped oracle when present, and
  `evidence-check` requires its bundled markers for
  `release-metadata-ready-evidence`.
  `kotoba-shell-updater-channel.json` records update channels, HTTPS-only
  channel URLs, signature requirements, staged rollout, rollback support,
  manual approval, and release-note requirements. `kotoba shell
  updater-channel-check --evidence` emits
  `kotoba-shell.updater-channel-check.v0` evidence, so updater policy is a
  release gate even before public URL publication.
  `kotoba-shell-updater-ui.json` records the in-app updater states, user
  actions, progress/error events, `window.kotobaShell.invoke` bridge contract,
  and native bindings to the updater manifest/channel policy. `kotoba shell
  updater-ui-check --evidence` emits `kotoba-shell.updater-ui-check.v0`
  evidence, so the update UX contract is release-gated and native-host visible.
  Generated macOS, iOS, Android, and Windows bridges now
  expose `updater.check`, `updater.download`, `updater.install`, and
  `updater.restart` commands tied to the manifest/channel policy, and
  `download`/`install`/`restart` write `kotoba-shell.updater-stage.v0` receipts
  under app data so the local staging UX is inspectable from native state.
  `kotoba shell updater-install-check --evidence` follows the updater
  evidence to the local artifact, copies it through download and install-staging
  directories, and verifies sha256 at both steps. Real in-app installer
  execution against a published feed remains a later release gate.
  `kotoba shell updater-publication-check --evidence <updater-published-evidence.json>`
  verifies that the updater artifact URL is public HTTPS and reachable with a
  HEAD probe, and release profiles require this publication evidence。`kotoba shell
  updater-finalize` fills the updater manifest from a concrete artifact,
  computed sha256, URL, and detached signature。
- Verification: macOS codesign verification plus static iOS/Android generated
  project verification for required files, permission metadata, and native
  provider evidence。iOS runtime checks create and auto-boot a temporary
  simulator by default, or use `KOTOBA_IOS_SIMULATOR_UDID` when explicitly set.
  Android runtime checks use a connected device/emulator when present or
  auto-start the first available AVD from the Android SDK. iOS/Android runtime checks install/launch the generated app and require a
  `KOTOBA_SHELL_READY` WebView load marker from simulator or device logs before
  reporting `Passed`。`kotoba shell doctor-check` emits JSON evidence for runtime
  prerequisites, missing prerequisites, remediation steps, and structured
  remediation command vectors such as iOS simulator runtime checks or Android
  SDK/AVD repair commands。With `--probe`, Android doctor also starts a short
  emulator bootability probe, so AVDs that appear in `avdmanager list avd` but
  fail before `adb wait-for-device` are recorded as `Skipped` with
  command/stdout/stderr evidence and concrete reinstall/recreate commands。
  `kotoba shell broker-check` verifies aiueos shell broker
  admission and optional dry-dispatch/audit evidence, and can append dry-run
  audit events to JSONL. `kotoba shell supervisor-check` verifies the aiueos
  component supervisor start plan, safe Kotoba policy evidence, manifest
  exports/imports, and provider-link surface, and can execute pure safe Kotoba
  component exports, auth.has-capability host-bound safe Kotoba exports, and kqe
  read/write host-bound safe Kotoba exports with snapshot lift, plus llm.infer
  host-bound safe Kotoba exports with deterministic response binding and host event capture under
  wasmtime fuel. Release export also generates
  `kotoba-shell-host-adapters.json`, and
  `kotoba shell adapter-check --hosted --probe --smoke --evidence` verifies
  production adapter environment readiness, public HTTPS deployment endpoints,
  endpoint reachability, contract invocation smoke, and minimal response-shape
  validation. `kotoba shell supervisor-check --run
  --adapter-manifest <release-dir>/kotoba-shell-host-adapters.json
  --kototama-app-components <release-dir>/kototama-app-components.edn` can route
  auth/kqe/llm host-bound safe Kotoba calls through those live adapter URLs
  while executing shipped safe Kotoba component artifacts under the same wasmtime
  fuel gate, and `--evidence <evidence.json>` writes a CI/release artifact with
  the resulting supervisor report. Adapter-supervisor promotion evidence rejects
  supervisor dry-runs that report `source compile` or omit the selfhost
  admission gate, analyzer ABI, analyzer component sha, artifact sha, source
  sha, or policy sha, so a Passed adapter-backed dry-run is tied to a shipped
  safe Kotoba Wasm artifact, the source/policy chain that produced it, and the
  selfhost analyzer component that admitted it. `evidence-check` applies the
  same contract to required `live-adapter-supervisor-evidence`, closing the
  direct profile path that would otherwise accept only schema/status.
  `kotoba shell adapter-supervisor-check --adapter-evidence ... --supervisor-evidence ...`
  combines those two artifacts into `kotoba-shell.adapter-supervisor-check.v0`
  release evidence and requires hosted/probe/smoke adapter checks plus a Passed
  live supervisor dry-run with host events.
  `kotoba shell sdk-check` also provides an SDK compiler gate with timeout and explicit pass/fail/skip status; the
  generated iOS WKWebView project passes a local iOS simulator SDK build, and
  the generated Android WebView project passes a local Gradle `assembleDebug`
  SDK build and produces a debug APK。`kotoba shell sdk-check --evidence` and
  `kotoba shell doctor-check --probe --evidence` and
  `kotoba shell runtime-check --evidence` provide CI/release JSON artifacts;
  runtime-check covers device/simulator install and launch smoke gates with
  explicit pass/fail/skip status。`kotoba shell runtime-release-check` combines
  runtime doctor and runtime-check artifacts into
  `kotoba-shell.runtime-release-check.v0` evidence, rejects dry-run runtime
  evidence, and requires a real launch command plus `KOTOBA_SHELL_READY` marker
  before mobile release promotion。The local macOS `.app` path now launches the
  generated WKWebView executable directly, waits for `KOTOBA_SHELL_READY macos`,
  and produces Passed runtime-check and runtime-release-check evidence. The local iOS simulator path has produced
  Passed SDK, runtime-check, and runtime-release-check evidence for the
  generated `kotoba-shell-hello` app. The local Android emulator path now also
  has Passed runtime doctor, SDK debug APK, runtime-check, and runtime-release-check
  evidence after repairing Android API 35 Google APIs arm64 and API 36.1 Google
  Play arm64 system images. Runtime checks can select an AVD with `--avd`, which
  allowed `Kotoba_Runtime_API_35` and `Medium_Phone_API_36.1` evidence to pass.
  `kotoba shell runtime-matrix-check` aggregates multiple
  `kotoba-shell.runtime-release-check.v0` reports, follows their doctor/runtime
  source evidence, requires specified targets and distinct runtimes, and emits
  `kotoba-shell.runtime-matrix-check.v0` release evidence. The local matrix now
  passes across iOS simulator, Android API 35, and Android API 36.1 runtime
  evidence. `kotoba shell device-farm-check` consumes runtime matrix evidence
  plus a hosted provider run URL and emits `kotoba-shell.device-farm-check.v0`
  evidence, so real device-farm runs can be release-gated without changing the
  runtime-check schema. `kotoba shell updater-bundle-check` consumes
  `kotoba-shell.updater-check.v0` evidence, follows the referenced updater
  manifest, verifies the local artifact file, sha256, detached signature, and
  public HTTPS URL shape without requiring the publication URL to be reachable,
  and emits `kotoba-shell.updater-bundle-check.v0` release evidence. This splits
  pre-publication bundle integrity and local install staging from the stronger
  `updater-publication-check` reachability probe. `kotoba shell
  updater-feed-check` verifies that a local or hosted updater feed body is a
  `kotoba-shell.updater.v0` manifest matching the release updater evidence for
  version, channel, artifact sha256/signature/url, and verify-before-install
  policy; release profiles require `kotoba-shell.updater-feed-check.v0`
  evidence before promotion.

This is not yet Tauri-mature. It is a reproducible shell/scaffold and evidence
generator with aiueos shell-surface and app-surface contracts plus release
disclosure evidence.
Remaining maturity is in broader iOS/Android device-farm provider pass evidence, real Apple/Google
submission evidence, real credential-backed signing evidence, reachable updater feed publication,
real hosted adapter pass evidence for the aiueos component supervisor, hosted
production remote ledger replication pass evidence, long-running production
compatibility migration history, Windows runner execution evidence, and native
desktop menu/tray behavior beyond the current macOS implementation. The current SDK gate is callable and auditable.
iOS now has a generated Xcode project that passes local simulator SDK build, and
Android now generates SDK/Gradle property files, a lightweight `gradlew` helper
pinned toward compatible local Gradle candidates, and a Java WebView runner that
passes local SDK debug APK assembly and emulator install/launch runtime smoke
across two local Android emulator API levels. CI runtime evidence artifacts are
now callable, but physical-device/device-farm provider runs, store-service,
updater-publication reachability, hosted-adapter, and production hosted remote ledger evidence
still need to pass before this can be counted as Tauri-level mature.

## 11. manimani への適用

manimani の既存構造はそのまま移行しやすい。

- `src/manimani/*.cljc`: shared app core。
- `src/manimani/*.cljs`: UI。
- `policy.kotoba` / `agent.kotoba`: safe Kotoba component 化候補。
- Tauri Rust commands: kotoba-shell capability providers へ移行。
- `facts/*.edn` / ledger: shell storage provider + aiueos audit と接続。

最初の移行は「Tauri を消す」ではなく、同じアプリを
`app.kotoba.edn` で記述し、kotoba-shell で macOS dev 起動すること。

## 12. Open Questions

- `kotoba-shell` を `com-junkawasaki/kotoba/crates` に置くか、
  独立 repo にするか。
- UI bridge の wire format を EDN / Transit / CBOR のどれにするか。
- iOS で wasm component runtime を native 側に置くか、WKWebView 側に置くか。
  初期は WKWebView/bundled wasm を優先する。
- aiueos の `:shell` surface を aiueos 本体に入れるか、
  kotoba-shell 側 crate に provider として置くか。
