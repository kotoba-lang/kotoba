# apn — operator quickstart

From a fresh clone to a provisioned, blocked, torn-down and re-provisioned
lightpath in about a minute. Every step below is also in
[`quickstart.cljk`](quickstart.cljk), which checks each result against what
this page says and exits 1 on any difference. Run that file to confirm this
page still matches the library.

## 0. Prerequisites

- `kbb` on `PATH` (the superproject's script host; no JVM needed).
- A clone of `kotoba-lang/apn`. Run every command from the repo root.

## 1. Run the portable suite

```sh
kbb --backend sci --classpath src:test test/run_portable.cljk
```

The tail should read:

```
Ran 27 tests containing 65 assertions.
0 failures, 0 errors.
```

`kbb -M:test` (the README's `## Test`) is the JVM-alias entry point and is
a separate run from this one.

## 2. Walk the lifecycle

```sh
kbb --backend sci --classpath src docs/quickstart.cljk
```

⚠ Keep your own scripts **inside the repo**. kbb reads `:deps` from the
nearest `nbb.edn` above the *script*. A copy under `/tmp` fails with
`Could not find namespace: kotoba.lang.coll` (a dependency of `apn.rwa`).

The script builds `tokyo-1 — nagoya-1 — osaka-1`. Each fibre carries only
DWDM channels `#{1 2}`:

```clojure
(-> (m/system)
    (m/add-node (m/node "tokyo-1" {}))
    (m/add-node (m/node "nagoya-1" {}))
    (m/add-node (m/node "osaka-1" {}))
    (m/add-link (m/link "tokyo-nagoya" "tokyo-1" "nagoya-1"
                        {:apn/distance-km 350.0 :apn/channels #{1 2}}))
    (m/add-link (m/link "nagoya-osaka" "nagoya-1" "osaka-1"
                        {:apn/distance-km 180.0 :apn/channels #{1 2}})))
```

It then prints one line per step:

| line | call | what it shows |
|---|---|---|
| `:grid [96 190.725]` | `grid/channels`, `grid/channel->frequency-thz` | 96 channels on the grid; channel 1 is 190.725 THz |
| `:valid? true` | `validate/valid?` | the topology is structurally sound |
| `:broken [{:apn/error :dangling-link-endpoint …}]` | `validate/validate` | a link to an undeclared node (`kyoto-1`) is reported, not thrown |
| `:assign {:apn/ok? true … :apn/wavelength 1}` | `rwa/assign` | RWA alone: a path and the lowest free channel; the topology is not changed |
| `:lp-1 … :wavelength 1` / `:lp-2 … :wavelength 2` | `provision/request` | each commit occupies its channel on every hop |
| `:lp-3 {… :apn/t :blocked :apn/reason :no-common-wavelength}` | `provision/request` | both channels are taken |
| `:blocked-mutates? true` | — | a blocked request returns the system unchanged |
| `:teardown {:apn/t :torn-down …}` | `provision/teardown` | lp-1 releases channel 1 on both hops |
| `:lp-3-retry … :wavelength 1` | `provision/request` | the freed channel is reused |
| `:dry-run [["a" :provisioned] ["b" :provisioned] ["c" :blocked]]` | `runner/dry-run` | the same three demands as one offline batch |

The last line must be:

```
quickstart: 11 checks, 0 mismatches
```

Any `MISMATCH expected …` line means the library and this page disagree,
and the script exits 1. `0 checks` also exits 1 (nothing ran).

## 3. Reading the results

- `:no-path`: the demand's endpoints are not connected.
- `:no-common-wavelength`: a path exists, but no single channel is free on
  every hop. Lightpaths never change wavelength along the way, so this is
  a real block and not a routing bug.
- `:same-node`: `src` and `dst` are the same node.
- The library does no I/O. A host applies `:apn/system'` and records
  `:apn/event`. `cloud-itonami-isic-6110` is the deployment that does both.
