# tsukasa

司（つかさ）— to administer. **the itonami node ledger.** A node declares who
it is, how independent its failures are, and which lifecycle state it is in;
tsukasa keeps that record and refuses declarations that cannot be trusted.
That is all it does.

Naming: metaphor name (司), owner-approved 2026-10-21, registered in
`manifest/concept-vocabulary.edn` (com-junkawasaki/root). Candidates that were
rejected for sibling slots: `hako`（箱）and `fune`（船）— reserved for a future
container / microVM exec backing, not used here. Owner 2026-10-22: "hako =
fune" — one name, fune, for the Linux-image runtime class (`container`).

**This library decides nothing about where work runs.** Every function takes
small values and returns small values — codes, verdicts, counts. No sockets,
no processes, no scheduling, no keys.

## The boundary, stated against each neighbour

| layer | repo | owns | tsukasa must not |
|---|---|---|---|
| node ledger (this) | `tsukasa` | registration verdicts, declaration validation, lifecycle transitions, failure-domain audit | — |
| cluster control plane | `murakumo` | enrollment, heartbeat, job placement, `fleet ps` observation | observe or place |
| T6 placement | `sahai` | leases, budgets, checkpoints, epoch fencing | lease or schedule |
| VM contract | `kototama` | reduction, state, authority receipt | execute |
| machine / grants | `aiueos` | boot, devices, grant decisions | grant or attest |
| storage node mechanics | `kura-node` | shard movement, audits, payment | move bytes |

## What it refuses

The three declarations below have **no default**. A default is a lie about
somebody's reliability — the same rule `kura-node` and `kura-coordinator`
enforce for storage nodes, applied to itonami nodes generally.

1. **`failure-domain` is required.** A node that does not declare how
   independent its failures are cannot be counted toward any durability
   claim. The host passes the domain as a string; how independent the domains
   are is the *caller's* policy, tsukasa only refuses the undeclared.
2. **`availability` is required and closed.** Exactly `"always-on"` or
   `"intermittent"`. Omitted → refused, not defaulted. Unknown value → refused.

3. **`runtime-classes` is required and closed** (JUN-287, ADR-0244 §3). A mask of
   the dapp runtime classes the node declares it can accept: `wasm = 1`,
   `container = 2` (named fune); valid masks are `1..3`. Owner 2026-10-22
   "hako = fune": a Linux OCI image is one class, and whether the node runs it
   as a container (Linux, rootless podman) or a microVM (aiueos vmm) is the
   node's choice, not a separate class. The earlier `microvm = 4` bit is gone.
   `0` (nothing declared) → `"tsukasa/missing-runtime-classes"`; outside `1..3`
   → `"tsukasa/unknown-runtime-class"`. This is a *declaration*, not a grant:
   whether a class may run on the node is kekkai/grant's decision, and where
   work lands is murakumo/sahai's. `has-runtime-class?` answers membership
   for a mask and a class name (`"wasm"`, `"container"`); any other name,
   `"microvm"` included, is never held.

   **Breaking change:** `first-problem` and `register-verdict` take the mask
   as a final `:i64` argument. Precedence is id, did, failure-domain,
   availability, runtime-classes.

Refusals carry a **pinned reason literal** — `"tsukasa/missing-failure-domain"`
and friends, the full set in `first-problem`'s branches. Tests assert the
literal, not just "it failed": a refusal for the wrong reason is a different
bug.

## Lifecycle

State codes: `0 proposed  1 admitted  2 active  3 draining  4 retired`.

```text
proposed → admitted → active ⇄ draining → retired
                ↘───────────────────────→ retired
```

`retired` is terminal. An illegal transition is refused with
`"tsukasa/illegal-transition"`; an out-of-range code is
`"tsukasa/unknown-state"` — a typo is never counted as a policy hit. A
refused transition returns no new ledger.

## Layout

```text
kotoba/tsukasa/ledger_core.kotoba   the whole component: verdicts, state
                                    machine, audit (pure, zero effects)
kotoba/tsukasa/node_state.kotoba    a node's state derived from L1 and L2,
                                    one legal step at a time (below)
```

The former `.cljk` host wrapper and its kbb test suite were retired
2026-10-21 (JUN-197): the guest is the component, not a core beside one.

## Node state from L1 and L2

`kotoba/tsukasa/node_state.kotoba` derives a node's ledger state from the
management plane's two layers (com-junkawasaki/root ADR-2610222140 §1;
Linear JUN-315). No coordinator writes the ledger: every node gets the same
state from the same inputs.

- **From L1** (the operator's signed intent):
  - the digest of the declaration the operator admitted (`""` if none;
    admission is a human decision)
  - `cordoned`
  - `retired`
- **From L2** (the node's own signed observation):
  - `first-problem` of its declaration
  - the declaration's digest
  - `fresh`: murakumo's `fleet-placement` `fresh?`
  - `self-drain`
- `node-target` names where the inputs point: `node/retired`, `node/refused`,
  `node/proposed`, `node/declaration-changed` (the node must be admitted
  again), `node/cordoned`, `node/stale`, `node/self-drain` or `node/active`.
- `next-state` takes one step from the previous state toward the target:
  - A new node enters as proposed.
  - It reaches active only through admitted.
  - An active node that cannot be scheduled drains, and drains before it
    retires.
  - Retired is terminal.
  - A heartbeat that stops sends an active node to draining, and one that
    comes back returns it to active.
- `test-legal` checks every (previous state, target) pair against
  `ledger_core`'s `legal?`, so the derived history never makes an illegal
  transition.

Gate (no Node.js, nbb, JVM or babashka). It builds on `ledger_core`, so both
module bodies go into the unit:

```bash
AMU=../amu; G=$(mktemp -d)   # G must be under a path podman can mount
cp "$AMU/seed/bootstrap/aarch64-linux-static-root.elf" "$G/root.elf"
L=kotoba/tsukasa/ledger_core.kotoba; N=kotoba/tsukasa/node_state.kotoba
{ echo '(ns tsukasa-node-state-gate (:export [main]))'
  tail -n +$(( $(grep -n 'test-runtime-classes\]))' $L | cut -d: -f1) + 1 )) $L
  tail -n +$(( $(grep -n 'test-legal test-paths\]))' $N | cut -d: -f1) + 1 )) $N
  cat <<'EOF'
(defn main [] :i64
  (+ (if (test-target) 1 0) (+ (if (test-steps) 2 0)
  (+ (if (test-legal) 4 0) (if (test-paths) 8 0)))))
EOF
} > "$G/node-state.kotoba"
podman run --rm --platform linux/arm64 --network none -e KEXE_CAP_RESOURCES_35="$G" \
  -v "$G:$G" -w "$G" docker.io/library/python:3.12-alpine sh -c \
  "./root.elf compile $G/node-state.kotoba --target aarch64-linux --output $G/node-state.elf --format static \
   && chmod +x node-state.elf && KEXE_STRUCTURED_REPORT=1 ./node-state.elf"
#   → {:status :ok :result 15 ...}     (15 = all four test-* true)
```

Measured on 2026-10-22 with the root of amu `f5b11a08`: `:result 15`. Two
negative controls each break one rule, and each gives `1`, because
`test-steps`, `test-legal` and `test-paths` all drop:

- retiring an active node directly, without draining
- making a proposed node active without admitting it first

Receipt: `docs/evidence/node-state-selfhost-gate-20261022.edn`.

## Gates

**Selfhost gate (no Node.js, nbb, JVM or babashka).** The Amu selfhost
compiler — the pinned `seed/bootstrap/aarch64-linux-static-root.elf` of amu,
sha256 `8256bfd8…dc7` — compiles the component plus a seven-test driver into
an `aarch64-linux` static image and runs it on arm64 Linux:

```bash
AMU=../amu; G=$(mktemp -d)   # G must be under a path podman can mount
cp "$AMU/seed/bootstrap/aarch64-linux-static-root.elf" "$G/root.elf"
F=kotoba/tsukasa/ledger_core.kotoba
end=$(grep -n 'test-runtime-classes\]))' $F | cut -d: -f1)
{ echo '(ns tsukasa-gate (:export [main]))'
  tail -n +$((end+1)) $F
  cat <<'EOF'
(defn main [] :i64
  (+ (if (test-registration) 1 0) (+ (if (test-duplicates) 2 0)
  (+ (if (test-transitions) 4 0) (+ (if (test-retired-terminal) 8 0)
  (+ (if (test-ledger) 16 0) (+ (if (test-audit) 32 0)
  (if (test-runtime-classes) 64 0))))))))
EOF
} > "$G/gate.kotoba"
podman run --rm --platform linux/arm64 --network none -e KEXE_CAP_RESOURCES_35="$G" \
  -v "$G:$G" -w "$G" docker.io/library/python:3.12-alpine sh -c \
  "./root.elf compile $G/gate.kotoba --target aarch64-linux --output $G/gate.elf --format static \
   && chmod +x gate.elf && KEXE_STRUCTURED_REPORT=1 ./gate.elf"
#   → {:ok true, :target :aarch64-linux, :format :static, ...}
#   → {:status :ok :result 127 ...}     (127 = all seven test-* true)
```

The driver only replaces the `ns` form (the seed takes no docstring and
exports only `:i64` functions) and adds `main`. The container image is
used only for its `sh`; nothing in it runs the compiler or the tests.

Measured 2026-10-22 on amu main `f5b11a08`: `:result 127`, and a mutated
`test-runtime-classes` gives `:result 63` (receipt:
`docs/evidence/selfhost-gate-20261022.edn`).

The earlier gate was `amu check` / `amu test` through the Node-hosted
`bin/amu` (21/21 = 7 test-* × :jvm-kir :js :wasm, 2026-10-22). It is not
the required path any more and was not re-run for the selfhost rewrite.
The port constraints that shaped this file are recorded in
`docs/kotoba-port-boundary.md`.

## Not implemented (measured boundary, not a plan)

- No persistence: the ledger is a value. Where records live (kotobase, EDN
  files, git) is the caller's decision.
- No network: enrollment and heartbeat belong to murakumo; tsukasa never
  learns node state on its own. `node_state` derives the state from what the
  caller passes in, and it reads nothing itself.
- No DID verification: `did` is checked for shape (`did:key:` prefix) only.
  Signature verification is aiueos/kotoba-id territory.
- No placement arithmetic: survivability analysis beyond the failure-domain
  count in `audit` is kura's, not this repo's.
- Ledger slots are bounded at 8 (the code range the audit scans). A larger
  fleet is the host's sharding problem until a sized collection is admitted.
