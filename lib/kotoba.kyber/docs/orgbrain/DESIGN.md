# orgbrain — kyber 組織運営オントロジー + BPMN + リスクシミュレーション設計

**ADR (superproject 正本)**: `90-docs/adr/2609142000-kyber-org-ontology-bpmn-risk.kotoba`
**Status**: draft → accepted (owner review)

## 一行定義

orgbrain ≝ 法人・組織の運営プロセス全般を **ontology (kg schema) × BPMN プロセス定義 ×
リスク計算モデル** の三層で定義し、経営リスク・運営リスクを決定論的に計算・シミュレートする
kyber の拡張面。

## 三層アーキテクチャ

```
第1層  ontology    docs/orgbrain/org-ontology.schema.edn
                   組織の主体 (法人/役員/部門/従業員/契約) と
                   責任 (responsibility)・権限 (authority)・委任 (delegation)
                   を EAVT datom 形状の EDN schema で定義。
                   既存 org-omg-bpmn / org-omg-dmn レジストリと同一の思想。

第2層  process     docs/orgbrain/*.bpmn.edn
                   運営プロセスを BPMN 2.0 意味論の EDN ダイアグラムで定義。
                   各 task に :actor-role と :authority-required を紐付け、
                   第1層の権限定義と照合できる。

第3層  risk        lg/lg_kyber/graphs/org_risk.cljk (+ test)
                   決定論的リスク計算:
                     - RACI カバレッジ (責任の空白 = governance risk)
                   - 権限過集中 (1 role が全 critical task を持つ = concentration risk)
                   - 委任深度 (delegation chain の深さ = operational risk)
                   - SLA 余裕 (task SLA に対する resource 分配)
                   モンテカルロではなく純関数のスコアリング — 同一入力は同一出力。
```

## データモデル (第1層の核)

```clojure
;; entity kinds
{:orgbrain.entity/corporation  {:orgbrain/name string}
 :orgbrain.entity/role         {:orgbrain/name string
                                :orgbrain/level [:board | :exec | :manager | :staff]}
 :orgbrain.entity/person       {:orgbrain/role-id ref}
 :orgbrain.entity/task         {:orgbrain/name string
                                :orgbrain/critical? boolean
                                :orgbrain/sla-days integer}
 :orgbrain.entity/delegation   {:orgbrain/from-role ref :orgbrain/to-role ref
                                :orgbrain/authority string}}

;; RACI matrix: task × role → #{:responsible :accountable :consulted :informed}
;; authority: [:approve-spend :sign-contract :hire :fire :compliance :it-admin]
```

## リスク計算 (第3層の核) — 純関数、決定論

| 風險軸 | 関数 | 高リスク条件 |
|---|---|---|
| governance | `raci-coverage-risk` | accountable が無い critical task |
| concentration | `authority-concentration-risk` | 1 role が全 authority の ≥70% を保持 |
| delegation | `delegation-depth-risk` | root→leaf 委任が ≥3 段 |
| continuity | `single-point-of-failure-risk` | 1 person しか在席しない critical role |
| compliance | `approval-gap-risk` | sign-contract/approve-spend 権限を誰も保持しない |

各軸 0.0–1.0、総合 = 加重平均 (weights は schema 側で定義しコードは読むだけ)。

## 憲章ゲート (実装が違反したら却下)

1. リスク計算は**決定論的純関数**。LLM 呼び出しをスコアに混入しない (LLM は解釈レイヤのみ)。
2. 実在人物の名前をリスクスコアの入力にしない (role まで匿名化)。
3. evidence script は REFUSED banner + exit 0 で盲目を報告する。捏造しない。
4. wholesale 再生成禁止。schema/BPMN の追記は外科的。
5. 1 tick = 1 PR 上限。main 直 push 禁止。force-push 禁止。

## 担当 bot: orgbrain-maint

- profile: `~/.hermes/profiles/orgbrain-maint/` (donor: fake-report-maint)
- worktree: `~/.gftd/worktrees/orgbrain` (repo `kotoba-lang/kyber`)
- cron: 日次 04:40 JST (`40 4 * * *`)
- 反復種別 (日付で決定、重複 PR 防止):
  - 偶数日 = **計測反復**: evidence script を走らせ、既存 schema/BPMN と整合する追加のみ
  - 奇数日 = **拡張反復**: 未定義の運営プロセス (人事/財務/法務/IT/危機対応 の順) を 1 つ
    BPMN+schema に追加し、リスクモデルの軸が計算できることを test で確認
- 検証: `bb run_tests.cljk` が green であること (既存 13 tests + org_risk tests)。
