/**
 * A Cloudflare Worker host for a Kotoba re-frame guest.
 *
 * ## Why this file is .mjs when the workspace says write ClojureScript
 *
 * A Worker entry has to be JS, and the rule is that no LOGIC lives in a
 * hand-written .mjs. There is none here. Every judgement -- what an event
 * means, what a subscription answers, what the view looks like, and whether a
 * request body parses -- is made by the guest compiled from `.kotoba`. This
 * file reads a request, calls one export, and writes a response. It is the
 * same host/guest split as amu's `runtime/dom-driver.mjs`, and the same
 * reason: effects belong to the host, decisions do not.
 *
 * ## The guest contract (re-frame's four verbs, at a text boundary)
 *
 *   init-text  ()                      -> db-text
 *   step-text  (db-text, event-text)   -> db-text
 *   fx-text    (db-text, event-text)   -> effects-text
 *   handle-text(db-text, event-text)   -> "{:db .. :fx ..}"
 *   query-text (db-text, query-text)   -> value-text
 *   view-text  (db-text)               -> view-document-text
 *
 * The text is EDN, printed and read by `reframe-core`'s `edn-print` /
 * `edn-read`. Not JSON: JSON has no keyword and no i64, and the ABI hands an
 * i64 across as a BigInt, which `JSON.stringify` refuses outright (measured
 * 2026-09-09). A cljs caller reads the answer with `read-string` and gets
 * ordinary data, which is why `shitsuke.re-frame.core` can route a dispatch
 * here without app call sites changing.
 *
 * The two envelope fields ARE JSON, because they are two strings.
 *
 * ## One instance per request
 *
 * `instantiateKotoba()` opens a fuel budget that is spent and never
 * replenished, so a shared instance answers for a while and then starts
 * trapping -- the failure would look like a bad request rather than an
 * exhausted one. A fresh instance per request is the fuel model working
 * rather than being worked around: one request is one bounded computation.
 * It is sound only because the guest is pure -- the db is an ordinary value
 * the CALLER holds between requests, and carries no instance identity.
 *
 * ## What a trap becomes
 *
 * Malformed request text traps inside `document-edn-read` before any handler
 * runs, with a named code (measured: `document-edn-read-trailing`,
 * `document-read-hex-charset`, `document-read-truncated`). That is the one
 * judgement this file makes: a guest trap on caller-supplied text is a 400
 * and the code is reported. A trap with no request text to blame is a 500.
 */

const EDN = { "content-type": "application/edn; charset=utf-8", "cache-control": "no-store" };
const TEXT = { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" };

function edn(body) {
  return new Response(body, { headers: EDN });
}

function fail(status, code) {
  return new Response(code + "\n", { status, headers: TEXT });
}

async function envelope(request, ...fields) {
  let body;
  try {
    body = await request.json();
  } catch {
    return { error: "request-body-is-not-json" };
  }
  if (body === null || typeof body !== "object") return { error: "request-body-is-not-an-object" };
  const out = [];
  for (const f of fields) {
    if (typeof body[f] !== "string") return { error: "missing-string-field:" + f };
    out.push(body[f]);
  }
  return { args: out };
}

/**
 * @param {object} guest   the compiled module: { instantiateKotoba, kotobaArtifact }
 * @param {object} [opts]
 * @param {string} [opts.prefix]  route prefix, default "/api"
 * @param {object} [opts.grants]  capability grants; a guest that requires none
 *                                is handed none, and asking for more than the
 *                                artifact declares is refused by the ABI.
 */
export function installReframeWorker(guest, opts = {}) {
  const prefix = opts.prefix ?? "/api";
  const grants = opts.grants ?? Object.freeze({});

  // A route is (guest export name, envelope fields). Nothing here inspects
  // the strings it moves.
  const routes = {
    "/init": { method: "GET", call: "init-text", fields: [] },
    "/dispatch": { method: "POST", call: "handle-text", fields: ["db", "event"] },
    "/step": { method: "POST", call: "step-text", fields: ["db", "event"] },
    "/fx": { method: "POST", call: "fx-text", fields: ["db", "event"] },
    "/query": { method: "POST", call: "query-text", fields: ["db", "query"] },
    "/view": { method: "POST", call: "view-text", fields: ["db"] },
  };

  return {
    async fetch(request) {
      const url = new URL(request.url);
      if (!url.pathname.startsWith(prefix)) return fail(404, "no-such-route");
      const route = routes[url.pathname.slice(prefix.length)];
      if (!route) return fail(404, "no-such-route");
      if (request.method !== route.method) return fail(405, "method-not-allowed");

      let args = [];
      if (route.fields.length > 0) {
        const parsed = await envelope(request, ...route.fields);
        if (parsed.error) return fail(400, parsed.error);
        args = parsed.args;
      }

      let instance;
      try {
        instance = guest.instantiateKotoba(grants);
      } catch (e) {
        // A grant mismatch is the host's mistake, not the caller's.
        return fail(500, "instantiate-failed:" + String(e && e.message));
      }
      const fn = instance[route.call];
      if (typeof fn !== "function") return fail(500, "guest-export-missing:" + route.call);

      try {
        return edn(fn(...args));
      } catch (e) {
        const code = String((e && e.message) || e);
        // Caller-supplied text reached the guest and the guest refused it.
        return fail(args.length > 0 ? 400 : 500, "guest-trap:" + code);
      }
    },
  };
}
