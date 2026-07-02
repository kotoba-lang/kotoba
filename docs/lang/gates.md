# Kotoba Language Gates

Current launcher gates are CLJ/EDN-first:

```sh
clojure -M:test
bin/kotoba-clj check --kind cli-contract --json
bin/kotoba-clj selfhost list --json
bin/kotoba-clj selfhost check --json
bin/kotoba-clj run src/demo.kotoba --json
bin/kotoba-clj run src/demo.cljc --json
bin/kotoba-clj run src/demo.cljc --reader-target cljs --json
bin/kotoba-clj wasm emit src/demo.kotoba --output target/kotoba/demo.wasm --json
node -e 'const fs=require("fs"); WebAssembly.instantiate(fs.readFileSync("target/kotoba/demo.wasm")).then(({instance})=>{if(instance.exports.main()!==42) process.exit(1)})'
bin/kotoba-clj wasm emit src/demo_call.kotoba --output target/kotoba/demo_call.wasm --json
node -e 'const fs=require("fs"); WebAssembly.instantiate(fs.readFileSync("target/kotoba/demo_call.wasm")).then(({instance})=>{if(instance.exports.main()!==43) process.exit(1)})'
bin/kotoba-clj wasm emit src/demo_cap.kotoba --policy src/demo_policy.edn --output target/kotoba/demo_cap.wasm --json
node -e 'const fs=require("fs"); const imports={kotoba:{has_capability:(id)=>id===203?1:0}}; WebAssembly.instantiate(fs.readFileSync("target/kotoba/demo_cap.wasm"), imports).then(({instance})=>{if(instance.exports.main()!==7) process.exit(1)})'
bin/kotoba-clj wasm emit src/demo_notify.kotoba --policy src/demo_policy.edn --output target/kotoba/demo_notify.wasm --json
node -e 'const fs=require("fs"); const imports={kotoba:{notify_show:(code)=>code+1}}; WebAssembly.instantiate(fs.readFileSync("target/kotoba/demo_notify.wasm"), imports).then(({instance})=>{if(instance.exports.main()!==42) process.exit(1)})'
bin/kotoba-clj wasm emit src/demo_providers.kotoba --policy src/demo_provider_policy.edn --output target/kotoba/demo_providers.wasm --json
node - <<'NODE'
const fs = require('fs');
let memory;
const text = (ptr, len) => new TextDecoder().decode(new Uint8Array(memory.buffer, ptr, len));
const imports = { kotoba: {
  clipboard_read: (outPtr, outLen) => outLen,
  clipboard_write: (ptr, len) => text(ptr, len).length,
  http_fetch: (reqPtr, reqLen, outPtr, outLen) => text(reqPtr, reqLen).length + outLen,
  keychain_read: (keyPtr, keyLen, outPtr, outLen) => text(keyPtr, keyLen).length + outLen,
  keychain_write: (keyPtr, keyLen, valuePtr, valueLen) => text(keyPtr, keyLen).length + text(valuePtr, valueLen).length,
  fs_read: (pathPtr, pathLen, outPtr, outLen) => text(pathPtr, pathLen).length + outLen,
  fs_write: (pathPtr, pathLen, dataPtr, dataLen) => text(pathPtr, pathLen).length + text(dataPtr, dataLen).length
}};
WebAssembly.instantiate(fs.readFileSync('target/kotoba/demo_providers.wasm'), imports).then(({instance}) => { memory = instance.exports.memory; if (instance.exports.main() !== 67) process.exit(1); });
NODE
bin/kotoba-clj wasm emit src/demo_memory.kotoba --output target/kotoba/demo_memory.wasm --json
node -e 'const fs=require("fs"); WebAssembly.instantiate(fs.readFileSync("target/kotoba/demo_memory.wasm")).then(({instance})=>{if(instance.exports.main()!==106 || !(instance.exports.memory instanceof WebAssembly.Memory)) process.exit(1)})'
bin/kotoba-clj wasm emit src/demo_memory_write.kotoba --output target/kotoba/demo_memory_write.wasm --json
node -e 'const fs=require("fs"); WebAssembly.instantiate(fs.readFileSync("target/kotoba/demo_memory_write.wasm")).then(({instance})=>{if(instance.exports.main()!==140) process.exit(1)})'
bin/kotoba-clj wasm emit src/demo_memory_grow.kotoba --output target/kotoba/demo_memory_grow.wasm --json
node -e 'const fs=require("fs"); WebAssembly.instantiate(fs.readFileSync("target/kotoba/demo_memory_grow.wasm")).then(({instance})=>{if(instance.exports.main()!==3 || instance.exports.memory.buffer.byteLength!==131072) process.exit(1)})'
bin/kotoba-clj wasm emit src/demo_i64.kotoba --output target/kotoba/demo_i64.wasm --json
node -e 'const fs=require("fs"); WebAssembly.instantiate(fs.readFileSync("target/kotoba/demo_i64.wasm")).then(({instance})=>{if(instance.exports.main()!==42n) process.exit(1)})'
bin/kotoba-clj wasm emit src/demo_i64_params.kotoba --output target/kotoba/demo_i64_params.wasm --json
node -e 'const fs=require("fs"); WebAssembly.instantiate(fs.readFileSync("target/kotoba/demo_i64_params.wasm")).then(({instance})=>{if(instance.exports.main()!==42n) process.exit(1)})'
bin/kotoba-clj wasm emit src/demo_i64_host.kotoba --policy src/demo_i64_host_policy.edn --output target/kotoba/demo_i64_host.wasm --json
node - <<'NODE'
const fs = require('fs');
const imports = { kotoba: { host_i64_roundtrip: (v) => v + 1n }};
WebAssembly.instantiate(fs.readFileSync('target/kotoba/demo_i64_host.wasm'), imports).then(({instance}) => { if (instance.exports.main() !== 42n) process.exit(1); });
NODE
bin/kotoba-clj wasm emit src/demo_indirect.kotoba --output target/kotoba/demo_indirect.wasm --json
node -e 'const fs=require("fs"); WebAssembly.instantiate(fs.readFileSync("target/kotoba/demo_indirect.wasm")).then(({instance})=>{if(instance.exports.main()!==42) process.exit(1)})'
bin/kotoba-clj wasm emit src/demo_alloc.kotoba --output target/kotoba/demo_alloc.wasm --json
node -e 'const fs=require("fs"); WebAssembly.instantiate(fs.readFileSync("target/kotoba/demo_alloc.wasm")).then(({instance})=>{if(instance.exports.main()!==162) process.exit(1)})'
bin/kotoba-clj wasm emit src/demo_alloc_checked.kotoba --output target/kotoba/demo_alloc_checked.wasm --json
node -e 'const fs=require("fs"); WebAssembly.instantiate(fs.readFileSync("target/kotoba/demo_alloc_checked.wasm")).then(({instance})=>{if(instance.exports.main()!==1) process.exit(1)})'
bin/kotoba-clj wasm emit src/demo_string_abi.kotoba --policy src/demo_provider_policy.edn --output target/kotoba/demo_string_abi.wasm --json
node - <<'NODE'
const fs = require('fs');
let memory;
const imports = { kotoba: { clipboard_write_str: (ptr, len) => new TextDecoder().decode(new Uint8Array(memory.buffer, ptr, len)).length }};
WebAssembly.instantiate(fs.readFileSync('target/kotoba/demo_string_abi.wasm'), imports).then(({instance}) => { memory = instance.exports.memory; if (instance.exports.main() !== 6) process.exit(1); });
NODE
bin/kotoba-clj wasm emit src/demo_buffer_abi.kotoba --policy src/demo_provider_policy.edn --output target/kotoba/demo_buffer_abi.wasm --json
node - <<'NODE'
const fs = require('fs');
let memory;
const imports = { kotoba: { clipboard_read: (outPtr, outLen) => {
  const view = new Uint8Array(memory.buffer, outPtr, outLen);
  view[0] = 65; view[1] = 66; view[2] = 67;
  return 3;
}}};
WebAssembly.instantiate(fs.readFileSync('target/kotoba/demo_buffer_abi.wasm'), imports).then(({instance}) => { memory = instance.exports.memory; if (instance.exports.main() !== 201) process.exit(1); });
NODE
bin/kotoba-clj wasm emit src/demo_provider_result.kotoba --policy src/demo_provider_policy.edn --output target/kotoba/demo_provider_result.wasm --json
node - <<'NODE'
const fs = require('fs');
const imports = { kotoba: { http_fetch: () => -7 }};
WebAssembly.instantiate(fs.readFileSync('target/kotoba/demo_provider_result.wasm'), imports).then(({instance}) => { if (instance.exports.main() !== 7) process.exit(1); });
NODE
bin/kotoba-clj wasm emit src/demo_result_record.kotoba --policy src/demo_provider_policy.edn --output target/kotoba/demo_result_record.wasm --json
node - <<'NODE'
const fs = require('fs');
const imports = { kotoba: { http_fetch: () => -7 }};
WebAssembly.instantiate(fs.readFileSync('target/kotoba/demo_result_record.wasm'), imports).then(({instance}) => { if (instance.exports.main() !== 8) process.exit(1); });
NODE
../shell/bin/kotoba-shell adapter check --target ios --json
../shell/bin/kotoba-shell adapter check --target android --json
../shell/bin/kotoba-shell native-host check --target macos --json
../shell/bin/kotoba-shell native-host check --target ios --json
../shell/bin/kotoba-shell native-host check --target android --json
../shell/bin/kotoba-shell native-host check --target windows --json
../shell/bin/kotoba-shell native-host run --target macos --host-command /bin/echo --host-arg kotoba-host-ok --json
../shell/bin/kotoba-shell native-host run --target ios --host-command /bin/echo --host-arg kotoba-ios-host-ok --json
../shell/bin/kotoba-shell native-host provider --target macos --provider-command clipboard/write-text --text kotoba-clipboard-ok --json
../shell/bin/kotoba-shell native-host provider --target macos --provider-command clipboard/read-text --json
../shell/bin/kotoba-shell app scaffold --target macos --target ios --target android --manifest-edn '{:app/id "demo" :app/name "Demo" :app/version "0.1.0" :ios/bundle-id "dev.demo" :android/application-id "dev.demo"}' --output-dir target/kotoba-shell/app-gate --json
../shell/bin/kotoba-shell app check --target macos --target ios --target android --manifest-edn '{:app/id "demo" :app/name "Demo" :app/version "0.1.0" :ios/bundle-id "dev.demo" :android/application-id "dev.demo"}' --output-dir target/kotoba-shell/app-gate --json
../shell/bin/kotoba-shell app build --target android --manifest-edn '{:app/id "demo" :app/name "Demo" :app/version "0.1.0" :android/application-id "dev.demo"}' --output-dir target/kotoba-shell/app-gate --json
../shell/bin/kotoba-shell release dry-run --target macos --target ios --target android --manifest-edn '{:app/id "demo" :app/name "Demo" :app/version "0.1.0" :ios/bundle-id "dev.demo" :android/application-id "dev.demo"}' --output-dir target/kotoba-shell/release-gate --json
../shell/bin/kotoba-shell release connect --target ios --target android --manifest-edn '{:app/id "demo" :app/name "Demo" :app/version "0.1.0" :ios/bundle-id "dev.demo" :android/application-id "dev.demo"}' --json
../shell/bin/kotoba-shell release verify --target macos --manifest-edn '{:app/id "demo" :app/name "Demo" :app/version "0.1.0"}' --output-dir target/kotoba-shell/release-gate --json
../shell/bin/kotoba-shell release sign --target macos --manifest-edn '{:app/id "demo" :app/name "Demo" :app/version "0.1.0"}' --sign-command /usr/bin/codesign --json
../shell/bin/kotoba-shell release submit --target ios --manifest-edn '{:app/id "demo" :app/name "Demo" :app/version "0.1.0" :ios/bundle-id "dev.demo"}' --submit-command xcrun --json
../shell/bin/kotoba-shell updater publish --target macos --manifest-edn '{:app/id "demo" :app/name "Demo" :app/version "0.1.0"}' --updater-feed target/kotoba-shell/release-gate/macos/updater-feed.edn --json
../shell/bin/kotoba-shell store request --target ios --manifest-edn '{:app/id "demo" :app/name "Demo" :app/version "0.1.0" :ios/bundle-id "dev.demo"}' --endpoint-url https://api.appstoreconnect.apple.com --json
../shell/bin/kotoba-shell store status --target android --manifest-edn '{:app/id "demo" :app/name "Demo" :app/version "0.1.0" :android/application-id "dev.demo"}' --json
../shell/bin/kotoba-shell distribution check --target ios --target android --manifest-edn '{:app/id "demo" :app/name "Demo" :app/version "0.1.0" :ios/bundle-id "dev.demo" :android/application-id "dev.demo"}' --json
../shell/bin/kotoba-shell api check --json
../shell/bin/kotoba-shell plugin check --plugin-edn '{:plugin/id "demo.plugin" :plugin/version "0.1.0" :plugin/api-version 1 :plugin/providers []}' --json
../shell/bin/kotoba-shell e2e check --target macos --target ios --target android --json
../shell/bin/kotoba-shell device-farm check --target ios --target android --strict --json
../shell/bin/kotoba-shell e2e check --target ios --target android --strict --json
../shell/bin/kotoba-shell ui smoke --substrate browser --script smoke:visual --execute --strict --json
../shell/bin/kotoba-shell ui smoke --substrate browser --script smoke:webgpu --execute --strict --json
bin/kotoba-clj check src/demo.kotoba --json
```

These gates verify that:

- the launcher delegates public CLI behavior to the CLJC authority;
- `.kotoba`, `.cljc`, `.clj`, and `.edn` source kinds are classified
  from `resources/kotoba/lang/source_contract.edn`;
- `.cljc` defaults to reader target `:kotoba` but can be planned for `:clj` or
  `:cljs`;
- `run` and `check` results are annotated with
  `:kotoba.launcher/source-plan` and
  `:kotoba.launcher/authority-request`;
- missing reader targets are reflected into the argv delegated to the CLJC
  authority as `--reader-target`;
- existing `.kotoba` and `.cljc` source files run through the CLJ-owned runtime
  slice and return `:run/completed`;
- `wasm emit` emits a WebAssembly MVP binary for supported zero-arity numeric
  `main` functions and writes it with `--output`;
- the Wasm emitter supports integer helper functions, direct function calls,
  `if`, and signed integer comparisons in the current subset;
- explicit `i64` constants and arithmetic can be emitted as an `i64` `main`
  result and run in standard WebAssembly runtimes;
- `^:i64` function params/results and `i64` locals are emitted for direct calls;
- `i64 -> i64` host imports can be emitted and called by standard WebAssembly
  runtimes using BigInt host values;
- `call-indirect` emits a function table, element segment, and `call_indirect`
  for the current `i32 -> i32` table slice;
- `has-capability?` requires an explicit policy and emits a deterministic
  `kotoba.has_capability(i32) -> i32` WebAssembly import;
- `notify-show` requires `notify/show` policy and emits
  `kotoba.notify_show(i32) -> i32`;
- clipboard, HTTP fetch, keychain, and app-data filesystem provider imports are
  policy-gated and emitted with deterministic pointer+length and request+buffer
  ABI names;
- emitted modules export `memory` with one minimum page;
- literal `str-len`, `bytes-len`, and `byte-at` compile to i32 constants;
- string and byte-vector literals can be placed into data segments and passed
  to provider imports through pointer+length ABI with `str-ptr`, `bytes-ptr`,
  `str-len`, and `bytes-len`;
- guest code can read and write memory bytes with `mem-byte-at` and
  `byte-store!`;
- guest code can query and grow memory with `memory-pages` and `memory-grow`;
- guest code can allocate dynamic buffers with the minimal bump allocator
  exposed as `alloc`;
- checked allocation with `alloc-checked` returns `-1` when the allocation
  would exceed the current Wasm memory size;
- provider read imports can write back into guest memory buffers that Kotoba
  code reads after the import returns;
- provider imports use the current integer result convention, where
  non-negative values are success lengths/codes and negative values are error
  codes checked with `result-ok?` and `result-err?`;
- provider result integers can be written into structured 8-byte records and
  read back with `result-status` and `result-value`;
- unreadable policy paths return stable `:wasm/policy-not-readable` results;
- the emitted wasm can be instantiated by a standard WebAssembly runtime;
- `../shell/bin/kotoba-shell adapter check` verifies mobile/desktop target contracts from bundled
  selfhost resources and reports `kotoba-lang/shell` as the shell authority;
- `../shell/bin/kotoba-shell native-host check` exposes native bridge/provider
  command and capability-gate contract evidence from bundled selfhost resources;
- `../shell/bin/kotoba-shell native-host run` connects to a real external host runner process for
  desktop and mobile targets, returning exit status and stdout. The
  `kotoba-lang/shell` authority now bundles default macOS, iOS `simctl`, and
  Android `adb` runner entrypoints;
- `../shell/bin/kotoba-shell native-host provider` executes target-specific provider commands; the
  current macOS clipboard provider uses `pbcopy` and `pbpaste`;
- `../shell/bin/kotoba-shell surface check/commit` verifies the Kotoba-native display path:
  `browser` plus `wasm-ui` and no required system WebView;
- `../shell/bin/kotoba-shell app scaffold/check` creates and verifies minimal
  native project skeletons for macOS, iOS, and Android from an EDN manifest;
- `../shell/bin/kotoba-shell app build` emits target-aware native build plans
  and runs the selected build command only with `--execute`;
- `../shell/bin/kotoba-shell policy check` and provider execution return policy decisions and
  `kotoba.shell.audit.v0` audit records;
- `../shell/bin/kotoba-shell release check/evidence` validates target manifests and reports
  packaging, signing, updater, artifact, and audit metadata for release gates;
- `../shell/bin/kotoba-shell release dry-run` writes target artifact evidence, dry-run signature
  evidence, and updater feed evidence for macOS, iOS, and Android without
  invoking platform stores;
- `../shell/bin/kotoba-shell release connect` verifies production signing,
  updater, App Store Connect, Google Play, and artifact prerequisites without
  submitting to the stores;
- `../shell/bin/kotoba-shell release verify` checks the artifact/signature/feed
  digest chain before promotion;
- `../shell/bin/kotoba-shell release sign` and `release submit` run real
  signing/submission commands only when `--execute` is present; otherwise they
  return target-aware default execution plans for CI promotion;
- `../shell/bin/kotoba-shell updater publish` publishes signed updater feeds or
  store-backed release tracks through the same plan/execute gate;
- `../shell/bin/kotoba-shell store request/status` generates App Store Connect,
  Google Play, notarization, or Microsoft Store HTTP request evidence and can
  execute it with the built-in Java HTTP client or an external HTTP adapter;
- `../shell/bin/kotoba-shell distribution check` combines production release
  connection readiness with API and plugin compatibility expectations for store
  or channel promotion;
- `../shell/bin/kotoba-shell api check` exposes the stable shell command/data
  contract, and `plugin check` validates third-party provider manifests against
  the stable plugin API;
- `../shell/bin/kotoba-shell doctor check` reports host runner and platform toolchain readiness,
  using warnings for local non-strict runs and failures for strict CI/device
  profiles;
- `../shell/bin/kotoba-shell e2e check` combines toolchain, surface, provider bridge, release
  metadata, and host smoke evidence, with strict mode for CI/device-farm gates.
  macOS executes the bundled local host runner, iOS probes `simctl` for a booted
  simulator, and Android probes `adb devices` for a connected device/emulator;
- `../shell/bin/kotoba-shell device-farm check` combines local iOS/Android
  readiness with an optional external device-farm command for continuous
  real-device E2E;
- `../shell/bin/kotoba-shell ui check` verifies the `browser` and `wasm-ui` substrate repos,
  required source files, package scripts, audit metadata, and the no-WebView
  surface path;
- `../shell/bin/kotoba-shell ui smoke` exposes browser/wasm-ui smoke scripts as shell evidence and
  can execute selected scripts for CI. Browser smoke execution starts the local
  static server automatically, waits until it accepts HTTP traffic, and covers
  the browser WebGL visual smoke plus the WebGPU smoke path when available;
- `kotoba-lang/kotoba` no longer exposes a shell shim. Shell gates execute
  `../shell/bin/kotoba-shell` directly, so language/runtime coverage and app
  shell authority are separated at the command boundary;
- live desktop host execution is proven by the local macOS runner smoke. Live
  mobile host connection is probed through `simctl` and `adb`; a strict mobile
  E2E gate still requires a booted simulator or connected Android device;
- selfhost EDN seeds from `../kotoba-selfhost-contracts/resources/kotoba/selfhost/`
  are listable and checkable through CLJ launcher commands;
- launcher resources are exercised through `bin/kotoba-clj` and the CLJ test gate.

## Package admission

Safe execution rejects unsafe package inputs end-to-end (issue #262, security
finding `F-001`). The launcher owns a package admission gate backed by the
`kotoba.lang.package-contract` validation kernel from
`kotoba-lang/kotoba-lang`:

```sh
bin/kotoba-clj package verify --lock kotoba.lock.edn --json
bin/kotoba-clj package verify --lock kotoba.lock.edn \
  --manifest package-manifest.edn \
  --trust trust.edn \
  --receipt target/kotoba/package-receipt.edn --json
bin/kotoba-clj wasm emit src/demo.kotoba --package-lock kotoba.lock.edn --json
```

- `package verify --lock <kotoba.lock.edn>` validates every lock entry and
  returns `:kotoba.cli/code` `package-verified` (exit 0) or `package-rejected`
  (exit 1). The optional `--manifest <package-manifest.edn>` also validates the
  package manifest (signatures, repo RID, CIDs) and supplies the declared
  capabilities; `--trust <trust.edn>` supplies
  `:declared-capabilities` / `:revoked-signers` / `:expired-signers` /
  `:compromised-signers`. Without either source of declared capabilities, no
  capability grant is admitted (strict default).
- Rejection classes mirror the kotoba-lang package-conformance negatives:
  version-only dependencies (`:package/missing-lock-field`), unsigned or
  bad-signature manifests (`:package/signature-required`,
  `:package/signature-alg-unsupported`), missing repo RID / manifest CID /
  tree CID, revoked/expired/compromised signers
  (`:package/signer-not-trusted`), capability grants exceeding the package
  declaration (`:package/capability-exceeds-declaration`), and — added by the
  admission layer in safe mode — local-path dependencies
  (`:package/local-path-dependency`: any `:package/local-root` /
  `:dep/local-root` key or path-looking `:dep/ref`/`:dep/url`).
- Both accept and reject emit a package-verification receipt
  (`:kotoba.package/receipt` with `:kotoba.package/verified?`,
  `:kotoba.package/lock-path`, `:kotoba.package/checked-at`,
  `:kotoba.package/problems`, and per-dependency `:kotoba.package/entries`
  carrying `:package/id`, `:package/repo-rid`, `:package/manifest-cid`,
  `:package/tree-cid`, `:package/result`). `--receipt <out.edn>` writes the
  receipt EDN file used as release evidence.
- The safe-build path takes an optional `--package-lock <path>` on
  `wasm emit`: admission runs before the build, a rejected lock aborts the
  build with `:wasm/package-rejected` and the receipt in the error payload,
  and an admitted lock attaches the receipt to the build result. Without
  `--package-lock` there are no package inputs to admit and behavior is
  unchanged.

Cargo/Rust gates are historical for this repository. Implementation-heavy
compiler conformance belongs in `kotoba-lang/kotoba-lang` or another authority
repo that owns the executable compiler/runtime.
