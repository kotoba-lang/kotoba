# hydrogen_electrolysis_efficiency

Kotoba deploy cell for the `hydrogen_electrolysis` actor.

The cell delegates deterministic simulation to:

- actor: `20-actors/hydrogen_electrolysis`
- engine: `40-engine/kami-engine/kami-hydrogen-electrolysis-sim`

It returns a kotoba payload containing ranked results, datom-style records, and a Kami scene spec.
