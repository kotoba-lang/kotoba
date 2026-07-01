# ADR — kotoba-shell: Tauri の kotoba/clj 版と aiueos / kototama の責務分離

Status: Accepted-in-progress
Date: 2026-06-28
Updated: 2026-07-01

## 1. 一行で

**kotoba-shell は Tauri 相当の「アプリ外殻」ではあるが、セキュリティ
モデルは Tauri 互換ではなく kotoba の capability confinement を正本にする。**

`kotoba-shell` は macOS / iOS / Android に配布できる WebView/native shell
であり、`aiueos` はその中で capability component 群を検証・起動する
OS substrate、`kototama`（実装名: `kotoba-clj`）は shell / aiueos に
投入される CLJ/Kotoba コードを安全な Wasm component にする実装層である。

```text
kotoba              = language + database + semantic substrate
kototama(kotoba-clj)= Kotoba/CLJ -> Wasm component + safe language gate
aiueos              = component OS / broker / capability graph
kotoba-shell        = app shell / WebView / native capability provider / packager
```

この ADR ではこの語彙を決定事項として扱う。`kotoba` は app shell や
compiler crate の名前ではなく、言語・database・意味空間の正本である。
`kototama` はその意味を実行可能にする層で、現実装名が `kotoba-clj`。
`aiueos` は実行可能 component 群を OS として扱う層で、capability broker /
component supervisor / audit graph を担う。

短く言えば:

```text
kotoba   : what is meant
kototama : how kotoba becomes executable
aiueos   : how executable components live together as an OS
```

この整理では、kotoba は単なる DSL ではなく database と言語を同じ意味空間
に置く substrate である。kototama/kotoba-clj はその意味を executable
Wasm component に落とす層であり、aiueos は component 群を OS として
検証・接続・監査する層である。

## 2. 背景

現状の manimani は Tauri v2 を native shell とし、ClojureScript UI と
`.cljc` 共有コアを持つ。これは実用上よいが、Tauri の権限モデルは
kotoba の「意味づけされた capability component graph」とは別物である。

欲しいものは「Tauri を Clojure で書き直す」ではなく、以下を kotoba の
正本モデルで束ねる app runtime である。

- app manifest は EDN。
- UI は CLJS / WebView。
- アプリロジックは kototama/kotoba-clj の safe profile から Wasm component。
- native 権限は capability として明示授与。
- 実行・拒否・権限解決は audit される。
- macOS / iOS / Android に配布できる。

## 3. 決定

`kotoba-shell` を新しいアプリ配布・実行単位として定義する。

```text
kotoba-shell
  ├─ EDN app manifest
  ├─ CLJS UI bundle
  ├─ kototama/kotoba-clj safe compiled wasm components
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
   :source "src/manimani/policy.clj"
   :safe true
   :exports [classify decide]
   :imports []}
  {:id :agent
   :source "src/manimani/agent.clj"
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

### 4.3 kototama / kotoba-clj

Kotoba 言語実装層。`kotoba-clj` は現在の実装名で、`kototama` は
「kotoba を実行体にする層」の概念名として扱う。ここには
`compile_safe_clj` 系の safe profile も含まれる。

責務:

- unsafe form の拒否: eval、require、reflection、ambient IO、
  raw memory primitive など。
- effect gate: 宣言された effect と実際の used effect の照合。
- capability gate: code が要求する import が policy に含まれること。
- memory / fuel / output size limits を wasm module に反映。
- deterministic build / reproducible wasm。

`kotoba-shell` から見ると、kototama/kotoba-clj は「アプリに同梱できる
component を作るための compiler + language admission gate」である。

Self-hosting の方針として、言語・admission gate・policy 推論の意味論は
可能な範囲から Kotoba/CLJ 自体へ移す。Rust は当面 bootstrap compiler /
Wasm emitter / host substrate として残るが、`kotoba-clj/selfhost` の
`safe_analyzer.kotoba` のように、safe-clj の effect/capability/policy
解析を Kotoba/CLJ で書き、Wasm component として実行し、Rust 実装と照合する
slice を正本化していく。

## 5. 依存方向

依存は一方向に固定する。

```text
kotoba-shell
  depends on aiueos
  depends on kotoba-runtime
  depends on kototama/kotoba-clj safe profile
  depends on kotoba-edn / kotoba-crypto / kotoba-datomic as needed

aiueos
  depends on kotoba-edn
  optionally depends on kototama/kotoba-clj safe profile / wasm runtime

kototama / kotoba-clj
  depends on kotoba-edn
  emits wasm component
  does not depend on kotoba-shell
  progressively self-hosts language/admission semantics in Kotoba/CLJ
```

禁止:

- `kototama` / `kotoba-clj` が shell API を知ること。
- `aiueos` が iOS/Android/macOS packaging を知ること。
- `kotoba-shell` が safe-clj の検査を迂回して CLJ component を実行すること。

## 6. 実行フロー

```text
kotoba app dev
  read app.kotoba.edn
  build CLJS UI
  for each :safe component:
    kototama/kotoba-clj safe check
    infer/minimal policy
    compile safe CLJ/Kotoba -> wasm component
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
| untrusted code | app-defined | safe-clj -> wasm component only |
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
- `kotoba-shell-evidence-profile.json`

Required environment:

- `KOTOBA_APPLE_CODESIGN_IDENTITY`
- `KOTOBA_NOTARY_PROFILE`

Local ad-hoc signing is acceptable only for development. Public distribution
requires Developer ID signing and notarization evidence.

### Windows

Windows has no Apple-style notarization equivalent. The release gate is
Authenticode signing plus Microsoft Defender SmartScreen download reputation.

Required generated artifacts:

- `windows-security-review.md`
- `sign-windows.sh`
- `smartscreen-windows.sh`
- `kotoba-shell-signing-plan.json`
- `kotoba-shell-evidence-profile.json`

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
- `kotoba shell build --target windows`, producing a Windows scaffold boundary.
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
    kotoba shell supervisor-check <app.kotoba.edn> --target <target> [--run --arg <i64> --auth-grant <resource:ability> --kqe-quad <graph,subject,predicate,object> --llm-echo]
    kotoba shell export <app.kotoba.edn> --target <target>
    kotoba shell doctor-check --target <target> [--probe]
    kotoba shell runtime-check --target <target> <project-dir>
    kotoba shell release-check --target <target> <release-dir>
    kotoba shell adapter-check --target <target> <host-adapters-manifest>
    kotoba shell updater-finalize --target <target> <updater-manifest> --artifact <artifact> --url <url> --signature-file <signature>
    kotoba shell updater-check --target <target> <updater-manifest>
    kotoba shell coverage [--json --evidence <coverage-evidence.json>]

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
  policy.clj safe component
  agent.clj safe component
```

Android/iOS の contacts/calendar/SMS は MVP 後。SMS は Android のみ。

## 10. Implemented slice

2026-06-29 時点の実装済み slice:

- `crates/kotoba-shell`: manifest parser, safe-clj admission, target-aware
  capability plan, native scaffold generator。
- `kotoba shell check/plan/dev/build/broker-check/supervisor-check/export/verify/sdk-check/runtime-check/release-check/signing-check/submission-check/adapter-check/evidence-check/updater-finalize/updater-check/coverage`。
- `kotoba shell coverage --json --evidence` emits a machine-readable
  `kotoba-shell.coverage.v0` assessment that separates functional coverage from
  release maturity and lists Tauri-baseline gaps. The generated
  `coverage-evidence.json` has `status: Passed` when the assessment itself was
  produced successfully, and CI/release evidence profiles require it alongside
  runtime, adapter, signing, and submission evidence.
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
- Release metadata: `kotoba-shell-release.json`,
  `kotoba-shell-permissions.json`, `kotoba-shell-capabilities.edn`,
  `aiueos-shell-surface.json`, `aiueos-shell-surface.edn`, Apple entitlements,
  Android permission XML, release checklist, updater manifest, Apple/Play Store
  disclosure metadata, production signing plan, target signing helper scripts,
  evidence profile manifest, macOS notarization helper script, iOS App Store
  Connect upload helper, and Android Google Play upload helper。
  Signing/submission helper scripts are generated executable,
  `kotoba shell release-check` verifies exported metadata
  plus credential environment readiness with explicit pass/fail/skip status,
  and `kotoba shell signing-check` verifies or executes target signing helpers
  with JSON evidence。`kotoba shell submission-check` verifies notarization/store
  metadata and can execute supported submission helpers with JSON evidence。
  `kotoba shell evidence-check --profile ci|android-release|store-release`
  aggregates JSON gate evidence and can require profile-specific reports to be
  `Passed` before CI/release promotion。`kotoba-shell-evidence-profile.json`
  records the generated CI/release promotion requirements in the release bundle
  and can be consumed with `evidence-check --profile-file ... --profile release`。
  `kotoba shell updater-check` verifies updater manifest structure,
  artifact sha256, signature, and URL publication readiness。`kotoba shell
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
  component supervisor start plan, safe-clj policy evidence, manifest
  exports/imports, and provider-link surface, and can execute pure safe-clj
  component exports, auth.has-capability host-bound safe-clj exports, and kqe
  read/write host-bound safe-clj exports with snapshot lift, plus llm.infer
  host-bound safe-clj exports with deterministic response binding and host event capture under
  wasmtime fuel. Release export also generates
  `kotoba-shell-host-adapters.json`, and
  `kotoba shell adapter-check --hosted --probe --smoke --evidence` verifies
  production adapter environment readiness, public HTTPS deployment endpoints,
  endpoint reachability, contract invocation smoke, and minimal response-shape
  validation. `kotoba shell supervisor-check --run
  --adapter-manifest <release-dir>/kotoba-shell-host-adapters.json` can route
  auth/kqe/llm host-bound safe-clj calls through those live adapter URLs while
  retaining the same wasmtime fuel gate, and `--evidence <evidence.json>` writes
  a CI/release artifact with the resulting supervisor report.
  `kotoba shell sdk-check` also provides an SDK compiler gate with timeout and explicit pass/fail/skip status; the
  generated iOS WKWebView project passes a local iOS simulator SDK build, and
  the generated Android WebView project passes a local Gradle `assembleDebug`
  SDK build and produces a debug APK。`kotoba shell sdk-check --evidence` and
  `kotoba shell doctor-check --probe --evidence` and
  `kotoba shell runtime-check --evidence` provide CI/release JSON artifacts;
  runtime-check covers device/simulator install and launch smoke gates with
  explicit pass/fail/skip status。

This is not yet Tauri-mature. It is a reproducible shell/scaffold and evidence
generator with an aiueos shell-surface contract and release disclosure evidence.
The current SDK gate is callable and auditable. iOS now has a generated Xcode
project that passes local simulator SDK build, and Android now generates SDK/
Gradle property files, a lightweight `gradlew` helper pinned toward compatible
local Gradle candidates, and a Java WebView runner that passes local SDK debug
APK assembly.

## 11. Closing slice: kotoba-lang/shell authority split

As of 2026-07-01, the implementation authority for the shell adapter has moved
to `kotoba-lang/shell`. `kotoba-lang/kotoba` keeps language/runtime coverage
and documentation, but the public shell command surface is now
`../shell/bin/kotoba-shell`; the old `kotoba-clj shell ...` compatibility shim
is intentionally removed.

Closed in this slice:

- `kotoba-lang/shell` now owns the Tauri-like shell adapter surface:
  native-host checks/runs/providers, app scaffold/check/build, policy/surface
  gates, release connect/verify/sign/submit, updater publish, store
  request/status, distribution plan/check, API freeze/compat, plugin check,
  Tauri-plugin compatibility check, doctor/e2e/device-farm/ui gates.
- Store submit/status can run through the built-in Java HTTP client with
  `--endpoint-url`, `--auth-token`, `--auth-token-file`,
  `KOTOBA_STORE_AUTH_TOKEN`, and `--store-header`. Tokens are not emitted in
  result data; evidence records only whether auth was configured.
- Release credentials accept `@secret-file` references, so signing/submission
  gates can consume local or CI-managed secrets without embedding secret values
  in EDN manifests.
- Device-farm operation has both a schedule artifact and an executable run-log
  artifact: `device-farm schedule --write --execute --run-log ...` records the
  external farm command results as EDN evidence.
- Stable API evidence is frozen and checked by `api freeze` and `api compat`.
  Removing a command from the v1 surface without a major-version bump is a
  compatibility failure.
- Tauri plugin migration is represented as a mechanical compatibility gate:
  `plugin tauri-check` maps Tauri-style command manifests to kotoba-shell plugin
  providers and reports unsupported commands.
- Canonical shell evidence is EDN-first. JSON remains an interop format for
  third-party tooling, store helpers, and CI consumers.

Remaining open maturity items:

- Run the store submit/status path against real App Store Connect and Google
  Play credentials and preserve the resulting request/response evidence.
- Run signing with real Developer ID/App Store/Android keystore material and
  preserve detached signature/notarization/store artifacts.
- Run iOS/Android device-farm schedules continuously on real devices, not only
  command-level local smoke.
- Add longer-lived Tauri plugin compatibility fixtures from real plugin
  manifests and publish migration guidance per plugin class.

Coverage/maturity relative to Tauri after this slice is estimated at roughly
64% functional coverage and 44% maturity: the shell has executable gates and
release evidence contracts, but not yet broad ecosystem compatibility, real
store submission history, or long-running device-farm operations.

## 12. manimani への適用

manimani の既存構造はそのまま移行しやすい。

- `src/manimani/*.cljc`: shared app core。
- `src/manimani/*.cljs`: UI。
- `policy.cljc` / `agent.cljc`: safe-clj component 化候補。
- Tauri Rust commands: kotoba-shell capability providers へ移行。
- `facts/*.edn` / ledger: shell storage provider + aiueos audit と接続。

最初の移行は「Tauri を消す」ではなく、同じアプリを
`app.kotoba.edn` で記述し、kotoba-shell で macOS dev 起動すること。

## 13. Open Questions

- `kotoba-shell` を `com-junkawasaki/kotoba/crates` に置くか、
  独立 repo にするか。
- UI bridge の wire format を EDN / Transit / CBOR のどれにするか。
- iOS で wasm component runtime を native 側に置くか、WKWebView 側に置くか。
  初期は WKWebView/bundled wasm を優先する。
- aiueos の `:shell` surface を aiueos 本体に入れるか、
  kotoba-shell 側 crate に provider として置くか。
