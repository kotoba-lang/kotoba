// Shared synthetic fixtures for the client-runtime tests (KOTOBA-159 finding 9). Not real recipients.
export const DISCLOSURE = Object.freeze({
  recipient: 'テスト用の送り先（合成）',
  country: 'JP',
  data: Object.freeze(['テスト用の合成データ']),
  'special-care': false,
  purpose: 'テストのため',
  frequency: 'one-time',
  withdrawal: 'テストのため取り消しの設定はありません',
});
