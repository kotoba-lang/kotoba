# kami-engine-pack

Reduced-order lithium battery **pack** solver (`:rom-pack`) — cell specific
energy scaled to pack level, then derated for the discharge rate the aircraft
actually pulls. Registers on the same `cae.solver` contract as the rotor, motor
and aero solvers.

Zero-dep portable `.cljc`. Run `kbb -M:dev:test`.

## Why a solver and not a constant

`vdesign.powertrain` carries a fixed 175 Wh/kg pack figure. That is right for a
car — an EV cruises near 0.5C, where the rate terms are noise. A multirotor
hovers at 3-6C and climbs at 10C or more, and there two effects stop being
noise:

- **energy** — Peukert: delivered capacity falls as `(1/C)^(k-1)`
- **power** — internal resistance: pack voltage sags roughly linearly in C

Endurance works out to `t = DoD · E_nom^k · P^-k`, so **doubling the load leaves
`2^-1.03 = 0.4897` of the endurance, not `0.5`.** A constant-Wh/kg model returns
exactly `0.5` and is optimistic by that gap on every drone it sizes.

## The inverse is closed form

Rate derating depends on the pack size being solved for, which looks like it
needs iteration. It does not:

```
E_usable = E_nom · DoD · (E_nom/P)^(k-1) = DoD · E_nom^k / P^(k-1)
=>  E_nom = (E_required · P^(k-1) / DoD)^(1/k)
```

A test bisects on pack mass until the forward solve returns the target
endurance and confirms the closed form landed on the same pack, so the algebra
is checked against something other than itself.

## Chemistry is a trade, not a ranking

| kind | cell Wh/kg | max C | Peukert k | sag /C |
|---|---|---|---|---|
| `:lipo-highrate` | 180 | 45 | 1.03 | 0.008 |
| `:li-ion-power` | 200 | 15 | 1.04 | 0.006 |
| `:li-ion-energy` | 260 | 5 | 1.06 | 0.014 |
| `:lfp` | 160 | 10 | 1.05 | 0.009 |
| `:si-anode` | 400 | 5 | 1.08 | 0.018 |

High-rate chemistries trade energy for power; that trade is the whole reason
this is a table and not one number. **These are representative catalogue
figures, not measurements.** An unknown chemistry is refused rather than
silently defaulted — a wrong pack mass that looks like a right one is the
expensive failure here.

## Scope

Energy and rate. **Not** temperature, **not** cycle ageing, **not** state of
health, **not** cell balancing, **not** thermal runaway. A pack at -10 °C or at
500 cycles is a different pack and this solver does not know it.

## Reference point

1.0 kg of high-rate LiPo (147.6 Wh/kg at pack level, 85% DoD) carrying the 585 W
a 5 kg quadrotor pulls in hover — the figure `kami-engine-rotor` produces for
that airframe:

```
nominal      147.6 Wh      C-rate 3.96
rate derate  0.9595        usable 120.4 Wh
endurance    12.35 min     voltage under load 96.8% of nominal
```

12 minutes on a 1 kg pack is what a real 5 kg quadrotor does. Sizing the same
duty for 20 minutes returns a 1.597 kg pack — **not** the 1.62 kg that scaling
the 12.35-minute pack linearly would suggest, because the bigger pack also runs
at a gentler C-rate.
