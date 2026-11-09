# JUN-502 drag遅延 分離測定計画

- issue: JUN-502（urgent, In Progress）
- 分析モデル: agy `gemini-3.8-flash-high`（測定・反復分析向け選定）
- 基準: origin/main 73e3c67a0（PR #965はMERGED済み）
- 方法: `lib/kotoba.aiueos/os/aiueos/native/desktop.kotoba` の実読＋QEMU手順提案
- 状態: 計画のみ。QEMU実測・6600H実機受入は未実施

## (1) input poll → present-frame 同期実行ループ

- `desktop-loop` が `clock-step` 後に `drain-input`（PS/2: `poll-input`、
  `consume-mouse-byte`、`apply-mouse-packet`）および `usb-input` を呼ぶ。
- 入力変化があれば同一ターン内で即座に `present-frame` を同期呼び出しし、
  完了後に `kernel-pause` で次ターンを待機する。

## (2) drag座標更新 → frame ops / damage / 合成

- 座標更新: `apply-pointer-delta`（ドラッグ判定・`drag-sample`・
  `titlebar-drag-id`）→ `move-window-id` でウィンドウ座標更新
  （解除時は `drag-release`、`inertia-step`）。
- Ops生成: `present-frame` 内で `aiueos-browser-frame2` を呼び op 列を生成。
- Damage算出: `frame-damage` → `list-damage`（`op-differs`、
  `translated-damage`、`damage-outside`、`damage-rect`）、`dirty-start` /
  `dirty-rect`（64x64セル単位の汚染フラグ化）、`close-blur-damage` /
  `blur-damage-pass`（ブラー周辺依存域の拡張）。
- 合成: `present-composited` → `present-scene`（完了後に `cache-ops`）。

## (3) tile-copy の GOP 読戻し・差分書き込み

- 差分走査: `present-scene` → `tile-walk`（`dirty-at`、`dirty-limit` で
  汚染セルを走査、`tile-blurs` で局所ブラー段数に応じたタイル幅を決定）。
- スクラッチ描画: `render-tile` → `present-ops`（`fill-rect`、
  `material-rect`、`capture-blur-row`）によりエフェクト領域へ中間描画。
- GOP読戻し: 直接/参照描画時（`tileMode=0`）は `backdrop-pixel`、
  `blend-page-span`、`framebuffer-pixel`、`cursor-pixels` が
  `kernel-load-u32-4k` でVRAMを直接読戻す。タイル描画時は `backdrop-pixel`
  が `tile-offset` 経由でスクラッチから読み GOP読戻しを回避（0回化）。
- 差分書込: `render-tile` → `tile-copy` → `tile-copy-span` により、
  汚染タイルの確定ピクセルのみを u64/u32 スパンでGOP VRAMへ一括書き込み
  （`tileStores` を加算）。

## (4) QEMU 分離測定手順と指標

1. CPU合成/blur分離: F1（`reduced` モード）ON/OFF を切替え、ブラー
   （`blur-row`、`material-rows`）有無による `sceneTileRasterCycles` の
   差分を比較。
2. FB read/write分離: F3（強制参照描画 `tileMode=0`、GOP読戻し発生）と
   タイル描画（`tileMode=1`、GOP読戻しゼロ・`tile-copy` のみ）を比較し、
   `sceneTileCopyCycles` と転送バイト数を計測。
3. input再poll待ち分離: QMP `mouse_move` 注入時刻とゲスト入力受信刻印
   （ctx word 117）の差、および `present-frame` 終了から次入力検出までの
   アイドル待機時間を比較。

測定指標:

- frame time (p50 / p95 / p99): `sceneTotalCycles`（PIT補正ms換算）の分位点分布。
- input queue age: QMPイベント送出時刻 〜 ゲスト側 `poll-input` /
  `usb-input` 処理開始のタイムスタンプ差。
- input-to-present: 入力検出（ctx word 117）から `present-frame` 描画完了
  （word 116/118）までの経過時間。
- FB read/write量: GOP読戻しバイト数（参照描画の読込回数x4B vs タイル時0B）と
  GOP書込量（`tileStores` x 4B）。

## 次の作業

- 上記(4)のQEMU実測（同一artifact・解像度・refresh固定、1窓/4窓・重なり・
  effects on/off）。
- 6600H実機でのowner受入（追従が滑らか・ちらつき無し）。
- QEMU測定と実機受入を混ぜて報告しない（issueの受入条件どおり分離記録）。
