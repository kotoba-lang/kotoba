# Native CLI migration (JUN-198)

The intended normal CLI, build and required CI run through Amu-produced native
code, without JVM, GraalVM, Node or nbb. CLJ remains an explicitly selected
bootstrap/compatibility tool. Authority and resource boundaries remain in
force; selfhost never grants capabilities. Track completion in
[JUN-198](https://linear.app/com-junkawasaki/issue/JUN-198).

## Reproducible compiler and runtime gate

`scripts/build-selfhost-toolchain.sh` takes a clean source snapshot at the
exact Amu revision in `scripts/native-toolchain.env` and a new output directory.
It verifies the manifest, concatenated 16-module source, native bootstrap and
trusted C supervisor source before executing them. The native bootstrap builds
G1; G1 builds G2; G2 builds G3. Every compiler image must match the reviewed
fixed-point digest, and G2/G3 containers and images must be byte-identical.
No hosted language implementation participates in compilation.

```sh
bash scripts/build-selfhost-toolchain.sh \
  --amu-source /absolute/path/to/pinned-amu \
  --output /absolute/path/to/new-selfhost-build
```

The gate currently qualifies macOS arm64. Other hosts refuse explicitly. The
C supervisor remains trusted bootstrap infrastructure; this is not a C-free
claim. Self-build has a finite arena, CPU and wall budget; compiler fuel is
disabled for this build only. Input and tool digests are checked around each
invocation. Outputs and logs never share a directory writable by the compiled
program with the host supervisor.

`scripts/test-selfhost-runtime.sh` uses the fresh G3 to compile the complete
19-module native runtime fixture from this repository and two immutable source
snapshots (the same pinned Amu checkout and portable bytes). It executes seven checks of
typed values, scalar compatibility, reader/policy refusal and runtime fuel,
then verifies native fuel exhaustion and unsupported target/policy refusal.
Source digests and execution reports are retained. The workflow pins all input
revisions and denies `java`, `javac`, `clojure`, `clj`, `bb`, `node`, `nbb`, `kbb`,
`npm`, `native-image`, `python` and `python3` during these steps.

The `CI` aggregate requires the native gate and the existing CLJ compatibility
gate during migration. The empty Python SDK packaging gate is retired.

## Public CLI cutover remains open

The toolchain gate proves native compiler self-build and this runtime fixture;
it does **not** claim that `bin/kotoba`, `scripts/build-native.sh` or all public
CLI targets are migrated. In particular:

* `bin/kotoba` still dispatches most commands through `kotoba-clj`.
* `scripts/build-native.sh` still builds the CLJ implementation with GraalVM.
* The native seed emits AArch64 macOS. It refuses the Wasm/Web targets used by
  the normal public package build. A compiler's self-build does not establish
  those targets or command parity.
* The previous 59-module combined native CLI depends on source overlays in its
  historical build records. Amu #1426 restores its 27 native modules and
  fixtures; frontend dependency integration and the full CLI build remain open.
  The compiler seed and native reader used by CI now share merged Amu
  `1b0687a5997c35fec1d3903840eecc76b934589e`.

The normal CLI and build switch, and removal of CLJ from required CI, must wait
for a reproducible complete native command graph and equivalent admission,
target, package-lock and execution checks. Do not replace those checks with
scalar shadows, omit source roots/locks, silently select another target or use
a hosted fallback to turn an unsupported route green.
