# torihiki-terminal

The trading terminal for [`torihiki`](https://github.com/kotoba-lang/torihiki).

**Deployed:** https://torihiki.pages.dev serves an **old build**, not this
branch. It predates the move to standalone nodes and still points at the
retired Cloudflare Worker devnet, which no longer answers (see
[What is real here](#what-is-real-here)). A build of the current tree reads
whatever standalone [`torihiki-node`](https://github.com/kotoba-lang/torihiki-node)
nodes it is given with `TK_NODES`.

## The page was a picture of itself

For the whole life of the "live client", this build emitted **no script tag**.
`client.cljs` was written, compiled to `public/js/app.js`, uploaded on every
deploy, and never referenced from the document.

So the deployed page held the zero frame the build rendered, and the status
line read `connecting to the node…` forever — which is indistinguishable from
a terminal whose node is slow to answer. Nothing looked wrong.

Everything else was green the entire time. The build succeeded. The bundle
existed and shipped. The HTML was valid. The design audit scored **100.00** on
a page that did nothing. The engine passed 140 tests. The previous commit here
described a client that polls and re-renders, and that client had never
executed in production.

It was found by opening the site in a real browser, which is the only place
the difference is visible.

Two things changed so it cannot happen quietly again:

- **`script/build.cljk` refuses to write a document that does not reference the
  bundle**, or when the bundle has not been compiled. That would have caught
  this exact bug.
- **`script/verify.cljk` clicks the deployed page** — waits for the session
  panel to fill, clicks the faucet, types a price and size, toggles a chip,
  clicks Buy, and asserts the chain moved. It exits non-zero when it does not,
  because a verification that always passes is the same kind of object as a
  page that always renders.

  ```
  NODE_PATH=<root>/node_modules kbb --backend sci script/verify.cljk
  TK_BASE=http://127.0.0.1:8899 kbb --backend sci script/verify.cljk
  ```

  Against production when it was written (2026-09, the Worker sequencer):
  `live · block 35`, faucet accepted at 36, chip toggled, buy accepted at 37,
  nonce 1 → 3. The default `TK_BASE` is still the deployed URL; it cannot
  pass there now (see below).

An assertion about the HTML still cannot tell you the page works. Only
clicking it can, so both exist.

## What is real here

The book, the fills, the funding rate and the state roots are read from
ordinary torihiki nodes — `torihiki-node`'s standalone process, running the
real engine — over plain HTTP. Nothing is mocked. The page reads the nodes in
`TK_NODES` (default: four local nodes, `127.0.0.1:8801`–`8804`) and compares
them rather than believing one. Earlier versions replayed a session generated
at build time, and later ones polled a single sequencer in a Cloudflare
Worker; that Worker implementation is frozen and deprecated in
`torihiki-node`, and its devnet has stalled.

There is **no public node set for this page today**. Build it against nodes
you run (see [Build](#build)).

**What https://torihiki.pages.dev serves (checked 2026-10-13).** A build from
before the standalone change: its `data-node` is
`torihiki-validator.04-feasts-minded.workers.dev`, which answers Cloudflare
`error code: 1042` (HTTP 404), so the page has no data. It still shows that
build's copy — a "recorded session" chip and a "running live in a Cloudflare
Worker" panel — neither of which is true. The other retired Workers still
answer but did not move while checked: the single sequencer (`torihiki-node`)
at height 62, and `torihiki-validator-v3` at height 5805 with no certificate
for its tip — where `torihiki-node` recorded it stalling on 2026-09-23. Redeploying `public/` from a `TK_*` build that names
real nodes is what fixes the site; until then, do not read it as live.

**It is not a decentralized chain yet.** The page reads a four-replica BFT
validator set whose keys one party holds, so a quorum is one party's word;
collateral is a faucet grant. The nodes say which of these they are in their
own responses and the page repeats it.

## The browser renders with the same functions the server does

`order-book`, `trades-panel`, `chain-panel` and `ticker-body` are pure hiccup
functions. `script/build.cljk` calls them to render the shell; the client calls
the same ones and swaps the result in with `kotoba-ui.core/->html`.

That replaced ~90 lines of hand-written JavaScript which built the same rows
by string concatenation. Two renderers for one panel is two things to keep in
agreement, and the JavaScript one could not use the design system's classes
without repeating them by hand — which it did.

## Failure is visible

When the node is unreachable the status line says so instead of leaving the
last good frame on screen. A terminal that silently shows stale prices is
worse than one that admits it is disconnected: the first invites a trade.

## Build

```bash
script/build_js.sh           # browser bundle -> public/js/app.js
kbb -M:build                 # shell         -> public/index.html
```

`public/` is static files; serve it from any host.

### What a deployment pins (`TK_*`)

The shell build reads the deployment's trust root from the environment and
renders it into the page (`torihiki-terminal.deploy`):

| env | |
|---|---|
| `TK_NODES` | `https://n1.example,https://n2.example:8443,...` — the standalone nodes the page reads and compares. Default: four local nodes. |
| `TK_SET` | `w1=<base64 spki>,w2=...` — the validator set. A balance shows as **proved** only when more than 2/3 of it signed the root. |
| `TK_EPOCH` | the engine epoch of that set (required with `TK_SET`) |
| `TK_CHAIN` | the chain id that set signs for (required with `TK_SET`); the page signs and verifies for this chain only, whatever the nodes report |

```bash
N=https://n1.example
D="$(curl -s $N/duties)"   # keys and epoch from ONE answer, so they agree
TK_NODES=$N,https://n2.example,https://n3.example,https://n4.example \
TK_SET="$(jq -r '.["segment-keys"] | to_entries | map("\(.key)=\(.value)") | join(",")' <<<"$D")" \
TK_EPOCH="$(jq -r .epoch <<<"$D")" \
TK_CHAIN="$(curl -s $N/attestation | jq -r .chain)" \
kbb -M:build
```

(Taking the set from a node, as above, is only as good as that node: check it
against what the operators publish before shipping the page.)

The pinned set is for ONE epoch. After the chain turns the set, the page says
"not verified" until it is rebuilt with the new set — it fails closed, not open.

The build **fails** — and says every reason — on a URL that is not a plain
base URL, plain `http://` to a non-local host (`TK_ALLOW_HTTP=1`), a key that
is not Ed25519 SPKI, a duplicate witness or key, a non-canonical spelling of
a key (one key spelled twice would count twice), a key of small order (anybody
can sign for it), fewer than 4 validators (`TK_ALLOW_SMALL_SET=1`), a set
without its epoch or chain, or keys a devnet derives — under the pinned chain
or a default devnet chain, for any devnet name — which anybody can sign with
(`TK_ALLOW_DEVNET=1`). Without `TK_SET` the page still works and says
its balance is NOT a proof.

`?nodes=a,b` on the page URL still overrides the node list; it cannot
override the set or the chain.

## Design system

Built on the paved road (`kotoba-uiux` skill, ADR-2607122200): requires
`kotoba-ui.core` only, one theme map, layout from shell, the eleven HIG text
styles, no raw hex outside the theme. App CSS is ~30 lines, covering what a
design system has no opinion about — tabular numerals and a depth bar.

design-quality: **100.00**, no findings.

## Known couplings

`config.cljk` duplicates the node's tick and lot scale so the terminal can
format integer ticks into dollars. The node already exposes both on `/market`;
taking them from there is the right fix and is not done yet.

`appkit` is absent because it cannot be depended on: its production `:deps`
names kotoba-ui as `{:local/root "../kotoba-ui"}`, so any consumer depending
on it through git cannot build a classpath.
