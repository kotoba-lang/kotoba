# fune image-manifest: draft native byte verification

This first component of [JUN-776](https://linear.app/kotobalabs/issue/JUN-776) verifies an OCI image **manifest envelope** against an explicit SHA-256 digest and checks a supplied config or layer blob against the descriptor in that same verified manifest. It accepts only schema 2, an OCI image manifest, OCI JSON config and 1–32 uncompressed OCI tar layer descriptors. The root must contain exactly `schemaVersion`, `mediaType`, `config` and `layers`; each descriptor must contain exactly `mediaType`, `digest` and `size`. Strict JSON rejects duplicate/escaped keys. Unknown fields and other profiles are refused. See the [proposed profile](https://github.com/network-awai/network-awai-apex/pull/78); it is not yet an accepted compatibility specification.

`manifest-problem` returns `ok` only for this bounded manifest envelope. `config-bytes-problem` and `layer-bytes-problem` revalidate the manifest, then check the selected bytes' length, octet range and SHA-256. `config-policy-problem` first verifies the config bytes through that manifest and then checks the strict config profile below. These functions do **not** fetch any bytes, verify actual layer bytes as part of the config call, parse tar, prevent filesystem races, create a rootfs, authorize a Cell, or start a container. In particular, the layer test bytes `abc` verify descriptor binding only and are not a tar archive. No entry point here is an image-execution admission decision.

The config policy accepts exactly `architecture`, `os`, `rootfs` and `config` at the top level; only `linux` / `arm64`; and a `rootfs` with exactly `type=layers` and `diff_ids` in the same order and number as the manifest. Because this manifest profile admits only **uncompressed** layers, each diffID must equal the corresponding layer descriptor digest. `config` must contain exactly `Entrypoint`, `Cmd`, `Env` and `WorkingDir`; entrypoint is a nonempty string array whose first element is absolute, command is a string array, and working directory is absolute. Strings cannot contain NUL; array counts and aggregate decoded bytes are bounded. Environment must currently be an empty array. This deliberately refuses many otherwise valid OCI images, including ordinary images with additional config fields or environment entries. No normalization, image-selected privilege or implicit shell/PATH lookup is authorized. Path resolution and executable checks must happen inside the verified rootfs later.

The component imports the existing `jcs.reader` and `sha2.core` rather than copying either implementation. The test below composes their source bodies only for a seed compiler feasibility test; it does **not** demonstrate the multi-module project linker or the production toolchain closure. It is a local test, not a CI gate.

## Local native feasibility test

Prerequisites: Linux ARM64 Podman VM, an already cached `docker.io/library/alpine:3`, and the Amu static ARM64 root. The example uses the workspace paths from JUN-776 and does not pull an image. Source and compiler revisions must be recorded when comparing results.

```sh
G=/Users/junkawasaki/github/workspaces/codex/jun776-manifest-gate
mkdir -p "$G"
cp /Users/junkawasaki/github/kotoba-lang/amu/seed/bootstrap/aarch64-linux-static-root.elf "$G/root.elf"
shasum -a 256 "$G/root.elf"
# From the repository root. Replace the temporary output name for a rerun.
{
  printf '(ns fune-manifest-gate (:export [main]))\n'
  sed '1,/\]))$/d' lib/gov.nist.sha2/kotoba/sha2/core.kotoba
  sed '1,/\]))$/d' lib/org.ietf.jcs/kotoba/jcs/reader.kotoba
  sed '1,/\]))$/d;s@json/@@g;s@sha/@@g' lib/kotoba.fune/kotoba/fune/image_manifest.kotoba
  sed '1,/\]))$/d;s@fune/manifest-problem@manifest-problem@g;s@fune/config-bytes-problem@config-bytes-problem@g;s@fune/layer-bytes-problem@layer-bytes-problem@g' lib/kotoba.fune/test/fune/manifest_gate.kotoba
} > "$G/gate.kotoba"
podman run --rm --pull never --platform linux/arm64 --network none \
  -e KEXE_CAP_RESOURCES_35=/gate -v "$G:/gate" -w /gate docker.io/library/alpine:3 \
  sh -c './root.elf compile /gate/gate.kotoba --target aarch64-linux --output /gate/new-gate.elf --format static && chmod +x /gate/new-gate.elf && KEXE_STRUCTURED_REPORT=1 /gate/new-gate.elf'
```

The native result `1000` means the 25 named conditions in the gate returned their expected results; any other positive result is the first failed condition number. Fixture digests were independently generated with Python `hashlib` as static test data, not computed by the implementation under test. The control replaces the manifest hash comparison with `false` in a *temporary copy* of the composed source. Compiling and running that copy must report result `15` for the wrong-manifest-digest case. It does not modify the tracked component.

For the config test, use the same composition but change the namespace to `fune-config-gate`, append the body of `image_config.kotoba` after `image_manifest.kotoba` (replace `json/` and `manifest/config-bytes-problem` with the unqualified names), then append `test/fune/config_gate.kotoba` (replace `config/config-policy-problem` with the unqualified name). Compile to a fresh output with the same offline command. Result `1000` means all 23 config cases passed. In a temporary copy, replacing the diffID-count comparison with `false` must produce result `8`. This control verifies the missing-diffID refusal can fail; it does not prove the full input language or OCI interoperability.

Remaining work includes the byte-oriented filesystem and bounded streaming path, real OCI fixtures, broader config semantics, tar safety and whiteouts, integration with qualified source locks and native project linking, and Linux runtime enforcement. Do not use this partial component to launch untrusted images.
