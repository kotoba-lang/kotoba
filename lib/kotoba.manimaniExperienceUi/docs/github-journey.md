# GitHub journey

## Core story

> ユーザーとして、org/repoの流れをまにまに君へ預け、agentと一緒にIssueから検証済みreceiptまで歩きたい。いつでも介入でき、blockerと根拠を確認できる。

## Home — choose and entrust

1. org → repo → projectを選ぶ
2. visibility、capability、未処理件数を確認する
3. next storyまたはIssueを選ぶ
4. loop（BMC / Lean / Design等）とagentを割り当てる
5. 「流れを預ける」でpreviewを開き、scopeを確認して開始する

中央のまにまに君は常時低速で回る。押下やshakeは応援feedbackであり、primary actionや承認を代行しない。

## Inbox — decide

人間にしか決められないものを集めます。通知一覧ではなく、承認、質問、競合、security、外部変更を「必要な判断」としてまとめます。各項目は影響、期限、推奨案、保留時の結果を示します。

## Walk — observe and intervene

Walkは線形stepperではなく、system dynamics loopを螺旋状に歩く画面です。

`Observe → Frame → Change → Verify → Learn → Observe'`

各周回はIssue、agent run、commit、PR、Actions、receiptへリンクします。blockerは経路上の障害物として、原因・owner・解除条件・滞留時間を表示します。ユーザーはpause、redirect、retry、take overを選べます。

## Chat — converse and act

Chatは会話と操作を分けませんが、発話と実行は区別します。

1. context chipでorg/repo/project/branchを固定
2. agentが提案と根拠を提示
3. issue作成、loop開始、PR操作はtool previewとして表示
4. user approvalまたは事前設定したpolicyで実行
5. tool resultをWalkの同じrunへ接続

## Receipt

最終画面は祝福より先に証跡を表示します。最低限、Issue、PR、merge commit、checks、deployment/verification、actor、timestampを含みます。receiptから次のObserveへ進み、螺旋の次周を始めます。
