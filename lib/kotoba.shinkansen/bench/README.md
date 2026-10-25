# bench — shinkansen against other Node web frameworks

Same machine, same bytes, same load. `run.cljk` starts each server on port 0,
drives it with autocannon, and refuses a run in which any response carried
the wrong status (a fast wrong answer is not a result).

```bash
npm i --prefix bench                      # pinned: express 5.2.1, fastify 5.12.5, hono 4.13.8
                                          # + @hono/node-server 2.1.1, next 16.3.6 + react 19.3.0,
                                          # nuxt 4.5.2, autocannon 8.0.0
KOTOBA_LANG=<superproject>/orgs/kotoba-lang \
  kbb --backend sci bench/run.cljk        # ROUNDS=3 DURATION=5 CONNECTIONS=100 WORKERS=4
                                          # WARMUP=2 (unmeasured seconds per scenario)
                                          # ONLY=shinkansen,nextjs  OUT=bench/results/<date>.edn
```

Next.js and Nuxt are built by the harness on first use (`next build` /
`nuxt build`, skipped while their output exists — delete `.next/` or
`.output/` after changing a fixture), then run as production servers
(`next start`, `node .output/server/index.mjs`) on a port the harness picks.

Publish a run (writes `docs/bench.md` + `docs/index.html`, the GitHub Pages
site served from `main` `/docs`; refuses a results file with an INVALID median):

```bash
K=<superproject>/orgs/kotoba-lang
KOTOBA_LANG=$K kbb --backend sci \
  --classpath $K/jp-go-digital-design-system/src:$K/html/src:$K/css/src:$K/text/src \
  bench/report.cljk bench/results/<run>.edn
```

Exit 0 only when every median is valid; 1 on any INVALID; 2 when a server
did not start. Output: `RESULT fw scenario rps p99ms cpu-us OK|INVALID`.

## Scenarios

| name | request | what it measures |
|---|---|---|
| `static` | `GET /` | the `:ssg` page (11.6 KB), 200 + ETag |
| `304` | `GET /` + `If-None-Match: <etag>` | revalidation — the common case for a name host (`Cache-Control: no-cache`) |
| `ssr` | `GET /todos/t3` | a page rendered from path params + loaded data |
| `ssr-miss` | `GET /live` | data changes on **every** request, so nothing may be answered from memory: load + render + ETag per request. shinkansen's worst case, on purpose |

## Meta-frameworks: how Next.js and Nuxt serve the same bytes

A page component would not answer the fixture's bytes (the byte check at
start refuses that), so both serve through their documented raw-response
routes, and each gets its best documented option for a static page:

| | `static` | `304` | `ssr` / `ssr-miss` |
|---|---|---|---|
| Next.js 16 | App Router Route Handler, `dynamic = 'force-static'`: prerendered at build, answered from Next's cache (`x-nextjs-cache: HIT`) | **a separate dynamic handler (`/revalidate`)**: the force-static route ignores If-None-Match and answers 200 + body (measured) | `force-dynamic` Route Handlers |
| Nuxt 4 | `nitro.prerender` → `.output/public/index.html`, served by Nitro's static handler | the same handler, its own ETag → 304 | Nitro server routes (`server/routes/`) |

Next.js's numbers were the least stable here: `force-static` measured 714 and
2,513 µs/response in two single runs an hour apart. Trust the median.

## Two numbers, and which one to rank by

- **rps** is what autocannon saw. On a shared machine it moves with everything
  else running (the 2026-09-23 runs had a load average of 60–80 on 10 cores;
  the same server moved ±2× between rounds).
- **cpu-us** is the server's own CPU time per response: user + sys of the
  server's process group from `ps`, read before and after each run, divided by
  responses. It is what the framework charges for one answer and holds up
  under contention far better than rps. **Rank by cpu-us.**

## Why shinkansen can answer cheaper than a JIT-compiled framework

A shinkansen document's ETag *is* the CID of its bytes, so an answered URL is
a value. `shinkansen.host/handle` attaches a plan (`:shinkansen.host/plan`)
saying what may be remembered and on what condition; `shinkansen.serve` keeps
it as a pre-encoded Buffer + flat header array (with `content-length`, so no
chunked framing) in a per-URL table:

- `:ssg` / `:isr` — the answer is a function of the URL: a hit is a Map lookup
  and one write.
- `:ssr` — the load still runs every request; the table answers only when it
  returns a value `=` to the data the bytes were rendered from. Otherwise the
  host renders, hashes and refreshes the entry. A render that reads anything
  but `(params, data)` declares `:memo? false`.
- `304` — decided from the stored ETag without touching the bytes.

The hit path is a small JS closure (`serve/answer-station`), so a hit never
enters the interpreter.

## What is still slower, and why

On `ssr-miss` (data changes every request) no framework may answer from
memory, and shinkansen still costs several times the JIT'd frameworks. The
split, measured 2026-09-23 inside the running server (a probe timing the
listener, the station check, `host/handle`, the station build) and by CPU time
per piece:

| part | µs / miss | whose |
|---|---:|---|
| the app's render fn (20 rows, `.cljc`) | ~70–110 | the app, interpreted by kbb/sci |
| CID: sha2-256 (native) + base32 (interpreted) | ~12 + ~36 | content-address |
| the rest of `host/handle` (load, render check, headers, plan) | ~100 | shinkansen, interpreted |
| station build + write (flat headers, Buffer) | ~40 | shinkansen, interpreted |
| Node's HTTP parse and write | ~45 | Node (every framework pays it) |

Already taken out of this path: a second run of the load per request (the
station check hands its value to the host), a clj->js of every response,
the route walk (remembered per identical tree), the whole-header conversion.

### The compiled path, measured: not yet

The obvious next lever is to stop interpreting the render: write it in
`.kotoba` and compile it with amu. Measured with the `/live` render written
in `.kotoba` (`amu compile --target js --jvm-free`, same output bytes, a fresh
guest instance per render):

| | µs / render (20 rows) |
|---|---:|
| `.cljc` render under kbb/sci | ~110 |
| `.kotoba`, kotoba-script before #103 | ~5,600 |
| `.kotoba`, kotoba-script 63d576e (#103 fixed) | ~330–630 |
| + handing the data across as EDN text (pr-str, interpreted) | +~100 |

The emitted runtime used to re-validate a value on every operation (a full
UTF-8 scan per string, a whole-document walk per access), so building a
string or walking a document was O(n²):
[kotoba-lang/kotoba-script#103](https://github.com/kotoba-lang/kotoba-script/issues/103),
fixed 2026-09-23 (a 30-row render 11.1 ms → 0.79 ms; linear in rows now).
What remains is per-call type checking on generic options and the EDN reader
([#104](https://github.com/kotoba-lang/kotoba-script/issues/104), profile
attached). Until that closes the compiled path is still ~3–6× the interpreted
one, so shinkansen does not switch to it yet.

## Competitor fixtures are JS on purpose

`competitors/*.js` are written the way each framework's own docs write them
so the numbers compare frameworks, not our port of them. They are comparison
fixtures, not tooling; nothing in shinkansen depends on them.
