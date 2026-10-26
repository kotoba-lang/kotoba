# AWAI-81 native Paris resource follow-on

These locks pin the checked Kotoba module closures for the 1,985-assertion
project gate, 33-assertion core resource gate, eight-row state boundary gate,
official full-state driver, live Ethereum durable domain, and process-level
durable store driver. The binaries were built by the measured Amu selfhost
compiler and executed as loaderless AArch64 Linux ELF artifacts in isolated
containers. `receipt.json` records their exact hashes and results.

`state-resource-input.txt.gz` contains the eight native rows: 4,096 storage
slots, 512 and 2,048 accounts, 65,536-byte code, and a serialized world above
the former 1 MiB limit, plus one-unit-over refusals for slots, accounts and
code. The five positive rows' account and storage roots were independently
regenerated with the included fixture-only Geth oracle source, its pinned
`go.mod`, and `geth-resource-input.json.gz`; all equal
`geth-resource-roots.json`. The oracle is not linked into the native product.

The receipt also pins the fixed-point Amu AArch64 runtime, the v39 native
project and full-state ELFs, ten selected official full-state cases, four
durable Ethereum replicas (34 assertions), and the process-crash durable
store gate (41 assertions). The selected official cases compare the stateRoot,
logs hash and gas for the exact manifest case. The full runner uses the same
v39 ELF but has its own separate all-case ledger.

The selected gates are evidence for a bounded candidate. The official
19,807-case Paris full-state result, the complete allocation and depth
envelope, and public runtime qualification remain open. The AArch64 static
string pool is 1 GiB in the pinned Amu candidate; the vector-item bound is
unchanged. Heavy CREATE and deep STATICCALL cases still require measured
results. Neither this Git branch nor a passing selected gate selects or
deploys the EVM.
