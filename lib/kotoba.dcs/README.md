# dcs-clj (分散制御システム)

[![CI](https://github.com/kotoba-lang/dcs/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/dcs/actions/workflows/ci.yml)

Handle a **Distributed Control System** — plant/area hierarchy, I/O tags,
PID control loops, and ISA-18.2-style alarms — as plain EDN data, in
portable Clojure. Every core namespace is `.cljc` with **zero third-party
runtime deps**, so it runs on the JVM, ClojureScript, and Clojure-on-WASM
hosts (SCI). A control system config is data you can `assoc`, diff, store,
or generate; the library adds structural validation, a pure PID algorithm,
an ISA-18.2 alarm state machine, and a pure scan-cycle engine around it.

Sibling of the other reusable domain kernels in this org
([ddl](https://github.com/kotoba-lang/ddl),
[dmn](https://github.com/kotoba-lang/dmn),
[bpmn](https://github.com/kotoba-lang/bpmn)).

## Scope

This is a **basic process control (BPC)** model — regulatory control loops,
process alarms, and the tag registry they operate on. It is not a Safety
Instrumented System (SIS): interlocks/trips with independent SIL ratings are
a distinct, separately-certified concern and out of scope here. It does not
claim compatibility with any commercial DCS vendor's proprietary
configuration format; it is an open, EDN-first substrate for that same
domain.

## The model: a DCS system as EDN (`dcs.model`)

Areas, tags, loops and alarms are id-keyed maps for O(1) lookup:

```clojure
{:dcs/areas  {"area-1" {:dcs/id "area-1" :dcs/name "Reactor"}}
 :dcs/tags   {"TIC-101.PV" {:dcs/id "TIC-101.PV" :dcs/kind :ai
                            :dcs/units :degC :dcs/range [0 500]}}
 :dcs/loops  {"TIC-101" {:dcs/id "TIC-101" :dcs/pv-tag "TIC-101.PV"
                         :dcs/output-tag "TIC-101.OUT" :dcs/mode :auto
                         :dcs/setpoint 350.0
                         :dcs/tuning {:kp 2.0 :ki 0.1 :kd 0.0}
                         :dcs/output-limits [0.0 100.0]}}
 :dcs/alarms {"TIC-101.HI" {:dcs/id "TIC-101.HI" :dcs/tag "TIC-101.PV"
                            :dcs/type :hi :dcs/setpoint 420.0
                            :dcs/priority :high :dcs/deadband 2.0}}}
```

A threading-friendly builder:

```clojure
(require '[dcs.model :as m])

(-> (m/system)
    (m/add-area (m/area "area-1" {:name "Reactor"}))
    (m/add-tag  (m/tag "TIC-101.PV" :ai {:units :degC :range [0 500]}))
    (m/add-tag  (m/tag "TIC-101.OUT" :ao {:range [0.0 100.0]}))
    (m/add-loop (m/ctrl-loop "TIC-101" {:pv-tag "TIC-101.PV" :output-tag "TIC-101.OUT"
                                        :mode :auto :setpoint 350.0
                                        :tuning {:kp 2.0 :ki 0.1 :kd 0.0}
                                        :output-limits [0.0 100.0]}))
    (m/add-alarm (m/alarm "TIC-101.HI" {:tag "TIC-101.PV" :type :hi :setpoint 420.0
                                        :priority :high :deadband 2.0})))
```

## Validation (`dcs.validate`)

Structural checks — never throws, returns a vector of problems:

```clojure
(require '[dcs.validate :as v])

(v/validate system)
;; => [{:dcs/error :unknown-pv-tag :dcs/loop "TIC-101" :dcs/tag "TIC-101.PV"} ...]
(v/valid? system) ; => boolean
```

Checks: dangling pv-tag/output-tag references, wrong tag kind (pv-tag must
be `:ai`, output-tag must be `:ao`), setpoint/output-limits outside the
tag's `:dcs/range`, negative tuning gains, dangling alarm tag references,
alarm setpoint outside the tag's range, negative deadband, and
`:hi`/`:hi-hi` (or `:lo`/`:lo-lo`) threshold ordering across alarms sharing
a tag.

## PID (`dcs.pid`)

A pure, positional-form PID with clamped anti-windup and bumpless
auto/manual transfer — no I/O, no host loop:

```clojure
(require '[dcs.pid :as pid])

(pid/step {:kp 2.0 :ki 0.1 :kd 0.0} (pid/init-state) pv sp dt [0.0 100.0])
;; => {:dcs/output 42.3 :dcs/state' {...}}

;; at the :manual -> :auto edge, start the output where the operator left it:
(pid/transfer-to-auto tuning pv sp last-manual-output)
```

## Alarms (`dcs.alarm`)

An ISA-18.2-inspired state machine (`:normal -> :unacked -> :acked ->
:normal`, with a `:rtn-unacked` branch when the condition clears before
acknowledgment), plus deadband hysteresis on `:hi`/`:hi-hi`/`:lo`/`:lo-lo`:

```clojure
(require '[dcs.alarm :as alarm])

(alarm/step alarm-cfg value prior-state) ; => {:dcs/state' s :dcs/event e-or-nil}
(alarm/ack :unacked)                     ; => :acked
```

## Scan-cycle engine (`dcs.execute` + `dcs.ports`)

`dcs.ports` defines the host-injected `IFieldIO` protocol only (read/write a
tag by id); the host supplies the implementation (a real fieldbus driver,
an OPC UA client, a simulator). `dcs.execute/scan` is pure over that
protocol — it performs no I/O of its own:

```clojure
(require '[dcs.execute :as exec])

(exec/scan system state io dt)
;; => {:dcs/state' state' :dcs/events [{:dcs/alarm "TIC-101.HI" :dcs/from :normal :dcs/to :unacked}]}
```

Each scan advances every `:auto` loop's PID (writing its output tag) and
every alarm's state machine; `:manual` and `:cascade` loops are skipped
(their output/setpoint is driven externally).

## Dry-run runner (`dcs.runner`, JVM only)

A conservative, host-side runner for offline commissioning checks: validate
a system, then simulate N scan cycles entirely in memory against a
caller-supplied PV trajectory. No fieldbus, no network, no live process I/O.

```clojure
(require '[dcs.runner :as runner])

(runner/dry-run system
                 {:n-cycles 10 :dt 1.0
                  :initial-values {"TIC-101.PV" 300.0}
                  :pv-overrides [nil nil {"TIC-101.PV" 425.0} ...]})
;; => {:dcs/valid? true :dcs/problems [] :dcs/trace [{:dcs/cycle 0 :dcs/tags {...} :dcs/events [...]} ...]}
```

Returns immediately with `:dcs/valid? false` and no simulation if
`dcs.validate/validate` finds any structural problems.

## Protocol-simulation layer (`dcs.gpio` / `dcs.modbus` / `dcs.opcua` / `dcs.plc`)

**SIMULATOR ONLY.** Everything in this section binds to `127.0.0.1`
(loopback) by default and refuses anything else. There is no real GPIO
chip driver, no real serial port device (`/dev/tty*`), no real fieldbus,
and no code here is intended to ever be pointed at real field equipment.
`dcs.modbus`/`dcs.opcua` implement the *real wire-format/semantics* of
their protocols — a genuine, unmodified Modbus TCP or OPC-UA client tool
can connect and it behaves indistinguishably from real equipment *at the
protocol level* — but every byte on the other side of that wire is backed
entirely by software state (`dcs.ports/IFieldIO`), most concretely a
CFD-backed digital twin in this org's `cloud-itonami-hygiene-access`. This
mirrors every other simulator-boundary disclosure in this actor family.

Each namespace below implements/wraps the existing `dcs.ports/IFieldIO`
protocol, so any real or mock `IFieldIO` — including a real CFD-backed one
— can be exposed through any of them without protocol-specific code
leaking into the domain layer (`dcs.model`/`dcs.execute`/`dcs.pid`/
`dcs.alarm`/`dcs.validate` are all untouched by this layer).

### `dcs.gpio` — simulated GPIO addressing model (portable `.cljc`)

A thin, in-process pin-numbers/modes addressing model over the tag
registry — no real transport, no real chip driver:

```clojure
(require '[dcs.gpio :as gpio])

(def hdr (-> (gpio/header)
             (gpio/add-pin (gpio/pin-spec 0 :digital-out "ALARM.RELAY"))
             (gpio/add-pin (gpio/pin-spec 1 :digital-in  "START.CMD"))))

(gpio/digital-read hdr io 1)        ; => boolean, from IFieldIO
(gpio/digital-write! hdr io 0 true) ; => writes IFieldIO
```

Digital pins are boolean at the GPIO edge; analog pins pass the tag's
numeric value through unchanged. Directional (reading a `:digital-out`
pin, or writing a `:digital-in` one, throws — real GPIO is directional).

Status: **fully real for what it claims to be** — a pure addressing
abstraction, no wire protocol implied.

### `dcs.modbus` — real Modbus TCP server (JVM only, primary deliverable)

A REAL Modbus TCP wire server: MBAP header framing, function codes 03
(read holding registers) / 04 (read input registers) / 06 (write single
register) / 16 (write multiple registers). The wire protocol itself is
supplied by `com.digitalpetri.modbus` (Kevin Herron, EPL-2.0, the same
author as Eclipse Milo — a real, independently-authored, actively
maintained Modbus-for-Java library); `dcs.modbus` supplies only the
register↔tag mapping on top of it, not a reimplementation of MBAP framing.
Binds to `127.0.0.1:15020` by default — **not** the real Modbus default
502, so a collision with a genuine local Modbus service, or mistaking this
for production infrastructure, is structurally hard to do by accident.

```clojure
(require '[dcs.modbus :as modbus])

(def rm (-> (modbus/register-map)
            (modbus/add-input   (modbus/input-register   0 "COV.PV"  (modbus/scaled-int16 1000 false)))
            (modbus/add-holding (modbus/holding-register 0 "FAN.SP"  (modbus/scaled-int16 1    false) :read-write))
            (modbus/add-holding (modbus/holding-register 1 "ALARM.ACTIVE" modbus/bool16 :read-only))))

(def handle (modbus/start-server! io rm {:port 15020}))
;; ... a real Modbus TCP client (any language/tool) connects and reads/writes ...
(modbus/stop-server! handle)
```

Real Modbus registers are 16-bit words; this library's domain values are
floats/percentages, so every register carries an explicit `:dcs/encoding`.
The one shipped so far is `:scaled-int16`: `word = round(value * scale)`,
clamped to the representable range (signed −32768..32767 or unsigned
0..65535 per `:dcs/signed?`) and inverted on read — e.g. a CoV (coefficient
of variation, a small fraction like 0.032) at `scale 1000` reads back as
the integer `32`, the "value × 1000" convention real Modbus integrations
use for sub-unity process values on 16-bit registers. `bool16` (word 0/1)
covers digital/alarm-style registers. `:read-only` holding registers
answer reads but reject writes with a real Modbus ILLEGAL_FUNCTION
exception; unmapped addresses answer with a real ILLEGAL_DATA_ADDRESS
exception — not silent success either way.

Status: **fully real wire protocol.** `test/dcs/modbus_test.cljk` connects
with `com.digitalpetri.modbus`'s OWN `ModbusTcpClient` — a real,
independent client, not an internal function call — over a real loopback
TCP socket, and proves FC03/04/06/16 round-trip, atomic rejection of a
multi-register write that spans a read-only register, real
ILLEGAL_DATA_ADDRESS / ILLEGAL_FUNCTION exception responses, and that
every other function code (coils, mask-write, ...) still answers with a
real exception response via the library's own interface defaults, not a
hang or a silently-wrong success.

### `dcs.opcua` — real OPC-UA binary server (JVM only)

A real OPC-UA server built on Eclipse Milo (`sdk-server` 0.6.16,
EPL-2.0 — the reference-quality open-source Java OPC-UA stack; genuinely
attempted, genuinely working, not scoped down to a facade). Real UA-TCP
binary transport, real SecureChannel/Session establishment, anonymous
auth, SecurityPolicy `#None` (a legitimate, common "test server"
configuration — not a corner cut: it is how most vendor test tools and
Milo's own example server ship by default; `Basic256Sha256`/etc. would
need a real self-signed application certificate + PKI trust-list
lifecycle, meaningfully more moving parts for a loopback simulator with no
real client population to defend against). `dcs.model` tags are exposed as
real `UaVariableNode`s under a dedicated namespace, with real Read/Write
service dispatch backed by `dcs.ports/IFieldIO`.

```clojure
(require '[dcs.opcua :as opcua])

(def nm (-> (opcua/node-map)
            (opcua/add-node (opcua/node-spec "CoV"   "COV.PV" :double :read-only))
            (opcua/add-node (opcua/node-spec "FanSp" "FAN.SP" :double :read-write))))

(def handle (opcua/start-server! io nm {:port 15021}))
;; a real OPC-UA client connects to (opcua/endpoint-url handle) ...
(opcua/stop-server! handle)
```

Implementation note (documented in the namespace docstring at length,
because it's a genuinely useful lesson for anyone else hitting this):
Milo's commonly-documented convenience path for a custom address space,
`ManagedNamespaceWithLifecycle`, gates every hook that matters
(`getLifecycleManager`, `getNodeManager`, ...) behind `protected` — only a
real Java subclass can call those (`gen-class` + AOT compilation, or a
companion `.java` file; both meaningfully more machinery than one
reader-conditional-friendly `.clj` namespace, and out of step with this
repo's `nbb`/`.cljc`-first tooling posture). `dcs.opcua` instead implements
the `AddressSpaceFragment` SERVICE INTERFACE directly via `reify` — all
public, no protected-access wall — and registers it with `OpcUaServer`'s
`AddressSpaceManager`. (A first attempt registered a bare `UaNodeManager`
without a fragment/filter: nodes were verifiably present server-side
[`containsNode` true], but a real client's Read still came back
`Bad_NodeIdUnknown`, because attribute-service dispatch routes through
registered `AddressSpaceFragment`s, not raw `NodeManager` membership —
that dead end is what motivated the fragment-based rewrite.)

Scope, stated plainly: only the Value attribute is served on Read/Write
(others get a real `Bad_AttributeIdInvalid`); no subscriptions/
MonitoredItems (`onDataItemsCreated`/etc. are real no-ops — a client that
tries to subscribe gets real "nothing happens," not a silently-wrong
success); and root-down Browse discovery of these custom nodes from the
standard `ObjectsFolder` doesn't surface them (`AddressSpaceComposite`
dispatches Browse by asking each fragment's filter whether it claims the
*source* NodeId, and ours only claims its own namespace — the Organizes
reference we record is real, present in our own reference table, just not
reachable via that particular path). **Direct NodeId access — read/write a
NodeId a client already knows — is this simulator's supported and verified
path.**

Status: **real UA-TCP binary protocol**, verified against a real,
independent Eclipse Milo `OpcUaClient`:

```
real Milo OpcUaClient connects over real UA-TCP  -> PASS
real client reads CoV = 0.032 from live IFieldIO -> PASS
real client reads FanSp = 1500.0                 -> PASS
real client write FanSp -> Good status           -> PASS
write reflected in the SAME IFieldIO             -> PASS
write to read-only node -> real Bad_NotWritable  -> PASS
rejected write left CoV untouched                -> PASS
```

This verification is **not** part of `kbb -M:test` — a real, reproduced
conflict: Milo 0.6.16's client transport (`sdk-client`) needs
`com.digitalpetri.netty:netty-channel-fsm:0.9`; `com.digitalpetri.modbus:
modbus-tcp` (dcs.modbus's dependency, in `:test`'s classpath via the base
`:deps`) needs `netty-channel-fsm:1.0.0`. Both on one classpath throws a
real `AbstractMethodError` at OPC-UA connect time — an incompatibility
between two otherwise-unrelated digitalpetri-authored libraries, not a
design choice. Reproduce the real-client proof in an isolated classpath:

```sh
kbb -M:opcua-verify -m dcs.opcua-client-verify
```

`test/dcs/opcua_test.cljk` (part of the main `:test` suite) covers the
exact same request-dispatch code path in-process instead — real
`AttributeServices$ReadContext`/`WriteContext` objects, real
`AddressSpaceFragment`, real `AttributeFilter` chain, only the actual TCP
bytes out of scope there (those are what `:opcua-verify` proves).

### `dcs.plc` — persistent scan-cycle service (JVM only)

`dcs.execute/scan` already IS the scan-cycle engine that's the core of
what a PLC does. `dcs.plc` runs it as a persistent background service — a
`ScheduledExecutorService` ticking `scan` on a fixed period, forever, until
stopped — instead of the single offline pass `dcs.runner` does:

```clojure
(require '[dcs.plc :as plc])

(def handle (plc/start! system io {:dt 0.1}))
;; ... scan cycles keep running on their own schedule ...
@(:dcs/cycle-count handle)   ; => growing over time
(plc/stop! handle)
```

This is what makes the rest of this layer a simulated *PLC* rather than a
static data server: `dcs.modbus`'s server and `dcs.plc`'s scan service
share the SAME live `IFieldIO`/tag registry, so a real Modbus client
polling the server while the scan cycle runs sees values actually
changing, because the PID/alarm logic is actually executing on its own
schedule. `test/dcs/plc_test.cljk`'s
`live-scan-cycle-is-observable-through-a-real-modbus-client` test is the
concrete proof: it starts both, polls `OUT1` twice through a real Modbus
client with a real sleep in between, and asserts the two reads differ.

Status: **fully real** — a real JVM scheduled background thread, no
simulation-of-a-simulation.

## Why a shared library (org placement)

Per kotoba-lang's role/scope taxonomy, reusable domain models live in
`kotoba-lang`. dcs-clj carries no plant-specific configuration and no real
fieldbus/network bindings (those are host-injected via `dcs.ports`) — it is
the dependency, not a deployment.

## Test

```sh
kbb -M:test    # everything, including dcs.gpio/dcs.modbus/dcs.opcua/dcs.plc
kbb -M:lint
```

For the isolated real-OPC-UA-client wire proof (kept out of `:test` for a
real dependency-conflict reason — see "Protocol-simulation layer" above):

```sh
kbb -M:opcua-verify -m dcs.opcua-client-verify
```
