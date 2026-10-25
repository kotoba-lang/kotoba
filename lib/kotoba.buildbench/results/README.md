# Published runs

One JSON per host, named for the host. Each is a record of one machine on one
day, not a portable ceiling — which is why the filename carries the host and
the file carries the machine descriptor, its fingerprint, and the load
observed at the start and end of every size.

## Reading one

Start with `absoluteTimes.qualified`. If it is `false`, the milliseconds are
true observations of that run and nothing more; the host was too busy for them
to mean anything on your machine. The ordering is qualified separately, under
`scales[].ordering`, because the lanes are interleaved and a gap that survives
perfgate's separation test survives the host being busy.

Then check `lanes[].available` and every `scales[].lanes[].status` before
reading a number next to it. Four statuses are not measurements and none of
them is zero:

| status | meaning |
|---|---|
| `measured` | samples, and the artifact answered correctly |
| `unavailable` | the tool is absent, or present and unable to reach its target |
| `invalid` | it built something that is not the program; `error` says what |
| `failed` | the build exited non-zero; `error` carries the tool's own text |

`method.declaredKotobaFuel` records the call-fuel budget the Kotoba lanes were
given. It is raised above the compiler default on purpose — see the fuel
section of the top-level README — and the comparators have no equivalent bound
to raise.

## Disagreeing with one

Run the harness on your own machine and compare. If your ordering differs, the
JSON has enough in it — samples, machine fingerprint, tool versions, exact
commands — to work out which of the two runs was measuring something else.
