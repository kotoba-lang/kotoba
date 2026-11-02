# fune image-manifest: draft native byte verification

This first component of [JUN-776](https://linear.app/kotobalabs/issue/JUN-776) verifies an OCI image **manifest envelope** against an explicit SHA-256 digest and checks a supplied config or layer blob against the descriptor in that same verified manifest. It accepts only schema 2, an OCI image manifest, OCI JSON config and 1–32 uncompressed OCI tar layer descriptors. The root contains `schemaVersion`, `mediaType`, `config` and `layers`; each descriptor contains `mediaType`, `digest` and `size`. Either may also have bounded string-to-string `annotations`, which are ignored for authorization and execution. Strict JSON rejects duplicate/escaped keys. Other fields and profiles are refused. See the [proposed profile](https://github.com/network-awai/network-awai-apex/pull/78); it is not yet an accepted compatibility specification.

`manifest-problem` returns `ok` only for this bounded manifest envelope. `config-bytes-problem` and `layer-bytes-problem` revalidate the manifest, then check the selected bytes' length, octet range and SHA-256. `layer-segments-problem` checks an already-present list of raw-byte chunks without flattening it to an integer vector. The caller must remove and validate transport framing before calling it. `config-policy-problem` first verifies the config bytes through that manifest and then checks the strict config profile below. `layer-archive-problem` verifies one complete layer's descriptor and then inspects a limited ustar profile. These functions do **not** fetch bytes, verify actual layer bytes as part of the config call, extract files, prevent filesystem races, create a rootfs, authorize a Cell, or start a container. The manifest unit test's `abc` layer bytes verify descriptor binding only and are not a tar archive. No entry point here is an image-execution admission decision.

The archive inspector admits ordinary ustar regular files and directories with ASCII paths, correct header checksums and bounded octal sizes. It refuses absolute paths, empty or dot path components, non-ASCII names, links, devices, PAX/GNU extensions, whiteout entries, invalid lengths and nonzero data after the two end blocks. Whiteouts and opaque directories need correct layer application before they can be admitted. Inspecting one tar is not a safe extraction plan: it does not resolve cross-layer collisions, apply metadata, enforce a total multi-layer quota, or ensure rootfs paths are safe at the time of file creation. The current vector-based interface materializes the entire layer; bounded streaming remains open.

The config policy requires `architecture`, `os`, `rootfs` and `config` at the top level and permits inert `created`, `history` and arm64 `variant=v8` metadata. It accepts only `linux` / `arm64` and a `rootfs` with exactly `type=layers` and `diff_ids` in the same order and number as the manifest. Because this manifest profile admits only **uncompressed** layers, each diffID must equal the corresponding layer descriptor digest. The process `config` admits only `Entrypoint`, `Cmd`, `Env` and `WorkingDir`; omitted or empty entrypoint uses `Cmd` directly, and the resulting executable path must be absolute. An omitted or empty working directory means `/`; an explicit nonempty one must be absolute. Environment entries use unique ASCII identifier names and `name=value` bytes. Strings cannot contain NUL; array counts and aggregate decoded bytes are bounded. Many otherwise valid OCI images, including images with other config fields, remain refused. No normalization, image-selected privilege or implicit shell/PATH lookup is authorized. The future executor must honor these values; path resolution and executable checks must happen inside the verified rootfs.

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
  sed '1,/\]))$/d;s@fune/manifest-problem@manifest-problem@g;s@fune/config-bytes-problem@config-bytes-problem@g;s@fune/layer-bytes-problem@layer-bytes-problem@g;s@fune/layer-segments-problem@layer-segments-problem@g' lib/kotoba.fune/test/fune/manifest_gate.kotoba
} > "$G/gate.kotoba"
podman run --rm --pull never --platform linux/arm64 --network none \
  -e KEXE_CAP_RESOURCES_35=/gate -v "$G:/gate" -w /gate docker.io/library/alpine:3 \
  sh -c './root.elf compile /gate/gate.kotoba --target aarch64-linux --output /gate/new-gate.elf --format static && chmod +x /gate/new-gate.elf && KEXE_STRUCTURED_REPORT=1 /gate/new-gate.elf'
```

The native result `1000` means the 35 named conditions in the gate returned their expected results; any other positive result is the first failed condition number. Fixture digests were independently generated with Python `hashlib` as static test data, not computed by the implementation under test. The control replaces the manifest hash comparison with `false` in a *temporary copy* of the composed source. Compiling and running that copy must report result `15` for the wrong-manifest-digest case. Disabling annotation validation reports result `28`. Neither control modifies the tracked component.

For the config test, use the same composition but change the namespace to `fune-config-gate`, append the body of `image_config.kotoba` after `image_manifest.kotoba` (replace `json/` and `manifest/config-bytes-problem` with the unqualified names), then append `test/fune/config_gate.kotoba` (replace `config/config-policy-problem` with the unqualified name). Compile to a fresh output with the same offline command. Result `1000` means all 33 config cases passed. In a temporary copy, replacing the diffID-count comparison with `false` produces result `8`; disabling duplicate environment-name checking produces result `14`. These controls do not prove the full input language or OCI interoperability.

For the layer gate, Python's standard `tarfile` independently stages fixture bytes and hashes, and the verdict is calculated by the native image. The test-only FS2 reader loads the staged manifest, config and tar files; it is not a production image loader.

```sh
python3 lib/kotoba.fune/test/fune/stage_layer_fixtures.py "$G/fixtures"
tar -tf "$G/fixtures/good.tar"       # independently inspect the positive archive
{
  printf '(ns fune-layer-gate (:export [main]))\n'
  sed '1,/\]))$/d' lib/gov.nist.sha2/kotoba/sha2/core.kotoba
  sed '1,/\]))$/d' lib/org.ietf.jcs/kotoba/jcs/reader.kotoba
  sed '1,/\]))$/d;s@json/@@g;s@sha/@@g' lib/kotoba.fune/kotoba/fune/image_manifest.kotoba
  sed '1,/\]))$/d;s@json/@@g;s@manifest/config-bytes-problem@config-bytes-problem@g' lib/kotoba.fune/kotoba/fune/image_config.kotoba
  sed '1,/\]))$/d;s@manifest/layer-bytes-problem@layer-bytes-problem@g' lib/kotoba.fune/kotoba/fune/layer_tar.kotoba
  sed '1,/\]))$/d;s@layer/layer-archive-problem@layer-archive-problem@g;s@config/config-policy-problem@config-policy-problem@g;s@manifest/manifest-problem@manifest-problem@g' lib/kotoba.fune/test/fune/layer_gate.kotoba
} > "$G/layer-gate.kotoba"
podman run --rm --pull never --platform linux/arm64 --network none \
  -e KEXE_CAP_RESOURCES_35=/gate -v "$G:/gate" -w /gate docker.io/library/alpine:3 \
  sh -c './root.elf compile /gate/layer-gate.kotoba --target aarch64-linux --output /gate/new-layer.elf --format static && chmod +x /gate/new-layer.elf && KEXE_STRUCTURED_REPORT=1 /gate/new-layer.elf'
```

Result `1000` means the 20 fixture conditions passed. Replacing the `..` component check with `false` in a temporary source copy produces result `5`. The positive archive's payload is sample data rather than an executable, and no layer is extracted or run by this gate. The additional unchanged OCI manifest fixture was exported by Podman from the already-cached `docker.io/library/alpine:3` ARM64 image (Alpine 3.24.3, manifest digest `sha256:3897cbb7d4a4a31a618b60d41e69e6dc3f8080d045172440721996ed4250bdac`); its annotations are accepted and its gzip layer is explicitly refused as unsupported. A second Podman export with `--uncompressed` produced manifest `sha256:0f1b6d241d7a58b1ed5843016248dbb42d6a8d94122e3186ccd263cd67c09971` and the original config `sha256:f7bbaec1bd0330a8dba26f03e05f421bb3c8b807bb41873df3c3b0c3d1083d8f`. The native gate accepts those exact metadata bytes, including Alpine's `PATH` and `/bin/sh` command. Neither metadata result proves that Alpine can be unpacked or run.

### Real layer feasibility probe

The optional `test/fune/large_layer_probe.kotoba` reads the exact 8,939,008-byte uncompressed Alpine layer with FS2's segmented reply, checks its full descriptor digest, and observes `fune/tar-type` for Alpine's first symlink. It then changes the final byte in memory and requires `fune/blob-digest`. On 2026-11-02 this returned `1000` on the ARM64 Linux VM; a temporary control disabling the blob digest comparison returned `4`. The independent system `tar -tvf` identified `bin/arch` as a symlink. Source was compiled using the same Amu root described above and an offline cached Alpine container.

To reproduce, export the locally cached image with `podman image save --uncompressed --format oci-dir` into a new task-owned workspace, confirm its uncompressed layer is exactly `sha256:a278e6f39431cd0ed74238a3d377893ad0d905d68b676bf9a65529080669756b`, and copy that blob to `$G/fixtures/alpine-uncompressed.layer`. Stage the tracked fixtures as above. Compose the SHA2, JSON reader, `image_manifest.kotoba`, `layer_tar.kotoba` and `large_layer_probe.kotoba` bodies using the same alias substitutions as the layer gate, compile to a fresh ELF and run offline with `/gate` granted. A changed cached image must not be silently substituted.

This is **not streaming**: the test-only reader materializes all segments into one `vector-i64` before hashing and inspecting, and the measured VM used approximately 155 MiB while active. The provider reads one open descriptor for this experiment, but production source locks, memory bounds, mutation/race handling, scoped filesystem admission and incremental hash/tar parsing remain unqualified. Symlink extraction, which Alpine needs, is not implemented. No layer was unpacked or run.

`test/fune/segmented_layer_probe.kotoba` is a second feasibility probe over the same pinned fixture. It validates the FS2 acknowledgement, strips it from the first reply chunk, checks the complete layer with `layer-segments-problem`, then changes one byte and requires a digest refusal. Its native ARM64 run reported `1000`; disabling the segment digest comparison produced `4`. One observed process memory sample was approximately 83 MiB, not a controlled benchmark or a peak-memory measurement. The existing FS2 provider still materializes the complete response and this test assumes its first segment contains the acknowledgement; neither streaming I/O nor production loader qualification is claimed.

The shared `sha2.core/sha256-segments-hex` reuses the existing SHA-256 compression logic and processes a list of `:bytes` values plus a skipped prefix, without a full `vector-i64` copy. It rejects invalid skip/aggregate lengths and caps input at 2,147,483,647 bytes. The ARM64 source-composed `sha_segments_gate.kotoba` covers 24 independent expected-value cases including empty chunks, prefix boundaries, SHA padding boundaries and 1 MiB input; result `1000` passed. Setting its encoded bit length to zero in a temporary control produced result `2`. The pre-existing SHA-224/SHA-256/HMAC native corpus also reported result `63`; project linking, x86 and full corpus/oracle qualification of the extension remain open. The SHA2 library's existing AGENTS.md and README describe the original eight-export surface; this new ninth export extends that surface and those documents have not been rewritten by this change.

Remaining work includes the byte-oriented filesystem and bounded streaming path, real OCI fixtures, broader config semantics, tar safety and whiteouts, integration with qualified source locks and native project linking, and Linux runtime enforcement. Do not use this partial component to launch untrusted images.
