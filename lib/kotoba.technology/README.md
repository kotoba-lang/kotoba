# kotoba-technology

Technology registry for kotoba-lang.

This repository gives `cloud-itonami-*` open businesses a stable way to refer
to technical capabilities such as EDA, CFD, CAE, BPMN, DMN, identity,
telemetry, optimization and audit ledgers without coupling business blueprints
to one implementation repository.

## Contract

```clojure
(require '[kotoba.technology :as tech])

(tech/get-technology :cfd)
(tech/capability-map [:simulation/flow :audit/evidence])
(tech/stack [:cfd :cae :telemetry])
```

Each technology entry declares:

- `:id`
- `:name`
- `:layer`
- `:capabilities`
- `:repos`
- `:contracts`
- `:operational-risk`

## Included Technology Families

| ID | Purpose |
|---|---|
| `:eda` | electronic design automation and verification |
| `:cfd` | computational fluid dynamics and flow simulation |
| `:cae` | solver dispatch, simulation contracts and engineering evidence |
| `:bpmn` | executable business process models |
| `:dmn` | decision tables and policy gates |
| `:identity` | DID, authn, consent and operator identity |
| `:telemetry` | sensor, meter and event ingestion |
| `:audit-ledger` | append-only proof and evidence logs |
| `:optimization` | planning, routing, scheduling and allocation |
| `:forms` | intake and structured human data capture |

## Use From Business

`kotoba-lang/industry` maps ISIC-coded businesses to required technology IDs.
`cloud-itonami` reads that mapping to show what a business can actually run.

## Test

```bash
kbb -M:test
```
