# apn-clj (全光ネットワーク / All-Photonics Network)

[![CI](https://github.com/kotoba-lang/apn/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/apn/actions/workflows/ci.yml)

Handle an **All-Photonics Network (APN)** — photonic nodes (ROADM sites),
DWDM fibre links, and end-to-end **lightpaths** (single-wavelength optical
circuits that never leave the optical domain) — as plain EDN data, in
portable Clojure. Every core namespace is `.cljc` with **zero third-party
runtime deps**, so it runs on the JVM, ClojureScript, and Clojure-on-WASM
hosts (SCI). A network topology is data you can `assoc`, diff, store, or
generate; the library adds structural validation, a pure Routing and
Wavelength Assignment (RWA) solver, and a pure lightpath-provisioning
lifecycle around it.

Sibling of the other reusable domain kernels in this org
([dcs](https://github.com/kotoba-lang/dcs),
[ddl](https://github.com/kotoba-lang/ddl),
[dmn](https://github.com/kotoba-lang/dmn),
[bpmn](https://github.com/kotoba-lang/bpmn)).

## Scope

This is a **network-topology and RWA** model — nodes, DWDM fibre links, and
the routing/wavelength-assignment algorithm that turns a (source,
destination) demand into a committed lightpath. It is **not**:

- a physical-layer engineering tool (optical power budget, OSNR, amplifier
  placement) — that lives one layer down, in a photonic-device/link-budget
  model such as `noroshi` (etzhayyim's photonics-electronics-convergence
  comms-chip actor). `apn` starts where a link is already known to close
  optically and only cares about topology, spectrum occupancy, and routing.
- a vendor's control-plane implementation (no GMPLS/PCEP wire protocol, no
  NETCONF/gNMI device driver) — those are host-injected concerns outside
  this library, the same way `dcs.ports` keeps fieldbus I/O out of `dcs`.
- an IOWN/NTT-branded or NDA-derived artefact. "APN" here is the generic
  industry term for a wavelength-routed all-optical transport network (no
  O-E-O regeneration in the data path); this library models that general
  shape from first principles and open literature, not any vendor's
  proprietary architecture or specification text.

## The model: an APN topology as EDN (`apn.model`)

Nodes, links and lightpaths are id-keyed maps for O(1) lookup:

```clojure
{:apn/nodes {"tokyo-1" {:apn/id "tokyo-1" :apn/name "Tokyo POP 1" :apn/role :roadm}}
 :apn/links {"tokyo-osaka" {:apn/id "tokyo-osaka" :apn/a "tokyo-1" :apn/z "osaka-1"
                            :apn/distance-km 515.0
                            :apn/channels #{1 2 3 ... 96}   ; available DWDM channels
                            :apn/occupied {}}}               ; channel -> lightpath-id
 :apn/lightpaths {"lp-1" {:apn/id "lp-1" :apn/src "tokyo-1" :apn/dst "osaka-1"
                          :apn/path ["tokyo-osaka"]
                          :apn/wavelength 5
                          :apn/state :active}}}
```

**Wavelength continuity is enforced structurally, not by a validator rule.**
A lightpath has exactly *one* `:apn/wavelength` field for its entire
`:apn/path` — there is no per-hop wavelength field, so a
wavelength-converting circuit (which would require O-E-O regeneration at a
hop) is simply inexpressible in this model. That is what makes this an
*all-photonics* model rather than a generic WDM-with-regenerators one.

A threading-friendly builder:

```clojure
(require '[apn.model :as m] '[apn.grid :as grid])

(-> (m/system)
    (m/add-node (m/node "tokyo-1" {:apn/name "Tokyo POP 1"}))
    (m/add-node (m/node "osaka-1" {:apn/name "Osaka POP 1"}))
    (m/add-link (m/link "tokyo-osaka" "tokyo-1" "osaka-1"
                         {:apn/distance-km 515.0 :apn/channels (set (grid/channels))})))
```

## The DWDM grid (`apn.grid`)

The ITU-T G.694.1 fixed 50 GHz grid, anchored at 193.1 THz. Channel numbers
here are an arbitrary sequential 1..96 numbering for modeling purposes (not
a claim of conformance to any operator's exact channel plan):

```clojure
(require '[apn.grid :as grid])

(grid/channels)                 ;; => [1 2 ... 96]
(grid/channel->frequency-thz 1) ;; => 190.725 (lowest channel, C-band)
(grid/valid-channel? 50)        ;; => true
```

## Validation (`apn.validate`)

Structural checks — never throws, returns a vector of problems:

```clojure
(require '[apn.validate :as v])

(v/validate system)
;; => [{:apn/error :wavelength-clash :apn/link "tokyo-osaka" :apn/wavelength 5
;;      :apn/lightpaths ["lp-1" "lp-2"]} ...]
(v/valid? system) ; => boolean
```

Checks: dangling node references on a link (`:apn/a`/`:apn/z`), dangling
node/link references on a lightpath, a lightpath's `:apn/path` not actually
connecting `:apn/src` to `:apn/dst` hop-by-hop, a lightpath's
`:apn/wavelength` not being a member of every hop's `:apn/channels`, and two
active lightpaths claiming the same wavelength on the same link.

## Routing and Wavelength Assignment (`apn.rwa`)

Given a topology and a (src, dst) demand, find a path and a single
wavelength free on every hop of that path:

```clojure
(require '[apn.rwa :as rwa])

(rwa/assign system "tokyo-1" "osaka-1")
;; => {:apn/ok? true :apn/path ["tokyo-osaka"] :apn/wavelength 1}
;; or, if nothing free: {:apn/ok? false :apn/reason :no-common-wavelength}
;; or, if unreachable:  {:apn/ok? false :apn/reason :no-path}
```

Routing is a plain Dijkstra shortest path (by `:apn/distance-km`, falling
back to hop count when distance is absent) plus a small set of alternates
generated by excluding one link of the shortest path at a time — **this is
a single-link-deviation heuristic, not a full k-shortest-loopless-paths
algorithm (e.g. Yen's)**. It is honest, testable, and sufficient for
first-fit wavelength assignment over a handful of alternate routes; it does
not claim to find the globally optimal k-shortest path set. Wavelength
assignment is first-fit: the lowest-numbered channel free on every hop of
the first alternate that has one.

## Lightpath lifecycle (`apn.provision`)

Pure state-transition functions — request → RWA → commit, and teardown:

```clojure
(require '[apn.provision :as provision])

(provision/request system "lp-1" "tokyo-1" "osaka-1")
;; => {:apn/system' system' :apn/event {:apn/t :provisioned :apn/lightpath "lp-1" ...}}
;; or                       {:apn/event {:apn/t :blocked :apn/lightpath "lp-1" :apn/reason :no-common-wavelength}}

(provision/teardown system' "lp-1")
;; => {:apn/system' system'' :apn/event {:apn/t :torn-down :apn/lightpath "lp-1"}}
```

No I/O — a host applies the returned `:apn/system'` and reacts to
`:apn/event` (e.g. write it to an audit ledger, as `cloud-itonami-isic-6110`
does).

## Dry-run runner (`apn.runner`, JVM only)

A conservative, host-side runner for offline what-if planning: apply a
batch of demands against a reference topology entirely in memory.

```clojure
(require '[apn.runner :as runner])

(runner/dry-run system [{:apn/id "lp-1" :apn/src "tokyo-1" :apn/dst "osaka-1"}
                        {:apn/id "lp-2" :apn/src "tokyo-1" :apn/dst "osaka-1"}])
;; => {:apn/system' system'' :apn/trace [{:apn/t :provisioned ...} {:apn/t :provisioned ...}]}
```

## Why a shared library (org placement)

Per kotoba-lang's role/scope taxonomy, reusable domain models live in
`kotoba-lang`. apn-clj carries no operator-specific topology and no real
control-plane/device bindings (those would be host-injected, the same way
`dcs.ports` isolates fieldbus I/O from `dcs`) — it is the dependency, not a
deployment. `cloud-itonami-isic-6110` (Wired Telecommunications Network
Operations) is the deployment that wraps this library with an
LLM-drafted-proposal ⊣ governor actuation gate and an audit ledger.

## Test

```sh
kbb -M:test
```

The portable suite (no JVM) and a self-checking walkthrough:

```sh
kbb --backend sci --classpath src:test test/run_portable.cljk
kbb --backend sci --classpath src docs/quickstart.cljk
```

See [`docs/operator-quickstart.md`](docs/operator-quickstart.md).
