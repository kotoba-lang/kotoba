# sgp4

**Where a satellite is, from the two lines the world publishes about it —
in portable `.cljc`, with no host in it.**

```clojure
(require '[sgp4.core :as sgp4] '[sgp4.frames :as frames] '[sgp4.time :as time])

(def sat
  (:sat (sgp4/initialize-tle
         "1 25544U 98067A   26237.66055538  .00007716  00000+0  14485-3 0  9993"
         "2 25544  51.6329 316.2335 0007673  83.1052 277.0809 15.49625410582525")))

;; 2026-08-25T18:00:00Z, about two hours after that element set's epoch
(let [ms 1787680800000
      [jd f] (time/unix-ms->jd ms)]
  (frames/subpoint (sgp4/propagate-at sat ms) jd f))
;; => {:lat-deg 30.66187302008259
;;     :lon-deg -136.04427577282044
;;     :alt-km 416.5486495305322
;;     :speed-km-s 7.365674062080849
;;     :ecef-km [-4210.9278 -4060.1618 3446.1316]}
```

Zero dependencies. Runs on ClojureScript (browser, Worker, nbb) and on the
JVM from the same source, because a propagator is arithmetic and arithmetic
does not need a platform.

| namespace | what it is |
|---|---|
| `sgp4.tle` | the two-line element set, parsed **by column** |
| `sgp4.core` | SGP4 initialisation and propagation, WGS-72 |
| `sgp4.frames` | TEME → ECEF → geodetic, WGS-84 |
| `sgp4.time` | Julian dates and Greenwich Mean Sidereal Time |

## Verified against an independent oracle, not against itself

`test/sgp4/golden.edn` is generated from the python `sgp4` package 2.27 —
Brandon Rhodes' port of Vallado's reference C++ — which shares no code with
this implementation. The assertions are on *distance from the oracle's
answer*, so a self-consistent mistake cannot pass.

Measured over the fixture (Vallado verification cases plus operational
element sets fetched from CelesTrak on 2026-08-26):

| | worst disagreement |
|---|---|
| position, t=0 | 8.4 × 10⁻⁹ km (8 nanometres) |
| position, t=2880 min | 3.8 × 10⁻⁴ km (0.38 mm) |
| velocity | 3.9 × 10⁻⁷ km/s |

That is floating-point association order, not algorithm. The suite's
threshold is 1 m, three orders of magnitude above the measured worst case,
so it fails on a change of algorithm rather than on a compiler's choices.

Frame conversions are checked against **two** oracles: `gstime` from the same
python package, and pyproj 3.7.2 / PROJ 9.5.1 for `EPSG:4978 → EPSG:4979`.

`npm test` — 27 tests, 4432 assertions.

### The suite is checked for being able to go red

A gate nobody has watched fail is not a gate. Three deliberate breakages,
run 2026-08-26:

| break | result |
|---|---|
| flip the sign of the J₂ short-period term in `mrt` | exit 1, 35 failures |
| widen the deep-space cutoff so nothing is refused | exit 1, 6 failures, all in `deep-space-is-refused-not-approximated` |
| replace `golden.edn` with `[]` | **exit 1**, 6 errors — an empty fixture does not read as a pass |

The third is the one worth having. `sgp4.fixtures/slurp-fixture` throws on a
truncated file and `fixture-is-not-empty` puts a floor under the count,
because every golden assertion lives inside a `doseq`: without both, a
fixture that failed to load would iterate nothing and report success.

## Deep space is refused, not approximated

An element set whose orbital period is 225 minutes or more needs SDP4 —
lunar-solar periodics and resonance terms. **Those are not implemented
here**, and the near-Earth path is not run in their place:

```clojure
(sgp4/initialize-tle
  "1 41866U 16071A   26237.66711072 -.00000094  00000+0  00000+0 0  9992"
  "2 41866   0.5042  84.9564 0001350 108.7145 275.7029  1.00273070 35807")
;; => {:ok? false
;;     :error :sgp4/deep-space-unsupported
;;     :detail "orbital period 1436 min >= 225 min: ..."}
```

Run through the near-Earth path, GOES-16 would come back with a position —
a wrong one, drifting by hundreds of kilometres inside a day — and nothing
about the answer would say so. **A refusal is a fact the caller can act on;
a confident wrong number is not.**

So this covers the low-Earth catalogue: the ISS, Starlink, the sun-synchronous
imagers, the NOAA and Sentinel birds. It does not cover GEO, Molniya or GNSS.
Which of those you are holding is visible in the return value.

## Errors are values, everywhere

Nothing here throws for an expected outcome. `{:ok? true ...}` or
`{:ok? false :error <keyword> :detail <string>}` — because these functions
are called in a loop over a catalogue of thousands, where a decayed satellite
and a malformed line are ordinary, not exceptional.

```clojure
(:failed (tle/parse-catalog (slurp "gp.php?GROUP=starlink")))
;; => [{:error :tle/checksum-mismatch :detail "line 1: column 69 says 3, computed 9" ...}]
```

`parse-catalog` always returns **both** `:ok` and `:failed`. A catalogue with
four bad entries must not be shaped like a clean one, and a caller that wants
to ignore the failures should have to say so.

## Why the parser is column-based

A TLE is a punched-card format, not a delimited one, and two of its fields
carry an assumed decimal point with a two-character exponent:

```
1 25544U 98067A   26237.66055538  .00007716  00000+0  14485-3 0  9993
                                             ^^^^^^^  ^^^^^^^
                                             nddot    BSTAR = 1.4485e-4
```

Split that on whitespace and hand the token to `parseFloat` and you get
`14485` — measured, not hypothetical. Not an error, a **number**, and one
that is 10⁸ times the true BSTAR. It flows into the drag term, moves the
satellite, and every downstream check still passes. So every field is taken
by its documented column range, and the parse refuses rather than guesses.

The modulo-10 check digit is verified by default (`:verify-checksum? false`
to waive it, deliberately). It earns its place: two of the fixture TLEs
were hand-transcribed while this was being written and the checksum caught
both. They were **dropped, not corrected** — a bad check digit means the
elements are suspect, not just column 69.

## Two ellipsoids, on purpose

SGP4 runs on **WGS-72** because that is the fit the published TLEs were
produced against; using WGS-84 there would be more modern and less correct.
`sgp4.frames` converts to geodetic on **WGS-84**, because that is the datum
every basemap and GNSS receiver uses. Mixing them is the correct pair, and
re-using WGS-72 for the second step would put the sub-satellite point about
100 m from where every map says it is.

Polar motion (TEME/PEF → ITRF) is deliberately not modelled: it is under
15 m, against a TLE's own kilometre of along-track error. That is a statement
about magnitudes — if you need metre-level ground truth, SGP4 is the wrong
propagator, not this the wrong rotation.

## Naming

`sgp4` is a **subject**-plane name (`manifest/repository-rules.edn`
`:plane-order`): SGP4 is not one vendor's product, it is the model the whole
catalogue is published against, so no origin prefix applies and no role
prefix does either. It is a reusable library and takes the bare name.

## Running it

[`docs/operator-quickstart.md`](docs/operator-quickstart.md) goes from an
empty directory to a position, with `scripts/where_is.cljk` as the entry
point:

```
$ kbb --backend sci --classpath src scripts/where_is.cljk 25544
object    ISS (ZARYA)  (NORAD 25544)
at        2026-08-30T23:37:22.447Z
lat/lon   -8.7062  143.2950
altitude  422.6 km
speed     7.360 km/s
epoch age 0.49 d
```

It exits `0` for an answer, `1` for a refusal and `2` when the question
could not be asked at all — because a shell reads exit status, and a
refusal that exits `0` is indistinguishable from an answer.

## Regenerating the fixtures

See [`scripts/regenerate-golden.md`](scripts/regenerate-golden.md), which
also records the two tolerances that must **not** be tightened and why.
