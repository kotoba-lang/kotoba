# toshokan-patents

**Library.** Worldwide patent bibliographic metadata: a Google Patents page →
a field-map → git-authoritative EDN quads `[entity attr value tx op]`.

Sibling of [`kotoba-lang/toshokan`](https://github.com/kotoba-lang/toshokan)
(national-library catalogs); same journal convention
([ADR-2607072300](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607072300-actor-public-data-git-journal-kotobase-index.edn)),
different subject. Source design:
[ADR-2607251552](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607251552-toshokan-patents-worldwide-patent-resident-harvest.edn).

## This repo holds no loop and no data

It used to. Until 2026-08-10 this repo also carried the resident daemon, the
seed list, the harvest cursor, and 618 harvested patents. **They now live in
[`cloud-itonami/hirameki`](https://github.com/cloud-itonami/hirameki)** (the
governed observatory actor that runs the loop) and
[`cloud-itonami/hirameki-patents`](https://github.com/cloud-itonami/hirameki-patents)
(the corpus dataset) — kotoba-lang holds libraries only.

Nothing was lost: the journal moved to the corpus repo, and this repo's git
history still has every tick. What changed is *who owns residency*. A library
that also runs a daemon cannot be depended on without inheriting the daemon.

## API

| | pure | JVM | cljs / nbb |
|---|---|---|---|
| `parse-html`, `->quads`, `page-url`, `country-code`, `cited-patent-ids`, `normalize-patent-id` | ✅ | ✅ | ✅ |
| `fetch-page`, `lookup` | — | **sync**, returns the value | **async**, returns a Promise |
| `quad/next-tx`, `record->quads`, `merge-quads`, `entities`, `render-journal`, `shard-name` | ✅ | ✅ | ✅ |
| `quad.fs/read-journal`, `write-journal!`, `append-journal!` | — | `clojure.java.io` | `node:fs` |
| `quad.fs/read-sharded`, `append-sharded!`, `shard-paths` | — | ✅ | ✅ |

**`quad` is pure; `quad.fs` is where the filesystem lives.** Split 2026-08-10:
`quad` had claimed purity in its docstring while requiring `node:fs` at the top
of the namespace, so a Cloudflare Worker trying to use the codec — the whole
reason this is a library — failed to build on a dependency it does not have. A
comment cannot enforce that boundary; a namespace can.

The network leg is deliberately **not** uniform across platforms. A JVM caller
gets a value; a ClojureScript caller gets a Promise. Wrapping the JVM leg in a
fake promise to make the signatures match would buy nothing and hide where the
blocking happens.

```clojure
(require '[toshokan-patents.sources.google-patents :as gp]
         '[toshokan-patents.quad :as quad])

;; pure: HTML you already have → quads
(->> (gp/parse-html html "US8697359B1")
     (gp/->quads (quad/next-tx existing) "2026-08-10T00:00:00Z"))

;; JVM: one polite request (nil if the id does not exist)
(gp/lookup "US8697359B1")
```

## The journal is sharded and line-oriented

A journal a resident loop appends to forever cannot be one file, and cannot be
one line.

The original writer emitted `(pr-str (vec quads))` — at 618 patents that was a
single **691 KB line**. Git stores a fresh blob per commit either way, but a
one-line file also defeats delta compression and makes `git diff` and
`git blame` useless on the exact artifact that is supposed to be the
authoritative record (ADR-2607072300).

So: `render-journal` writes one quad per line inside a single top-level EDN
vector — still one `edn/read-string`-able form, so **every existing reader keeps
working unchanged** — and `append-sharded!` seals a shard at 1 MiB and rolls
over. A sealed shard is byte-identical forever, so git stores it once and
DataLad/annex can take it later; only the bounded active shard is rewritten.

Shards are named `<source>.NNNN.journal.edn` **in the same directory**, not a
subdirectory, so consumers that glob `*.journal.edn` (the query plane, the
corpus fold, the verifier) need no change either.

`read-sharded` also picks up a legacy single `<source>.journal.edn` if present,
and puts it FIRST — that file holds the oldest facts, and dropping it silently
would look exactly like a corpus that had always been smaller.

## What it extracts, and what it does not

Bibliographic fields from the page's **own** structured metadata: title,
patent/application number, jurisdiction, filing date, grant date, inventors,
assignees, and the cited-patent list. Never claims, never specification text,
never a paywall or bot-detection bypass.

`DC.relation scheme=references` is the field worth having: it names the patents
this one cites, in compact form (`JP2004224907A`), which is what lets a consumer
walk the citation graph and grow its own seeds. Filing date vs. grant date and
inventor vs. assignee are told apart by the `scheme` attribute — both pairs
share a `name` (`DC.date`, `DC.contributor`), so reading `name` alone silently
conflates them. The tests assert exactly that.

## Tests

The fixture is a **real** page (US8697359B1 — Broad Institute CRISPR-Cas9),
reduced to its `<title>` and all 2,329 `<meta>` tags. The same `.cljc` test
namespace runs on both platforms, because "pure" is a claim about platform
agreement:

```bash
kbb -M:test                              # JVM      → 7 tests, 42 assertions
kbb --backend sci --classpath src:test run-tests.cljk      # nbb/cljs → 7 tests, 42 assertions
```

## Rate discipline is the caller's

This library performs one request when asked and has no timer, no retry, and no
concurrency of its own. Identifying User-Agent, sequential, polite rate — the
*rate* is set by whoever runs the loop.

## License

Apache-2.0.
