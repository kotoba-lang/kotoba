var __defProp = Object.defineProperty;
var __name = (target, value) => __defProp(target, "name", { value, configurable: true });

// worker/git-worker.mjs
var json = /* @__PURE__ */ __name((value, status = 200, headers = {}) => new Response(JSON.stringify(value), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", ...headers }
}), "json");
var text = /* @__PURE__ */ __name((value, status = 200, headers = {}) => new Response(value, {
  status,
  headers: { "content-type": "text/plain; charset=utf-8", ...headers }
}), "text");
var validRepo = /* @__PURE__ */ __name((s) => /^[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+$/.test(s), "validRepo");
var validSha = /* @__PURE__ */ __name((s) => /^[0-9a-f]{40}$/.test(s), "validSha");
var validRef = /* @__PURE__ */ __name((s) => /^refs\/(heads|tags)\/[A-Za-z0-9._/-]+$/.test(s) && !s.includes("..") && !s.endsWith("/"), "validRef");
var validDid = /* @__PURE__ */ __name((s) => /^did:key:z[1-9A-HJ-NP-Za-km-z]{40,}$/.test(s), "validDid");
var enc = new TextEncoder();
var hex = /* @__PURE__ */ __name((bytes) => [...new Uint8Array(bytes)].map((x) => x.toString(16).padStart(2, "0")).join(""), "hex");
var b64urlBytes = /* @__PURE__ */ __name((s) => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(s.length / 4) * 4, "=")), (c) => c.charCodeAt(0)), "b64urlBytes");
var b58alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
function base58(bytes) {
  let n = 0n;
  for (const b of bytes) n = (n << 8n) + BigInt(b);
  let out = "";
  while (n > 0n) {
    out = b58alphabet[Number(n % 58n)] + out;
    n /= 58n;
  }
  for (const b of bytes) {
    if (b !== 0) break;
    out = `1${out}`;
  }
  return out || "1";
}
__name(base58, "base58");
var didFromPublicKey = /* @__PURE__ */ __name((pk) => `did:key:z${base58(new Uint8Array([237, 1, ...pk]))}`, "didFromPublicKey");
var digestHex = /* @__PURE__ */ __name(async (bytes, algorithm = "SHA-256") => hex(await crypto.subtle.digest(algorithm, bytes)), "digestHex");
async function deflate(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream("deflate"));
  return new Response(stream).arrayBuffer();
}
__name(deflate, "deflate");
var audit = /* @__PURE__ */ __name((env, op, repo, subject, signer, evidence = {}) => env.GIT_DB.prepare(
  "INSERT INTO audit(id,op,repo,subject,signer_did,evidence_json,created_at) VALUES(?,?,?,?,?,?,?)"
).bind(crypto.randomUUID(), op, repo || null, subject || null, signer || null, JSON.stringify(evidence), (/* @__PURE__ */ new Date()).toISOString()).run(), "audit");
async function verifySignedRequest(request, env, body) {
  const did = request.headers.get("x-nekko-did") || "";
  const pub64 = request.headers.get("x-nekko-public-key") || "";
  const sig64 = request.headers.get("x-nekko-signature") || "";
  const timestamp = request.headers.get("x-nekko-timestamp") || "";
  const nonce = request.headers.get("x-nekko-nonce") || "";
  if (!validDid(did) || !pub64 || !sig64 || !nonce || nonce.length > 160) return null;
  const at = Date.parse(timestamp);
  if (!Number.isFinite(at) || Math.abs(Date.now() - at) > 3e5) return null;
  const pub = b64urlBytes(pub64);
  if (pub.length !== 32 || didFromPublicKey(pub) !== did) return null;
  const url = new URL(request.url);
  const bodyHash = await digestHex(body);
  const message = `${request.method}
${url.pathname}${url.search}
${bodyHash}
${timestamp}
${nonce}`;
  try {
    const key = await crypto.subtle.importKey("raw", pub, { name: "Ed25519" }, false, ["verify"]);
    if (!await crypto.subtle.verify("Ed25519", key, b64urlBytes(sig64), enc.encode(message))) return null;
    await env.GIT_DB.prepare("INSERT INTO nonces(did,nonce,created_at) VALUES(?,?,?)").bind(did, nonce, (/* @__PURE__ */ new Date()).toISOString()).run();
    return { did, bodyHash };
  } catch (_) {
    return null;
  }
}
__name(verifySignedRequest, "verifySignedRequest");
async function authority(env, repo, did, claim = false) {
  const row = await env.GIT_DB.prepare("SELECT owner_did FROM repos WHERE name=?").bind(repo).first();
  if (!row && claim) {
    await env.GIT_DB.prepare("INSERT INTO repos(name,owner_did,created_at) VALUES(?,?,?)").bind(repo, did, (/* @__PURE__ */ new Date()).toISOString()).run();
    return "owner";
  }
  if (row?.owner_did === did) return "owner";
  const delegated = await env.GIT_DB.prepare("SELECT active FROM delegates WHERE repo=? AND did=?").bind(repo, did).first();
  return delegated?.active === 1 ? "delegate" : null;
}
__name(authority, "authority");
async function signedWrite(request, env, url) {
  if (request.method !== "PUT") return json({ ok: false, error: "MethodNotAllowed" }, 405);
  const body = await request.arrayBuffer();
  const signed = await verifySignedRequest(request, env, body);
  if (!signed) return json({ ok: false, error: "InvalidNekkoSignatureOrReplay" }, 401);
  const repo = url.searchParams.get("repo") || "";
  if (!validRepo(repo)) return json({ ok: false, error: "InvalidRepo" }, 400);
  const role = await authority(env, repo, signed.did, url.pathname === "/xrpc/kotobase.git.object.put");
  if (!role) return json({ ok: false, error: "NotAuthorizedForRepo" }, 403);
  const now = (/* @__PURE__ */ new Date()).toISOString();
  if (url.pathname === "/xrpc/kotobase.git.object.put") {
    const sha = url.searchParams.get("sha") || "";
    if (!validSha(sha)) return json({ ok: false, error: "InvalidSha" }, 400);
    if (body.byteLength > 100 * 1024 * 1024) return json({ ok: false, error: "ObjectTooLarge" }, 413);
    const parents = (url.searchParams.getAll("parent") || []).filter(validSha);
    if (parents.length !== url.searchParams.getAll("parent").length) return json({ ok: false, error: "InvalidParent" }, 400);
    const computedSha = await digestHex(body, "SHA-1");
    if (computedSha !== sha) return json({ ok: false, error: "GitObjectIntegrityFailed", expected: sha, computed: computedSha }, 422);
    const looseBytes = await deflate(body);
    await env.GIT_OBJECTS.put(`${repo}/objects/${sha.slice(0, 2)}/${sha.slice(2)}`, looseBytes, {
      customMetadata: { sha1: sha, sha256: signed.bodyHash, signer: signed.did }
    });
    await env.GIT_DB.prepare("INSERT OR REPLACE INTO objects(repo,sha,oid_sha256,size,parents_json,signer_did,created_at) VALUES(?,?,?,?,?,?,?)").bind(repo, sha, signed.bodyHash, body.byteLength, JSON.stringify(parents), signed.did, now).run();
    await audit(env, "put-object", repo, sha, signed.did, { sha256: signed.bodyHash, size: body.byteLength, parents });
    return json({ ok: true, repo, sha, cid: `sha256:${signed.bodyHash}` }, 201);
  }
  if (url.pathname === "/xrpc/kotobase.git.ref.set") {
    const ref = url.searchParams.get("ref") || "";
    const sha = url.searchParams.get("sha") || "";
    const old = url.searchParams.get("old");
    if (!validRef(ref) || !validSha(sha) || old !== null && old !== "" && !validSha(old)) return json({ ok: false, error: "InvalidRefUpdate" }, 400);
    const object = await env.GIT_DB.prepare("SELECT parents_json FROM objects WHERE repo=? AND sha=?").bind(repo, sha).first();
    if (!object) return json({ ok: false, error: "UnknownObject" }, 409);
    const current = await env.GIT_DB.prepare("SELECT sha FROM refs WHERE repo=? AND ref=?").bind(repo, ref).first();
    const currentSha = current?.sha || null;
    if ((old || null) !== currentSha) return json({ ok: false, error: "CompareAndSetFailed", current: currentSha }, 409);
    const parents = JSON.parse(object.parents_json);
    if (currentSha && currentSha !== sha && !parents.includes(currentSha)) return json({ ok: false, error: "NonFastForward" }, 409);
    await env.GIT_DB.prepare("INSERT INTO refs(repo,ref,sha,updated_at,signer_did) VALUES(?,?,?,?,?) ON CONFLICT(repo,ref) DO UPDATE SET sha=excluded.sha,updated_at=excluded.updated_at,signer_did=excluded.signer_did").bind(repo, ref, sha, now, signed.did).run();
    if (ref === "refs/heads/main") {
      await env.GIT_DB.prepare("INSERT INTO heads(repo,ref,updated_at) VALUES(?,?,?) ON CONFLICT(repo) DO UPDATE SET ref=excluded.ref,updated_at=excluded.updated_at").bind(repo, ref, now).run();
    }
    await audit(env, "set-ref", repo, ref, signed.did, { old: currentSha, sha, role });
    return json({ ok: true, repo, ref, old: currentSha, sha });
  }
  if (url.pathname === "/xrpc/kotobase.git.delegate.set") {
    if (role !== "owner") return json({ ok: false, error: "OwnerRequired" }, 403);
    const delegate = url.searchParams.get("did") || "";
    const active = url.searchParams.get("active") !== "false";
    if (!validDid(delegate)) return json({ ok: false, error: "InvalidDelegateDid" }, 400);
    await env.GIT_DB.prepare("INSERT INTO delegates(repo,did,active,updated_at) VALUES(?,?,?,?) ON CONFLICT(repo,did) DO UPDATE SET active=excluded.active,updated_at=excluded.updated_at").bind(repo, delegate, active ? 1 : 0, now).run();
    await audit(env, active ? "delegate-add" : "delegate-remove", repo, delegate, signed.did);
    return json({ ok: true, repo, did: delegate, active });
  }
  return json({ ok: false, error: "NotFound" }, 404);
}
__name(signedWrite, "signedWrite");
async function gitRead(request, env, url) {
  if (request.method !== "GET" && request.method !== "HEAD") return text("method not allowed", 405);
  const path = url.pathname.replace(/^\/+/, "");
  let m = path.match(/^([^/]+\/[^/]+)\/info\/refs$/);
  if (m) {
    const rows = await env.GIT_DB.prepare("SELECT ref,sha FROM refs WHERE repo=? ORDER BY ref").bind(m[1]).all();
    if (!rows.results.length) return text("repository not found", 404);
    return text(rows.results.map((r) => `${r.sha}	${r.ref}
`).join(""));
  }
  m = path.match(/^([^/]+\/[^/]+)\/HEAD$/);
  if (m) {
    const row = await env.GIT_DB.prepare("SELECT ref FROM heads WHERE repo=?").bind(m[1]).first();
    return row ? text(`ref: ${row.ref}
`) : text("repository not found", 404);
  }
  m = path.match(/^([^/]+\/[^/]+)\/objects\/([0-9a-f]{2})\/([0-9a-f]{38})$/);
  if (m) {
    const value = await env.GIT_OBJECTS.get(`${m[1]}/objects/${m[2]}/${m[3]}`);
    return value ? new Response(request.method === "HEAD" ? null : value.body, { status: 200, headers: { "content-type": "application/x-git-loose-object", etag: value.httpEtag } }) : text("object not found", 404);
  }
  return text("not found", 404);
}
__name(gitRead, "gitRead");
var git_worker_default = { async fetch(request, env) {
  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname === "/health") {
    return json({
      ok: true,
      service: "kotobase-git",
      version: env.SERVICE_VERSION,
      refs: "d1-transactional",
      objects: "r2-content-addressed",
      auth: "nekko-ed25519",
      protocol: "git-dumb-http"
    }, 200, { "cache-control": "no-store" });
  }
  if (url.pathname.startsWith("/xrpc/kotobase.git.")) return signedWrite(request, env, url);
  return gitRead(request, env, url);
} };
export {
  git_worker_default as default
};
//# sourceMappingURL=git-worker.js.map
