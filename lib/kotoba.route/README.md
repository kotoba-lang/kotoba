# route

**kotoba-lang single-page apps の fragment ルーティング。** 純 `.cljc`（ブラウザに
触るのは `route.browser` の 1 ns だけ）、依存は `jp-go-dds` のみ。

```clojure
(require '[route.core :as route])

(def views
  [{:id :editor  :fragment "#/"        :label "Editor"}
   {:id :compare :fragment "#/compare" :label "Compare"}])

(route/validate! views)                    ; 壊れた表はここで落とす
(route/fragment->view views "#/compare?x=1")  ; => {:id :compare ...}
(route/nav views :compare)                 ; => hiccup（DADS の button、実リンク）
```

## なぜライブラリになったか

kotoba-lang の UI は single-page app（ADR-2608080100）で、**1 文書・1 バンドル・
1 mount**、画面の移動は state の変更であって location の変更ではない。それを実装する
ために 3 つの app が同じ約 76 行のファイルに辿り着いた —— `kami-app-daw` /
`kami-app-nle` / `kami-app-suji`。**先の 2 つは互いに 6 行しか違わず、うち 5 行は
view の表、1 行は docstring の単語である。** `kotoba-uiux` skill が「3 つ目の app が
抽出の trigger」と定めており、これがそれ。`jp-go-dds` には置かない —— routing は
markup でも CSS でもないため。

## 守っている 2 つの不変条件

**view はデータで、nav はそこから生成する。** dispatch に足して nav に足し忘れた
view は「live に見える dead code」になる。同じ表から nav を生成すれば、それは
構造的に起きない —— 誰かが憶えている必要が無い。`check-views` は、この性質を
保てない表を拒否する（id の重複・fragment の重複・既定 view の不在は、実行時には
「router のバグ」の顔をして現れる）。

**path ではなく fragment。** これらの app は静的ホスト（GitHub Pages、
cloud-itonami の sites plane）が配信する。`history.pushState` で `/editor` にすると、
**reload されるまで動く URL** ができ、reload した瞬間にホストが 404 を返す。
fragment はホストに送られないので、reload・ブックマーク・共有に耐える。
server rewrite を持つ経路でだけ pushState を選んでよい —— **実在することを確かめてから。**

## 検証

```bash
kbb -M:test                                       # JVM  — 6 tests / 36 assertions
kbb --backend sci --classpath "src:test:$(kbb -Spath)" scripts/nbb_test.cljk   # cljs — 同じ 6 / 36
kbb -M:lint                                       # 0 errors / 0 warnings
```

cljs 側でも回すのは、この ns が `.cljc` を名乗りつつ実際に使われるのはブラウザだから
——JVM だけのスイートは、そこで load しない ns にも緑を返す。runner には evidence
floor があり、スイートに到達できないときは exit **2**（0 でも 1 でもない）で終わる。
