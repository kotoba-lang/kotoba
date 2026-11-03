# kami-engine-echem

[![CI](https://github.com/kotoba-lang/kami-engine-echem/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/kami-engine-echem/actions/workflows/ci.yml)

Reduced-order PEM fuel-cell solver (`:rom-fc`) — polarization curve → cell voltage, LHV efficiency, stack power → real H2 consumption. The right 'combustion' analog for an FCEV is electrochemistry. A kami-echem CFD registers `:pemfc-cfd`.

Part of the clean-sheet vehicle-design / CAE stack (purpose-split shared libs).
Zero-dep portable `.cljc`. Run `kbb -M:test`.

Duty-profile integration (`echem.profile` / `:rom-fc-profile`): resolves `echem.system/demand-point` at each net-bus-power sample of a duty cycle and trapezoid-integrates H2 mass and net energy — per-sample ROM efficiency instead of a caller-supplied scalar. Transients, thermal lag, purge/recirculation and DC/DC part-load stay declared `:unmeasured`.

The shared `cae.solver/solve` dispatch accepts `{:solver {:kind :rom-fc-profile}}` with the profile and system inputs on the case. In `:on-infeasible :skip` mode, only original adjacent intervals with two feasible endpoints contribute to the integral. `:integrated-duration-s`, `:profile-duration-s` and `:skipped-interval-indices` report coverage; isolated feasible samples contribute zero duration. DC/DC losses are included when solving for the requested bus power.
