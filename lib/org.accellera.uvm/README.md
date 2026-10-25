# kotoba-lang/org-accellera-uvm

Zero-dep portable `.cljc` implementation of core UVM (Universal
Verification Methodology) concepts, published by Accellera Systems
Initiative (accellera.org). UVM is a SystemVerilog class library/
methodology for building reusable, layered testbenches. Part of the
kotoba-lang EDA standards-substrate reverse-domain naming initiative
(ADR-2607072500, `com-junkawasaki/root`).

| Namespace | Purpose |
|---|---|
| `uvm.component` | component-tree model + find-by-type tree walk |
| `uvm.sequence` | sequence/sequence-item model + apply-sequence driver execution |
| `uvm.phase` | the 9 standard UVM phases + a real top-down phasing engine (run-phases) |
| `uvm.factory` | uvm_factory-style type-override registry with create/override resolution |
| `uvm.sv-class` | UVM component/object types resolved against `org-ieee-systemverilog`'s real class model |
| `uvm.rtl-driver` | UVM-style driver/monitor pair that drives `kotoba-lang/rtl`'s simulator |

## Status

New — simplified but functionally real: component trees, phase
execution ordering, sequence-driving, and factory overrides all actually
execute (not just modeled as inert data). Not implemented: the full
SystemVerilog class-library surface (TLM ports/exports/analysis,
config_db, register abstraction layer).

## `uvm.sv-class` — UVM types are SystemVerilog classes

UVM is, in reality, a SystemVerilog class library: `uvm_object` and
`uvm_component` are ordinary SystemVerilog classes with single
inheritance (IEEE 1800 clause 8), not a parallel type system. `uvm.sv-class`
supplies `uvm-object-class`/`uvm-component-class` as
[`org-ieee-systemverilog`](https://github.com/kotoba-lang/org-ieee-systemverilog)
`systemverilog.class` maps (`uvm_component :extends "uvm_object"`, adding
the parent/children hierarchy and the build_phase/connect_phase/run_phase
method hooks), and `component->class-instance` resolves a `uvm.component`
runtime instance's `:class` (defaulting to `"uvm_component"`) against a
class-registry via `systemverilog.class/resolve-members` — so a concrete
component (e.g. a `"my_driver"` class extending `"uvm_component"`) gets
its full flattened field/method list, inherited build_phase/connect_phase
included, the same way `uvm_component`-derived SystemVerilog code
actually resolves overrides. UVM's runtime component tree is typed
against SystemVerilog's static class semantics, not inert `:type` keywords.

```clojure
(require '[uvm.sv-class :as uvm-sv]
         '[systemverilog.class :as sv-class]
         '[uvm.component :as component])

(def my-driver-class
  (sv-class/make-class "my_driver" "uvm_component"
                        [{:name "vif" :type "virtual_if"}]
                        [{:name "run_phase" :args ["phase"]}
                         {:name "drive_item" :args ["item"]}]))

(def registry (assoc (uvm-sv/base-class-registry) "my_driver" my-driver-class))
(def drv (assoc (component/component {:name "drv0" :type :driver}) :class "my_driver"))

(uvm-sv/component->class-instance drv registry)
;; => {:component {...} :resolved-class {:fields [...parent children vif...]
;;                                        :methods [...get_name build_phase
;;                                                  connect_phase run_phase
;;                                                  drive_item...]}}
```

## `uvm.rtl-driver` — driving a real simulator

A UVM testbench's whole point is applying stimulus to a DUT and
observing the response — `uvm.rtl-driver` does this for real against
[`kotoba-lang/rtl`](https://github.com/kotoba-lang/rtl)'s event-driven
`rtl.simulator`. `drive-signal-sequence` is the driver: it runs a UVM
sequence of `{:time :value}` items through `uvm.sequence/apply-sequence`,
threading the simulator's clock forward (`rtl.simulator/run`) and
committing each value (`rtl.simulator/set-input`) at its scheduled time.
`monitor-signal-response` is the paired monitor: it reads
`rtl.simulator/get-signal-history` back out as the same
`[{:time :value} ...]` sequence-item shape, so driver output and monitor
observation round-trip through one common shape. `run-simple-testbench`
wires the pair together end to end against one simulator instance —
a small but genuine UVM-style driver/monitor testbench loop.

```clojure
(require '[rtl.simulator :as sim]
         '[uvm.rtl-driver :as rtl-driver])

(def s0 (-> (sim/simulator)
            (sim/register-signal "din" 1)
            (sim/register-signal "dout" 1)
            (sim/schedule-event 15 "dout" [:one])))  ; canned DUT response

(rtl-driver/run-simple-testbench
 s0 "din" "dout"
 [{:time 0 :value [:one]} {:time 10 :value [:zero]}]
 20)
;; => {:driven [{:time 0 :value [:one]} {:time 10 :value [:zero]}]
;;     :watched [{:time 15 :value [:one]}]}
```

## Develop

```bash
kbb -M:test
```
