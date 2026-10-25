# newsfeed

The A layer this workspace kept designing and never built: **fetch primary
sources, and turn them into article datoms a channel can be produced from.**

It exists because the layer above it had nowhere to get news. `newscaster`
(ai-gftd-newscaster) implements a full AI news broadcast — rundown, anchor
script, EditorialGovernor, YouTube publisher — against a `NewsFeed` port whose
only implementation is `mock-feed`. `cloud-itonami/news` has the XRPC surface
for RSS ingest but defers the fetching to `NEWS_POD_URL`, a pod that does not
exist in this workspace, on a host that no longer answers. And no repository
anywhere held a single feed URL. Measured 2026-08-03; see ADR-2608031500.

Pure `.cljc` throughout, with IO only in `bin/*.cljs` (nbb). It holds no loop,
no clock and no publishing key.

## Use

```bash
# fetch every active source and append new articles to the ledger
kbb --backend sci --classpath src:resources bin/ingest.cljk

# ...or see what would happen without writing
kbb --backend sci --classpath src:resources bin/ingest.cljk --dry-run --only phoronix,blocksandfiles

# ledger + channel -> the episode brief a video is produced from
kbb --backend sci --classpath src:resources bin/digest.cljk --channel murakumo-gpu-ai \
    --out brief.edn --explain

# tests (ClojureScript first; the JVM alias runs the same .cljc as a check)
kbb --backend sci --classpath src:test test/run.cljk
kbb -M:test
```

`digest.cljs` exits **0** with a brief and **3** when nothing cleared the
channel's threshold. A day with no story is a real outcome, not an error, and a
caller chaining into production needs to tell those apart without reading prose.

## Layers

```
resources/sources.edn   17 feeds + 2 channels, as data
        │
   bin/ingest.cljk      fetch (IO)
        │
 newsfeed.parse         RSS 2.0 | Atom 1.0 | RDF -> uniform items   (pure)
 newsfeed.article       item + source -> :news/* datom              (pure)
        │
state/articles.ledger.edn    append-only, one EDN map per line
        │
 newsfeed.catalog       re-join the CURRENT catalog over the ledger (pure)
 newsfeed.score         rank for one channel, explainably           (pure)
 newsfeed.digest        cluster, spread, brief + citations          (pure)
        │
   bin/digest.cljk      brief.edn (IO)
```

Downstream, `:brief/topic` is the string handed to `dougaka-vector`'s
storyboard actor, and `:brief/citations` are article ids straight out of the
ledger — which is what `newscaster`'s EditorialGovernor gates on (`cites ⊆
ingested`), satisfied by construction rather than by a model being careful.

## Attribute names are borrowed, deliberately

Articles are `:news/*` and sources are `:news.source/*`, taken verbatim from
`cloud-itonami/news`'s `news.schema`, including its `art-<sha256hex(url)>` id
convention and its `rightsPolicy` vocabulary. That A layer is unreachable
today, but it is the workspace's existing vocabulary for this data, and a
parallel one would mean a translation layer the day it or a successor returns.

Records carry `:source/dataset "newsfeed"` so they query alongside the
workspace's other datasets.

## Two things that are easy to get wrong here

**The ledger is observation; the catalog is opinion.** Credibility, source
class and rights policy live in `resources/sources.edn` and get revised as we
learn. An append-only ledger cannot be revised, so `newsfeed.catalog/enrich`
re-joins the current catalog over every article at read time. The ingest still
writes its snapshot into the ledger — that is provenance, what was believed
then — and the join always wins over it. This was found the hard way: adding
`:news.source/class` changed nothing at all until the join existed, because
every article already ingested predated the field.

**Ranking is not a running order.** The scorer was right and the result was
still wrong: it led the GPU/AI channel with four arXiv preprints (an abstract
is keyword-dense by construction) and gave the storage channel five of six
items from one outlet. Both are fixed in `newsfeed.digest/take-spread` with
per-source and per-class caps declared on the channel — not by making the
scorer distrust preprints, which would have been a lie about relevance.

## Sources

17 feeds, every one fetched before being listed, each carrying what that fetch
measured. Candidates that did not answer are kept under `:rejected` with their
status rather than deleted, so the next person does not rediscover them:
arXiv's advertised RSS endpoints serve empty documents (the Atom API works),
The Register has no per-section feeds, `blog.min.io/rss` is empty, SNIA blocks
non-browser agents.

Two feeds ship **no summary at all** — Blocks & Files sends
`<description><![CDATA[]]></description>` and Hugging Face omits it — so they
carry `:newsfeed/has-summary false`. Anything written as though a summary will
be there is wrong for those two.

## Channels

| channel | site | sources | leads with |
|---|---|---|---|
| `murakumo-gpu-ai` | murakumo.cloud | 12 | vendor blog, then releases and trade |
| `kotobase-storage` | kotobase.net | 8 | storage trade press, then releases |

A channel is a lens over the shared pool, not a private set of feeds. The
Register publishes one all-sections feed and both channels read it; the keyword
and url-hint gates decide what each takes. `:channel/sources` is **honoured**,
not advisory — a channel that quietly drew from feeds it does not list could
not be reviewed by reading its own definition.

## What this does not do

No loop, no schedule, no publishing. `loop-ka-production` owns cadence for this
fleet and a second scheduler would be a second answer to "is it time yet".
No prose is generated here: `:brief/topic` is the lead headline verbatim, and
the only generative step in the pipeline stays where it already was, in
`dougaka-vector`'s storyboard actor.

## 台帳の永続化（DataLad + B2、ADR-2608031900）

`state/articles.ledger.edn` は **append-only の観測記録**で、日次 ingest のたびに
育つ。以前は `.gitignore` で捨てていたので、**run を跨いだ dedup が実際には一度も
効いていなかった**（毎回 clone 直後の空 ledger に対して「0 already in ledger」と
報告していた）。

いまはこの repo 自身が DataLad dataset で、`state/**` だけが annex → Backblaze B2
に載る。git 側はポインタのみ（実測: 1.38 MB の台帳が git 上 131 byte）。

```bash
# 認証（値は repo に置かない。参照先は manifest/repos.edn の :b2 :credentials）
eval "$(kbb --backend sci --classpath orgs/kotoba-lang/secret-resolve/src:scripts/nbb_compat:. \
        scripts/b2-creds.cljs)"          # superproject 側で実行
export AWS_ACCESS_KEY_ID=$B2_KEY_ID AWS_SECRET_ACCESS_KEY=$B2_APP_KEY

kbb --backend sci --classpath src:resources bin/ingest.cljk   # 追記
datalad save -m "ingest <date>"                 # annex 化してコミット
datalad push --to b2                            # 実体を B2 へ
git annex drop state/articles.ledger.edn        # 手元を解放（B2 から戻せる）
git annex get  state/articles.ledger.edn        # B2 から復元
```

**`.gitattributes` はパスで明示的に振り分ける。** `datalad create -c text2git` の
既定（バイナリなら annex）は中身 sniffing なので、実体がテキスト EDN のこの dataset
では目的を満たさない。`com-junkawasaki/product-corpus` と同じ判断。
