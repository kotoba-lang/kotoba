#!/usr/bin/env node
// Real-node check for the hosted Torihiki app (JUN-827). Not CI, not a gate: run by a person or an agent who was told to.
//
//   node scripts/session-torihiki-live.js <https-endpoint>
//       READ-ONLY. GET /head /market /book /trades /candles /account only. Checks that the node's answers have the
//       shapes the page's screens rely on and that the page's view models accept them. Sends nothing else.
//
//   node scripts/session-torihiki-live.js <https-endpoint> --write --confirm <same origin>
//       ALSO WRITES to that node, once: POST /faucet, one far-from-touch post-only order, one cancel-all (all signed with
//       a throwaway key made in this process and never stored). It shows whether the node accepts the page's signing
//       payload (a node on another engine version answers bad-signature). Refuses unless /head's chain-id contains
//       "devnet" and --confirm repeats the origin exactly. Devnet collateral is unbacked; do not point it at anything else.
//
// No default endpoint. Exit 0 only if every check passed.
"use strict";
const path = require("path");
const api = require(path.resolve(__dirname, "../resources/aiueos/session/assets/torihiki.js"));

const args = process.argv.slice(2);
const origin = api.endpointOrigin(args.find((a) => !a.startsWith("--")));
const write = args.includes("--write");
const confirm = args.includes("--confirm") ? args[args.indexOf("--confirm") + 1] : null;
if (!origin) { console.error("usage: session-torihiki-live.js <https endpoint> [--write --confirm <origin>]"); process.exit(2); }

let fails = 0;
function check(name, ok, detail) { console.log((ok ? "PASS " : "FAIL ") + name + (detail ? "  " + detail : "")); if (!ok) fails++; }
const num = (x) => typeof x === "number" && Number.isFinite(x);
async function get(p) {
  const r = await fetch(origin + p, { redirect: "error", credentials: "omit", cache: "no-store", signal: AbortSignal.timeout(15000) });
  const t = await r.text(); let j; try { j = JSON.parse(t); } catch (e) { j = null; }
  return { status: r.status, json: j, text: t };
}
async function post(p, body) {
  const r = await fetch(origin + p, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body), redirect: "error", credentials: "omit", signal: AbortSignal.timeout(15000) });
  const t = await r.text(); let j; try { j = JSON.parse(t); } catch (e) { j = null; }
  return { status: r.status, json: j, text: t };
}

(async () => {
  console.log("endpoint " + origin + (write ? "  (READ + WRITE)" : "  (read-only)"));
  const h = await get("/head");
  const chain = h.json && h.json["chain-id"];
  check("head: chain-id is a string containing devnet", api.isDevnet(chain), String(chain));
  check("head: height is a number", num(h.json && h.json.height), String(h.json && h.json.height));
  console.log("info  code-version " + (h.json && h.json["code-version"]) + "; consensus " + (h.json && h.json.consensus));
  if (!api.isDevnet(chain)) { console.log("stop: not a devnet chain; nothing else was asked."); process.exit(1); }

  const mk = await get("/market?id=1");
  check("market: object with id", mk.status === 200 && mk.json && num(mk.json.id), "symbol " + (mk.json && mk.json.symbol));

  const bk = await get("/book?market=1&depth=10");
  const bids = (bk.json && bk.json.bids) || null, asks = (bk.json && bk.json.asks) || null;
  const lvl = (r) => r && num(r.level) && num(r.qty) && num(r.cum);
  check("book: bids and asks are arrays of {level,qty,cum}", Array.isArray(bids) && Array.isArray(asks) && bids.every(lvl) && asks.every(lvl), (bids && bids.length) + " bids, " + (asks && asks.length) + " asks");
  check("book: nearest the touch first (bids descend, asks ascend)", bids && asks && bids.every((r, i) => i === 0 || bids[i - 1].level > r.level) && asks.every((r, i) => i === 0 || asks[i - 1].level < r.level));
  const bm = api.bookModel(bk.json);
  check("page bookModel accepts it", bm && Array.isArray(bm.asks) && (bm.spread === null || num(bm.spread)), "spread " + bm.spread);

  const tr = await get("/trades?n=14");
  const tlist = tr.json && tr.json.trades;
  check("trades: array of {level,qty,side 0|1,h}", Array.isArray(tlist) && tlist.every((x) => num(x.level) && num(x.qty) && (x.side === 0 || x.side === 1) && num(x.h)), (tlist && tlist.length) + " rows");

  const cd = await get("/candles?span=1&n=300");
  const cl = cd.json && cd.json.candles;
  const okc = (c) => num(c.h) && [c.open, c.high, c.low, c.close, c.volume].every(num) && c.high >= Math.max(c.open, c.close) && c.low <= Math.min(c.open, c.close);
  check("candles: array of {h,open,high,low,close,volume} with sane ranges", Array.isArray(cl) && cl.every(okc), (cl && cl.length) + " candles, unit " + (cd.json && cd.json.unit));
  if (Array.isArray(cl)) {
    for (const span of [1, 5, 20]) {
      const cm = api.chartModel(api.rebucket(span, cl));
      const finite = cm.empty || cm.candles.every((c) => [c.x, c.yHigh, c.yLow, c.yTop, c.bodyH, c.volY, c.volH].every(num));
      check("page chartModel span " + span + " has finite geometry", finite, cm.empty ? "empty" : cm.candles.length + " candles");
    }
  }

  // a throwaway key: only its derived account id is used for the read; nothing is stored
  const kp = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"]);
  const pub = Buffer.from(await crypto.subtle.exportKey("raw", kp.publicKey)).toString("base64");
  const acct = await api.deriveAccount(pub);
  const ac = await get("/account?id=" + acct);
  check("account: next-nonce, positions, free-collateral present", ac.json && num(ac.json["next-nonce"]) && typeof ac.json.positions === "object" && "free-collateral" in ac.json, "next-nonce " + (ac.json && ac.json["next-nonce"]));
  check("account: next-nonce is 1 for a fresh key", ac.json && ac.json["next-nonce"] === 1);

  if (write) {
    if (confirm !== origin) { console.log("stop: --write needs --confirm " + origin); process.exit(2); }
    const priv = kp.privateKey;
    const send = async (tx) => {
      const a = await get("/account?id=" + acct);
      const env = await api.signEnvelope(priv, pub, chain, acct, a.json["next-nonce"], tx);
      return post("/tx", env);
    };
    const f = await post("/faucet", { account: acct });
    check("write: faucet answers", f.status === 200 && f.json, f.text.slice(0, 120));
    await new Promise((r) => setTimeout(r, 4000));
    const level = Math.max(1, ((bids && bids[0] && bids[0].level) || 1000) - 500);
    const o = await send({ tx: "order", market: 1, side: "buy", level, qty: 1, flags: 1 });
    check("write: signed post-only order accepted (payload matches this node's engine)", o.json && o.json.ok === true, o.text.slice(0, 160));
    const after = await get("/account?id=" + acct);
    check("write: the order consumed the nonce", after.json && after.json["next-nonce"] === 2, "next-nonce " + (after.json && after.json["next-nonce"]));
    const c = await send({ tx: "cancel-all", market: 1 });
    check("write: cancel-all accepted", c.json && c.json.ok === true, c.text.slice(0, 160));
  }
  console.log(fails ? "AIUEOS_TORIHIKI_LIVE_FAIL checks failed: " + fails : "AIUEOS_TORIHIKI_LIVE_" + (write ? "WRITE" : "READ") + "_OK");
  process.exit(fails ? 1 : 0);
})().catch((e) => { console.error("AIUEOS_TORIHIKI_LIVE_FAIL " + (e && e.message ? e.message : e)); process.exit(1); });
