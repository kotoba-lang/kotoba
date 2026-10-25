(ns signal-integrity.ibis-adapter
  "Adapter deriving `signal-integrity.eye-diagram/generate-eye-data`
  input parameters from a real IBIS I/O buffer model
  (`kotoba-lang/org-ibis`'s `ibis.model`), closing the gap this repo's
  own README used to flag: IBIS models were `Related:` but \"not yet
  wired as a code dependency.\"

  ## What comes from the buffer model, and what doesn't

  Only two of `generate-eye-data`'s six parameters are properties of the
  *driver buffer itself*, and can be derived from an IBIS `[Model]`:

  * `:amplitude-mv` — the driver's static output swing, read off the
    `:pullup`/`:pulldown` V-I table voltage range (`model->amplitude-mv`).
  * `:rise-time-ps` — the driver's edge speed, from the `[Ramp]`
    section's dV/dt (`model->rise-time-ps`).

  The remaining four — `:bit-rate-gbps` `:noise-rms-mv` `:jitter-rms-ps`
  `:num-bits` — are **link-level** parameters: the protocol's data rate,
  the channel/receiver noise budget, the timing budget's jitter, and how
  many bits to simulate. None of that is encoded in an IBIS `[Model]`
  section (a buffer model doesn't know what channel or receiver it will
  be driving, or what bit pattern length a caller wants to simulate), so
  `model->eye-params`/`eye-data-from-ibis` never invent defaults for
  them — callers must always supply them via `overrides`."
  (:require [ibis.model :as ibis-model]
            [signal-integrity.eye-diagram :as eye-diagram]))

(defn model->amplitude-mv
  "First-order static output-swing estimate, in mV peak-to-peak, from an
  IBIS `model`'s `:pullup`/`:pulldown` V-I tables: the voltage span
  between the highest-voltage point (the high-side/VDD-ish rail) and the
  lowest-voltage point (the low-side/GND-ish rail) across both tables.

  Simplification, stated plainly: real IBIS output swing depends on load
  conditions (the receiver termination, PCB trace impedance, `:r-load`)
  — the V-I curve is a *curve*, not a single output level, precisely
  because the actual operating point moves along it depending on what's
  connected. This function ignores load entirely and just reads the V-I
  table's total voltage range, i.e. the swing the buffer is *capable of*
  driving into a high-impedance/open circuit — not the actual loaded
  swing a real board would see. That's good enough for a first-pass eye
  estimate; a fuller derivation would intersect the V-I curve with the
  load line implied by `(:ramp model)`'s `:r-load`."
  [model]
  (let [voltages (map first (concat (:pullup model) (:pulldown model)))]
    (* 1000.0 (- (apply max voltages) (apply min voltages)))))

(defn model->rise-time-ps
  "Rise time, in ps, derived from an IBIS `model`'s `[Ramp]` dV/dt
  (`ibis.model/ramp-rate`) and its V-I-table-derived amplitude
  (`model->amplitude-mv`): the time to traverse the full output swing at
  the ramp's constant rate.

  Unit conversion (this is the detail that matters here):
  `ibis.model/ramp-rate`'s own docstring is explicit that it returns
  dV/dt in **volts per second** — i.e. `:dt` is assumed to already be in
  SI seconds, *not* nanoseconds — so:

      rise-time-s  = amplitude-v / dv-dt-v-per-s
      rise-time-ps = rise-time-s * 1.0e12

  (A naive ns-based scaling — treating `ramp-rate`'s result as V/ns and
  multiplying by `1000.0` — would be off by 9 orders of magnitude; the
  correct scalar for a V/s rate is `1.0e12`, not `1000.0`.)

  Returns nil (rather than throwing) when `(:ramp model)` is missing
  `:dv`/`:dt` or `:dt` is zero, mirroring `ibis.model/ramp-rate`'s own
  nil-on-missing-input contract."
  [model]
  (when-let [dv-dt-v-per-s (ibis-model/ramp-rate (:ramp model))]
    (let [amplitude-v (/ (model->amplitude-mv model) 1000.0)]
      (* (/ amplitude-v dv-dt-v-per-s) 1.0e12))))

(defn model->eye-params
  "Build a full parameter map for
  `signal-integrity.eye-diagram/generate-eye-data` from an IBIS `model`
  plus a caller-supplied `overrides` map.

  Only `:amplitude-mv` and `:rise-time-ps` are derived from `model`
  (buffer-level properties — see the namespace docstring for why the
  other four params can't be). `overrides` supplies the rest
  (`:bit-rate-gbps` `:noise-rms-mv` `:jitter-rms-ps` `:num-bits` —
  link-level, not buffer-level) and, on any key present in both,
  `overrides` wins — so a caller can also override the IBIS-derived
  `:amplitude-mv`/`:rise-time-ps` (e.g. to substitute a loaded-swing
  measurement for this namespace's static V-I estimate)."
  [model overrides]
  (merge {:amplitude-mv (model->amplitude-mv model)
          :rise-time-ps (model->rise-time-ps model)}
         overrides))

(defn eye-data-from-ibis
  "Convenience wrapper: `signal-integrity.eye-diagram/generate-eye-data`
  called with `(model->eye-params model overrides)`. See
  `model->eye-params` for the split between what `model` derives and
  what `overrides` must supply."
  [model overrides]
  (eye-diagram/generate-eye-data (model->eye-params model overrides)))
