(ns graphql.ports
  "GraphQL クエリ実行のための host-injected ポート。graphql-clj はプロトコルを定義し、
  ホストが具体的な実装を提供する(DB 参照・API 呼び出し・純粋データアクセス等)。
  graphql.execute のエグゼキュータは IResolver を純粋なオーケストレーション層として使う。"
  (:refer-clojure :exclude [resolve]))

(defprotocol IResolver
  "GraphQL フィールドの解決。フィールドセレクションごとに一度呼ばれる。

  - type-name:  解決中の GraphQL 型名 (String)
  - field-name: フィールド名 (String)
  - parent:     親オブジェクト(任意の値。ルートフィールドでは nil またはルート値)
  - args:        クエリからパースされた引数マップ {field-name → value}
  - ctx:         execute-query から透過的に渡されるコンテキスト値"
  (resolve [this type-name field-name parent args ctx]
           "type-name field-name parent args ctx → 解決された値"))
