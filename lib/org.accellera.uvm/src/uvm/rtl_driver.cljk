(ns uvm.rtl-driver
  "A genuine, if minimal, UVM-style driver/monitor pair that actually
  drives `kotoba-lang/rtl`'s event-driven simulator (`rtl.simulator`)
  -- the way a real `uvm_driver::run_phase` pulls transactions off its
  sequencer and applies them to the DUT pin it owns, while a paired
  `uvm_monitor::run_phase` samples a DUT pin and reports what it saw.
  `drive-signal-sequence` is the driver: it runs a UVM sequence (via
  `uvm.sequence/apply-sequence`) whose items are `{:time :value}`
  stimulus, threading the simulator's clock forward and committing
  each value at its scheduled time. `monitor-signal-response` is the
  monitor: it reads a simulator signal's history back out as the same
  `[{:time :value} ...]` shape a sequence is made of, so driver output
  and monitor observation round-trip through one common shape."
  (:require [rtl.simulator :as sim]
            [uvm.sequence :as useq]))

(defn drive-signal-sequence
  "Drive `signal-name` on `simulator` with `sequence-items` (a UVM-
  style stimulus sequence: a vector of `{:time t :value v}` maps,
  where `v` is an `rtl.simulator` value vector such as `[:one]`) --
  the way `uvm_driver::run_phase` pulls one transaction at a time off
  its sequencer (`get_next_item`/`item_done`) and applies it to the
  DUT pin it drives.

  Threads the simulator forward through `uvm.sequence/apply-sequence`:
  for each item, in order, the driver-fn first `rtl.simulator/run`s
  the simulator up to that item's `:time` (settling anything already
  queued up to then), then `rtl.simulator/set-input`s `signal-name` to
  the item's `:value` and immediately runs a zero-duration step so the
  change is committed to the signal's state/history before the next
  item is considered. `apply-sequence` itself has no accumulator
  parameter (it just maps a driver-fn over items), so the evolving
  simulator state is threaded through an atom closed over by the
  driver-fn -- the same pattern a real driver uses to hold onto its
  virtual interface handle across `get_next_item` calls.

  Returns the final simulator state after every item has been
  applied."
  [simulator signal-name sequence-items]
  (let [sim-atom (atom simulator)
        sq (useq/uvm-sequence signal-name sequence-items)
        driver-fn (fn [{:keys [time value] :as item}]
                    (let [delta (- time (:time @sim-atom))]
                      (when (pos? delta)
                        (swap! sim-atom sim/run delta)))
                    (swap! sim-atom sim/set-input signal-name value)
                    (swap! sim-atom sim/run 0)
                    item)]
    (useq/apply-sequence sq driver-fn)
    @sim-atom))

(defn monitor-signal-response
  "Sample `signal-name`'s recorded history on `simulator` and report it
  as a UVM-style sequence-item vector, `[{:time t :value v} ...]` --
  the same shape `drive-signal-sequence` consumes, so a monitor's
  observation round-trips through the identical shape a sequence is
  made of (mirroring how a `uvm_monitor` packages what it samples off
  the bus into analysis-port transactions of the same transaction type
  the driver applied). Returns `[]` if `signal-name` was never
  registered/has no history."
  [simulator signal-name]
  (mapv #(select-keys % [:time :value])
        (sim/get-signal-history simulator signal-name)))

(defn- ensure-signal-registered
  "Register `signal-name` on `simulator` (width 1) if it is not
  already registered; otherwise return `simulator` unchanged so an
  existing signal's state/history/width is preserved."
  [simulator signal-name]
  (if (sim/get-signal simulator signal-name)
    simulator
    (sim/register-signal simulator signal-name 1)))

(defn run-simple-testbench
  "A minimal, genuine UVM-style driver + monitor testbench loop against
  a real `rtl.simulator`: registers `driven-signal`/`watched-signal`
  on `simulator` if either is not already registered, drives
  `driven-signal` with `stimulus-items` via `drive-signal-sequence`,
  then runs the simulator forward `duration` more time units (settling
  any DUT response scheduled beyond the last stimulus item), and
  finally monitors both signals via `monitor-signal-response`.

  Returns `{:driven [...] :watched [...]}`, each a UVM-style
  sequence-item vector -- `:driven` is what the driver actually
  applied and `:watched` is what the monitor observed on the DUT's
  output pin, the standard driver/monitor pair that anchors a UVM
  testbench."
  [simulator driven-signal watched-signal stimulus-items duration]
  (let [sim0 (-> simulator
                 (ensure-signal-registered driven-signal)
                 (ensure-signal-registered watched-signal))
        driven-sim (drive-signal-sequence sim0 driven-signal stimulus-items)
        final-sim (sim/run driven-sim duration)]
    {:driven (monitor-signal-response final-sim driven-signal)
     :watched (monitor-signal-response final-sim watched-signal)}))
