# kami-engine-multirotor

The multirotor **mass spiral**, and the refusal that comes out of it.

Zero-dep portable `.cljc` over `kami-engine-rotor`, `kami-engine-pack` and
`kami-engine-motor`. Run `kbb -M:dev:test`.

```clojure
(mc/check {:payload-kg 1.5 :endurance-min 20.0})
;; => feasible, 4.926 kg on 413 mm rotors, 558 W hover, 1.52 kg of battery

(mc/check {:payload-kg 1.5 :endurance-min 60.0})
;; => :mass-closure — no self-consistent mass exists. Not a hard design; an
;;    aircraft that does not exist on these cells.
```

## Why it is a spiral and not a sum

A car's mass enters through road load, so its spiral is gentle and nearly always
closes. On a rotorcraft **thrust equals weight**: every gram must be carried by
rotors that grow, turned by motors that grow, fed by a pack that grows, on
structure that is a fraction of the total. Loop gain is high and **a
specification that does not close is ordinary, not exotic.**

So the output is a verdict, not a mass:

| | |
|---|---|
| converged | here is the aircraft, broken down |
| diverged | no self-consistent mass exists — **this is the refusal** |

That refusal is why a proposer (an LLM, a catalogue, an optimistic engineer)
cannot quietly hand back a 2 kg drone that flies for three hours. It is the
design-side counterpart of a safety governor, the role
`vdesign.physics/close-mass` plays for cars.

## Two ways to fail, and they are not the same finding

The loop deliberately **does not consult the MTOW ceiling.** `Exceeds the 25 kg
class limit` and `no self-consistent mass exists` need different fixes, and
stopping the iteration at the ceiling reports the first as the second:

```
12 kg payload / 12 min  ->  CLOSES at 26.9 kg   :mtow-limit     (a real aircraft, wrong class)
1.5 kg payload / 60 min ->  DIVERGES            :mass-closure   (no aircraft, any class)
```

Raising the ceiling to 50 kg rescues the first and not the second. An early
version stopped the spiral at the ceiling and told an engineer to abandon a
design that merely needed a different class; a test now pins the distinction,
and reintroducing that stop reddens exactly that test.

## Gates

Independent; a design must pass all of them.

- `:mass-closure` — the spiral did not converge
- `:mtow-limit` — closed, but heavier than the class ceiling
- `:blade-stall` — `CT/σ` past the limit **at peak thrust**, not at hover
- `:pack-rate-hover` / `:pack-rate-peak` — C-rate past the cell's rating. The
  peak gate exists because the pack is sized by hover and then has to survive
  the climb: at a 2:1 thrust margin peak power is `2^1.5 = 2.83×` hover, so the
  peak C-rate is too. A hover-only calculation never sees it.

## Not modelled

Rotor-on-rotor interference, ground effect, wind and gust margin, centre of
gravity and packaging, cooling, structural loads beyond a mass fraction, and any
regulatory boundary other than the MTOW number the caller passes in. Sizing is
delegated to the three solvers; this library owns only the loop and the verdict.

## One structural result worth keeping

Rotor and motor mass grow as `m^1.5`, so the loop is **superlinear**: the same
duty can close for a light payload and not for a heavy one (0.1 kg for 38 min
closes; 1.5 kg for 38 min does not). A first guess that hover power is merely
linear in mass predicts that a duty closes for every payload or for none — the
model says otherwise, and a test pins it.

## The numbers moved once already

On 2026-08-30 motor mass stopped coming from `motor.solver` (a traction-motor
shear model, measured 40-53% **heavy** two orders of magnitude below the size it
was written for) and started coming from `motor.bldc`, fitted to five published
motors. The baseline aircraft lost 375 g, and **the feasible envelope grew**:
specifications this library used to report as non-existent now close. 14 kg for
12 minutes was a divergence example in the first version of the ADR; it closes
at 31.6 kg.

That is worth stating plainly, because a refusal is only as good as the sizing
underneath it. **This library refuses designs; the accuracy of the refusal is
the accuracy of the three solvers it calls.**
