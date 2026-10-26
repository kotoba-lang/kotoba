# kotoba-vm — a Kototama actor-kernel implementation

**The IPLD actor invocation kernel for a Kotoba app-chain.**
[`Kototama`](https://github.com/kotoba-lang/kototama/blob/main/docs/kototama-virtual-machine.md)
owns the versioned VM contract, as the EVM specification does in its own
ecosystem. This repository implements one partial `core/v1` actor-kernel
profile with Filecoin's FVM shape (Machine / Call Manager / Kernel / syscalls /
invocation-local handles / message-local overlay); it is neither the complete
Kototama machine nor Filecoin compatibility by itself.

This repo is the missing execution plane behind `inga.state`'s `:invoke-fn` seam. Consensus does not import it. It is injected, the same way `codebase.actor` is.

> kotoba-vm names itself here because the short name does not tell you which VM.
> It is **not the whole** `kototama` specification, **not** `codebase.actor` (a pure function),
> **not** `io-filecoin` (a protocol client), **not** `kotoba-lang/machine`
> (hardware descriptors), and **not** the historical etzhayyim Rust Pregel crate
> of the same name.

The machine-readable [`kototama-profile.edn`](kototama-profile.edn) states the
current boundary without overclaiming it: partial `core/v1` (including a
pure data-i64 evaluator for Amu's canonical program envelope, with bounded
i64 arithmetic and nil/boolean/text/vector/map values), FVM
**shape-only**, and no current `evm/v1` or `fevm/v1` conformance. FVM, EVM or
FEVM compatibility is earned by pinning the external protocol versions and
passing the corresponding Kototama differential suites; architectural
resemblance is not sufficient.

The core profile now includes a bounded positive Datalog evaluator and the
closed five-origin eligibility join. Effect-bearing methods are gated before
their bodies run, including internal method calls, and the local message result
records each allowed method/effect/resource tuple. Facts receive provenance
from separate AMU/VM/Grant/policy/runtime input slots. A machine-level
`:authority-facts-fn` supplies those facts and must authenticate each source
and return deterministic, read-only results across replicas. Its request binds
the actor, caller, program CID, current actor-state CID, method, effect,
arguments, authority proof and call depth. Source authentication adapters,
Biscuit delegation verification and the complete
Kototama authority/receipt contract remain omissions, so this does not claim
complete `core/v1` conformance.

Amu's canonical `"effect" / "invoke-capability"` node now reaches a separate
machine `:effect-fn` port only when its exact capability is declared by the
current method and that method passed the five-origin gate. The port receives
the actor, authenticated caller field, code and state CIDs, method, effect,
arguments, proof and call depth. Hosts must authenticate the caller, reserve
any scoped use before external work, bound the provider, and return a portable
value; this VM does not supply those host guarantees or an effect receipt.
Missing ports and mismatched declarations fail closed. A real Amu-generated
capability artifact exercises this boundary in
`test/kotoba/vm/kototama_program_test.cljk`.

The v1 register-machine guest format below is this engine's artifact format,
not Kototama's universal program encoding. Wasm is not required to execute
this profile, and this repository does not claim macOS or Windows qualification
without host-specific conformance evidence.

## Shape (FIP-0030 analogue)

```
guest (canonical Kototama closed-expression i64 subset, this engine's v1
register machine, or a test-only host-fn)
  ↕ kotoba.vm syscalls
Kernel (handles, overlay)
  ↕
Call Manager (stack, fuel, revert)
  ↕
Machine apply-message
  ↕ externs: get-fn / put!   (io-ipld storage port)
inga.state :invoke-fn adapter (callee state only)
```

Takes F1 / F2 / F3 from ADR-2608038000. This implementation currently rejects
Expected Consensus, HAMT, MPT, EVM opcodes, FIL gas markets, PoRep/PoSt. Those
omissions are why its declaration does not claim `fvm-actor/v1`, `evm/v1` or
`fevm/v1` compatibility. Fuel exhaustion is a **value**, never a throw, and
never a Wasm `unreachable` trap.

## What a guest may do

IPLD: `open` / `read` / `write` / `link` / `stat`. Self: `root` / `set-state`. Nested: `actor/call` (depth cap 8). That is the whole surface.

Writes land in a message-local overlay. Success flushes through `:put!`. Revert drops the overlay. A nested call snapshots the overlay; child failure restores it (the caller's writes from before the call stay; the callee's do not). Handles are invocation-local.

The guest never sees `:get-fn` or `:put!`. A replica that disagrees on bytes under a CID throws `:ipld/cid-mismatch` — a storage fault, not an actor refusal.

## What this is not for

Do not put this kernel on the kotobase query / index hot path (ADR-2608610000). A prolly-tree transaction through an FVM-style host/guest boundary is the cost that decision measured. This kernel runs **committed messages**, not database reads.

Wasm is not the production guest. Compiler Wasm fuel traps; the production path is `.cljc`. A later `.kotoba` / wasm guest is additive behind the same syscalls.

## Code CID (v1)

```clojure
{"kotoba.vm/guest" 1
 "methods" {"inc" [["self" "s"] ["open" "s" "h"] …]}}
;; or, test seam only:
{"kotoba.vm/guest" 1
 "host" "counter"}
```

## Use

```clojure
(require '[kotoba.vm :as vm]
         '[ipld.core :as ipld])

(def store (vm/memory-store))
(def machine {:get-fn (:get-fn store) :put! (:put! store)})
(def code (vm/put-code! (:put! machine)
                        {"kotoba.vm/guest" 1
                         "methods" {"inc" [["self" "s"]
                                           ["open" "s" "h"]
                                           ["node" "h" "n"]
                                           ["get" "n" "count" "c"]
                                           ["inc" "c" "c"]
                                           ["put" "n" "count" "c" "n"]
                                           ["write-node" "n" "s"]
                                           ["set-state" "s"]
                                           ["return" "c"]]}}))
(def state (ipld/put-node! (:put! machine) {"count" 0}))

(vm/apply-message machine
  {:actors {"alice" {:code code :state state :nonce 0 :balance 0}}
   :from "bob" :to "alice" :method "inc" :args [] :fuel 10000})
;; => {:ok? true :actors {…} :receipt {:exit :ok :return 1 …}}

;; Thin adapter for inga.state — writes only the callee's record.
((vm/invoke-fn machine)
 {:address "alice" :caller "bob" :code code :state state
  :method "inc" :args [] :fuel 10000})
;; => {:state <cid>} or {:refused :fuel-exhausted|:no-code|…}
```

Cross-actor mutation needs `apply-message`. `invoke-fn` cannot write another actor's record; that is the consensus seam's invariant, not a VM limitation.

## Bind (inga injects this; neither repo imports the other)

A deployment constructs the machine. `kotoba-vm` does not depend on `inga`.
`inga` does not depend on `kotoba-vm`. Filecoin protocol clients
(`io-filecoin`, Lotus, builtin-actors, ref-fvm) are not in either graph.

```clojure
(require '[inga.state :as state]
         '[kotoba.vm :as vm])

(def store (vm/memory-store))
(def invoke (vm/invoke-fn {:get-fn (:get-fn store) :put! (:put! store)}))

(state/machine
 {:decode-block :ops
  :put! (:put! store)
  :get-fn (:get-fn store)
  :blind-fn pr-str
  :encrypt-fn identity
  :height-fn :height
  :invoke-fn invoke})
```

`test/kotoba/vm_inga_bind_test.cljk` is the proof: an `:actor-call` through
that machine advances only the callee's state CID. The production `:deps`
set remains `{io-ipld}`; a gate fails if Filecoin or inga arrive there.

## Test / lint

```bash
kbb -M:test
kbb -M:lint
```

The suite is written to fail if the claimed property is broken: determinism, fuel-as-value, IPLD roundtrip, cross-actor call, nested revert, store isolation, boundary accounting, the inga-shaped seam, CID-mismatch as throw, the inga bind, and a Filecoin-free production classpath.

## Explicit v2 execution

See [execution v2](docs/execution-v2.md) and [owner contract](spec/execution-v2.edn).
New target bindings, authority-issued invocation/leases and authenticated admission
are explicit APIs; existing v1 runtime defaults remain compatible.

## Experimental native EVM work

[AWAI-81's native candidate](docs/native-evm-status.md) contains a Paris frame
subset and a restricted signed ordered-message domain. It has source-unity
native gates; full `evm/v1`, canonical project linkage, durable finalization
and production integration remain unqualified. The existing implementation
profile and runtime selection are unchanged.
