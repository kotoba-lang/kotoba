# AWAI-81 native module build

The current 1,985-assertion closure passes through the canonical **per-module
compiler and machine-code linker**, without source concatenation, alias
rewriting, interface removal, or `--unpinned`.

The original 204-assertion receipt remains a historical linkage baseline.
The entry is `test/kotoba/vm/evm/native_project_gate.kotoba`. Each test imports
its implementation normally. Inga's test namespace is now at the canonical
`test/native/inga/native_prefix_gate.kotoba` path. The two crypto provider
modules are unchanged upstream bytes pinned in the recorded source lock.

## Native build stages

With the exact staged/mounted roots named by `project.lock`, invoke the
pinned loaderless compiler (recorded in the receipt):

```text
compiler.elf compile /work/native-project/test/kotoba/vm/evm/native_project_gate.kotoba \
  --source-path /work/native-project/src \
  --source-path /work/native-project/test \
  --source-path /work/native-project/providers \
  --source-path /work/native-project/inga \
  --source-path /work/native-project/inga-test \
  --source-lock /work/native-project/project.lock \
  --target aarch64-macos --output /work/native-project/project.kseed

compiler.elf compile /work/runner.kotoba --target aarch64-linux \
  --output /work/native-project/linked.elf --format packed \
  --payload /work/native-project/project.kseed
```

The runner source is `(ns runner (:export [main])) (defn main [] :i64 0)`.
The core target name `aarch64-macos` here emits a **native instruction
container**, not a macOS process or loader. The Linux packed stage links the
C-free runtime with those AArch64 instructions. The final artifact is a
static AArch64 Linux ELF with no interpreter. It executes linked native code;
no Kotoba interpreter, source rewriting, host crypto, JVM/Node or C loader
runs in either build stage or final execution.

Libraries are compiled against their checked export interfaces and imported
record schemas. Import stubs are patched to native clause addresses; one
runtime supplies shared value representations. The full gate exercises
vector and record arguments/returns across those imports. The initial 204-assertion result/fuel matched its source-unity baseline; the
current expanded gate is recorded in the follow-on receipt.

Negative controls refuse a mismatched source digest (E6015) and a private
function import (E6004), without emitting a container. All inputs, compiler,
container and final ELF are pinned in
[the historical receipt](evidence/awai81-native-linked-20261024/receipt.json) and
[the current receipt](evidence/awai81-native-paris-20261024/receipt.json).

This qualifies this bounded closure's native module linkage on arm64 Linux.
It does not qualify the whole legacy EVM API, an entry ABI exporting complex
values to an external host, the direct Linux source-path CLI variant, x86,
resource/fuel envelopes, a package/release controller or production routes.
The whole remaining AWAI-81 acceptance matrix still applies.
