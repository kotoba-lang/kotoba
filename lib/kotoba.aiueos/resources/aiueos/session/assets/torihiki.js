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

  // --- pure view models (no DOM; tested in scripts/session-torihiki-test.js) ----
  // torihiki-chart.candle shape: { h, open, high, low, close, volume }, ticks and lots as integers.
  function rebucket(span, candles) {
    var out = [], cur = null;
    (candles || []).forEach(function (c) {
      var b = Math.floor(c.h / span) * span;
      if (cur && cur.h === b) {
        cur.high = Math.max(cur.high, c.high); cur.low = Math.min(cur.low, c.low);
        cur.close = c.close; cur.volume += c.volume;
      } else {
        cur = { h: b, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume };
        out.push(cur);
      }
    });
    return out;
  }
  // Geometry of the candle chart inside a W x H viewBox; empty data gives {empty:true}.
  function chartModel(cs, o) {
    o = o || {};
    var W = o.width || 640, H = o.height || 300, padR = 56, top = 10, priceH = 200, volTop = 220, volH = 58;
    cs = (cs || []).slice(-(o.max || 120));
    if (!cs.length) return { empty: true, width: W, height: H };
    var lo = Infinity, hi = -Infinity, vmax = 0;
    cs.forEach(function (c) { lo = Math.min(lo, c.low); hi = Math.max(hi, c.high); vmax = Math.max(vmax, c.volume); });
    if (hi === lo) { hi += 1; lo -= 1; }
    var pad = (hi - lo) * 0.05; hi += pad; lo -= pad;
    var plotW = W - padR - 8, step = plotW / cs.length, bw = Math.max(1, Math.min(14, step * 0.7));
    function y(v) { return top + (hi - v) / (hi - lo) * priceH; }
    var candles = cs.map(function (c, i) {
      var cx = 8 + step * (i + 0.5), up = c.close >= c.open;
      var yo = y(c.open), yc = y(c.close);
      return { h: c.h, x: cx, w: bw, up: up, yHigh: y(c.high), yLow: y(c.low), yTop: Math.min(yo, yc), bodyH: Math.max(1, Math.abs(yo - yc)),
               volY: volTop + volH - (vmax ? c.volume / vmax * volH : 0), volH: vmax ? c.volume / vmax * volH : 0 };
    });
    var yTicks = [];
    for (var i = 0; i <= 4; i++) { var v = lo + (hi - lo) * i / 4; yTicks.push({ y: y(v), label: String(Math.round(v)) }); }
    var xTicks = [], every = Math.max(1, Math.ceil(cs.length / 6));
    for (var j = 0; j < cs.length; j += every) xTicks.push({ x: candles[j].x, label: String(cs[j].h) });
    var last = cs[cs.length - 1].close;
    return { empty: false, width: W, height: H, plotRight: W - padR, candles: candles, yTicks: yTicks, xTicks: xTicks,
             lastY: y(last), lastLabel: String(last), volTop: volTop, volBottom: volTop + volH };
  }
  // Order book rows: nearest the touch first (as the node sends them); bars scaled by cumulative size.
  function bookModel(book) {
    var bids = (book && book.bids) || [], asks = (book && book.asks) || [];
    var max = 0;
    bids.concat(asks).forEach(function (r) { max = Math.max(max, r.cum || r.qty || 0); });
    function rows(list) { return list.map(function (r) { return { level: r.level, qty: r.qty, cum: r.cum, pct: max ? Math.round((r.cum || r.qty) / max * 100) : 0 }; }); }
    var bestBid = bids.length ? bids[0].level : null, bestAsk = asks.length ? asks[0].level : null;
    return { bids: rows(bids), asks: rows(asks).reverse(), bestBid: bestBid, bestAsk: bestAsk,
             spread: bestBid !== null && bestAsk !== null ? bestAsk - bestBid : null,
             mid: bestBid !== null && bestAsk !== null ? (bestAsk + bestBid) / 2 : null };
  }

  var api = { FIELDS: FIELDS, deriveAccount: deriveAccount, signingPayload: signingPayload,
              signEnvelope: signEnvelope, rebucket: rebucket, chartModel: chartModel, bookModel: bookModel, endpointOrigin: endpointOrigin, isDevnet: isDevnet };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; return; }

  var root = document.getElementById("torihiki");
  if (!root) return;
  function $(sel) { return root.querySelector(sel); }
  function $$(sel) { return Array.prototype.slice.call(root.querySelectorAll(sel)); }
  function slot(name) { return $('[data-slot="' + name + '"]'); }
  function say(text) { slot("tk-result").textContent = text; }
  function bindTk(name, text) { $$('[data-bind="' + name + '"]').forEach(function (n) { n.textContent = text; }); }
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function put(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; }
  var SVGNS = "http://www.w3.org/2000/svg";
  function svg(tag, attrs, text) {
    var n = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (text !== undefined) n.textContent = text;
    return n;
  }

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
  var busy = false, live = null;
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
      host.scrollIntoView({ block: "nearest" });
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
      return { chain: chain, height: r.json.height };
    });
  }
  function pretty(j) { try { return JSON.stringify(j, null, 2); } catch (e) { return String(j); } }
  function intField(sel, min) {
    var e = $(sel), v = e ? e.value.trim() : "";
    if (!/^\d+$/.test(v) || Number(v) < min || Number(v) > Number.MAX_SAFE_INTEGER) return null;
    return Number(v);
  }
  function currentOrigin() { return endpointOrigin(($("#tk-endpoint") || {}).value); }
  var BADURL = "接続先は https のアドレス（この端末の http://localhost も可）で入力してください。何も送っていません。";

  // --- screens ---------------------------------------------------------------
  var state = { side: "buy", span: 5, candles: [], market: 1 };
  function fmt(n) { return n === null || n === undefined ? "—" : String(n); }

  function renderBook(book) {
    var m = bookModel(book);
    function fill(id, rows) {
      var c = $(id); c.textContent = "";
      if (!rows.length) { c.appendChild(el("div", "tk-empty", "注文がありません")); return; }
      rows.forEach(function (r) {
        var row = el("div", "tk-row"), bar = el("i");
        bar.style.width = r.pct + "%";
        row.appendChild(bar); row.appendChild(el("span", "", String(r.level))); row.appendChild(el("span", "", String(r.qty))); row.appendChild(el("span", "", String(r.cum)));
        row.setAttribute("data-level", String(r.level)); row.title = "価格欄に入れる";
        c.appendChild(row);
      });
    }
    fill("#tk-asks", m.asks); fill("#tk-bids", m.bids);
    $("#tk-mid").textContent = m.mid === null ? "—" : String(m.mid) + (m.spread !== null ? "（スプレッド " + m.spread + "）" : "");
    bindTk("tk-spread", m.spread === null ? "—" : String(m.spread));
  }
  function renderTrades(t) {
    var c = $("#tk-trades"); c.textContent = "";
    var list = (t && t.trades) || [];
    if (!list.length) { c.appendChild(el("div", "tk-empty", "約定がありません")); return; }
    list.slice(0, 14).forEach(function (x) {
      var row = el("div", "tk-row");
      row.appendChild(el("span", x.side === 0 ? "tk-buy-px" : "tk-sell-px", String(x.level)));
      row.appendChild(el("span", "", String(x.qty))); row.appendChild(el("span", "", String(x.h)));
      c.appendChild(row);
    });
    bindTk("tk-last", String(list[0].level));
  }
  function renderChart() {
    var host = $("#tk-chart"); host.textContent = "";
    var m = chartModel(rebucket(state.span, state.candles));
    if (m.empty) { host.appendChild(el("div", "tk-empty", "ローソク足がありません。ライブ表示を始めると、ノードの約定履歴から描きます。")); return; }
    var s = svg("svg", { viewBox: "0 0 " + m.width + " " + m.height, preserveAspectRatio: "xMidYMid meet" });
    m.yTicks.forEach(function (t) {
      s.appendChild(svg("line", { x1: 8, x2: m.plotRight, y1: t.y, y2: t.y, "class": "grid" }));
      if (Math.abs(t.y - m.lastY) > 12) s.appendChild(svg("text", { x: m.plotRight + 6, y: t.y + 4 }, t.label));
    });
    m.candles.forEach(function (c) {
      var cls = c.up ? "up" : "down";
      s.appendChild(svg("line", { x1: c.x, x2: c.x, y1: c.yHigh, y2: c.yLow, "class": cls }));
      s.appendChild(svg("rect", { x: c.x - c.w / 2, y: c.yTop, width: c.w, height: c.bodyH, "class": cls }));
      s.appendChild(svg("rect", { x: c.x - c.w / 2, y: c.volY, width: c.w, height: c.volH, "class": cls + " vol" }));
    });
    s.appendChild(svg("line", { x1: 8, x2: m.plotRight, y1: m.lastY, y2: m.lastY, "class": "last" }));
    s.appendChild(svg("text", { x: m.plotRight + 6, y: m.lastY - 4 }, m.lastLabel));
    m.xTicks.forEach(function (t) { s.appendChild(svg("text", { x: t.x, y: m.height - 2, "text-anchor": "middle" }, t.label)); });
    host.appendChild(s);
  }
  function renderAccount(a) {
    var c = $("#tk-positions"); c.textContent = "";
    function kv(k, v) { c.appendChild(el("span", "", k)); c.appendChild(el("b", "", v)); }
    kv("アカウント", fmt(a.account)); kv("担保（cents）", fmt(a.collateral)); kv("エクイティ", fmt(a.equity));
    kv("使える担保", fmt(a["free-collateral"])); kv("次の nonce", fmt(a["next-nonce"]));
    var pos = a.positions || {}, ks = Object.keys(pos);
    if (!ks.length) kv("ポジション", "なし");
    ks.forEach(function (k) { var p = pos[k]; kv("市場 " + k + " " + (p.size >= 0 ? "ロング" : "ショート"), p.size + " lot @ " + p.entry + "（含み " + p.unrealized + "）"); });
  }
  function setSide(side) {
    state.side = side;
    $$("[data-tk-side]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-tk-side") === side ? "true" : "false"); });
    var b = $("#tk-submit"); b.className = "tk-submit " + (side === "buy" ? "tk-submit-buy" : "tk-submit-sell");
    b.textContent = side === "buy" ? "買い注文を送る" : "売り注文を送る";
  }
  function showTab(id) {
    $$("[data-tk-panel]").forEach(function (p) { p.hidden = p.getAttribute("data-tk-panel") !== id; });
    $$("[data-tk-tab]").forEach(function (t) { t.setAttribute("aria-selected", t.getAttribute("data-tk-tab") === id ? "true" : "false"); });
    if (id === "chart") renderChart();
  }
  function setStatus(text, on) { var n = $('[data-bind="tk-status"]'); n.textContent = text; n.setAttribute("data-live", on ? "1" : "0"); }

  // --- the live view: one approved operation, bounded ------------------------
  var LIVE_EVERY_MS = 3000, LIVE_MAX = 20;
  function stopLive(why) {
    if (live) { clearTimeout(live.timer); live = null; }
    setStatus(why || "停止中", false);
  }
  function liveRound(origin, m, n) {
    return head(origin).then(function (h) {
      bindTk("tk-height", String(h.height));
      return Promise.all([call(origin, "/market?id=" + m), call(origin, "/book?market=" + m + "&depth=10"),
                          call(origin, "/trades?n=14"), call(origin, "/candles?span=1&n=300")]);
    }).then(function (rs) {
      var mk = rs[0].json || {};
      bindTk("tk-symbol", mk.symbol || ("市場 " + m));
      renderBook(rs[1].json); renderTrades(rs[2].json);
      state.candles = (rs[3].json && rs[3].json.candles) || [];
      if ($('[data-tk-panel="chart"]').hidden === false) renderChart();
      setStatus("ライブ " + n + "/" + LIVE_MAX, true);
    });
  }
  function startLive() {
    if (live || busy) { say("すでに実行中です。"); return; }
    var origin = currentOrigin();
    if (!origin) { say(BADURL); return; }
    var m = intField("#tk-market", 1); if (m === null) { say("市場 id は 1 以上の整数です。"); return; }
    put("itonami.torihiki.endpoint", origin); state.market = m;
    busy = true;
    approve("承認が必要です: read-quotes（ライブ表示）",
      "サービス: Torihiki devnet\nエンドポイント: " + origin + "\n操作: read-quotes\nリクエスト: GET /head, GET /market?id=" + m + ", GET /book?market=" + m + "&depth=10, GET /trades?n=14, GET /candles?span=1&n=300\n" +
      "回数: " + LIVE_EVERY_MS / 1000 + " 秒ごとに最大 " + LIVE_MAX + " 回（約 " + LIVE_EVERY_MS * LIVE_MAX / 1000 + " 秒）。停止ボタンでいつでも止められます。上限に達すると自動で止まり、続けるには再度承認が要ります。\n送るデータ: 市場 id " + m + "\n注意: devnet のみ。実資金は扱いません。")
      .then(function (ok) {
        busy = false;
        if (!ok) { say("拒否しました。何も送信していません。"); return; }
        var n = 0; live = { timer: null };
        (function tick() {
          if (!live) return;
          n++;
          liveRound(origin, m, n).then(function () {
            if (!live) return;
            if (n >= LIVE_MAX) { stopLive("上限に達したので停止しました"); return; }
            live.timer = setTimeout(tick, LIVE_EVERY_MS);
          }).catch(function (e) { stopLive("停止しました"); say("ライブ表示を止めました: " + (e && e.message ? e.message : e)); });
        })();
      });
  }

  // --- one-shot operations ---------------------------------------------------
  function execute(plan) {
    if (busy) { say("ほかの操作を実行中です。"); return; }
    var origin = currentOrigin();
    if (!origin) { say(BADURL); return; }
    put("itonami.torihiki.endpoint", origin);
    busy = true;
    loadSession(!!plan.needsKey).then(function () {
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
  var PLANS = {
    "account": function () {
      return { op: "read-account", needsKey: true,
        requests: function () { return ["GET /head", "GET /account?id=" + session.account]; },
        data: function () { return "アカウント id " + session.account; },
        run: function (origin) {
          return head(origin).then(function () { return call(origin, "/account?id=" + session.account); })
            .then(function (r) { renderAccount(r.json || {}); return "口座を読みました (HTTP " + r.status + ")。「取引」タブの『ポジションと口座』に表示しています。"; });
        } };
    },
    "faucet": function () {
      return { op: "request-devnet-funds", needsKey: true,
        requests: function () { return ["GET /head", "POST /faucet"]; },
        data: function () { return "アカウント id " + session.account; },
        run: function (origin) {
          return head(origin).then(function () { return call(origin, "/faucet", { method: "POST", body: { account: session.account } }); })
            .then(function (r) { return "devnet 資金の請求 (HTTP " + r.status + "):\n" + pretty(r.json); });
        } };
    },
    "submit": function () {
      var m = intField("#tk-market", 1), level = intField("#tk-price", 1), qty = intField("#tk-size", 1);
      if (m === null || level === null || qty === null) { say("市場 id・価格（tick）・数量（lot）は 1 以上の整数です。"); return null; }
      var flags = ($("#tk-post").checked ? 1 : 0) | ($("#tk-ioc").checked ? 2 : 0) | ($("#tk-ro").checked ? 4 : 0);
      var side = state.side;
      return submitPlan({ tx: "order", market: m, side: side, level: level, qty: qty, flags: flags },
        "注文 " + (side === "buy" ? "買い" : "売り") + " 市場 " + m + " 価格 " + level + " tick 数量 " + qty + " lot フラグ " + flags);
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
        return head(origin).then(function (h) { chain = h.chain; return call(origin, "/account?id=" + session.account); })
          .then(function (a) {
            var nonce = (a.json && a.json["next-nonce"]) || 1;
            return signEnvelope(session.priv, session.pub, chain, session.account, nonce, t);
          })
          .then(function (env) { return call(origin, "/tx", { method: "POST", body: env }); })
          .then(function (r) { return label + "\nノードの返答 (HTTP " + r.status + "):\n" + pretty(r.json); });
      } };
  }

  root.addEventListener("click", function (ev) {
    var t = ev.target.closest && ev.target.closest("[data-tk-tab]");
    if (t) { showTab(t.getAttribute("data-tk-tab")); return; }
    var sd = ev.target.closest && ev.target.closest("[data-tk-side]");
    if (sd) { setSide(sd.getAttribute("data-tk-side")); return; }
    var sp = ev.target.closest && ev.target.closest("[data-tk-span]");
    if (sp) {
      state.span = Number(sp.getAttribute("data-tk-span"));
      $$("[data-tk-span]").forEach(function (b) { b.setAttribute("aria-pressed", b === sp ? "true" : "false"); });
      renderChart(); return;
    }
    var row = ev.target.closest && ev.target.closest(".tk-row[data-level]");
    if (row) { $("#tk-price").value = row.getAttribute("data-level"); return; }
    var b = ev.target.closest && ev.target.closest("[data-tk]");
    if (!b) return;
    var k = b.getAttribute("data-tk");
    if (k === "save-endpoint") {
      var o = currentOrigin();
      if (!o) { say(BADURL); return; }
      put("itonami.torihiki.endpoint", o); $("#tk-endpoint").value = o; say("接続先を保存しました（この端末のみ。何も送っていません）: " + o); return;
    }
    if (k === "live-start") { startLive(); return; }
    if (k === "live-stop") { if (live) { stopLive("停止しました"); say("ライブ表示を止めました。"); } return; }
    var plan = PLANS[k] ? PLANS[k]() : null;
    if (plan) execute(plan);
  });

  var saved = get("itonami.torihiki.endpoint");
  if (saved && $("#tk-endpoint")) $("#tk-endpoint").value = saved;
  setSide("buy"); showTab("trade"); renderBook(null); renderTrades(null);
  if (!(window.crypto && crypto.subtle && window.indexedDB)) {
    say("このブラウザは Ed25519 の署名か IndexedDB に未対応です。注文は送れません。");
  }
  loadSession(false).then(function () { showSession(); }).catch(function () { showSession(); });
})();
