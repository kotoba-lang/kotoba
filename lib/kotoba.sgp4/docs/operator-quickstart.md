# Operator quickstart

From nothing to a position you have a reason to trust.

Every command on this page was run against this repository at `7c8cf09` on
2026-08-30, and every output is transcribed from that run. Where a number
moves between runs — the ISS does not wait — that is said in place.

## What you need

`node` and `nbb`. Nothing else: the library itself has no dependencies, and
the operator script reaches only for node's own `fs` and `fetch`.

```
$ node --version
v26.7.0
$ nbb --version
nbb v1.5.212
```

`deps.edn` also carries a `:test` alias for the JVM. **This page does not
cover it** — it was not walked, so it is not claimed.

## 1. Check the tool before you trust it

```
$ npm test
Ran 27 tests, 4432 assertions passed, 0 failed, 0 errored.
OK
```

Those assertions are against `test/sgp4/golden.edn`, generated from the
python `sgp4` package — an independent port of Vallado's reference C++ that
shares no code with this one. Agreement with an outside oracle is the claim;
self-consistency is not.

### Make it go red before you believe the green

A suite nobody has watched fail says nothing. Two breakages, thirty seconds
each, both run 2026-08-30:

**Drop the transport term** from the velocity rotation in
`src/sgp4/frames.cljk` — delete the `omega-earth` corrections so the vector
becomes `[vxe vye vz]`:

```
Ran 27 tests, 4411 assertions passed, 21 failed, 0 errored.   (exit 1)

FAIL in (earth-rotation-is-in-the-velocity)
FAIL in (iss-subpoint-is-physically-plausible)
```

The failing tests are named for the invariant that broke, not for the
function that changed. That is the property worth checking for.

**Empty the fixture** — `echo "[]" > test/sgp4/golden.edn`:

```
Ran 27 tests, 4220 assertions passed, 0 failed, 6 errored.   (exit 1)

ERROR in (fixture-is-not-empty)
ERROR in (near-earth-matches-the-oracle)
```

This is the one to run. Every golden assertion lives inside a `doseq`, so a
fixture that failed to load would iterate nothing and report a pass. It
errors instead, because `sgp4.fixtures/slurp-fixture` throws on a truncated
file and `fixture-is-not-empty` puts a floor under the count.

`git checkout -- .` after each, and confirm you are back at 4432 passing
before you go on.

## 2. Ask where something is

```
$ kbb --backend sci --classpath src scripts/where_is.cljk 25544
object    ISS (ZARYA)  (NORAD 25544)
at        2026-08-30T23:30:26.196Z
lat/lon   12.4173  128.1512
altitude  418.7 km
speed     7.365 km/s
epoch age 0.48 d
```

`25544` is the NORAD catalog number; the element set is fetched from
CelesTrak at run time. Your latitude and longitude will differ — the ISS
crosses that much of the Earth in under a minute.

For a fixed instant, pass `--at`:

```
$ kbb --backend sci --classpath src scripts/where_is.cljk 25544 --at 2026-09-01T12:00:00Z
object    ISS (ZARYA)  (NORAD 25544)
at        2026-09-01T12:00:00.000Z
lat/lon   6.5457  126.9012
altitude  419.8 km
speed     7.364 km/s
epoch age 2.00 d   <- propagated far from epoch; refetch
```

Fixing the instant does not fix the answer: the element set is still
fetched now, and CelesTrak republishes it several times a day. Ask for the
same instant tomorrow and you get a slightly different — and better —
position, from a newer set with a smaller `epoch age`.

To work from element sets you hold rather than fetch — a whole CelesTrak
group, not just one object:

```
$ curl -sS --fail -o iss.tle 'https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=tle'
$ kbb --backend sci --classpath src scripts/where_is.cljk --file iss.tle
```

**`--fail` is not optional.** Without it, an error response is written into
the file and `curl` exits `0`:

```
$ curl -sS -o iss.tle '...CATNR=99999...' ; echo "exit=$?"
exit=0
$ cat iss.tle
No GP data found
```

Sixteen bytes of prose, in a file your pipeline now believes is an element
set. With `--fail`, `curl` exits non-zero and writes no file at all.
CelesTrak also returns `503` under repeated requests — measured while
writing this page — so a fetch that worked a minute ago is not a fetch that
works now. The tool refuses a poisoned file rather than parsing past it:

```
$ kbb --backend sci --classpath src scripts/where_is.cljk --file iss.tle ; echo "exit=$?"
REFUSED :tle/orphan-line -- line is neither a TLE line 1 nor followed by one
exit=1
```

## 3. Read the exit code, not just the text

The library returns refusals as values, because it is called in a loop over
thousands of objects. A command line must not, because a shell reads exit
status and a refusal that exits `0` is indistinguishable from an answer.

| exit | means | example |
|---|---|---|
| `0` | every element set produced a position | `where_is.cljs 25544` |
| `1` | at least one was **refused**, named on stderr | `where_is.cljs 41866` |
| `2` | the question could not be **asked** | `where_is.cljs 99999` |

`1` and `2` are kept apart on purpose. "We did not look" must not read as
"we looked and that orbit is unsupported" — those call for opposite actions.

A catalogue with one bad entry exits `1` even though the good entries
printed. Build one by appending a copy of `iss.tle` with its check digit
bumped:

```
$ python3 -c "
l = open('iss.tle').read().replace(chr(13),'').rstrip().split(chr(10))
l[1] = l[1][:-1] + str((int(l[1][-1]) + 1) % 10)
open('mixed.tle','w').write(open('iss.tle').read() + chr(10).join(l) + chr(10))"
$ kbb --backend sci --classpath src scripts/where_is.cljk --file mixed.tle >out 2>err ; echo "exit=$?"
exit=1

$ cat out
object    ISS (ZARYA)  (NORAD 25544)
at        2026-08-30T23:39:27.492Z
lat/lon   -14.9793  148.0013
altitude  424.7 km
speed     7.358 km/s
epoch age 0.49 d

$ cat err
REFUSED :tle/checksum-mismatch -- line 1: column 69 says 1, computed 0
```

Positions go to stdout and refusals to stderr, so `> positions.txt` keeps
them apart without losing either. Do not read anything into the order they
appear in a terminal: they are two streams, buffered separately, and which
line lands first varies between runs.

## What the refusals mean

| you see | what happened | what to do |
|---|---|---|
| `:sgp4/deep-space-unsupported` | period ≥ 225 min: GEO, Molniya, GNSS. Needs SDP4, which is not implemented here | use a deep-space propagator. Do **not** waive this — the near-Earth path would return a confident number drifting by hundreds of km within a day |
| `:tle/checksum-mismatch` | column 69 disagrees with the modulo-10 sum of the line | refetch. A bad check digit means the elements are suspect, not just the digit — do not hand-correct it |
| `:sgp4/decayed` | the propagator put the object below the surface | the element set is describing something that is no longer there |
| `celestrak: HTTP 404` | no GP data for that catalog number | decayed, never existed, or not in the public catalog. This is exit `2`, not `1` |
| `celestrak: HTTP 503` | CelesTrak is throttling | exit `2`. Measured repeatedly while writing this page. Wait and retry; a fetch that worked a minute ago is not a fetch that works now |
| `celestrak: fetch failed -- getaddrinfo ENOTFOUND` | no network | exit `2`. The cause is printed because `fetch failed` alone is not actionable |

## The largest term in your error budget is the epoch age

`epoch age` is printed on every answer rather than only when it is bad,
because nothing else in the output reveals it and it dominates everything
else. SGP4's own modelling error is small next to propagating a week-old
element set.

The set fetched for the run above was `0.48 d` old, so CelesTrak is
republishing at least daily; if yours comes back days old you are reading a
cached copy. Past one day the line carries a marker:

```
epoch age 2.00 d   <- propagated far from epoch; refetch
```

## The other trap: CelesTrak serves CRLF

A line-anchored edit does nothing, silently:

```
$ sed 's/ 9990$/ 9991/' iss.tle | diff - iss.tle && echo "NO CHANGE"
NO CHANGE
```

The `$` sits after the `\r`, so the pattern never matches — and `sed`
reports success either way. This bit while writing this page: a fixture
meant to be corrupted was not, and the test built on it passed without
testing anything. `sgp4.tle/parse-catalog` strips the `\r` itself, so the
library is unaffected; your shell pipeline is not.

## Where to look next

`README.md` covers what the answers mean: why the propagator runs on WGS-72
while the geodetic conversion runs on WGS-84 (that pairing is correct, and
using one ellipsoid for both would move the subpoint about 100 m), why the
parser works by column rather than by whitespace, and what polar motion
being unmodelled costs you.

`scripts/regenerate-golden.md` covers regenerating the fixtures, including
the two tolerances that must not be tightened and why.
