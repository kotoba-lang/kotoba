# Operator quickstart

Take this repository from a fresh clone to a built, inspected app bundle, in an
order that tells you *which* half broke when something breaks.

Every command below was walked from a clean checkout on the machine described in
"Measured on", and the outputs are pasted as they were printed. Two of the steps
print something that reads greener than it is; both are called out where they
occur.

It stops one step short of a Finder mount. §4 measures the built artifact to
show what is missing, and is explicit about which part of that is a reading of
the binary and which part is Apple's requirement rather than something observed
here.

## Measured on

| | |
|---|---|
| commit | steps 2–7 `25b10f4`; step 1 re-walked at `3d6e710` (2026-09-09) |
| macOS | 26.3.1, arm64 |
| Xcode | 26.6 (17F113) |
| Swift | 6.3.3 (`swiftlang-6.3.3.1.3`) |
| XcodeGen | 2.45.4 |
| Clojure CLI | 1.12.5.1654 |
| nbb | 1.5.212 |

Re-measure rather than trust this table; it is a record of one walk, not a
supported matrix. `xcodegen` is the only non-Apple prerequisite
(`brew install xcodegen`).

## 0. The two halves fail independently

```
  policy                            transport
  src/fileprovider/model.cljk       Sources/KotobaFileProvider/
  ── schedule / residency           ── DriveItem wire shape
  ── eviction safety                ── localhost HTTP + bearer
  ── badge vocabulary               ── NSFileProviderReplicatedExtension
      ↓ step 1                          ↓ steps 2–3
  nbb / kbb -M:test             swift test, then xcodebuild
```

A policy change breaks step 1 and leaves 2–3 green. A wire-shape change does the
opposite. If both go red at once you changed something in `DriveItem`'s meaning,
not its encoding — the two halves only meet at the schedule/residency vocabulary.

Neither step proves Finder mounts it. That is a third property; §4.

## 1. Policy — `kbb -M:test`, or `kbb --backend sci test/run_tests.cljk`

The policy half is portable `.cljc` and has two runners. They load the same
namespace and must agree; they are listed in the order this workspace reaches
for them.

```
$ kbb --backend sci --classpath src:test test/run_tests.cljk

Testing fileprovider.model-test

Ran 12 tests containing 101 assertions.
0 failures, 0 errors.
fileprovider model: OK
```

```
$ kbb -M:test
Running tests in #{"test"}

Testing fileprovider.model-test

Ran 12 tests containing 101 assertions.
0 failures, 0 errors.
```

Under a second for `nbb`. Four seconds for `kbb -M:test` with `.cpcache`
removed, two warm, on the machine above — the very first run on a new machine is
slower because it also clones the test-runner git dependency into `~/.gitlibs`.
`test/run_tests.cljk` is the `nbb` entry point only; the Clojure runner does not
pick it up, which is why both report 12 and not 13.

The tests are the repository's invariants, not smoke. Four hold the happy path
of each mode — schedule and residency move independently, `:open` on a
placeholder materialises, eviction never discards the only known-good copy,
every local state has a badge. The other eight hold the half that decides when
an operation is **refused**: that `:materialized` is the one state whose bytes
may be discarded, that a completed upload clears the pending flag, that pausing
outranks pinning, that unpin frees what pin was holding, that each validity
field is checked on its own, and that an event the model does not know moves
nothing.

**Confirm it discriminates before you trust a green.** Relax the eviction guard
in `src/fileprovider/model.cljk` — change `can-evict?`'s `(not= :pinned
residency)` to `true` — and the suite names the invariants you broke:

```
FAIL in (pin-and-unpin-move-only-what-must-move) (model_test.cljc:155)
unpinning frees bytes it was only holding because they were pinned
expected: (false? (model/can-evict? pinned))
  actual: (not (false? true))

FAIL in (eviction-is-lossless) (model_test.cljc:36)
dirty, unverified and pinned bytes are never evicted
expected: (false? (model/can-evict? item))
  actual: (not (false? true))
...
Ran 12 tests containing 101 assertions.
3 failures, 0 errors.
```

Exit status is `1` from both runners. Revert with
`git checkout -- src/fileprovider/model.cljk`.

That one edit is the cheapest check, not the whole one. Eleven separate
regressions of this model are registered as mutations in the superproject's
`scripts/maturity-loop/mutations.edn`, which applies each to a throwaway
worktree and fails if the suite stays green. Ten of the eleven were measured
surviving the four-test suite this file described before 2026-09-09; the floor
below is what that costs to keep.

The exit status catches a *failing* test and not a *missing* one. Empty
`test/fileprovider/model_test.cljk` down to its `ns` form and the runner reports
`Ran 0 tests containing 0 assertions. 0 failures, 0 errors.` and exits `0`. A
check built on this step therefore needs a floor on the count as well as the
exit status — today, 12 tests and 101 assertions. §2 has the same shape for the
Swift side, and the reason to state it twice is that the two runners disagree
about almost everything else.

## 2. Swift transport — `swift test`

```
$ swift test
Building for debugging...
...
Build complete! (15.56s)
Test Suite 'All tests' started at 2026-08-31 01:30:30.441.
Test Suite 'All tests' passed at 2026-08-31 01:30:30.443.
	 Executed 0 tests, with 0 failures (0 unexpected) in 0.000 (0.003) seconds
◇ Test run started.
↳ Testing Library Version: 1902
↳ Target Platform: arm64e-apple-macos14.0
✔ Test residencyMapsToFinderContentPolicy() passed after 0.001 seconds.
✔ Test wireShapeRoundTrips() passed after 0.001 seconds.
✔ Test onlyLocalBridgeEndpointsAreAccepted() passed after 0.008 seconds.
✔ Test run with 3 tests in 0 suites passed after 0.009 seconds.
```

**`Executed 0 tests, with 0 failures` is not your result.** These tests use
swift-testing, not XCTest, so the XCTest suite legitimately runs nothing — and
reports that in the vocabulary a CI log scraper is most likely to be grepping
for. The line that carries the answer is the last one: `Test run with 3 tests`.

This is not a theoretical hazard. Break the map — in
`Sources/KotobaFileProvider/FileProviderExtension.swift`, send `.onlineOnly` to
`.downloadEagerlyAndKeepDownloaded` instead of `.downloadLazily` — and the two
reports disagree in the same run:

```
Test Suite 'All tests' passed at 2026-08-31 01:28:34.872.
	 Executed 0 tests, with 0 failures (0 unexpected) in 0.000 (0.004) seconds
...
✘ Test residencyMapsToFinderContentPolicy() recorded an issue at BridgeTests.swift:34:5:
  Expectation failed: (item(.onlineOnly).contentPolicy → NSFileProviderContentPolicy(rawValue: 3))
                   == (.downloadLazily → NSFileProviderContentPolicy(rawValue: 1))
✘ Test run with 3 tests in 0 suites failed after 0.008 seconds with 1 issue.
```

The XCTest line still says **passed** and still says **0 failures**. Only the
`✘ Test run` line and the exit status (`1`) know.

The exit status catches a *failing* test. It does not catch a *missing* one.
Emptying `Tests/KotobaFileProviderTests/BridgeTests.swift` down to its imports
gives:

```
$ swift test ; echo $?
Test Suite 'All tests' passed at 2026-08-31 01:29:18.507.
	 Executed 0 tests, with 0 failures (0 unexpected) in 0.000 (0.003) seconds
◇ Test run started.
✔ Test run with 0 tests in 0 suites passed after 0.001 seconds.
0
```

Green on every channel: XCTest, swift-testing, and the exit status. So a check
built on this step needs **both** — the exit status, and a floor on the count in
`Test run with N tests` (today, `N = 3`). Without the floor, "the tests were
deleted" and "the tests passed" are the same observation.

Revert with `git checkout -- Sources/ Tests/`.

## 3. The app bundle — `xcodegen generate`, then `xcodebuild`

The `.xcodeproj` is generated, never committed; `project.yml` is its input.

```
$ xcodegen generate
⚙️  Generating plists...
⚙️  Generating project...
⚙️  Writing project...
Created project at .../KotobaFileProvider.xcodeproj

$ xcodebuild -project KotobaFileProvider.xcodeproj -scheme KotobaDrive \
    -configuration Debug -derivedDataPath DerivedData \
    CODE_SIGNING_ALLOWED=NO build
...
** BUILD SUCCEEDED **
```

About 2 minutes cold on the machine above. What this buys you is *structural*:
the app extension has to be built as an `app-extension` target and embedded in
the host app's `PlugIns` directory, and that wiring lives in `project.yml`
rather than in any source file, so nothing in steps 1–2 can catch it breaking.

Check the structure directly rather than trusting `BUILD SUCCEEDED`:

```
$ ls DerivedData/Build/Products/Debug/KotobaDrive.app/Contents/PlugIns/
KotobaDriveFileProvider.appex

$ /usr/libexec/PlistBuddy -c 'Print :NSExtension:NSExtensionPointIdentifier' \
    DerivedData/Build/Products/Debug/KotobaDrive.app/Contents/PlugIns/KotobaDriveFileProvider.appex/Contents/Info.plist
com.apple.fileprovider-nonui
```

An `.appex` sitting beside the `.app` instead of inside it is a build that
succeeded and produced nothing macOS will load.

## 4. Why this build cannot appear in Finder

`CODE_SIGNING_ALLOWED=NO` is what makes step 3 runnable without an Apple
Developer account, and it is also precisely what stops the result from mounting.
The reason is visible in the artifact:

```
$ codesign -dv DerivedData/Build/Products/Debug/KotobaDrive.app
CodeDirectory v=20400 size=420 flags=0x20002(adhoc,linker-signed) ...
Signature=adhoc
TeamIdentifier=not set

$ codesign -d --entitlements - DerivedData/Build/Products/Debug/KotobaDrive.app
Executable=.../KotobaDrive.app/Contents/MacOS/KotobaDrive
```

The second command prints the executable path and then nothing. **No
entitlements are embedded** — not the app group, not
`com.apple.developer.fileprovider.testing-mode`. The two `.entitlements` files in
`Host/` and `Extension/` are inputs to a signing step that did not run, so both
binaries are ad-hoc signed with an empty entitlement set and no team.

That is the measurement. The consequence is Apple's documented requirement
rather than something this walk observed: macOS loads a File Provider extension
only when it is signed by a team whose provisioning profile grants the File
Provider entitlements, and the app group in §5 is likewise an entitlement the
sandbox honours. Neither is present here, so `NSFileProviderManager.add` has
nothing it can register.

To go further you need an Apple Developer team, a provisioning profile granting
`com.apple.developer.fileprovider.testing-mode` and the
`group.org.kotoba.drive` app group, and a signed build.

**None of that was walked.** Everything above §4 was executed and its output
pasted; the signed path was not attempted, and the host app was deliberately not
launched — launching it registers a File Provider domain on the machine, which
is a system change and not something a quickstart should make on your behalf as
a side effect of being read. Treat this section as a diagnosis of the artifact,
not a report of a mount that failed.

## 5. What the extension reads at runtime

The extension holds no credentials and discovers no configuration. The host
process injects two values, and the extension reads them back out of the app
group:

| env var on the host | app-group key | read by |
|---|---|---|
| `CLOUD_ITONAMI_FILE_PROVIDER_URL` (default `http://127.0.0.1:1338/`) | `bridgeBaseURL` | `FileProviderExtension.swift:72` |
| `CLOUD_ITONAMI_FILE_PROVIDER_BEARER` (**no default**) | `bridgeBearer` | `FileProviderExtension.swift:73` |

Written at `Host/KotobaDriveApp.swift:19-23`. Note the asymmetry: the URL is
always written, with a fallback; the bearer is written *only if the environment
variable is present*.

So the first failure of a correctly signed but misconfigured install is
`NSFileProviderError(.notAuthenticated)`, thrown at
`FileProviderExtension.swift:74` when either key is missing. In Finder this
surfaces as a domain that appears and immediately refuses to enumerate — the
extension is loading fine; it has no token.

Two constraints are enforced in code rather than documentation:

- `Bridge.swift:75` — `precondition(baseURL.host == "127.0.0.1" || "localhost")`.
  A non-loopback base URL traps the extension at construction rather than
  sending the bearer off-box. Pointing this at a remote host is not a
  configuration option.
- The bearer is short-lived and host-injected. Nothing in this repository mints,
  stores or refreshes it.

## 6. The other side of the wire

`HTTPDriveBridge` is a client for routes owned by `cloud-itonami-app`. Read as of
that repository's `15f425c`, dispatch is at `src/cloud/itonami/app/server.clj`
line 3065, and the handler is `handle-file-provider!` at line 1313:

```
GET    /v1/file-provider/items/:id
GET    /v1/file-provider/items/:id/children[?page=]
GET    /v1/file-provider/items/:id/content     → body + X-Kotoba-Item (base64 JSON)
POST   /v1/file-provider/items
PATCH  /v1/file-provider/items/:id
PATCH  /v1/file-provider/items/:id/mode        ← no Swift client
PUT    /v1/file-provider/items/:id/content
DELETE /v1/file-provider/items/:id
```

Two things an operator should know before debugging a 4xx:

- **Bearer is the whole authentication story.** `require-session!`
  (`server.clj:461`) tries the bearer token before the cookie. `require-origin!`
  (`:433`) and `require-csrf!` (`:514`) both begin with `(when-not (bearer-token
  exchange) ...)`, so a bearer request skips them by construction — CSRF and
  Origin exist for the browser, which attaches its cookie by itself. A missing
  `Origin` header from the extension is therefore not the bug you are looking
  for.
- **Residency is not settable from Finder.** The `…/mode` route sets schedule and
  residency, and the `DriveBridge` protocol in `Bridge.swift` has no method that
  calls it. Those two controls are changed from the Cloud Itonami web UI; Finder
  consumes them. This is a deliberate asymmetry, not a gap in the client.

The server was not started during this walk. The lines above are readings at the
commits named, which `grep -n 'file-provider' src/cloud/itonami/app/server.clj`
will relocate if they have moved.

## 7. Cleanup

Everything the steps above produce is generated and already ignored:

```
$ git status --short      # empty after all of the above
$ rm -rf .build DerivedData KotobaFileProvider.xcodeproj .cpcache
```

If `git status` is *not* empty here, you edited a source file — most likely the
discrimination check in step 1 or 2 that you meant to revert.
