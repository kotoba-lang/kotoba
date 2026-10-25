# grant

**Who may do what, decided as pure data.** This repository is the capability
broker for the Kotoba stack: it normalises a manifest, resolves a policy,
admits or refuses a component, and returns a capability *specification*. It
never turns that specification into a runtime handle, never opens a socket,
and never executes anything.

It came out of [`kotoba-lang/aiueos`](https://github.com/kotoba-lang/aiueos)
on 2026-08-21 (root ADR-2608219500). Aiueos kept the machine; this kept the
decision.

```clojure
(require '[grant.broker :as broker]
         '[grant.policy :as policy]
         '[grant.manifest :as manifest])
```

## Lisp machine architecture

AiueOS is the OS for a modern Kotoba Lisp machine in development. Kototama
is its implementation-independent Lisp VM contract: closed S-expression
computation, IPLD state, bounded authority and content-addressed receipts.
Amu checks and compiles code; grant decides permission; runtime hosts and OS
mechanisms enforce the admitted boundary. Kototama also has hosted engines
and does not require AiueOS for every execution.

The [stack architecture](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-architecture.md) separates responsibility, source/library
and artifact dependencies. Its [composition contract](https://github.com/kotoba-lang/kotoba-lang/blob/main/lang/stack-architecture.edn) routes
to each owner's specification; it is not a new language or runtime semantics.
"Modern Lisp machine" describes the architectural direction. It does not
certify a complete integrated debugger, live system modification, full heap
image restore, selfhost compiler or physical-machine qualification.

## Why it is separate

`aiueos` named two things at once — the authority that decides which hand to
lend, and the operating system that lends it. Both were real and both were
growing, and measured at the split they were nearly the same size: about 6,400
lines of decision against about 6,100 lines of mechanism plus 7,000 lines of C
and assembly. One repository cannot be dependency-minimal and own a kernel.

The dependency direction is one-way and checkable: **aiueos depends on grant,
grant does not depend on aiueos.** At the split the require graph had zero
edges from the decision plane into the machine, so the cut needed no
rewriting to make it hold — it was already true and simply unstated.

## What is here

| Namespace | Decides |
|---|---|
| `grant.authority` | the Principal–Intent–Decision kernel: `:allow` / `:deny` / `:challenge` |
| `grant.causal-trust` | scoped evaluator claims → trust challenge → ordinary authority decision and secret-free receipt |
| `grant.broker` | grant/deny per component, the ADR-0004 admission gate, run-plan and run-receipt shaping |
| `grant.policy` | the policy reasoner: signers, forbidden effects, ABAC, surface conformance |
| `grant.contract` | the pure EDN contract every other namespace here validates against |
| `grant.manifest` | trust / limits / quota / schedule / topic defaults |
| `grant.graph` | the capability graph, boot order, dependency depth |
| `grant.surface` | the deployment-surface and provider registry |
| `grant.signing` | ed25519 manifest verification (verification only; key custody is not here) |
| `grant.publisher` `grant.update` `grant.ota` `grant.anchors` `grant.enroll` `grant.key-lifecycle` | the decision half of release, update, pairing and signer lifecycle |
| `grant.boot-admission` `grant.deployment-profile` `grant.native-effect` | may these artifacts boot, under which profile, with which effects |
| `grant.cloud` `grant.net` `grant.kagi-policy` | may this component reach that remote authority, that URL, that secret reference |
| `grant.audit` `grant.clock` `grant.cli` `grant.decide` `grant.component-abi` `grant.execution-decision` | the append-only record, trusted time, the CLI contract, and the bridges into all of it |
| `grant.runtime-class` (`kotoba/grant/runtime_class.kotoba`) | may this host run an app of runtime class wasm / container (see below) |

## Runtime class policy

`kotoba/grant/runtime_class.kotoba` is the first Kotoba source here
(JUN-288, network-awai-apex ADR 0010 §2.5). An itonami app declares one
runtime class: `wasm` or `container` (named fune). Owner 2026-10-22 "hako =
fune": a Linux OCI image is one class, and whether the node runs it as a
container (Linux) or a microVM (aiueos) is the node's choice, not a class.
Class codes are the tsukasa mask bits, `wasm = 1`, `container = 2`.

`class-verdict` takes the class name, the node's tsukasa declaration (a mask
`1..3`) and the host's allow mask (`0..3`, `0` allows nothing). It answers one
pinned literal, in this precedence: `grant/unknown-runtime-class`,
`grant/bad-runtime-class-declaration`, `grant/runtime-class-not-declared`,
`grant/bad-allow-mask`, `grant/runtime-class-not-granted`, else `grant/ok`.
`default-allow-mask` is `1`: by default only `wasm` runs, and `container`
needs the host's explicit allow. Digest and manifest checks are the
node agent's, not this module's.

It is written in the Amu selfhost seed subset, and its gate builds it with the
pinned selfhost root compiler (no Node.js, nbb, JVM or babashka):

```bash
AMU=../amu; G=$(mktemp -d)   # G must be under a path podman can mount
cp "$AMU/seed/bootstrap/aarch64-linux-static-root.elf" "$G/root.elf"
F=kotoba/grant/runtime_class.kotoba
end=$(grep -n 'test-precedence\]))' $F | cut -d: -f1)
{ echo '(ns grant-runtime-class-gate (:export [main]))'
  tail -n +$((end+1)) $F
  cat <<'EOF'
(defn main [] :i64
  (+ (if (test-class-codes) 1 0) (+ (if (test-masks) 2 0)
  (+ (if (test-default) 4 0) (+ (if (test-verdicts) 8 0)
  (if (test-precedence) 16 0))))))
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
`:result 31`; a mutated `test-default` gives `27`. Receipt:
`docs/evidence/runtime-class-selfhost-gate-20261022.edn`. The `.cljk`
namespaces and `kbb -M:test` below are unchanged and were not run.

## What is deliberately not here

- **No Wasm engine, and no engine dependency of any kind.** `aiueos.execute`
  and its Chicory dependency stayed with the machine. Deciding whether a
  component may run is not the same act as running it, and a decision plane
  behind an engine cannot be audited without one.
- **No credential parsing.** `grant.authority` accepts verified, data-only
  facts. Cookies, CACAO, Passkeys, JWTs and private keys are adapter concerns.
- **No key custody.** `grant.signing` verifies; it does not sign.
- **No hardware.** PCI, DMA, IRQ and MMIO are aiueos.

## One covering relation

`grant.authority` still accepts its stable `[action resource]` EDN contract,
but it now projects each value into an unambiguous `authority.scope` segment
and delegates covering to
[`kotoba-lang/authority`](https://github.com/kotoba-lang/authority). Exact
resources and the legacy `:*` resource wildcard therefore use the same partial
order as the rest of the fleet. EDN type tags come from `pr-str`; path-shaping
characters are escaped before a value becomes one segment, so prefix confusion
cannot be reintroduced by string coercion.

## Contract data keeps its `aiueos` vocabulary

The EDN under `resources/aiueos/` and every `:aiueos.policy/*`,
`:aiueos.broker/*` and `:aiueos/*` key is unchanged, and so are the classpath
paths that load them. Those keys are on the wire — `kototama`'s adapter, the
example manifests, and every stored decision read them. Renaming code is cheap
and renaming a vocabulary is not, so only the namespaces moved. The same call
was made when the pin registry became genpon and `:fleet/repos` stayed
(ADR-2608147300).

Some contract entries name files that live in the other repository:
`src/aiueos/vm.cljk`, `src/aiueos/pid1.cljk` and `src/aiueos/provider/cloud.cljk`
(under `:enforced-by`, `:read-at-boot-by` and `:consumed-by`), and
`cloud_contract.edn`'s `"kotoba-lang/aiueos: …"` strings
(`src/aiueos/provider/cloud.cljk`, `src/aiueos/cloud_live.cljk`,
`resources/aiueos/cloud_live.edn`). This repository cannot see that tree, so
nothing here checks them. The `"kotoba-lang/aiueos: …"` strings in
`cloud_contract.edn` are checked from the other side, by
`aiueos.cloud-contract-paths-test` against the grant revision aiueos pins; the
bare paths in the anchors and boot-admission contracts are checked by nothing,
which is why they are named here.

## Verify

```bash
kbb -M:test
```

291 tests, 918 assertions at the split.

Three tests stayed in `aiueos` because they reach into the machine:
`manifest_test` (needs `aiueos.execute`), `key_lifecycle_test` (needs
`aiueos.launcher`) and `deployment_profile_test` (needs
`aiueos.reproducibility`), plus `example_fixtures_test`, which reads the
`examples/` tree where each `.edn` is paired with the `.wat` it describes.
`grant.manifest`, `grant.key-lifecycle` and `grant.deployment-profile`
therefore ship here without an in-repository test.

## License

Apache-2.0.

## Target-neutral and distributed stack architecture

Intersects requested, delegated and policy authority and returns decisions. Does not execute effects or depend on an OS/engine. Neutral descriptors and authority semantics are separate from target import binding; the current abi dependency remains until a compatible component migration. Placement, CID possession and successful replication never mint permission.

See the [owner integration guide and dependency direction](docs/stack-architecture.md),
[composition metadata](spec/stack-integration.edn), and
[whole-stack refactor procedure](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-refactor-procedure.md).
The direction is adopted; runtime contract migration and qualification remain
explicit, separately verified work. Tier labels are responsibility axes, not
a single dependency ranking.

## Execution contract entrypoints

Neutral descriptors are imported from `kotoba.core.execution` (core-contracts).
Component/WIT profiles and unchanged mixed v1 identity/lease codecs are imported
from `kotoba.abi.component` (abi). The old `kotoba.abi.contract` facade remains
readable for existing callers; new production imports select their owner.
The [integration contract](spec/execution-profile-integration.edn) records this
cutover. Existing v1 blocks/WIT/CIDs remain unchanged; v2 neutral identities
require a verified target binding and fresh CID/signature. This change does not
enable v2 runtime admission or claim Q9/native qualification.

## Explicit v2 execution

See [execution v2](docs/execution-v2.md) and [owner contract](spec/execution-v2.edn).
New target bindings, authority-issued invocation/leases and authenticated admission
are explicit APIs; existing v1 runtime defaults remain compatible.
