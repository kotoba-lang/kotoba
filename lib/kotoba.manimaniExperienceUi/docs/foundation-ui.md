# Foundation UI

Foundation UIは業務上の信頼を担当します。装飾テーマから独立し、Home / Inbox / Walk / Chatで同じ意味を保ちます。

## 情報階層

1. **Context** — org / repo / branch / visibility
2. **Intent** — user storyと達成条件
3. **State** — Issue / Agent / PR / Actions / Approval / Receipt
4. **Next action** — 一画面にprimary actionは原則一つ
5. **Evidence** — diff、log、check、actor、timestamp、URL

## Navigation

- Home: 仕事を選び、流れを預ける入口
- Inbox: 人間の判断、通知、外部入力
- Walk: agent loopの現在地、blocker、system dynamics loop
- Chat: repo/org/projectを文脈に会話し、previewを経て操作する

タブは常に同じ順序とラベルを保ち、アイコンだけにしません。現在タブは色だけでなく形とアクセシビリティ状態で示します。

## Controls

- 最小タップ領域: 44 × 44pt相当
- 本文: 原則16px以上。拡大200%で機能を失わない
- focus: 常に視認可能。DOM順と視覚順を一致させる
- disabled: 理由を隣接表示。権限不足と処理中を同じ表現にしない
- destructive: 動詞と対象を明記し、primary actionと離す
- loading: 受付済みか未受付かを明示する

## State grammar

| 状態 | 必須表示 |
|---|---|
| queued | 待ち理由、順番または再評価時点 |
| running | 実行主体、現在step、経過、stop |
| blocked | 原因、owner、解除条件、代替経路 |
| needs approval | 変更内容、影響範囲、approver |
| failed | 失敗step、証跡、retry/rollback |
| verified | 外部receipt、検証時刻、対象revision |

「Done」は外部の検証receiptが存在するときだけ使います。agentの発話だけで完了扱いにしません。

## Privacy and capability

visibilityとcapabilityを分離します。

- Visibility: public / internal / private
- Capability: read / triage / write / maintain / admin
- Sensitivity: public / internal / confidential / privileged

publicだから安全、privateだから書込み可能、とは推論しません。ChatとWalkでは実行前にactor、scope、対象repo、変更種別を表示します。secret、token、private内容をマスコットの台詞や通知previewへ漏らしません。

## Accessibility and motion safety

- `prefers-reduced-motion` では移動・回転を抑え、opacityまたは静的stateへ置換
- 自動回転は業務状態を示す低速motionに限定し、停止手段を用意
- flashingは3回/秒未満。強い画面振動を使わない
- sound/hapticsは補助。無音でも完全に理解可能
- contrastはWCAG AAを最低線とする
