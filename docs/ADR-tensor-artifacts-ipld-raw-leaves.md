# ADR — Tensor artifacts as IPLD raw leaves（CID/IPLD を維持した CPU/LLM 分散推論のデータ面）

- **Status**: Proposed
- **Date**: 2026-07-02
- **Owners**: kotoba data plane / kotodama.inference
- **Related**: `docs/ADR-sealed-cold-tier.md`（block store 階層）、
  `docs/ADR-kotoba-mesh-wasm-hosting.md`（libp2p 面）、
  `kotoba-lang/net`（gossip / bitswap / WantSince delta-sync の EDN semantics）、
  `kotoba-lang/inference`（GGUF Q4_K/Q6_K dequant・分散推論 contract）、
  `kotoba-lang/num`（NDArray）、`kotoba-lang/transit`（wire 投影）、
  `kotoba-lang/dag-cbor`

## Context

kotoba のデータ面は現在 3 層で層別されている:

- **EDN** — in-memory / authoring の正本。
- **Transit JSON** — Kotoba-owned API の既定 wire 投影
  （`application/transit+json`）。plain JSON / OpenAPI / GraphQL / XRPC は
  adapter surface。
- **DAG-CBOR + CIDv1 (sha2-256, tag-42 link)** — 永続 block・content
  addressing・p2p 制御メッセージ（CBOR + 署名）。on-disk index は
  history-independent な **Prolly Tree**（4 索引 arrangement のミラー）を
  DAG-CBOR/IPLD encode して IPFS block として格納する。

一方、推論スタック（`kotoba-lang/inference` / `num`）の現状:

- 重みは **GGUF/GGML**（Q4_K = 144B block, Q6_K = 210B block, fp16）を
  byte-level dequant して `num.array/NDArray` に載せる実装が実在する。
- 分散推論は `kotodama.inference.runtime` の **EDN contract のみ**
  （`:kotodama/shard-strategy :tensor-parallel` / `:tensor-parallel-size` /
  `:pipeline-parallel-size` / `:paged-kv-cache?`）で、KV 転送・スケジューラ・
  マルチノード実装は未着手（vLLM 様 host が bind する前提のデータ）。
- モデル同一性は **plain SHA-256 hex**（`:kotodama/digest`、Ollama 由来）で、
  CID/IPLD 化されていない。
- num-clj の host 境界は plain double vector 化（コピーコスト大）。
- Arrow / 圧縮（zstd 等）はコーパス全体で不使用。

問題: このままでは (a) 重み配布が content-addressed graph に乗らず
bitswap/dedup の恩恵を受けられない、(b) バルクのテンソル byte を DAG-CBOR に
包むと mmap/zero-copy 読みが壊れる、(c) KV-cache などのホットパスに
content addressing を誤適用すると latency を失う。

## Decision

**control plane と data plane を分離する。CID/IPLD は維持し、バルクの
テンソル byte だけを IPLD raw leaf にする。**

### 1. 重み = IPLD raw leaf (codec 0x55) + DAG-CBOR manifest

- テンソル実体（GGUF/GGML quant block 列・fp16 row）は **raw codec (0x55) の
  leaf block** として格納する。CBOR に包まない。leaf はそのまま
  mmap / zero-copy で dequant カーネル（`kotodama.inference.gguf`）に渡せる。
- chunk 境界は **quant block 境界に整列**する（Q4_K=144B / Q6_K=210B の倍数、
  実用上はテンソル row 境界または 1 MiB 整列）。整列 chunking は
  Prolly Tree / CDC と同型の性質を持ち、**fine-tune 間で base 層 block が
  dedup される**。
- テンソル manifest は dag-cbor node:

  ```clojure
  {:kotoba.tensor/name   "blk.0.attn_q.weight"
   :kotoba.tensor/dtype  :q4-k          ; :q4-k :q6-k :f16 :f32 ...
   :kotoba.tensor/shape  [4096 4096]
   :kotoba.tensor/quant  {:block-bytes 144 :block-elems 256}
   :kotoba.tensor/leaves [CID ...]}     ; tag-42 raw-leaf links, 順序 = row-major
  ```

  モデル manifest はテンソル manifest の集合 + hyperparameter map
  （`kotoba-lang/inference` の `gemma.cljc` にある形を dag-cbor 化）。
- **モデル同一性は CIDv1 に置換する**: `:kotodama/digest`（SHA-256 hex）→
  モデル manifest の CID。multihash は同じ sha2-256 なので、既存 digest は
  「manifest CID の祖先メタデータ」として温存できる。

### 2. 配布 = 既存 bitswap semantics（shard = CID 集合）

- tensor-parallel の shard 割当は「その rank が fetch する raw-leaf CID 集合」
  として manifest から機械導出する。`kotoba.net.bitswap` の
  want-list / have-list / `WantSince` semantics がそのまま重み配布
  プロトコルになる（新規プロトコル不要）。
- cold tier は既存の `KuboBlockStore` / B2 経路（ADR-sealed-cold-tier）。
  raw leaf は IPFS block としてそのまま公開 replicate できる。

### 3. ホットパスは IPLD に載せない

- **KV-cache 転送・activation・all-reduce・token stream は content-address
  しない。** ephemeral かつ latency-critical であり、CID 計算・block 化は
  純オーバーヘッド。libp2p QUIC stream（`kotoba-lang/net` が明示的に先送り
  している future native adapter）上の **raw frame** で運ぶ。
- frame 形式は「素の typed buffer（dtype/shape ヘッダ + little-endian body）」
  を最小既定とし、columnar なバッチ（logits / embeddings table / token batch）
  には **Arrow IPC frame** を許す。Arrow は重み形式には使わない
  （業界標準は GGUF/safetensors。Arrow の効果域は columnar I/O と
  datom スキャン投影に限定する）。
- 永続化したい Arrow IPC frame は frame 丸ごと raw leaf にして CID 化できる
  （IPLD との両立はこの 1 点で足りる）。

### 4. 圧縮はトランスポート層のみ、CID は非圧縮 byte に対して

- **CID は常に非圧縮 byte で計算する**（圧縮後 byte で振ると dedup が壊れる）。
- zstd は bitswap message / HTTP 転送層で optional に適用する。
  なお Q4_K/Q6_K 量子化済み重みは高エントロピーでほぼ縮まないため、
  圧縮の本命は datom / Transit block 側である。

### 5. host 境界の zero-copy

- num-clj の host 境界を plain double vector から **typed raw buffer**
  （dtype タグ付き byte view）に拡張する。in-process の runtime 間交換は
  DLPack 規約（ABI であって wire ではない）に合わせる。

## Consequences

- (+) fine-tune 系列で base 重みの block が dedup され、配布帯域と
  cold-tier 容量が縮む。shard fetch が「CID 集合の bitswap」に還元される。
- (+) CPU 推論は raw leaf の mmap 直読 + 整列 chunk で copy を踏まない。
- (+) 監査・provenance: モデルも datom も同じ CID graph に載る
  （台帳から model CID を参照できる）。
- (−) manifest 設計・chunker・`:kotodama/digest` → CID 移行の実装コストが要る。
- (−) raw leaf は self-describing でない（dtype/shape は manifest 側が正本）。
  leaf 単独では解釈できないことを仕様として明記する。
- (0) ホットパスを IPLD 外に置く線引きは「永続 artifact だけが CID を持つ」
  という既存設計（Prolly Tree / sealed cold tier）と一貫する。

## Alternatives considered

- **全部 DAG-CBOR に包む** — CBOR byte-string 化で alignment/mmap を失い、
  encode/decode コストがバルク帯域に乗る。却下。
- **全部 Arrow（重みも Arrow）** — 重みのエコシステム（GGUF/safetensors/
  llama.cpp/Ollama）から外れ、quant block 表現も不自然。Arrow は columnar
  I/O とスキャン投影に限定。
- **safetensors container を丸ごと 1 block** — dedup 単位が失われ、
  shard 部分取得もできない。header(JSON)+aligned data という構造は
  manifest+raw-leaf 分解と同型なので、分解して格納する。
- **KV-cache も CID 化** — merkle 化の恩恵（検証・dedup）が ephemeral データ
  では回収できず、latency を直撃する。却下。

## Migration steps

1. `kotoba-lang/inference`: `:kotodama/digest` に加えて
   `:kotodama/model-cid`（manifest CID）を contract に追加、validate を拡張。
2. tensor chunker（quant-block 整列）+ manifest builder を
   `kotoba-lang/dag-cbor` / `multiformats` の上に CLJC で実装
   （raw leaf は encode 不要なので純関数は境界計算のみ）。
3. `kotoba-lang/num`: typed raw buffer の host 境界を追加
   （`from-bytes` / `->bytes`、dtype タグ）。
4. `kotoba-lang/net`: shard→CID 集合の導出と want-list 生成を
   EDN semantics として追加（transport は従来どおり adapter に先送り）。
5. Arrow IPC は必要になった時点で「frame = raw leaf」の 1 契約だけ足す
   （datom スキャン投影は別 ADR）。
