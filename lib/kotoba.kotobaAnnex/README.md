# kotoba-annex

**git-annex external special remote** that persists DataLad/git-annex large
binaries to a **content-addressed block store** — either `kotobase.net`
(kotobase's block store, the `put!/get-fn/head` contract) or a local directory.

Written in `.cljc`/`.cljs` (nbb-first, per the workspace runtime priority). The
protocol engine is pure and testable; the block store is an **injected seam**
(same design as `kotobase-server`'s injectable `store` map) so directory /
kotobase.net / B2 backends are interchangeable.

## Why

Large binaries (rendered video, synthesized audio, model weights, datasets) must
not go into git history. The workspace standard is DataLad + git-annex + a
Backblaze B2 S3 special remote (see `m365-archive`). This adds **kotobase.net as
an alternative git-annex backend**: because a git-annex *key* is itself a content
hash (`SHA256E-s<size>--<hash>`), it maps 1:1 onto kotobase's content-addressed
block store — the annex key *is* the block cid.

## Verified

The special remote is **verified end-to-end against real `git-annex`** (v10) —
with the directory store *and* against **real kotobase.net**（下記）:

```
git annex initremote kotobase type=external externaltype=kotobase encryption=none
git annex add sample.wav
git annex copy sample.wav --to kotobase      # STORE  -> block SHA256E-s191020--… .wav
git annex drop sample.wav --force
git annex get  sample.wav --from kotobase    # RETRIEVE -> checksum ok
git annex fsck sample.wav                     # content integrity ok
```

### Verification matrix (all against real `git-annex` v10)

| operation | encryption=none | encryption=shared |
|---|---|---|
| STORE (`copy --to`)        | ✓ block keyed by annex key | ✓ block keyed by `GPGHMACSHA256--…` |
| RETRIEVE (`get --from`)    | ✓ checksum ok | ✓ decrypt + checksum ok |
| CHECKPRESENT (`fsck`/`whereis`) | ✓ | ✓ |
| REMOVE (`drop --from`)     | ✓ block store 1→0 | — |
| **at rest**                | plaintext block | **encrypted block** (block sha ≠ plaintext sha) |

encryption is transparent to the remote: git-annex encrypts before STORE and
decrypts after RETRIEVE; the remote stores/serves opaque blocks. Use
`encryption=shared` for non-public assets (audio/video with proprietary voices,
private datasets), `encryption=none` for public/regenerable content.

## Layout

- `src/kotoba/annex/protocol.cljk` — pure external-special-remote protocol
  (parse + response strings). No IO.
- `src/kotoba/annex/store.cljk` — store contract (`store!/retrieve/present?/
  remove!/init!/prepare!`) + in-memory impl for tests.
- `src/kotoba/annex/directory.cljk` — local directory block store (fallback /
  verification).
- `src/kotoba/annex/kotobase.cljk` — kotobase.net block store (maps the store
  contract to a blob XRPC surface).
- `bin/git-annex-remote-kotobase.cljk` — the executable git-annex invokes
  (stdin/stdout protocol loop).

## kotobase.net backend — **動く。が、層を誤っている**（2026-07-17 実測 + 設計評価）

> **先に読むこと**: この backend は実 git-annex → 実 kotobase.net で往復検証済み
> （下記）だが、**ストレージ層の選択が誤っている**。`net.kotobase.store`(istore) の
> 実体は **Cloudflare KV**（`TENANT_STATE`、**billing/funnel カウンタと同居**）で、
> 小さい値・読み取り主体の**ドキュメント面**であって blob 面ではない。下の
> 「必須事項」に並ぶ制約（chunk 必須 / 191KB timeout / ~25KB/s / max 900KB）は
> **全てこの層ミスの症状**であり、本来必要な制約ではない。
> **本番の大量アップロードにこの backend を使わない**（22.5MB ≒ ~700 chunk が
> billing KV 名前空間に書き込まれる）。恒久保存は当面 `directory` store か B2 を使う。
> 正しい面は kotobase に既にある — `PUT /ipfs/:cid`（`archive_put.cljc`: raw
> CIDv1(sha2-256) を認証付きで **B2 archive** へ直接）。annex key
> `SHA256E-s<size>--<sha256>` は CIDv1(raw, sha2-256) へ機械変換できるので直接噛み合い、
> chunk も base64 も DAG-CBOR も要らなくなる。張り替えは follow-up（ADR-2607175000）。

### 検証内容（「動く」ことの証明。「適切」の証明ではない）

**訂正**: 当初は kotobase-server に blob 面を足す設計だったが、net-kotobase の live
worker は kotobase-server ではなく `kotobase.istore` を使っており、
**`net.kotobase.store.{put,get,list,append,read}` は既に kotobase.net で live**。
よって **server 変更も deploy も不要**だった。

認証は **CACAO 自己発行** — actor が自分の Ed25519 鍵を生成し、鍵由来 did:key が
自分の graph（skill build-actor）。`resolve-viewer` は CACAO を検証して did を取り
出すだけなので、**自分の鍵 → 自分の tenant** で完結し owner の token 受け渡しは不要。

```sh
export KOTOBASE_ENDPOINT=https://kotobase.net       # これだけで kotobase backend
git annex initremote kb type=external externaltype=kotobase \
    encryption=none chunk=32KiB                      # chunk は必須（下記）
git annex copy asset.wav --to kb                     # STORE  -> ok
git annex drop asset.wav --force
git annex get  asset.wav --from kb                   # RETRIEVE -> (checksum...) ok
git annex fsck asset.wav                             # content integrity ok
```

**実測（kagaku の合成音声 95,788 bytes、実 git-annex v10 → 実 kotobase.net）**:
STORE ok / RETRIEVE (checksum) ok / fsck ok。tenant を `store.list` すると chunk
`SHA256E-s95788-S32768-C1..C3--…` が実在。

### 実装上の必須事項（実測で判明。1 は層ミスの症状、2–3 は本物）

1. **`chunk=` は必須**。istore の `max-value-bytes` は 900000 だが、実測では 191KB の
   単一 put が 2 分超で timeout。**32KiB chunk で安定**（1KB/32KB は即応）。
   ⚠ これは KV の write latency + グローバル伝播に起因する**層ミスの症状**で、
   B2 archive（`/ipfs/:cid`）へ張り替えれば不要になる。
2. **不在キーでも HTTP 200 が返る**（body が `{"ok":false,"error":"NotFound"}`）。
   これは **XRPC(atproto) の作法であり kotobase の欠陥ではない** — HTTP status で
   判定した**こちらのクライアントが誤りだった**。誤ると **不在キーを present と誤答 →
   git-annex が STORE を丸ごとスキップし「copy は ok と言うのに実際は空」**になる。
   必ず **body の `ok`/`val`** を見る（回帰テスト
   `absent-key-returns-http200-with-error-body` で固定）。backend を替えても
   「HTTP status を成功判定に使わない」は維持する。
3. **stdin close で即 `process.exit` しない**。実行中の非同期 STORE/RETRIEVE が応答
   前に殺される。in-flight を追跡し全完了後に exit する（bin の `track!`）。

## backend 一覧

| backend | 状態 | 用途 |
|---|---|---|
| `directory`（既定） | ✓ 全操作 + 暗号化を実 git-annex 検証済み | ローカル / オフライン / CI / **当面の恒久保存の正本** |
| `kotobase.net`（`KOTOBASE_ENDPOINT` 設定時） | △ 往復は検証済みだが **層が誤り**（istore = billing と同居の Cloudflare KV。`chunk=32KiB` 必須、~25KB/s） | **実験・小さい検証のみ。大量アップロードに使わない** |
| kotobase `PUT /ipfs/:cid`（B2 archive）= `kotoba.annex.archive` | ✓ 実装済み（`src/kotoba/annex/archive.cljk`）。**層としてはこれが正**。上限 4 MiB / REMOVE 未対応 / 置いたものは public gateway から読める | 共有・恒久保存 |
| kotobase grant/settle = `kotoba.annex.grant` | ✓ 実装済み（`src/kotoba/annex/grant.cljk`）。**GB 級はここ** —— presigned URL なので bytes が Worker を通らず、4 MiB 天井が構造的に無い（単発上限は S3 の 5 GiB。multipart は未公開で、超えると本番は 413 に `:missing-capability :multipart-put` を付ける）。認証は **CACAO**（`kotoba://can/object:*`）で `/ipfs/:cid` の Bearer / Biscuit とは別物。REMOVE は false | 大容量アーカイブ |
| B2 S3 special remote | 既存（`m365-archive` 先例、本 remote 非経由） | 大容量アーカイブ |

### 封緘（`kotoba.annex.sealed`）

内側の store（`archive` / `grant` / `directory`）を包んで、**identity と location を
分ける**（ADR-2608301039 D2）:

| | 何を指すか | どこへ行くか |
|---|---|---|
| **identity** | annex key `SHA256E-s<n>--<sha256>` から導く平文の CIDv1 | **object store には出ない。** annex branch に留まる |
| **location** | 暗号文の sha256 から作る CIDv1 | object store が鍵にするのはこちら |

**git-annex の `encryption=shared` は使わない。** 使うと remote 側の key が
`GPGHMACSHA256--…` になって内容ハッシュでなくなり、CID へ機械変換できない
（`kotoba.annex.cid` の実測）。annex 層を `encryption=none` のまま保ち、封緘は
この seam の中で行う。

対応表（identity → location + 封筒）は **git-annex の per-key state**
（`SETSTATE`/`GETSTATE`）に置く。annex branch に載って repo と複製され、remote ごとに
分かれる。**state が無い key は `:no`** —— `:unknown` や `:yes` にすると、対応表を
失った時に「在ることになっている bytes」が生まれ、git-annex は numcopies 充足と
信じて最後のローカルコピーを落とす。

⚠ **state を JSON にしない。** `clj->js` は namespace 付きキーワードの namespace を
落とすので、`:envelope/recipients` が `:recipients` になって帰る。envelope の全キーが
namespaced なので、往復した封筒は `entry-for` から見えなくなり、**封緘は成功したまま
二度と開けない**。EDN（`pr-str` / `edn/read-string`）は namespace を保ち、改行も出さない
（annex の state 値は 1 行でなければならない）。実測 2026-08-30 —— この形で
roundtrip テストだけが落ちた。

受信者は現状 operator 鍵 1 本（WebAuthn PRF から X25519 を導く経路が入るまで、他に
存在しない）。**共有は content key を wrap し直すだけで、オブジェクトを暗号化し直さない。**

### grant/settle を使うときの 2 点

**STORE は 3 手で、成功は settle が決める。** `grant` は presigned URL を返して
`:object/state :pending` を立てるだけで、custody（`:holding/*`）を立てるのは
`settle` だけである。intent を custody と report すると、URL を渡した直後に client が
落ちた場合に **git-annex が numcopies 充足と信じて最後のローカルコピーを drop** し、
bytes が消えたのに記録は全て正常に見える。`kotoba.annex.grant` は settle が 200 を
返すまで STORE を成功にしない（回帰テスト `grant-is-not-custody`）。

**REMOVE はできない。** 本番の `grant-response` は `(if upload? "PUT" "GET")` で
presign するので、**`remove` の grant も GET を返す**。従っても削除は起きないので
`remove!` は false を返す（`archive` が `/ipfs/:cid` に delete 面が無いことに対して
そうしているのと同じ理由 —— tombstone で「消えたことにする」誤魔化しをしない）。
実測 2026-08-30。

## Test

`src:test` alone **does not run** — it stops at `Could not find namespace:
ed25519.core`, then at four more, one per attempt. The suite needs five sibling
trees. Paths are relative to the west superproject root (measured 2026-08-30,
23 tests / 63 assertions green):

```sh
ROOT=<west superproject root>
kbb --backend sci --classpath "src:test\
:$ROOT/orgs/kotoba-lang/org-ietf-ed25519/src\
:$ROOT/orgs/kotoba-lang/org-chainagnostic-cacao/src\
:$ROOT/orgs/kotoba-lang/org-ietf-cbor/src\
:$ROOT/orgs/kotoba-lang/authority/src\
:$ROOT/orgs/net-kotobase/control-plane/kotobase-api-gateway-cljs/src" \
  test/run.cljk
```

The last one is why `archive` can be tested at all: `kotoba.annex.archive`
reuses `kotobase.archive-put`'s CID parser rather than carrying a second one.
