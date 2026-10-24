# Navigation and application shell

## Tab selection motion

tab選択は「ページが切り替わった」と「現在地」を同時に伝えます。

1. active pillが選択先へ220msのspringで移動する
2. 新しいicon/labelが1.04倍、上へ2pxだけliftする
3. 前画面は80msで薄くなり、新画面は160msで現れる
4. labelとtab幅は変えず、layout shiftを起こさない
5. hapticは選択成立時に一度だけ。再選択では鳴らさない

reduced-motionではpillを瞬時に移し、色・太さ・`aria-current`だけを変えます。bounce、連続pulse、全画面slideは使いません。

## Chat exception

Chatでcomposerへfocusしたらbottom tab barを180msで下へ退避し、safe-areaにcomposerを固定します。keyboardを閉じても会話中は隠したままにし、画面上部の「‹ Home」またはsystem back gestureで離脱します。

- tab barを隠しても脱出経路を必ず残す
- keyboard animation curve/durationへ追従する
- tool previewのapprove/rejectが隠れたらcomposerより上へscrollする
- voice input、hardware keyboard、floating keyboardでも同じ状態モデルを使う
- desktopの十分な高さではtabを残してよい

## Launch

Launch画面はbrand animationではなく、起動状態の正確な通知を担当します。

- まにまに君とマニ車を中央に置く
- `Local inventory → GitHub session → Agent harness` の現在stepを表示
- 2秒を超えたら待ち理由、offline継続、診断を表示
- session復元前にHomeを偽表示しない
- reduced-motionでは静止mascotとstep labelを使う

## Profile

Profileは人格ページではなく、actorとauthorityの確認場所です。

- GitHub identity、active org、GitHub App installation
- device-local identityとagent identityを分離
- repo capabilityの要約とprivate data boundary
- usage/tokenは煽らず、期間、provider、上限を明記
- sign out、credential revoke、data exportを提供

## Settings

設定は次の4群に限定します。

- Experience: motion、sound、haptics、celebration density
- Agents: Codex CLI、default loop、approval policy、concurrency
- GitHub: installations、repo access、sync、receipt policy
- Accessibility & Privacy: reduced motion、contrast、text size、telemetry、local retention

危険な設定変更には影響範囲と復旧方法を表示します。設定変更が現在のrunへいつ反映されるかも明記します。
