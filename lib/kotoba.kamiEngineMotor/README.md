# kami-engine-motor

[![CI](https://github.com/kotoba-lang/kami-engine-motor/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/kami-engine-motor/actions/workflows/ci.yml)

Reduced-order traction-motor solver (`:rom-motor`) — air-gap shear sizing + loss-fraction efficiency → torque density, peak power, mass. A kami-emag magnetostatic FEA registers `:emag-fea` on the same contract.

Part of the clean-sheet vehicle-design / CAE stack (purpose-split shared libs).
Zero-dep portable `.cljc`. Run `kbb -M:test`.

## `motor.bldc` (`:rom-bldc`) — small motors, calibrated instead of extrapolated

`motor.solver` above is a traction motor. Applied to a multirotor it is being
asked about machines two orders of magnitude smaller than anything it was
written for, and it does not say so. Measured 2026-08-30 against T-MOTOR's own
published figures it is **40-53% HEAVY** at drone scale:

```
shaft 343 W  ->  traction model 115 g   calibrated  82 g   (+40%)
shaft 800 W  ->  traction model 267 g   calibrated 175 g   (+53%)
```

`motor.bldc` fits `mass_g = a * P_W^b` over five published motors
(MN2806/4006/5208/8012/8017, 46-453 g, 216-3180 W): **a = 0.374, b = 0.898,
R² = 0.979 in log space, worst residual 18.6%.** The fit is computed from the
table at call time, so adding a motor changes the answer and no constant can
drift away from the data it came from.

It reports `:extrapolated?` outside 216-3180 W rather than returning a number
that looks the same as an interpolated one, and carries `:worst-residual` so a
caller gets the error bar the data supports instead of invented confidence.

The power basis is the vendor's **180-second** rating — right for sizing to peak
thrust, wrong for continuous cruise. KV is not in the fit: mass tracks torque
more closely than power, and these datasheets do not state rpm at max power, so
the table's KV 100-400 spread is part of the residual above.

## `motor.envelope` (`:rom-motor-envelope`) — torque–speed envelope

`motor.solver` answers one point: torque at `:rpm-base`. `motor.envelope`
extends a sized motor result to every speed the drive visits — constant torque
up to base speed, ideal constant power above it (torque = T0·ω_base/ω, which
is only the P = T·ω identity). Real field weakening delivers less than this
ideal line and the amount is not modeled here: every above-base point carries
`:weakening-eff-unmodeled? true`. `:rpm-base` and `:rpm-max` are required from
the caller — rotor burst speed is a mechanical limit of the actual rotor and
nothing in this library measures it, so there is no default to invent. Claims
past `:rpm-max` refuse loudly.
## `motor.dcbus` (`:dcbus-balance`) — DC-bus power balance + buffer-battery SoC
Per-interval split of a demand series between the fuel cell (capped at
`:p-fc-max-kW`) and the buffer battery (capped by `:p-bat-dis-max-kW` /
`:p-bat-chg-max-kW`, confined to the `:soc-min`..`:soc-max` window), with a
uniform `:dt-h`. Unmet power and regen power that cannot be absorbed are
reported per interval and summed — never silently shifted onto another
component. The bus is idealized lossless; converter efficiency, battery
round-trip loss, and the fuel-cell partial-load curve are all declared
`:unmeasured` on the result. Registers `:dcbus-balance` on the shared
`cae.solver/solve` contract. Zero-dep portable `.cljc`; run with
`kbb -M:test`.
