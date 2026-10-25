(ns daichou.receipt
  "agent の行為1件ぶんの受領証。

   **この台帳の主張は『承認と実行が同じ記録の中にある』の一点である。**
   記録するだけの製品はすでに無料でもあり有償でもある(microsoft/agent-governance-toolkit、
   Microsoft Agent 365、Asqav)。ここが違うのは、`:approval` を欠いた受領証を
   **作れない**ことにある — 承認の無い行為は、後から承認を書き足せない。

   受領証は pure な値で、連鎖は前件のハッシュで結ぶ:
     :receipt/action-ref     行為の正規形の SHA-256
     :receipt/previous-hash  直前の受領証のハッシュ(先頭は 0 詰め)
     :receipt/hash           この受領証自身の正規形の SHA-256
   `:receipt/hash` は自分自身を含まない部分から計算するので、再計算で検証できる。"
  (:require [daichou.canonical :as canonical]
            [daichou.hash :as h]))

(def ^:private required-approval-keys
  #{:approval/by :approval/decision :approval/policy-version})

(defn- check-approval! [approval]
  (when-not (map? approval)
    (throw (ex-info "受領証には :approval が要る。承認の無い行為は記録できない"
                    {:approval approval})))
  (let [missing (remove (partial contains? approval) required-approval-keys)]
    (when (seq missing)
      (throw (ex-info "承認は「誰が・何を決めたか・どの policy 版で」が揃って初めて承認になる"
                      {:missing (vec missing) :approval approval}))))
  (when-not (contains? #{:allow :deny :review} (:approval/decision approval))
    (throw (ex-info "決定は :allow / :deny / :review のいずれか"
                    {:decision (:approval/decision approval)}))))

(defn make
  "受領証を1件作る。

   `action` は行為(agent・種別・対象など)、`approval` は誰がどの policy 版で
   何を決めたか。`previous-hash` は直前の受領証の :receipt/hash、先頭なら nil。"
  [{:keys [action approval previous-hash at]}]
  (when-not (map? action)
    (throw (ex-info "行為が無い受領証は作れない" {:action action})))
  (check-approval! approval)
  (let [body {:receipt/action action
              :receipt/approval approval
              :receipt/at (or at (throw (ex-info "受領証には時刻が要る" {})))
              :receipt/action-ref (h/sha256 (canonical/write action))
              :receipt/previous-hash (or previous-hash h/zero-hash)}]
    (assoc body :receipt/hash (h/sha256 (canonical/write body)))))
;; 注: make が計算する hash は body(署名を含まない)に対するもので、
;; recompute-hash の除外集合と一致している必要がある。ずれると「作った直後の
;; 受領証が intact? を通らない」という形で必ず test に出る。

(defn recompute-hash
  "受領証の :receipt/hash を、その中身から計算し直す。

   **:receipt/signature も除く。**署名はハッシュ*の上*にあるので、ハッシュ*の中*に
   入れられない — 入れると、署名を足した瞬間にハッシュが変わり、その受領証は
   自分自身と整合しなくなる(実際に最初の実装がそうなっており、test が掴んだ)。
   同じ理由で、署名を後から差し替えても連鎖のハッシュは動かない。壊れた署名は
   `signature-valid?` が落とす — 検出の担当を分けてある。"
  [receipt]
  (h/sha256 (canonical/write (dissoc receipt :receipt/hash :receipt/signature))))

(defn intact?
  "この受領証1件が、書かれた内容と整合しているか。"
  [receipt]
  (and (= (:receipt/hash receipt) (recompute-hash receipt))
       (= (:receipt/action-ref receipt)
          (h/sha256 (canonical/write (:receipt/action receipt))))))

(defn sign
  "受領証に署名を足す。

   署名するのは `:receipt/hash` — それが行為・承認・前件ハッシュのすべてを覆って
   いるので、連鎖上の位置ごと固定できる。

   `signer` は `hex-message -> hex-signature` の関数。**鍵はここに来ない** —
   呼び出し側(kagi 経路)が閉じ込めたまま署名だけを返す。`by` は署名した主体の
   識別子で、`:approval/by`(承認した主体)とは**別物**。fleet が書き、governor が
   承認する構成では両者は一致しない。"
  [receipt {:keys [signer by public-key]}]
  (when-not (:receipt/hash receipt)
    (throw (ex-info "ハッシュの無い受領証には署名できない" {})))
  (when-not (and (fn? signer) (string? by) (string? public-key))
    (throw (ex-info "signer(関数) / by(署名主体) / public-key が要る" {:by by})))
  (assoc receipt :receipt/signature
         {:signature/alg :ed25519
          :signature/by by
          :signature/public-key public-key
          :signature/value (signer (:receipt/hash receipt))}))

;; **intact? と signature-valid? は担当が違う。**署名は :receipt/hash に対する
;; ものなので、本文だけ書き換えられた受領証では署名は当たったままになる(捕まえるのは
;; intact?)。逆に本文とハッシュを両方書き換えられた受領証は intact? を通るが、
;; 新しいハッシュに対する署名を持たないので signature-valid? が落とす。
;; **どちらか一方だけを見て「無事」と判断すると、対応する側の改ざんを見逃す。**
;; chain/verify が両方を順に見るのはこのため。
(defn signature-valid?
  "署名がこの受領証のハッシュに対して正しいか。`verifier` は
   `[public-key message signature] -> bool`。署名が無い受領証は false ではなく
   nil を返す — 『署名が無い』と『署名が壊れている』を混ぜない。"
  [receipt verifier]
  (when-let [s (:receipt/signature receipt)]
    (boolean (verifier (:signature/public-key s)
                       (:receipt/hash receipt)
                       (:signature/value s)))))
