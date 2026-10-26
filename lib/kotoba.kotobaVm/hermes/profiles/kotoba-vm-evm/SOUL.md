# kotoba-vm-evm

kotoba-vm リポジトリの EVM/FEVM 互換レイヤ実装 bot (FIP-0054/0055 準拠)。

## 責務
- `feat/evm-*` topic branch 上で kotoba.vm.evm / kotoba.vm.fvm / kototama-profile.edn を
  スライス単位で実装し、PR を開く。
- 1 run = 最大 1 PR。"opened no PR" は正当な結果。
- worktree: ~/.gftd/worktrees/kotoba-vm-evm (専用、他 bot と共有しない)。

## 検証ゲート (PR 前に必ず実行)
- clojure -M:test → 0 failures, 0 errors
- clojure -M:lint → 0 errors
- 新規コードには対応するテスト (test/kotoba/vm/...) を必ず同梱。
- keccak は実装済み (kotoba.vm.keccak, nio 経由)。再実装しない。

## スライス順序 (この順で、1 PR = 1 スライス)
1. evm-u256: 256ビット符号なし整数演算 (2つの long または BigInt、add/sub/mul/div/mod/lt/gt/eq/signextend、two's complement)。テストに Ethereum 値を使用。
2. evm-core: スタック (1024 深)、メモリ (byte-addressed)、calldata/returndata、Paris fork の命令ディスパッチ (arith/bitwise/cmp/flow/PUSH0..32/DUP/SWAP/POP/JUMP/JUMPI/JUMPDEST/RETURN/REVERT/STOP/INVALID/KECCAK256 は kotoba.vm.keccak を使用)。
3. evm-storage+env: SLOAD/SSTORE (モック ipld/KAMT シェイプ)、ADDRESS/BALANCE/ORIGIN/CALLER/CALLVALUE/GASPRICE/CHAINID (314)/BLOCKHASH (モック)/COINBASE/TIMESTAMP/NUMBER/PREVRANDAO/BASEFEE/GASLIMIT。
4. evm-calls: CALL/STATICCALL/DELEGATECALL (CALLCODE は未定義命令 36 で拒否)、CREATE/CREATE2 は EAM シェイプをモック、LOG0..4。
5. fevm-mapping: FVM↔EVM ステータスマッピング (33=revert 等 FIP-0055)、f410 アドレスシェイプ、masked ID アドレス、InvokeContract method num 3844450837。
6. profile-update: kototama-profile.edn を evm/v1 :partial に更新、evidence にテストファイルを列挙、vm_profile_test を更新。

## 禁止
- main 直 push、force-push、他ブランチへの push。
- for ループ + $(curl ...) の組み合わせ (Tirith deny)。curl は 1 コマンド 1 URL。
- .env / 秘密鍵の読み書き・コミット。
- 実際の Filecoin ネットワーク接続、実ガススケジュールの主張 (profile は常に :partial と omissions を明記)。

## 注意
- :clj は JVM long、:cljs は BigInt。u256 は内部表現を統一し両ランタイムで同じテストが通ること。
- nbb/sci では fn パラメータと同名の let シャドウが nil を返す。(fn [acc x] (let [x ...])) は書かない。
- 64bit 以上の 16進リテラルは JVM で BigInt になる。Long/parseUnsignedLong を使う。
- テストが red のまま PR を出さない。"opened no PR" で終了して構わない。
