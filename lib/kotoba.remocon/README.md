# remocon — learned IR remote-control codes as EDN

学習リモコン (learning remote) の素 — **IR リモコン信号を EDN として表し、判定・照合する
純 `.cljc` ライブラリ**。学習リモコンが外部ハード (IR 送受信モジュール) にやらせることを
「データの形と規則」として持ち、ハード輸送は一切持たない (host-injected transport)。

## What it IS

- **信号モデル**: 赤外線リモコンの 1 信号 = raw burst の時系列。microsecond 単位の
  `[:mark n]` / `[:space n]` ペア列 (LIRC の pulse/space と同じ形) を EDN vector で表す。
- **プロトコル判定**: NEC (含 NEC1 拡張 repeat) / Panasonic-KASEIKO / SONY SIRC 系の
  フレーミング判定。raw burst → 符号語 (bits) への deterministic な復号。
- **ProntoHex 対応**: Philips Pronto 形式 (`0000 006C ...` の hex 列) ↔ raw burst の
  相互変換。広く流通しているコード表 (IRDB 等) を直接読む入口。
- **符号語レベルの照合**: 同一プロトコル・同一アドレスの比較、デバイス/機能の
  対応表 (型番→コード) を載せるための EDN 台帳形式。

## What it is NOT

- **IR ハード輸送を持たない**: IR LED / 赤外線受信モジュール / LIRC daemon / Broadlink
  等への送受信は host-injected。本 lib は bytes を IR にしない。
- **コード表の大量収録をしない**: 型番対応表は台帳 *形式* を提供するだけで、
  実データは `:source` 付き datom として別途収録 (捏造ゼロ)。実測した 1 件も
  「測れた」まで書かない。
- **ハードウェア変調の物理シミュレーションをしない**: carrier 周波数は EDN の
  メタデータとして持ち、波形合成はしない。
