# org-oci-distribution

**An [OCI Distribution Spec](https://github.com/opencontainers/distribution-spec)
v1.1 server projected onto [kotobase](https://github.com/kotoba-lang/kotobase)**
— the same one-datom/document/block-plane pattern as
[`kotoba-lang/kotobase-protocols`](https://github.com/kotoba-lang/kotobase-protocols)
(s3/ipfs/atproto/git), scoped to its own repo per
[ADR-2607172210](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607172210-kotobase-protocol-layer-extension.edn)
in `com-junkawasaki/root`. Addressing contract: the Kotoba Resource
Protocol §16.2
(`90-docs/protocols/kotoba-resource-protocol.edn`,
[ADR-2607172200](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607172200-kotoba-resource-protocol-0.2-addendum.edn)).

## ORAS is NOT a second protocol — read this before adding one

**ORAS does not get its own implementation in this repo, and should
not get its own repo either.** ORAS's client is a convention over this
exact same OCI Distribution Spec v1.1 API — the same `/v2/...`
manifest/blob/referrers endpoints, used to distribute arbitrary
artifacts (Helm charts, SBOMs, WASM modules, arbitrary files) instead
of container images. There is no separate ORAS wire protocol to
implement: one server (this one) satisfies both OCI clients (`docker
pull`, `crane`, container runtimes) and ORAS clients (`oras push`/`oras
pull`) identically. This was confirmed and documented in
ADR-2607172210's Context and Rejected sections specifically so nobody
re-derives "maybe ORAS needs its own thing" from scratch later.

Every surface is a **pure cljc handler** over the injected
`kotobase.store/IStore` — the same seam that lets an app run standalone
on `kotobase.local/LocalStore` or against `kotobase.net`. No I/O, no
host JSON parser, no crypto library dependency (SHA-256 is computed via
`java.security.MessageDigest` on the JVM / `node:crypto` under
nbb/cljs — no third-party deps either way); deploy shells (Cloudflare
Worker, browser worker, fleet peer) own transport and bearer-token
authentication.

| Route | Method | Behavior |
|---|---|---|
| `/v2/` | GET | ping/version check — 200, empty body |
| `/v2/<name>/manifests/<reference>` | GET, HEAD | fetch manifest by tag or digest |
| `/v2/<name>/manifests/<reference>` | PUT | store manifest; digest computed + validated |
| `/v2/<name>/blobs/<digest>` | GET, HEAD | fetch blob by digest |
| `/v2/<name>/blobs/uploads/?digest=<d>` | POST | monolithic blob upload (full body, one request) |
| `/v2/<name>/tags/list` | GET | list tags (not digests) known for `<name>` |

`<name>` may contain `/` (e.g. `gftdcojp/kami-engine`), matching the
Docker/OCI repository-name convention.

```clojure
(require '[kotobase.local :as local]
         '[kotobase.protocols.oci :as oci])

(def ctx {:store (local/local-store) :apex "kotobase.net"})

(oci/handle ctx {:method :put :path "/v2/myorg/myapp/manifests/latest"
                 :headers {"authorization" "Bearer ..."
                           "content-type" "application/vnd.oci.image.manifest.v1+json"}
                 :body "{\"schemaVersion\":2}"})
;; => {:status 201 :headers {"docker-content-digest" "sha256:…" …} :body nil}

(oci/handle ctx {:method :get :path "/v2/myorg/myapp/manifests/latest"})
;; => {:status 200 … :body "{\"schemaVersion\":2}"}
```

## Scope guards (read before extending)

- **Chunked upload session flow is out of scope for v0.1.** Only
  monolithic upload (`POST .../blobs/uploads/?digest=<d>` with the
  full body in one request) is implemented — the multi-request
  `POST` (start session) → `PATCH` (chunks) → `PUT` (finalize) flow is
  a documented follow-up, mirroring `kotobase-protocols/s3.cljc`'s own
  explicit multipart-upload carve-out.
- **Bearer-token verification is deliberately NOT implemented.**
  `PUT` manifest and `POST` blob upload emit the real
  `WWW-Authenticate: Bearer realm="...",service="...",scope="..."`
  challenge shape when no `Authorization` header is present at all —
  but any non-empty header is accepted without checking a signature or
  claim. Real verification is the deploy shell's job, exactly as
  SigV4 verification lives outside `s3.cljc`, not inside it.
- **String bodies only (v0.1).** `kotobase.protocols.http`'s `:body`
  is an opaque string, matching `s3.cljc` exactly — this handler
  hashes and stores that string as-is. Real deployments will often
  push binary-shaped OCI layers; base64/binary-body handling is a
  follow-up in the shared `http.cljc` shape, not reinvented here.
- **Digests are real SHA-256, not the `hash.cljc` fingerprint
  convention.** KRP §16.2 is explicit that an OCI digest is Content
  identity (§3.3), a real CID-shaped hash — unlike the non-cryptographic
  FNV-1a fingerprints `kotobase-protocols/hash.cljc` uses for S3 ETags,
  which are explicitly documented as NOT CIDs. See
  `src/kotobase/protocols/oci/digest.cljk`.
- **No Referrers API** (`GET /v2/<name>/referrers/<digest>`) yet — not
  required for the v0.1 push/pull round trip; follow-up once a concrete
  ORAS/SBOM-discovery consumer needs it.
- **No manifest content validation.** Manifest JSON bytes are stored
  and digest-validated opaquely; `schemaVersion`/`mediaType`-specific
  referential integrity (e.g. that referenced config/layer blobs
  actually exist) and garbage collection of unreferenced blobs are not
  implemented.

## Develop / test

First-class runtime is **nbb/cljs** (repo-wide runtime priority):

```bash
git clone https://github.com/kotoba-lang/kotobase .deps/kotobase
kbb --backend sci --classpath "src:test:.deps/kotobase/src" bin/run_tests.cljk
```

The `:test` alias in `deps.edn` is the JVM **compat** suite only.

## Kotoba decisions

`kotoba/oci/itonami_artifact.kotoba` decides what an itonami app release must
look like in OCI (JUN-288; network-awai-apex ADR 0010 §2.2–§2.4):

- `index-problem`: a release is one image index
  (`application/vnd.oci.image.index.v1+json`) with artifactType
  `application/vnd.itonami.app.v1`.
- `class-annotation-problem`: the `org.itonami.runtime-class` annotation must
  equal the class the L5 manifest declares (`wasm` / `container`; container
  is named fune, and container vs microVM is the node's choice — owner
  2026-10-22 "hako = fune").
- `digest-problem`: only `sha256:` + 64 lowercase hex is admitted; another
  algorithm is `itonami/unsupported-digest`.
- `digest-cid` / `cid-digest` / `cid-codec`: a digest and the CIDv1 of the same
  bytes share one sha2-256 multihash (codec raw `0x55` or dag-cbor `0x71`,
  multibase base32). `cid-digest` takes only the canonical spelling.

It is written in the Amu selfhost seed subset, and its gate builds it with the
pinned selfhost root compiler (no Node.js, nbb, JVM or babashka):

```bash
AMU=../amu; G=$(mktemp -d)   # G must be under a path podman can mount
cp "$AMU/seed/bootstrap/aarch64-linux-static-root.elf" "$G/root.elf"
F=kotoba/oci/itonami_artifact.kotoba
end=$(grep -n 'test-round-trip\]))' $F | cut -d: -f1)
{ echo '(ns oci-itonami-artifact-gate (:export [main]))'
  tail -n +$((end+1)) $F
  cat <<'EOF'
(defn main [] :i64
  (+ (if (test-index) 1 0) (+ (if (test-classes) 2 0)
  (+ (if (test-digests) 4 0) (+ (if (test-digest-cid) 8 0)
  (if (test-round-trip) 16 0))))))
EOF
} > "$G/gate.kotoba"
podman run --rm --platform linux/arm64 --network none -e KEXE_CAP_RESOURCES_35="$G" \
  -v "$G:$G" -w "$G" docker.io/library/python:3.12-alpine sh -c \
  "./root.elf compile $G/gate.kotoba --target aarch64-linux --output $G/gate.elf --format static \
   && chmod +x gate.elf && KEXE_STRUCTURED_REPORT=1 ./gate.elf"
#   → {:ok true, :target :aarch64-linux, :format :static, ...}
#   → {:status :ok :result 31 ...}      (31 = all five test-* true)
```

Measured 2026-10-22 with amu main `f5b11a08` (root sha256 `8256bfd8…dc7`):
`:result 31`; a wrong expected CID gives `23`, admitting a non-canonical
CID gives `15`, and (after the two-class change) treating `"microvm"` as a
class gives `29`. The test vectors are sha256 of `""` and of `"itonami"`, with
CIDs computed independently. Receipt:
`docs/evidence/itonami-artifact-selfhost-gate-20261022.edn`. The `.cljk`
suite above is unchanged and was not run.

## License

Apache-2.0
