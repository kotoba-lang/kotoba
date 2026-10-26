# Kototama Virtual Machine specification v1

Kototama is the virtual-machine contract of the Kotoba world. It occupies the
same architectural position that the EVM occupies for Ethereum and the FVM
occupies for Filecoin, but it is not defined by one opcode table or one engine.
It is a deterministic transition relation over closed Lisp data, IPLD state,
an admission predicate written in Kotoba Form, and content-addressed receipts.

The machine-readable authority for this document is
[`spec/kototama-vm-v1.edn`](../spec/kototama-vm-v1.edn). The keywords MUST,
MUST NOT, REQUIRED, SHOULD and MAY are normative.

## Stack composition and presentation

Kototama is the **Kotoba VM platform and normative execution contract**. Its
role is analogous to the EVM in the Ethereum ecosystem: the versioned machine
rules are shared by tools, artifacts and independent engines. This analogy
does not imply Ethereum bytecode, consensus or client compatibility. AiueOS is
one OS that can host Kototama and provide device mechanisms; other OSes may
host conforming engines without AiueOS. Grant owns permission decisions;
engines and OS mechanisms enforce them. This terminology changes no transition
or qualification rule.
See the [composition spec](https://github.com/kotoba-lang/kotoba-lang/blob/main/lang/stack-architecture.edn) and
[responsibility/dependency diagrams](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-architecture.md),
and [Kototama VM platform ADR](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kototama-vm-platform.md).

## Definition

Given a program, message, world state, authority context and resource budget,
Kototama produces an outcome, a successor state, events and a receipt:

```text
K |- <program, message, state, authority, budget>
  => <outcome, state', events, receipt>
```

The relation, not a particular interpreter, is the VM. A native engine, a Wasm
host, a JVM compatibility tender, an EVM bytecode adapter and an FVM-shaped
actor kernel can all implement Kototama. No implementation becomes the
definition merely because it shipped first. Kototama has no preferred engine;
each target/host/operation profile must publish its own conformance evidence.
The canonical program envelope is the engine-neutral artifact shape. Amu owns
compiler target selection and uses it as the default portable application
artifact; selecting a native, Wasm or Component target is an explicit
host-specific build choice.

Kototama does not define consensus, block production, fleet placement, grant
policy or compilation. Consensus decides which messages and roots are
committed. Amu proves what a program can attempt. A capability chain carries
delegated rights. The local authorizer decides whether those rights may be
exercised.
Kototama performs the resulting transition and records it.

## The four planes

Native programs inside one closed execution domain use typed calls and keep
context-owned values. Guest/host is a profile-specific embedding boundary,
not a required split between each library and its caller. A verified input is
decoded at admission and handed directly to the execution mechanism; canonical
encoding remains at artifact, wire, state and receipt boundaries. Native i64
provider bindings constrain the external operation, not internal record/list
helper signatures. Admission, per-effect grant checks/reservations, fuel,
arenas and supervisor limits remain enforced. See the shared
[native execution-domain decision](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-native-execution-domains.md).

### Reduction plane: Lisp as the machine language

The semantic program is a closed S-expression. Kotoba, Clojure and
ClojureScript may be source dialects, but their host runtimes are not part of
the VM. Macros run before admission, symbols are resolved before execution,
and closures are explicit pairs of a code CID and a bounded environment.

The canonical wire form uses tagged DAG-CBOR vectors. It preserves list
semantics without depending on a JVM reader or JavaScript object behaviour.
There is no host `eval`, reflection, class loading, ambient FFI or accidental
access to the host filesystem, clock, network, environment or randomness.

Clojure contributes the value model: immutable persistent values, structural
equality, lexical scope and transformation by value. Imperative operations
such as EVM storage writes are expressed as pure transitions of the
message-local state overlay.

### State plane: IPLD as memory

Programs, actor code, actor state, messages and receipts are content addressed.
Reads MUST verify bytes against their CID before decoding. Writes MUST
canonicalize bytes before deriving the CID.

Every message executes against an overlay. Successful execution atomically
replaces the world root. Revert, refusal and resource exhaustion discard the
overlay. A nested call snapshots the current overlay; child failure restores
that snapshot without erasing earlier caller writes.

CARv2 packages and transports blocks. Possession of a CAR is never authority
to execute the blocks it contains.

### Logic plane: a closed predicate in Kotoba Form

The admission core is written in Kotoba Form and compiled by amu
([`src/kototama/admission.kotoba`](../src/kototama/admission.kotoba), entry
`eligible?`). It holds no Datalog engine and reads no Biscuit (root
ADR-2610082200). It has no effects, no user rules and no recursion, and it has
a DefCID like any other definition, so every qualified target runs the same
predicate.

A concrete capability exists only for the intersection:

```text
Amu static effect
  ∩ VM requested intent
  ∩ capability-chain delegated grant
  ∩ local policy allow
  ∩ runtime availability
  = invocation-local capability
```

Each origin is resolved by its own owner into a closed set of keys before
admission, and the core only tests membership in all of them:

```clojure
(and (catalog kind)                       ; the closed effect catalog
     (amu:requires definition kind)       ; amu's static effects
     (= (amu:world definition) runtime:world)
     (vm:requests actor kind resource)
     (grant:right actor kind resource)    ; meet over the capability chain
     (policy:allows actor kind resource)
     (runtime:available kind resource))
```

`grant:right` is the effective authority of a capability chain: IPLD blocks
whose bodies are S-expressions, folded as a meet by `kotoba-lang/authority`
(`dango`, root ADR-2609242100). A chain may supply `grant:right` only; it
MUST NOT impersonate `amu:*`, `vm:*`, `policy:*` or `runtime:*`. A missing
origin denies, because an empty set contains nothing. Only the local
authorizer may decide `allow`.

**The grant origin from a chain.** `eligible?` takes `grant:right` as a set
already resolved. `admit` resolves it from the presented delegation chain with
`authority.delegation/authorize` (kotoba-lang/authority, pure Kotoba): the
cap `[kind resource]` becomes a scope by `dango.chain/cap->scope`'s rule
(`"ns/name"` and `"scheme://path"` give `"ns://name/scheme/path"`), and the
request is covered when every link of the chain covers that scope, the chain
is live at `now`, and the holder is the leaf's. `admit` answers a reason code
so a receipt can name the origin that refused: 1 admitted; 2–7 the chain's own
reason; 10–16 the catalog, the amu effect, the world, the VM intent, the
policy, the runtime, or a cap that is not a scope. Static origins are checked
before the chain, the chain before policy and availability.

**Lifted out of the core.** Biscuit and UCAN are adapters at the Authn
boundary: a token in either format is transcoded into a capability chain
before anything here sees it. Datalog is a query library for logic Forms over
the datom index, and a policy authoring language whose output is the
`policy:allows` set. A rule Form may evaluate bounded Datalog only over facts
fixed by CID. None of them may decide admission.

**Call kinds.** A logic Form is called with `:invoke` and holds the
capabilities admitted above. A rule Form is called with `:validate`, holds no
capability, may only abort, reads only the action, its entry, dependencies
fetched by CID and the author's chain prefix, and answers `valid`, `invalid`
or `unresolved`. Unresolved (a CID not yet fetched) is not invalid.

The capability produced by a successful admission is unforgeable,
invocation-local and non-serializable. Raw bearer tokens (including Biscuit),
private keys and host handles MUST NOT appear in a CAR or receipt.

### Evidence plane: receipts as values

Every attempt leaves a receipt, including reverts and exhausted executions.
The receipt binds the machine specification, implementation, compatibility
profile, message and program CIDs, before/after state roots, outcome, fuel,
events and authority decision. Authority evidence names the Amu manifest CID,
grant identifiers, local policy, world and epoch—not the bearer token.

Content addressing proves which value is cited. It does not by itself prove
authorization, uniqueness, consensus acceptance or at-most-once execution.

## Message and call model

A canonical message contains `chain-id`, sender, recipient, method, parameters,
value, nonce, fuel limit and epoch. It may name a compatibility profile, parent
receipt and effect intent. Its identity is the CID of that canonical value.

The core call vocabulary includes actor calls, static calls, delegated calls
and creation. A profile may narrow or map these operations. Call depth, value
size, collection size, logic derivations and recursion are bounded. Resource
exhaustion is an ordinary outcome value and MUST NOT become an uncatchable host
trap.

Storage corruption is different from actor failure. CID mismatch is a host
integrity fault; an actor cannot catch it and reinterpret corrupt bytes as a
business-level refusal.

## Compatibility profiles

“EVM compatible” and “FVM compatible” are incomplete claims. A Kototama
implementation MUST name a profile version, compatibility level, pinned
external protocol version and evidence suite.

### `core/v1`

The canonical Kotoba profile executes closed S-expressions over IPLD state with a
closed admission predicate in Kotoba Form and deterministic receipts. It requires no JVM,
Wasm engine, EVM bytecode or Filecoin protocol dependency.

### `fvm-actor/v1`

This profile exposes the FVM-shaped actor contract: actor addresses, numeric
methods, IPLD blockstore access, actor state roots, nested send, exit codes,
gas accounting and message-local overlay/revert. It MUST pin an FVM network
version, actor ABI and gas schedule.

It does not import Filecoin consensus, storage proofs or a FIL market into
Kototama. An implementation can conform at the message, actor-ABI or state
level and MUST state which levels it actually passes.

### `evm/v1`

This profile projects the EVM into Kototama values and transitions. It pins a
chain specification, hardfork, gas schedule and precompile set. It specifies
U256 modular arithmetic, a 1024-item stack, byte-addressed volatile memory,
separate code, 20-byte addresses, calldata and returndata, account
code/storage/nonces/balances, CALL/STATICCALL/DELEGATECALL,
CREATE/CREATE2, RETURN/REVERT, logs and Keccak-256.

Compatibility has four cumulative, separately reportable levels:

1. **message** — transactions and contract ABI values round-trip.
2. **semantic** — result, state delta, logs and gas match the pinned EVM.
3. **bytecode** — valid bytecode for that EVM version can execute directly or
   through a proven semantics-preserving translation.
4. **state** — canonical receipts and trie roots match.

The Kototama core does not acquire bytecode compatibility merely by providing
EVM-like calls. Semantic, bytecode and state claims require differential tests
against the pinned reference vectors.

### `fevm/v1`

FEVM compatibility is the composition of `fvm-actor/v1` and `evm/v1`, plus
the boundary between them: delegated-address mapping, EVM calldata carried by
an FVM message, FVM exit-code to EVM status mapping, event/log mapping and the
system-actor boundary. The Filecoin network version, FEVM actor version,
Ethereum hardfork, gas mapping and precompile set MUST all be pinned.

The composition deliberately takes EVM message and bytecode compatibility,
not Ethereum gas or state-root identity. FEVM meters execution in Filecoin gas;
its gas costs are not 1:1 with Ethereum and it has documented behavioural
differences. An FEVM claim therefore MUST expose Ethereum JSON-RPC/tooling,
the Ethereum Address Manager/delegated-address mapping, its Filecoin gas
mapping and the divergence set. It MUST NOT relabel Filecoin gas as Ethereum
gas.

This lets the same Kotoba S-expression describe an actor-native call, an
EVM-shaped contract call or an FEVM call while preserving one content-addressed
state and receipt model. Compatibility lives in a profile and adapter; it does
not leak mutable EVM or Filecoin machinery into the language core.

## Implementation declaration

Every engine publishes a `:kototama.vm/implementation-profile-v1` value. It
lists implemented profiles and levels, pinned versions, passed suites and
omissions. Partial conformance is valid; silent omission is not.

The common conformance suite covers transition determinism, fuel, nested
overlay/revert, IPLD integrity, authority provenance and receipts. EVM and
FEVM claims additionally require content-addressed upstream vectors and
differential execution evidence.

This separation is intentional:

```text
Kototama                  semantic VM platform contract
  ├─ core/v1 engines      Kotoba/IPLD execution
  ├─ kotoba-vm            FVM-shaped actor-kernel implementation
  ├─ EVM adapter          evm/v1 implementation
  └─ FEVM adapter         fevm/v1 composition
```

Kototama is therefore one VM platform contract with several explicitly tested
profiles. `core/v1` defines the canonical Kotoba/IPLD machine; `evm/v1` and
`fvm-actor/v1` define compatibility projections. They may use separate
engines, and an engine's conformance to one profile does not establish
conformance to another. Kototama does not require one concrete engine to
replace all existing hosts.

## External compatibility authorities

Kototama profiles are projections onto versioned external authorities, not
forked copies of them:

- Ethereum execution behaviour is pinned to the
  [Ethereum execution specifications](https://github.com/ethereum/execution-specs)
  and, where formal notation is useful, a named version of the
  [Yellow Paper](https://ethereum.github.io/yellowpaper/paper.pdf).
- FVM architecture, actor calls, syscalls and IPLD behaviour are pinned to
  [FIP-0030](https://github.com/filecoin-project/FIPs/blob/master/FIPS/fip-0030.md)
  and its versioned conformance vectors.
- FEVM runtime integration and divergences are pinned to
  [FIP-0054](https://github.com/filecoin-project/FIPs/blob/master/FIPS/fip-0054.md),
  [FIP-0055](https://github.com/filecoin-project/FIPs/blob/master/FIPS/fip-0055.md)
  and the named Filecoin network version.

These references may evolve. A receipt and implementation declaration cite
the exact versions used for a run; the word “current” is never a compatibility
identifier.
