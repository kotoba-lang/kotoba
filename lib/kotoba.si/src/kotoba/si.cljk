(ns kotoba.si
  "KAMI Signal Integrity — transmission line analysis, eye diagram
  generation, crosstalk analysis, and S-parameter extraction.

  Ported from the retired Rust `kami-si` crate
  (`orgs/kotoba-lang/kami-engine`, deleted-but-uncommitted working tree)
  into pure `.cljc`, per ADR-2607010000. Pure data + pure functions
  throughout; no network, no I/O, no GPU. See README for what was
  intentionally not ported.

  ## Shared vocabulary across `kotoba.si.*`

  * transmission-line parameters — a plain map with namespaced keys
    `:tline/z0-ohm` `:tline/delay-ps-per-mm` `:tline/loss-db-per-mm`
    `:tline/length-mm`, produced by
    `kotoba.si.transmission-line/calculate-z0`.
  * transmission-line geometry — a plain map with `:tline-type/kind`
    (`:microstrip` `:stripline` `:coplanar`) plus that kind's
    geometry fields, built by `kotoba.si.transmission-line/microstrip`
    / `stripline` / `coplanar`.

  ## Submodules

  * `kotoba.si.constants` — physical/empirical constants for the domain
    namespaces below, loaded from `resources/kotoba/si/constants.edn`.
  * `kotoba.si.math` — cross-platform (JVM/cljs) math primitives shared
    by the domain namespaces below.
  * `kotoba.si.transmission-line` — characteristic impedance,
    propagation delay, and loss for microstrip / stripline / coplanar
    waveguide geometry.
  * `kotoba.si.crosstalk` — near-end (backward/NEXT) and far-end
    (forward/FEXT) crosstalk coupling between adjacent transmission
    lines.
  * `kotoba.si.eye-diagram` — eye-diagram waveform sample generation and
    quality metrics (height, width, jitter, BER estimate) for serial
    link analysis.
  * `kotoba.si.s-param` — 2-port S-parameter summary metrics and
    Touchstone `.s2p` export.")
