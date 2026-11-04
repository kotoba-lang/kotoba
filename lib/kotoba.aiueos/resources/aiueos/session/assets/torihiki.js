/* Torihiki app of the hosted session (JUN-822): devnet / demo only.

   Runs in the user's browser and talks straight to the node endpoint the user
   typed. It has no default endpoint, sends nothing until the user approves the
   displayed operation, and signs nothing unless the node says its chain id is a
   devnet. A denial sends nothing; redirects are refused.

   The signing payload and the account id derivation are the engine's own
   (torihiki.auth/signing-payload, torihiki.address/derive), written out here
   because this page has no engine. They are checked against vectors the engine
   produced (test/session/torihiki-vectors.json, scripts/session-torihiki-test.js);
   a node whose payload has a different number of fields rejects every signature
   as bad-signature, so FIELDS below must follow the node's engine version. */
(function () {
  "use strict";

  var FIELDS = 37; // f0 .. f36 of torihiki.auth/tx-fields at the vectors' engine version
  var FLOOR = 100000, SPACE = 35184372088832; // torihiki.address
  var enc = new TextEncoder();

  function b64(buf) {
    var a = new Uint8Array(buf), s = "";
    for (var i = 0; i < a.length; i++) s += String.fromCharCode(a[i]);
    return btoa(s);
  }

  // torihiki.address/derive: the first six bytes of SHA-256 over the base64 text of the key.
  function deriveAccount(pubB64) {
    return crypto.subtle.digest("SHA-256", enc.encode(pubB64)).then(function (d) {
      var b = new Uint8Array(d), acc = 0;
      for (var i = 0; i < 6; i++) acc = acc * 256 + b[i];
      return FLOOR + (acc % SPACE);
    });
  }

  // torihiki.auth/signing-payload for the transactions this page builds.
  // Positions: f0 tx, f1 market, f2 side (keyword, so ":buy"), f3 level, f4 qty, f5 flags, f6 oid.
  function signingPayload(chain, account, nonce, tx) {
    var f = [];
    for (var i = 0; i < FIELDS; i++) f.push("");
    f[0] = tx.tx;
    f[1] = tx.market === undefined ? "" : String(tx.market);
    if (tx.side !== undefined) f[2] = ":" + tx.side;
    if (tx.level !== undefined) f[3] = String(tx.level);
    if (tx.qty !== undefined) f[4] = String(tx.qty);
    if (tx.flags !== undefined) f[5] = String(tx.flags);
    if (tx.oid !== undefined) f[6] = String(tx.oid);
    return "torihiki/tx/v1\nchain=" + chain + "\naccount=" + account + "\nnonce=" + nonce + "\n" +
      f.map(function (v, i) { return "f" + i + "=" + v; }).join("\n") + "\n";
  }

  function signEnvelope(priv, pubB64, chain, account, nonce, tx) {
    return crypto.subtle.sign({ name: "Ed25519" }, priv, enc.encode(signingPayload(chain, account, nonce, tx)))
      .then(function (sig) { return { tx: tx, account: account, nonce: nonce, pubkey: pubB64, sig: b64(sig) }; });
  }

  // Only https, or http on this machine. Returns the origin, or null.
  function endpointOrigin(text) {
    var u;
    try { u = new URL(String(text || "").trim()); } catch (e) { return null; }
    var local = u.hostname === "localhost" || u.hostname === "127.0.0.1" || u.hostname === "[::1]";
    if (u.protocol === "https:" || (u.protocol === "http:" && local)) return u.origin;
    return null;
  }

  function isDevnet(chainId) { return typeof chainId === "string" && /devnet/i.test(chainId); }

  var api = { FIELDS: FIELDS, deriveAccount: deriveAccount, signingPayload: signingPayload,
              signEnvelope: signEnvelope, endpointOrigin: endpointOrigin, isDevnet: isDevnet };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }

  var root = document.getElementById("torihiki");
  if (!root) return;
  function $(sel) { return root.querySelector(sel); }
  function slot(name) { return $('[data-slot="' + name + '"]'); }
  function say(text) { slot("tk-result").textContent = text; }
  function bindTk(name, text) { root.querySelectorAll('[data-bind="' + name + '"]').forEach(function (n) { n.textContent = text; }); }
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function put(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  // --- session key: non-extractable Ed25519 in IndexedDB --------------------
  function idb() {
    return new Promise(function (ok, no) {
      var r = indexedDB.open("itonami-torihiki", 1);
      r.onupgradeneeded = function () { r.result.createObjectStore("keys"); };
      r.onsuccess = function () { ok(r.result); };
      r.onerror = function () { no(r.error); };
    });
  }
  function idbGet(db, k) {
    return new Promise(function (ok, no) {
      var q = db.transaction("keys").objectStore("keys").get(k);
      q.onsuccess = function () { ok(q.result); }; q.onerror = function () { no(q.error); };
    });
  }
  function idbPut(db, k, v) {
    return new Promise(function (ok, no) {
      var t = db.transaction("keys", "readwrite"); t.objectStore("keys").put(v, k);
      t.oncomplete = function () { ok(); }; t.onerror = function () { no(t.error); };
    });
  }
  var session = null;
  function loadSession(create) {
    if (session) return Promise.resolve(session);
    return idb().then(function (db) {
      return idbGet(db, "session-v1").then(function (rec) {
        if (rec) return rec;
        if (!create) return null;
        return crypto.subtle.generateKey({ name: "Ed25519" }, false, ["sign", "verify"]).then(function (kp) {
          return crypto.subtle.exportKey("raw", kp.publicKey).then(function (raw) {
            var made = { priv: kp.privateKey, pub: b64(raw) };
            return idbPut(db, "session-v1", made).then(function () { return made; });
          });
        });
      });
    }).then(function (rec) {
      if (!rec) return null;
      return deriveAccount(rec.pub).then(function (acc) { session = { priv: rec.priv, pub: rec.pub, account: acc }; return session; });
    });
  }
  function showSession(chain) {
    var lines = [];
    lines.push(session ? "セッション鍵: " + session.pub.slice(0, 12) + "…\nアカウント: " + session.account : "セッション鍵: まだありません（最初の操作で端末内に作ります）");
    lines.push("鍵は端末の外に出ません。ウォレットではなく、devnet 専用の使い捨てです。");
    if (chain) lines.push("チェーン: " + chain);
    bindTk("tk-session", lines.join("\n"));
  }

  // --- consent ---------------------------------------------------------------
  var busy = false;
  function approve(title, detail) {
    return new Promise(function (resolve) {
      var host = slot("tk-approval"), tpl = document.getElementById("dapp-approval");
      if (!host || !tpl) { resolve(false); return; }
      host.textContent = ""; host.appendChild(tpl.content.cloneNode(true));
      var t = host.querySelector('[data-bind="approval-title"]'), d = host.querySelector('[data-bind="approval-detail"]');
      t.textContent = title; d.textContent = detail; d.style.whiteSpace = "pre-line";
      function done(v) { host.textContent = ""; resolve(v); }
      host.querySelector('[data-action="approve"]').addEventListener("click", function () { done(true); });
      host.querySelector('[data-action="deny"]').addEventListener("click", function () { done(false); });
    });
  }

  // --- requests --------------------------------------------------------------
  function call(origin, path, opts) {
    var ctl = new AbortController(), timer = setTimeout(function () { ctl.abort(); }, 10000);
    var init = { method: (opts && opts.method) || "GET", credentials: "omit", cache: "no-store", redirect: "error", signal: ctl.signal };
    if (opts && opts.body !== undefined) { init.body = JSON.stringify(opts.body); init.headers = { "content-type": "application/json" }; }
    return fetch(origin + path, init).then(function (r) {
      return r.text().then(function (txt) {
        var j; try { j = JSON.parse(txt); } catch (e) { j = { raw: txt.slice(0, 200) }; }
        return { status: r.status, json: j };
      });
    }).finally(function () { clearTimeout(timer); });
  }
  function head(origin) {
    return call(origin, "/head").then(function (r) {
      var chain = r.json && r.json["chain-id"];
      if (!isDevnet(chain)) throw new Error("このノードのチェーン id は devnet ではありません（" + chain + "）。何も署名せず、何も送っていません。");
      showSession(chain);
      return chain;
    });
  }
  function pretty(j) { try { return JSON.stringify(j, null, 2); } catch (e) { return String(j); } }
  function intField(sel, min) {
    var el = $(sel), v = el ? el.value.trim() : "";
    if (!/^\d+$/.test(v) || Number(v) < min || Number(v) > Number.MAX_SAFE_INTEGER) return null;
    return Number(v);
  }

  var DATA = {
    "read-quotes": "市場 id",
    "read-account": "アカウント id",
    "request-devnet-funds": "アカウント id",
    "submit-order": "取引（市場・売買・価格・数量・フラグ）、公開鍵、署名"
  };

  // plan: { op, requests:[text], data:text, run:function(origin, chain?) -> Promise<text>, needsKey:bool }
  function execute(plan) {
    if (busy) { say("ほかの操作を実行中です。"); return; }
    var origin = endpointOrigin(($("#tk-endpoint") || {}).value);
    if (!origin) { say("接続先は https のアドレス（この端末の http://localhost も可）で入力してください。何も送っていません。"); return; }
    put("itonami.torihiki.endpoint", origin);
    busy = true;
    var prep = plan.needsKey ? loadSession(true) : loadSession(false);
    prep.then(function () {
      if (plan.needsKey && !session) throw new Error("セッション鍵を作れませんでした。");
      showSession();
      var detail = "サービス: Torihiki devnet\nエンドポイント: " + origin + "\n操作: " + plan.op +
        "\nリクエスト: " + plan.requests(session).join(", ") + "\n送るデータ: " + plan.data(session) +
        "\n注意: devnet のみ。実資金は扱いません。";
      return approve("承認が必要です: " + plan.op, detail);
    }).then(function (ok) {
      if (!ok) { say("拒否しました。何も送信していません。"); return null; }
      return plan.run(origin).then(function (text) { say(text); });
    }).catch(function (e) {
      say("失敗しました: " + (e && e.message ? e.message : e));
    }).finally(function () { busy = false; });
  }

  var tx = null; // the transaction chosen by the clicked button, read from the form
  var PLANS = {
    "quotes": function () {
      var m = intField("#tk-market", 1); if (m === null) { say("市場 id は 1 以上の整数です。"); return null; }
      return { op: "read-quotes", needsKey: false,
        requests: function () { return ["GET /head", "GET /market?id=" + m, "GET /book?market=" + m + "&depth=10"]; },
        data: function () { return DATA["read-quotes"] + " " + m },
        run: function (origin) {
          return head(origin).then(function () {
            return Promise.all([call(origin, "/market?id=" + m), call(origin, "/book?market=" + m + "&depth=10")]);
          }).then(function (rs) { return "市場:\n" + pretty(rs[0].json) + "\n\n板:\n" + pretty(rs[1].json); });
        } };
    },
    "account": function () {
      return { op: "read-account", needsKey: true,
        requests: function () { return ["GET /head", "GET /account?id=" + session.account]; },
        data: function () { return DATA["read-account"] + " " + session.account; },
        run: function (origin) {
          return head(origin).then(function () { return call(origin, "/account?id=" + session.account); })
            .then(function (r) { return "口座 (HTTP " + r.status + "):\n" + pretty(r.json); });
        } };
    },
    "faucet": function () {
      return { op: "request-devnet-funds", needsKey: true,
        requests: function () { return ["GET /head", "POST /faucet"]; },
        data: function () { return DATA["request-devnet-funds"] + " " + session.account; },
        run: function (origin) {
          return head(origin).then(function () { return call(origin, "/faucet", { method: "POST", body: { account: session.account } }); })
            .then(function (r) { return "devnet 資金の請求 (HTTP " + r.status + "):\n" + pretty(r.json); });
        } };
    },
    "order": function (side) {
      var m = intField("#tk-market", 1), level = intField("#tk-price", 1), qty = intField("#tk-size", 1);
      if (m === null || level === null || qty === null) { say("市場 id・価格（tick）・数量（lot）は 1 以上の整数です。"); return null; }
      var flags = ($("#tk-post") && $("#tk-post").checked ? 1 : 0) | ($("#tk-ioc") && $("#tk-ioc").checked ? 2 : 0) | ($("#tk-ro") && $("#tk-ro").checked ? 4 : 0);
      var t = { tx: "order", market: m, side: side, level: level, qty: qty, flags: flags };
      return submitPlan(t, "注文 " + (side === "buy" ? "買い" : "売り") + " 市場 " + m + " 価格 " + level + " tick 数量 " + qty + " lot フラグ " + flags);
    },
    "cancel-all": function () {
      var m = intField("#tk-market", 1); if (m === null) { say("市場 id は 1 以上の整数です。"); return null; }
      return submitPlan({ tx: "cancel-all", market: m }, "全注文の取消 市場 " + m);
    }
  };
  function submitPlan(t, label) {
    return { op: "submit-order", needsKey: true,
      requests: function () { return ["GET /head", "GET /account?id=" + session.account, "POST /tx"]; },
      data: function () { return label + "、公開鍵 " + session.pub.slice(0, 12) + "…、署名"; },
      run: function (origin) {
        var chain;
        return head(origin).then(function (c) { chain = c; return call(origin, "/account?id=" + session.account); })
          .then(function (a) {
            var nonce = (a.json && a.json["next-nonce"]) || 1;
            return signEnvelope(session.priv, session.pub, chain, session.account, nonce, t);
          })
          .then(function (env) { return call(origin, "/tx", { method: "POST", body: env }); })
          .then(function (r) { return label + "\nノードの返答 (HTTP " + r.status + "):\n" + pretty(r.json); });
      } };
  }

  root.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest("[data-tk]");
    if (!b) return;
    var k = b.getAttribute("data-tk");
    if (k === "save-endpoint") {
      var o = endpointOrigin(($("#tk-endpoint") || {}).value);
      if (!o) { say("接続先は https のアドレス（この端末の http://localhost も可）で入力してください。"); return; }
      put("itonami.torihiki.endpoint", o); $("#tk-endpoint").value = o; say("接続先を保存しました（この端末のみ。何も送っていません）: " + o); return;
    }
    var plan = k === "order-buy" ? PLANS.order("buy") : k === "order-sell" ? PLANS.order("sell") : PLANS[k] ? PLANS[k]() : null;
    if (plan) execute(plan);
  });

  var saved = get("itonami.torihiki.endpoint");
  if (saved && $("#tk-endpoint")) $("#tk-endpoint").value = saved;
  if (!(window.crypto && crypto.subtle && window.indexedDB)) {
    say("このブラウザは Ed25519 の署名か IndexedDB に未対応です。注文は送れません。");
  }
  loadSession(false).then(function () { showSession(); }).catch(function () { showSession(); });
})();
