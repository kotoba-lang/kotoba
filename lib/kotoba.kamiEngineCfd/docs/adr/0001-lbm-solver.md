# ADR-0001: kami-cfd — clean-room LBM の設計と、自動車 Cd への校正の旅

- Status: Superseded as in-repo runtime (2026-07-01)
- Scope: historical `kami-cfd` D2Q9 / D3Q19 lattice-Boltzmann runtime, now represented by CLJC contracts
- 関連: 90-docs/adr/2606272330(CAE 共有 lib + seed + :lbm backend), aero-clj(:lbm 配線元)

## 課題

cae-solver の `:lbm` 高忠実度 backend として、Isaac/Cosmos では解けない空力 CFD を
clean-room・zero-dep の runtime として実装する。reduced-order(aero-clj `:rom-buildup`)が成分
build-up で Cd を相関するのに対し、こちらは流れ場を格子上で解いて運動量交換で抗力を測る。
最終目標は自動車 Cd(~0.3, Re≈1e6, 乱流・付着流)。

## 現在の決定

この repository は Rust solver runtime を保持しない。`src/kami_engine/cfd/contract.cljk`
を CFD request/result の authority とし、LBM/RANS/LES/GPU/native/remote solver は
別 adapter repository が EDN contract に準拠して実装する。

削除済み:

- `Cargo.toml` / `Cargo.lock`
- `src/*.rs`
- `tests/*.rs`

## 過去の決定（採用したスキームと、その理由＝校正の旅）

LBM を段階的に成熟させ、実車 Cd との残差の原因を一つずつ除去した。各段は前段の限界が
動機:

1. **D2Q9 BGK(2D 断面)**: 最小実装。運動量交換(Ladd)で断面 Cd。blunt>streamlined の
   ランキングは正しいが断面 Cd は車両 Cd ではない。
2. **D3Q19(3D 車両 Cd)**: 前面積正規化で真の車両 Cd。`:dim 2|3` で選択。
3. **並列化**: collide は per-cell 独立 → `std::thread::scope`(zero-dep)で分割。streaming は
   scatter 衝突を避けるため **pull 形式(gather)** に書き換え並列化。drag は read-only リダクション。
4. **Smagorinsky LES**: 単緩和 BGK は **laminar** かつ τ→½ で不安定(Re600 で NaN)。非平衡運動量
   フラックス Q_ab から渦粘性 ν_t=(Cs·Δ)²·S̄ を加え τ を局所的に上げる。→ 高 Re 安定化 ＋
   **乱流の Re 非依存プラトー**(box3d Cd 3.5→2.34→2.33 @Re150→3000→6000)を再現。
   ※ TRT も試したが magic parameter が高 Re で ω⁻→0 を強制し逆に不安定化 → 却下。
5. **free-slip 遠方境界**: 側/天井を無滑り跳ね返りから鏡面反射(REFLECT_Y/Z)へ。路面のみ
   no-slip(road)。閉じ込めによる Cd 膨張を除去(box3d 2.34→2.07)。
6. **実ジオメトリ voxel 化**: box/fastback プリミティブから、二値 STL + Ahmed body 生成 +
   `Body3::from_triangles`(列ごとレイ偶奇で中実化)へ。

## 帰結

- **検証**: Ahmed body(自動車 CFD の標準ブラフ体)を voxel 化。25° スラントは squareback より
  低抗力(ランキング正)。校正後 **~0.22 vs 実験 ~0.29(±25%)** = 認知された実測地形に乗った。
- **校正定数**(aero-clj): 残差(生値 ~1.8 vs ~0.3)の原因のうち **物理(LES)・境界(free-slip)・
  ジオメトリ(mesh)は解決**。残るは **グリッド解像度のみ**。よって校正定数は「精度不足」ではなく
  「粗格子の既知スケール差」を吸収するものとして**明示・文書化して保持**する。
- clean-room 不変条件(NVIDIA 等の外部コード非リンク)維持。zero external dep。
- `cargo test` green: 2D 3 + 3D LES 2 + mesh 3(STL round-trip / Ahmed slant ランキング含む)。

## 既知の限界 / 次段

- 絶対 Cd を ~0.3 に合わせるには **fine/large・低 blockage 格子** が必要 → 単一 CPU では非現実的。
  **GPU(wgpu)compute** が本筋(LBM は compute shader に好適)。kami-engine の wgpu スタックを
  再利用 or kami-cfd を同 workspace へ統合するのが次段。
- 既定 cargo target がリポ既定で wasm32 のため、ネイティブ実行/テストは
  `--target aarch64-apple-darwin`(host)を指定する。

## 却下案

- **BGK 単独で高 Re**: τ→½ で不安定。LES の渦粘性が必須。
- **TRT**: 高 Re で ω⁻→0 を強制し不安定化。
- **校正定数の即時撤廃**: 解像度由来の残差は GPU なしでは消えない。明示保持が誠実。

## Addendum (2026-07-16): ソルバーは portable CLJC として repo 内に復元

上記の「現在の決定」（2026-07-01、Rust 削除・CLJC contract のみ保持・solver は
別 adapter repo が実装）は、実際にはどの adapter repo にも実装されないまま
solver 自体が未実装の状態で放置されていた。com-junkawasaki/root の
`.cljc`/`.kotoba` ランタイム優先順位ルール（2026-07-10 改訂、Rust は新規/既存
問わず降格・`kotoba-lang/mesher`/`pnr`/`rtl`/`ic-packaging` と同じ
clj-wgsl migration パターン、ADR-2607010930）に従い、削除前の Rust
（commit `2958ba8`、`755fa13` の親）を git 履歴から復元し、`kami-cfd` /
`kami-cfd.mesh` / `kami-cfd.d3` として portable `.cljc` に忠実移植した
（詳細・設計判断はリポジトリ README 参照）。この addendum 以外の本文
（上記「現在の決定」を含む）は歴史的記録としてそのまま保持し書き換えない —
solver の実装状況の正本は README。物理設計（D2Q9→D3Q19→LES→free-slip→
実ジオメトリ voxel 化の校正の旅）はホスト言語が変わっただけで変更なし、
本 ADR の物理的な内容は今も正確。
