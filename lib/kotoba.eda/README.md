# kotoba EDA

EDN-driven CLJC kernels for native kotoba EDA computation.

License: Apache-2.0.

kotoba-lang repositories are Apache-2.0 by default. If a repository is a fork,
port, or derivative of an upstream project such as browser-use, the upstream
repository license and required notices take precedence and must be preserved.

UI source: `kotoba.eda.site` is the canonical Hiccup + shadow-css data source
for the published docs page. `docs/index.html` is generated from that source
with `kbb -M:site`.

This repository does not claim to be a drop-in replacement for full OpenROAD,
OpenSTA, KLayout, Netgen, ngspice, or commercial ATE stacks. It provides a
portable kotoba-native execution model with deterministic evidence output:

- OpenSTA class: timing graph / PVT slack analysis
- OpenROAD class: grid routing and overflow checks
- KLayout class: rectangle width / spacing DRC
- Netgen class: connectivity LVS comparison
- ngspice class: linear DC modified nodal analysis
- ATE class: stuck-at fault coverage from vectors
- OSS report normalizer: OpenROAD/OpenSTA/KLayout/Magic/Netgen/ngspice/OpenLane
  reports to `:eda.signoff/*` evidence

All inputs and outputs are EDN maps. The kernels are pure CLJC so the same data
model can run in a browser, CI, or a host runner.

## Current coverage and maturity

Status date: 2026-06-30.

| Area | Coverage now | Maturity | Notes |
| --- | --- | --- | --- |
| EDN data contract | Flow jobs, OSS report manifests, signoff evidence rows | CI-verifiable | Stable enough for sample CI and workbench import. Schema still needs versioned compatibility tests before external users depend on it. |
| CLJC native kernels | Timing graph, grid routing, rectangle DRC, connectivity LVS, linear DC solve, stuck-at coverage | Prototype | These perform real deterministic calculations, but are intentionally small educational/pre-signoff kernels, not full tool replacements. |
| OSS report normalization | OpenSTA, OpenROAD, KLayout, Magic, Netgen, ngspice, OpenLane sample reports | CI-verifiable | Converts report text to `:eda.signoff/*` evidence and blocks negative slack, overflow, DRC/LVS failures, and ngspice fatal errors. |
| Browser/workbench integration | Links from kotoba EDA workbench, evidence import, sample signoff evidence | Demo-to-alpha | Good for reviewing evidence shape and handoff packets. Needs real project upload/auth/storage before production use. |
| CI reproducibility | `kbb -M:test` plus `kbb -M:oss-normalize docs/oss_manifest.edn` | CI-verifiable | Current CI proves parser/kernel behavior on fixtures. It does not yet install and execute OpenROAD/OpenSTA/KLayout/Netgen/ngspice. |
| Tapeout/manufacturing signoff | Evidence shape for PVT/DRC/LVS/SPICE/route/ATE | Not signoff-ready | Real tapeout still requires foundry PDK/rule decks, real OSS tool execution, waiver review, corner/PVT matrix, and human approval. |

Practical maturity level: **alpha evidence pipeline**. It is useful for building
repeatable CI evidence around OSS EDA outputs, but it is not a production
replacement for full OpenROAD/OpenSTA/KLayout/Netgen/ngspice runs or foundry
signoff.

## Run

```sh
kbb -M:test
kbb -M:site
kbb -M -e "(require '[kotoba.eda.core :as eda] '[clojure.edn :as edn]) (println (eda/run-flow (edn/read-string (slurp \"docs/sample_flow.edn\"))))"
kbb -M:oss-normalize docs/oss_manifest.edn
```

## Data contract

The main entry point is:

```clojure
(kotoba.eda.core/run-flow flow-edn)
```

Each flow contains `:eda.flow/jobs`. A job has:

- `:eda.job/id`
- `:eda.job/tool`
- `:eda.job/operation`
- tool-specific EDN payload

Each result is signoff evidence with `:eda.signoff/type`, `:eda.signoff/tool`,
`:eda.signoff/operation`, `:eda.signoff/status`, metrics, and deterministic CID.

## OSS verification mode

`kotoba.eda.oss-report` converts real OSS tool reports into the same evidence
shape as the CLJC kernels. This lets CI or a host runner execute OpenROAD,
OpenSTA, KLayout, Magic, Netgen, ngspice, or OpenLane, then store only stable
EDN evidence in the kotoba workbench.

Manifest example:

```edn
{:eda.oss/reports
 [{:eda.job/tool :sw/opensta
   :eda.job/operation :op/analyze-timing
   :eda.job/report "oss-reports/opensta.rpt"
   :eda.signoff/corner "tt_1p80v_25c"}]}
```

The normalizer is intentionally strict: negative slack, route overflow, DRC
violations, LVS mismatches, or ngspice fatal errors become failed evidence.

## SDC-driven timing jobs

`kotoba.eda.sdc-adapter` lets `analyze-timing` be driven by a real SDC
(Synopsys Design Constraints) script from
[`kotoba-lang/org-synopsys-sdc`](https://github.com/kotoba-lang/org-synopsys-sdc)
instead of requiring a hand-built `:eda.timing/clock-period-ns` number:

```clojure
(require '[kotoba.eda.sdc-adapter :as sdc-adapter])

(sdc-adapter/analyze-timing-from-sdc
  "create_clock -period 10.0 -name clk [get_ports clk]"
  {:eda.job/tool :sw/opensta
   :eda.job/operation :op/analyze-timing
   :eda.timing/corners [{:corner/id :tt :corner/scale 1.0}]
   :eda.timing/nodes [:in :u1 :out]
   :eda.timing/edges [{:from :in :to :u1 :delay-ns 3.0}
                       {:from :u1 :to :out :delay-ns 3.0}]
   :eda.timing/endpoints [:out]})
```

It parses the script with `sdc.parser/parse-script`, takes the FIRST
`create_clock` command's `-period` value, and merges it in as
`:eda.timing/clock-period-ns`. This is intentionally minimal: only the
primary clock period crosses the wire today, org-synopsys-sdc's
`set_input_delay`/`set_output_delay`/`set_false_path`/`set_multicycle_path`
models are not yet consumed by any kernel here. A script with no
`create_clock` command raises a clear `ex-info` rather than silently
defaulting the period to zero. Same alpha, prototype-grade maturity as the
rest of this repo -- see the coverage table above.
