# ADR 0001: Kinetic Companion UI

- Status: Accepted
- Date: 2026-07-21

## Context

manimaniはGitHub業務UIとして高い情報精度が必要だが、単なる管理dashboardでは「流れを預ける」という価値を表現できない。一方、全面的なtoy UIはprivate/public、blocker、approval等の重大情報を曖昧にする。

## Decision

UIをFoundationとExperienceの二層に分ける。FoundationはHIG/WCAGとGitHubの状態モデルに従う。Experienceは独自のKinetic Companion UIとし、まにまに君の運動を入力受付、実行、待機、blocker、receiptへ対応させる。

キャラクターは機能の代替にしない。ユーザーの連打やshakeは運動へのimpulseとfeedbackのみを生み、権限、課金、agent progressを偽装しない。

## Consequences

- mascotなし／reduced-motionでも全journeyを完遂できる必要がある。
- system stateとcharacter stateの対応表をテスト対象にする。
- 成功はGitHub等の外部receipt後にのみ祝う。
- 見た目を既存ゲームやキャラクターに寄せず、振る舞いの原則として独自性を作る。
