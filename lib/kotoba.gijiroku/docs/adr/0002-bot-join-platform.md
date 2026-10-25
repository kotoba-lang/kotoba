# ADR-0002: bot-join Platform — meeting access without an OAuth app

- Status: accepted (2026-07-03)
- 関連: ADR-0001（gijiroku 本体設計）、superproject ADR-2607031100（「録音取得方式の検討」で
  bot 参加方式を charter 外・follow-up と位置づけた箇所）

## Context

ADR-0001／superproject ADR-2607031100 は録音取得の既定を公式クラウド API
（Zoom Cloud Recording API / Google Workspace Meet REST API / Microsoft
Graph）に置いた。しかしこれらは **例外なく OAuth app 登録・admin consent が
前提**（Zoom は Server-to-Server OAuth app、Google Meet は Workspace
service account + domain-wide delegation、Teams は Entra ID app registration）
であり、各社ともここを迂回する API キーのみのアクセス経路を提供していない
（録音・文字起こしという機微データを守るための意図的な設計）。

一方、`MeetingPlatform` を protocol にしてあるのは正にこの想定のためで、
**会議 URL だけで参加するヘッドレスブラウザ bot**（Otter.ai/Fireflies/Read.ai
等が実際に採る方式）を第二の実装として差し込めば、OAuth app 登録なしで
アクセスできる。既存資産 `kotoba-lang/playwright`（Playwright for Java の
Clojure ラッパー、`launch`/`goto`/`click`/`fill`/`wait-for` を提供）がある。

## Decision

`gijiroku.bot-join`（`:bot-join` alias、`io.github.kotoba-lang/playwright`
依存 — **gijiroku のコア deps ではない**、OAuth-API 経路を使うだけの消費者に
Playwright を強制しない）を追加し、`MeetingPlatform` の第二実装とする。

1. **join-url**: 各社の「カレンダー招待に貼るリンクをブラウザで開く」のと
   同じ web-client 直リンク（Zoom `zoom.us/wc/join/{id}?pwd=`、Google Meet
   `meet.google.com/{code}`、Teams `teams.microsoft.com/v2/?meetingjoin=true#/l/meetup-join/{id}`）。
   API 呼び出しは一切ない。
2. **join!**: `playwright-clj` で headless Chromium を起動 → 名前入力 →
   参加ボタン → 「会議内」セレクタが hidden になる（＝会議終了）まで
   ポーリング → 退出。**BLOCKING**（実会議時間そのまま掛かるため
   StateGraph ノードから直接呼ばない — scheduler/worker から呼ぶ）。
3. **音声キャプチャは host-caps 注入**（`:audio-start-fn`/`:audio-stop-fn`）。
   既定実装は ffmpeg が PulseAudio の null-sink monitor を録る
   （sink 自体のルーティングは運用側の前提、Xvfb+PulseAudio+ffmpeg の
   ホスト構成は「デプロイの関心事」であり gijiroku のコードでは作らない）。
4. **文字起こしは新規 `gijiroku.transcriber` port**（bot-join 経由の録音は
   各社ネイティブ transcript を持たないため）。既定 `mock-transcriber`、
   実装 `gijiroku.whisper`（OpenAI 互換 `/v1/audio/transcriptions`、
   verbose_json、host-caps 注入）。**話者分離（diarization）は無い**
   （verbose_json に speaker フィールドが無いため、:speaker は常に nil —
   公式 API 経路との明確な機能差として記録する）。
5. **会議メタデータの発見手段が無い**ため（公式 API と違い bot-join には
   `GET /meetings/{id}` に相当するものが無い）、`register-meeting!` で
   呼び出し側が事前登録する（カレンダー連携等、呼び出し側が既に持っている
   情報を渡すだけ）。未登録の external-id は最小限のスタブを返す。

`gijiroku.operation`（StateGraph 本体）・`gijiroku.governor`（PrivacyGovernor）
は無変更 — bot-join は `:recording/fetch`/`:transcript/ingest` の **別ソース**
というだけで、同意・テナント分離・redaction・no-actuation の不変条件は
そのまま全部門する。

## Consequences

- (+) OAuth app 登録・admin consent が一切不要（会議 URL だけ）。組織側で
  ネイティブ録音/文字起こし機能が有効化されていない会議も記録できる。
- (+) `MeetingPlatform` を protocol にした設計判断（ADR-0001）が効いて、
  `operation.cljc`/`governor.cljc` を一切変更せず追加できた。
- (−) live 未検証（実会議・Xvfb/PulseAudio/ffmpeg ホストが本環境に無い）。
  オフライン検証済みなのは join-url 構築・host-caps 注入契約・
  Whisper multipart body 形状のみ（`test/gijiroku/bot_join_test.cljk`
  `test/gijiroku/whisper_test.cljk`）。
- (−) join-flow セレクタは各社 web client の DOM に依存する UI ヒューリス
  ティックで、UI 変更で壊れる（namespace docstring に明記）。
- (−) 話者分離が無い（Whisper 経由の STT は speaker を返さない）。
- (−) 各社 ToS 上、無許可の自動参加 bot を制限する場合がある — 組織ごとに
  有効化前の評価が必要（superproject ADR-2607031100 で既出の留保）。

## References

- `orgs/kotoba-lang/playwright`（Playwright for Java の Clojure ラッパー）
- `src/gijiroku/bot_join.cljk` / `src/gijiroku/transcriber.cljk` / `src/gijiroku/whisper.cljk`
- superproject ADR-2607031100 の「録音取得方式の検討」節
