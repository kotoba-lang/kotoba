// office-sw.js — Background-Sync drain of the office sync queue (docs/gftd-office).
//
// The page enqueues PRE-SIGNED transact requests into IndexedDB (kotoba.syncq); this
// Service Worker POSTs them when connectivity returns — on a Background Sync 'sync'
// event (fires even with the tab CLOSED) or when the page nudges it via postMessage.
// The SW never signs (no WebAuthn in a worker) — it only delivers what the page signed.

const DB = "kotoba-office";
const STORE = "syncq";
const TAG = "office-sync";

function openDb() {
  return new Promise((res, rej) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => {
      const db = r.result;
      if (!db.objectStoreNames.contains(STORE))
        db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
    };
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
}
function getAll(db) {
  return new Promise((res, rej) => {
    const rq = db.transaction(STORE, "readonly").objectStore(STORE).getAll();
    rq.onsuccess = () => res(rq.result);
    rq.onerror = () => rej(rq.error);
  });
}
function del(db, id) {
  return new Promise((res, rej) => {
    const t = db.transaction(STORE, "readwrite");
    t.objectStore(STORE).delete(id);
    t.oncomplete = () => res();
    t.onerror = () => rej(t.error);
  });
}

async function drain() {
  const db = await openDb();
  const jobs = await getAll(db);
  let synced = 0;
  for (const j of jobs) {
    try {
      const r = await fetch(j.url, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: j.body,
      });
      if (r.ok) { await del(db, j.id); synced++; }
      // non-ok (e.g. nonce/auth) → drop so it can't wedge the queue forever
      else if (r.status >= 400 && r.status < 500) { await del(db, j.id); }
    } catch (e) { /* offline → keep for the next drain */ }
  }
  const remaining = (await getAll(db)).length;
  const clients = await self.clients.matchAll({ includeUncontrolled: true });
  clients.forEach((c) => c.postMessage({ type: "office-synced", synced, remaining }));
  return remaining;
}

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) =>
  // claim first; a drain failure must never block activation.
  e.waitUntil(self.clients.claim().then(() => drain()).catch(() => {})));
self.addEventListener("sync", (e) => { if (e.tag === TAG) e.waitUntil(drain()); });
self.addEventListener("message", (e) => {
  if (e.data && e.data.type === "office-flush") e.waitUntil(drain());
});
