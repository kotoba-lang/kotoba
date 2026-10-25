# etzhayyim デザインシステム

etzhayyim エコシステム向けのデザインシステムライブラリです。Svelte 5 (Runes) と Tailwind CSS をベースに、アクセシビリティと高い再利用性を考慮して構築されています。

## 特徴

- **Svelte 5 (Runes)**: 最新の Svelte 機能を活用したリアクティブなコンポーネント。
- **Tailwind CSS**: 柔軟なスタイリングとデザイントークンの統合。
- **アクセシビリティ**: WAI-ARIA 基準に準拠し、必要に応じて Bits UI などのヘッドレス UI ライブラリを統合。
- **ライブラリ構成**: `svelte-package` を使用し、他の Svelte プロジェクトから簡単に利用可能。

## 技術スタック

- **Core**: Svelte 5
- **Styling**: Tailwind CSS
- **Headless UI**: [Bits UI](https://bits-ui.com/)
- **Build Tool**: Vite, svelte-package
- **Lint/Format**: Biome

## 開発ガイド

### インストール

```bash
npm install
```

### ビルド (ライブラリの生成)

```bash
npm run build
```
`dist/` ディレクトリに配布用ファイルが生成されます。

### 型チェック

```bash
npm run check
```

## コンポーネント一覧

### アトミック
- **Button**: 各種サイズ・バリエーション対応ボタン
- **Input / Textarea**: エラー状態・サイズ対応入力フィールド
- **Checkbox / Radio**: カスタムスタイルの選択コンポーネント
- **Select**: ドロップダウン選択
- **Label / Legend**: フォームラベル
- **Badge / StatusBadge**: 状態表示バッジ
- **Link / UtilityLink**: リンクコンポーネント

### 複合コンポーネント
- **Accordion / Disclosure**: 開閉式コンテンツ
- **Breadcrumbs**: パンくずリスト
- **NotificationBanner / EmergencyBanner**: 通知・緊急案内バナー
- **Carousel**: 画像・コンテンツスライダー
- **LanguageSelector**: 多言語切り替え

### v1 互換 (Deprecated)
- **Dialog**: ダイアログ（v2版へ移行予定）
- **Pagination**: ページネーション
- **ScrollToTopButton**: ページトップへ戻るボタン

## 利用方法

ライブラリとしてインストール後、各コンポーネントをインポートして使用してください。

```svelte
<script>
  import { Button } from '@etzhayyim/design-system';
</script>

<Button variant="solid-fill" size="md">
  アクション
</Button>
```

## ライセンス

MIT
